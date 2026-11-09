#!/usr/bin/env python3
"""거상 YOLO 학습용 합성 데이터셋 생성기.

인게임 스프라이트(assets/monsters)와 실제 사냥 화면 배경(assets/backgrounds)을
합성해 100% 정답 라벨(YOLO txt)을 가진 이미지를 대량으로 만든다.

무엇을 재현하나
  - 스프라이트의 인게임 표시 배율/도트 확대(nearest), 좌우 반전, 미세 회전
  - 몬스터 발밑 그림자, 머리 위 HP 바, 피격 시 붉은/흰 발광
  - 데미지 숫자, 드랍 아이템 아이콘과 이름표
  - 학습 대상이 아닌 다른 몬스터(하드 네거티브) — 오탐 억제용
  - 배경 밝기/색/블러/노이즈/JPEG 압축 열화

라벨 규칙(YOLO)
  class_id x_center y_center width height  (모두 0~1 정규화)
  가려짐(occlusion)이 심해 실제로 보이는 픽셀이 35% 미만인 개체는 라벨에서 제외한다.

사용 예
  python tools/generate_yolo_dataset.py --out datasets/gersang_yolo --images 1000
  python tools/generate_yolo_dataset.py --out /content/data/gersang_yolo --images 1000 --preview 16
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["imugi", "yeomra", "docheol", "nue", "sammun", "icecrab", "tuttleman", "item_drop"]

# 인게임 화면에서 관측한 표시 배율(640x640 캔버스 기준).
#   이무기   : 773x513 실사격에서 약 95px 높이 -> 원본 127px의 0.9배
#   염라대왕 : 보스라 1.3~1.6배로 크게 그려진다(유명계 3층 실사격/썸네일 확인)
#   나머지   : 원본 크기 ±25%
SCALE_RANGE = {
    "imugi": (0.70, 1.05),
    "yeomra": (1.15, 1.65),
    "docheol": (0.80, 1.25),
    "nue": (0.80, 1.25),
    "sammun": (0.80, 1.25),
    "icecrab": (0.80, 1.25),
    "tuttleman": (0.85, 1.25),
}
ITEM_SCALE_RANGE = (0.35, 0.62)
KO_NAMES = {
    "imugi": "이무기", "yeomra": "염라대왕", "docheol": "어린도철",
    "nue": "누에", "sammun": "중독된삼문", "icecrab": "얼음게",
    "tuttleman": "거북궁사", "item_drop": "드랍아이템",
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def load_font(size: int) -> ImageFont.ImageFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def hflip(im: Image.Image) -> Image.Image:
    return im.transpose(Image.FLIP_LEFT_RIGHT)


def color_jitter(im: np.ndarray, rng: random.Random,
                 bright: float = 0.18, contrast: float = 0.18,
                 sat: float = 0.18, hue: float = 0.0) -> np.ndarray:
    """RGB float array (h,w,3) 0~255 -> 0~255"""
    x = im / 255.0
    b = 1.0 + rng.uniform(-bright, bright)
    x = x * b
    c = 1.0 + rng.uniform(-contrast, contrast)
    x = (x - 0.5) * c + 0.5
    if sat:
        g = x @ np.array([0.299, 0.587, 0.114], np.float32)
        s = 1.0 + rng.uniform(-sat, sat)
        x = g[..., None] + (x - g[..., None]) * s
    if hue:
        sh = rng.uniform(-hue, hue)
        x = np.clip(x + sh, 0, 1)
    return np.clip(x, 0, 1) * 255.0


def shift_hue(im: np.ndarray, degrees: float) -> np.ndarray:
    """RGB(float 0~255) 배열의 색상(hue)만 회전. 속성별 색 변형(火/水/風/雷)을 흉내낸다."""
    if abs(degrees) < 0.5:
        return im
    import cv2
    u8 = np.clip(im, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_RGB2HSV).astype(np.int16)
    hsv[..., 0] = (hsv[..., 0] + int(degrees / 2)) % 180  # OpenCV H: 0~179
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    return out


def tint(im: np.ndarray, rgb: tuple[int, int, int], amount: float) -> np.ndarray:
    t = np.array(rgb, np.float32)
    return np.clip(im * (1 - amount) + t * amount, 0, 255)


class Assets:
    def __init__(self, root: Path):
        self.monsters: dict[str, list[Image.Image]] = {c: [] for c in CLASSES[:-1]}
        self.items: list[Image.Image] = []
        self.negatives: list[Image.Image] = []
        self.backgrounds: list[Path] = []

        for cls in CLASSES[:-1]:
            for p in sorted((root / "assets" / "monsters" / cls).glob("*.png")):
                self.monsters[cls].append(Image.open(p).convert("RGBA"))
        for p in sorted((root / "assets" / "items").glob("*.png")):
            self.items.append(Image.open(p).convert("RGBA"))
        for p in sorted((root / "assets" / "negatives").glob("*.png")):
            self.negatives.append(Image.open(p).convert("RGBA"))
        self.backgrounds = sorted((root / "assets" / "backgrounds").glob("*.jpg"))

        missing = [c for c in CLASSES[:-1] if not self.monsters[c]]
        if missing:
            raise SystemExit(f"스프라이트가 없습니다: {missing} — tools/collect_assets.py 먼저 실행")
        if not self.items:
            raise SystemExit("아이템 아이콘이 없습니다")
        if len(self.backgrounds) < 5:
            raise SystemExit("배경이 부족합니다 — tools/make_backgrounds.py 먼저 실행")
        print(f"에셋: 몬스터 {sum(len(v) for v in self.monsters.values())}종, "
              f"아이템 {len(self.items)}, 네거티브 {len(self.negatives)}, "
              f"배경 {len(self.backgrounds)}")


class Scene:
    """한 장 합성. objects: (cls_id, sprite_rgba, x, y, scale, flip, alpha_flash)"""

    def __init__(self, size: int):
        self.size = size
        self.objs: list[dict] = []

    def add(self, **kw):
        self.objs.append(kw)


def make_background(assets: Assets, size: int, rng: random.Random) -> Image.Image:
    p = rng.choice(assets.backgrounds)
    bg = Image.open(p).convert("RGB")
    # 배경 안에서 임의 크기 크롭 후 확대/축소 -> 배율 다양화
    w, h = bg.size
    side = int(min(w, h) * rng.uniform(0.62, 1.0))
    x = rng.randint(0, max(0, w - side))
    y = rng.randint(0, max(0, h - side))
    crop = bg.crop((x, y, x + side, y + side)).resize((size, size), Image.BILINEAR)
    if rng.random() < 0.5:
        crop = hflip(crop)
    arr = np.asarray(crop, np.float32)
    arr = color_jitter(arr, rng, bright=0.16, contrast=0.16, sat=0.20)
    if rng.random() < 0.35:
        arr = arr * rng.uniform(0.82, 1.12)  # 스크린샷 촬영 환경(밤/낮) 차이
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if rng.random() < 0.25:
        out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))
    return out


def place_sprite(canvas: np.ndarray, owner: np.ndarray,
                 sprite: Image.Image, cx: int, cy: int, scale: float,
                 rng: random.Random, flip: bool, obj_id: int,
                 tint_rgb=None, tint_amount=0.0) -> tuple[int, int, int, int] | None:
    """스프라이트를 캔버스에 합성. 실제로 그려진 픽셀의 bbox(절대좌표)를 돌려준다."""
    H, W = canvas.shape[:2]
    w = max(4, int(round(sprite.width * scale)))
    h = max(4, int(round(sprite.height * scale)))
    # 보행/대기 호흡 애니메이션 신축(squash & stretch) 모사
    if rng.random() < 0.65:
        squash = rng.uniform(0.93, 1.07)
        w = max(4, int(round(w / squash)))
        h = max(4, int(round(h * squash)))
    spr = sprite
    if flip:
        spr = hflip(spr)
    # 인게임은 원본 픽셀을 크게 확대해 그린다 -> nearest 후 약한 스무딩
    spr = spr.resize((w, h), Image.NEAREST)
    if scale > 1.4 and rng.random() < 0.6:
        spr = spr.filter(ImageFilter.GaussianBlur(0.4))
    angle = rng.uniform(-4, 4)
    if abs(angle) > 0.8:
        spr = spr.rotate(angle, resample=Image.BICUBIC, expand=True)
    w, h = spr.size
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    arr = np.asarray(spr, np.float32)
    alpha = arr[..., 3] / 255.0
    if tint_amount > 0:
        arr[..., :3] = tint(arr[..., :3], tint_rgb, tint_amount)
    # 반투명 테두리 정리(스프라이트 가장자리 잔여 알파)
    alpha = np.clip((alpha - 0.08) * 1.15, 0, 1)

    # 캔버스와 교집합
    xs0, ys0 = max(0, x0), max(0, y0)
    xs1, ys1 = min(W, x0 + w), min(H, y0 + h)
    if xs1 - xs0 < 3 or ys1 - ys0 < 3:
        return None
    sub_a = alpha[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0]
    sub_rgb = arr[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0, :3]
    region = canvas[ys0:ys1, xs0:xs1, :3]
    canvas[ys0:ys1, xs0:xs1, :3] = region * (1 - sub_a[..., None]) + sub_rgb * sub_a[..., None]
    m = sub_a > 0.45
    owner[ys0:ys1, xs0:xs1][m] = obj_id

    ys, xs = np.where(sub_a > 0.35)
    if len(xs) == 0:
        return None
    return (xs0 + xs.min(), ys0 + ys.min(), xs0 + xs.max() + 1, ys0 + ys.max() + 1)


def draw_shadow(canvas: np.ndarray, cx: int, cy: int, w: int, h: int) -> None:
    H, W = canvas.shape[:2]
    rw, rh = max(6, int(w * 0.48)), max(3, int(w * 0.16))
    layer = Image.new("L", (rw * 2, rh * 2), 0)
    d = ImageDraw.Draw(layer)
    d.ellipse((0, 0, rw * 2 - 1, rh * 2 - 1), fill=95)
    layer = layer.filter(ImageFilter.GaussianBlur(max(1.0, rw * 0.18)))
    arr = np.asarray(layer, np.float32) / 255.0
    x0, y0 = cx - rw, cy - rh
    xs0, ys0 = max(0, x0), max(0, y0)
    xs1, ys1 = min(W, x0 + 2 * rw), min(H, y0 + 2 * rh)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    sub = arr[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0][..., None]
    canvas[ys0:ys1, xs0:xs1, :3] *= (1 - 0.55 * sub)


def draw_hp_bar(canvas: np.ndarray, box, rng: random.Random) -> None:
    x0, y0, x1, y1 = box
    H, W = canvas.shape[:2]
    w = max(14, int((x1 - x0) * rng.uniform(0.75, 1.0)))
    h = max(3, int(round((y1 - y0) * 0.045)))
    bx = int((x0 + x1) / 2 - w / 2) + rng.randint(-2, 2)
    by = max(0, y0 - h - rng.randint(2, 7))
    fill_ratio = rng.uniform(0.25, 1.0)
    col = (170, 30, 25) if rng.random() < 0.6 else (40, 40, 46)
    for yy in range(h):
        for xx in range(w):
            px, py = bx + xx, by + yy
            if 0 <= px < W and 0 <= py < H:
                edge = xx == 0 or yy == 0 or xx == w - 1 or yy == h - 1
                if edge:
                    canvas[py, px, :3] = (18, 18, 18)
                elif xx < w * fill_ratio:
                    canvas[py, px, :3] = col
                else:
                    canvas[py, px, :3] = (58, 58, 62)


def draw_damage_numbers(canvas: np.ndarray, boxes, rng: random.Random,
                        font_cache: dict) -> None:
    if not boxes:
        return
    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(1, 4)):
        box = rng.choice(boxes)
        size = rng.randint(15, 30)
        if size not in font_cache:
            font_cache[size] = load_font(size)
        text = rng.choice([
            str(rng.randint(60, 9999)),
            str(rng.randint(100, 99999)),
            "MISS",
        ])
        col = rng.choice([(255, 255, 255), (255, 226, 120), (255, 150, 120), (140, 220, 255)])
        x = int((box[0] + box[2]) / 2 + rng.randint(-25, 25))
        y = int(box[1] + rng.uniform(-0.1, 0.7) * (box[3] - box[1]))
        for dx, dy, cc in ((2, 2, (0, 0, 0)), (0, 0, col)):
            d.text((x + dx, y + dy), text, font=font_cache[size], fill=cc)
    canvas[:] = np.asarray(img, np.float32)


def draw_skill_fx(canvas: np.ndarray, boxes, rng: random.Random) -> None:
    """연옥술·화염 및 빙결·얼음 계열 스킬이 몬스터를 덮는 상황을 흉내낸다(가림/광원 강화)."""
    if not boxes or rng.random() > 0.40:
        return
    H, W = canvas.shape[:2]
    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    overlay = Image.new("RGB", (W, H), (0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    do = ImageDraw.Draw(overlay)
    dm = ImageDraw.Draw(mask)
    warm = [(255, 190, 90), (255, 120, 40), (250, 240, 220), (200, 60, 30)]
    cold = [(160, 230, 255), (100, 180, 255), (220, 250, 255), (140, 200, 240)]
    palette = cold if rng.random() < 0.5 else warm
    for _ in range(rng.randint(2, 6)):
        b = rng.choice(boxes)
        cx = int((b[0] + b[2]) / 2 + rng.uniform(-0.5, 0.5) * (b[2] - b[0]))
        cy = int(b[3] - rng.uniform(0.0, 0.7) * (b[3] - b[1]))
        r = int(rng.uniform(0.3, 1.1) * max(12, (b[2] - b[0])))
        col = rng.choice(palette)
        do.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        dm.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rng.randint(60, 150))
    overlay = overlay.filter(ImageFilter.GaussianBlur(rng.uniform(3, 8)))
    mask = mask.filter(ImageFilter.GaussianBlur(rng.uniform(3, 8)))
    mx = np.asarray(mask, np.float32)[..., None] / 255.0
    additive = rng.random() < 0.5
    if additive:
        canvas += (np.asarray(overlay, np.float32) - canvas * 0) * mx * rng.uniform(0.25, 0.55)
    else:
        canvas[:] = canvas * (1 - mx * 0.7) + np.asarray(overlay, np.float32) * mx * 0.7


def build_scene(assets: Assets, size: int, rng: random.Random,
                scene_type: str) -> tuple[np.ndarray, list[dict]]:
    bg = make_background(assets, size, rng)
    canvas = np.asarray(bg, np.float32).copy()
    owner = np.zeros((size, size), np.int32)
    boxes_out: list[dict] = []
    font_cache: dict = {}

    plan: list[tuple[str, int]] = []
    if scene_type == "imugi":
        plan.append(("imugi", rng.randint(5, 14)))
    elif scene_type == "yeomra":
        plan.append(("yeomra", rng.randint(3, 8)))
    elif scene_type == "docheol":
        plan.append(("docheol", rng.randint(2, 7)))
    elif scene_type == "nue":
        plan.append(("nue", rng.randint(2, 7)))
    elif scene_type == "sammun":
        plan.append(("sammun", rng.randint(3, 9)))
    elif scene_type == "icecrab":
        plan.append(("icecrab", rng.randint(4, 11)))
    elif scene_type == "tuttleman":
        plan.append(("tuttleman", rng.randint(3, 9)))
    elif scene_type == "mixed":
        picks = rng.sample(CLASSES[:-1], rng.randint(2, 4))
        for c in picks:
            plan.append((c, rng.randint(1, 4)))
    elif scene_type == "drop":
        if rng.random() < 0.75:
            plan.append((rng.choice(CLASSES[:-1]), rng.randint(0, 3)))
        plan.append(("item_drop", rng.randint(1, 4)))
    else:
        plan.append((rng.choice(CLASSES[:-1]), rng.randint(0, 2)))

    # 하드 네거티브(학습 대상이 아닌 몬스터)
    if assets.negatives and rng.random() < 0.75:
        n_neg = rng.randint(1, 4)
    else:
        n_neg = 0

    items = []  # (cls, sprite, cx, cy, scale, flip, is_item)
    occupied: list[tuple[int, int, int]] = []

    def pick_pos(w: int, h: int, cluster_prob: float = 0.45) -> tuple[int, int]:
        # 실제 사냥은 몰이(무리) 사냥이라 몬스터가 겹쳐 쌓인다. 절반 가까이는 기존 개체 옆에 붙인다.
        if occupied and rng.random() < cluster_prob:
            ox, oy, ow = rng.choice(occupied)
            for _ in range(12):
                cx = ox + int(rng.gauss(0, 0.45 * (w + ow) / 2))
                cy = oy + int(rng.gauss(0, 0.22 * (h + ow) / 2))
                cx = max(-w // 5, min(size + w // 5 - 1, cx))
                cy = max(int(size * 0.05), min(int(size * 0.97), cy))
                return cx, cy
        for _ in range(30):
            cx = rng.randint(-w // 6, size + w // 6 - 1)
            cy = rng.randint(int(size * 0.08), int(size * 0.95))
            if all(math.hypot(cx - ox, cy - oy) > 0.16 * (w + ow) / 2 + 4
                   for ox, oy, ow in occupied) or rng.random() < 0.15:
                return cx, cy
        return rng.randint(0, size - 1), rng.randint(int(size * 0.1), int(size * 0.95))

    for cls, count in plan:
        for _ in range(count):
            if cls == "item_drop":
                spr = rng.choice(assets.items)
                scale = rng.uniform(*ITEM_SCALE_RANGE) * (size / 640.0)
            else:
                spr = rng.choice(assets.monsters[cls])
                base = size / 640.0
                lo, hi = SCALE_RANGE[cls]
                scale = base * rng.uniform(lo, hi)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h)
            occupied.append((cx, cy, w))
            items.append((cls, spr, cx, cy, scale, rng.random() < 0.5, cls == "item_drop"))

    negs = []
    for _ in range(n_neg):
        spr = rng.choice(assets.negatives)
        scale = (size / 640.0) * rng.uniform(0.5, 1.35)
        scale = min(scale, (0.42 * size) / max(spr.width, spr.height))
        w, h = int(spr.width * scale), int(spr.height * scale)
        cx, cy = pick_pos(w, h)
        occupied.append((cx, cy, w))
        negs.append((spr, cx, cy, scale, rng.random() < 0.5))

    # 뒤->앞(위->아래) 순으로 그려 겹침이 자연스럽게
    entries = [(y, "obj", i) for i, (_, _, _, y, _, _, _) in enumerate(items)]
    entries += [(y, "neg", i) for i, (_, _, y, _, _) in enumerate(negs)]
    entries.sort()

    obj_boxes: dict[int, tuple[int, int, int, int]] = {}
    for _, kind, idx in entries:
        if kind == "obj":
            cls, spr, cx, cy, scale, flip, is_item = items[idx]
            obj_id = idx + 1
            cy_draw = cy
            if not is_item:
                draw_shadow(canvas, cx, cy, int(spr.width * scale), int(spr.height * scale))
            else:
                # 아이템은 바닥의 작은 받침 위에 놓인 느낌
                canvas = np.asarray(
                    Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(0.01)), np.float32)
            if not is_item and rng.random() < 0.28:
                spr = spr.copy()
                a = np.asarray(spr, np.float32)
                a[..., :3] = shift_hue(a[..., :3], rng.uniform(-45, 45))
                spr = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
            flash = None
            amount = 0.0
            if not is_item and rng.random() < 0.13:
                flash = rng.choice([(255, 255, 255), (255, 80, 80)])
                amount = rng.uniform(0.25, 0.6)
            box = place_sprite(canvas, owner, spr, cx, cy_draw, scale,
                               rng, flip, obj_id, tint_rgb=flash, tint_amount=amount)
            if box:
                obj_boxes[idx] = box
                if not is_item and rng.random() < 0.45:
                    draw_hp_bar(canvas, box, rng)
        else:
            spr, cx, cy, scale, flip = negs[idx]
            draw_shadow(canvas, cx, cy, int(spr.width * scale), int(spr.height * scale))
            place_sprite(canvas, owner, spr, cx, cy, scale, rng, flip, 9000 + idx)

    # 가시성 검사 후 라벨 확정
    boxes_for_numbers = []
    for idx, box in obj_boxes.items():
        cls, spr, cx, cy, scale, flip, is_item = items[idx]
        obj_id = idx + 1
        x0, y0, x1, y1 = box
        own = owner[y0:y1, x0:x1] == obj_id
        visible = own.sum()
        bbox_px = (x1 - x0) * (y1 - y0)
        if visible < max(20, 0.30 * bbox_px):
            continue
        if (x1 - x0) < 7 or (y1 - y0) < 7:
            continue
        if x1 <= 0 or y1 <= 0 or x0 >= size or y0 >= size:
            continue
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(size, x1), min(size, y1)
        if (x1c - x0c) * (y1c - y0c) < 0.45 * bbox_px:
            continue
        xs = (x0c + x1c) / 2 / size
        ys = (y0c + y1c) / 2 / size
        ws = (x1c - x0c) / size
        hs = (y1c - y0c) / size
        boxes_out.append({"cls": CLASSES.index(cls), "xyxy": [x0c, y0c, x1c, y1c],
                          "yolo": [xs, ys, ws, hs]})
        boxes_for_numbers.append((x0c, y0c, x1c, y1c))

    draw_skill_fx(canvas, boxes_for_numbers, rng)

    if rng.random() < 0.55 and boxes_for_numbers:
        draw_damage_numbers(canvas, boxes_for_numbers, rng, font_cache)

    # 후처리: 색/노출/노이즈/비네트
    if rng.random() < 0.35:
        canvas = shift_hue(canvas, rng.uniform(-35, 35))
    canvas = color_jitter(canvas, rng, bright=0.06, contrast=0.08, sat=0.10)
    if rng.random() < 0.4:
        img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.7)))
        canvas = np.asarray(img, np.float32)
    if rng.random() < 0.5:
        canvas += np.random.normal(0, rng.uniform(1.5, 5.0), canvas.shape)
    if rng.random() < 0.4:
        yy, xx = np.mgrid[0:size, 0:size]
        r = np.sqrt(((xx - size / 2) / (size / 2)) ** 2 + ((yy - size / 2) / (size / 2)) ** 2)
        vig = np.clip(1.05 - 0.22 * r ** 2, 0.6, 1.0)[..., None]
        canvas *= vig

    return np.clip(canvas, 0, 255).astype(np.uint8), boxes_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="datasets/gersang_yolo")
    ap.add_argument("--images", type=int, default=1000)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--preview", type=int, default=0, help="라벨을 그려 미리보기 저장")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()

    out = Path(args.out)
    assets = Assets(Path(args.root))
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    if args.preview:
        (out / "preview").mkdir(parents=True, exist_ok=True)

    n_val = max(1, int(round(args.images * args.val_ratio)))
    n_train = args.images - n_val
    split_rng = random.Random(args.seed + 1)
    val_idx = set(split_rng.sample(range(args.images), n_val))
    scene_types = ["imugi", "yeomra", "docheol", "nue", "sammun", "icecrab", "tuttleman", "drop", "mixed", "icecrab", "drop"]
    stats = {c: {"train": 0, "val": 0} for c in CLASSES}
    boxes_total = {"train": 0, "val": 0}

    previews = []
    for i in range(args.images):
        split = "val" if i in val_idx else "train"
        rng = random.Random(args.seed + i * 7919)
        scene_type = scene_types[i % len(scene_types)] if i < len(scene_types) * 3 else \
            rng.choice(scene_types)
        arr, boxes = build_scene(assets, args.size, rng, scene_type)
        img = Image.fromarray(arr)
        stem = f"{split}_{i:05d}"
        img.save(out / "images" / split / f"{stem}.jpg", quality=rng.randint(72, 94))
        with open(out / "labels" / split / f"{stem}.txt", "w", encoding="utf-8") as f:
            for b in boxes:
                f.write(f"{b['cls']} " + " ".join(f"{v:.6f}" for v in b["yolo"]) + "\n")
        for b in boxes:
            stats[CLASSES[b["cls"]]][split] += 1
        boxes_total[split] += len(boxes)
        if args.preview and len(previews) < args.preview:
            previews.append((img.copy(), boxes, stem))
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{args.images} ...")

    # 미리보기: 라벨 박스 오버레이
    for img, boxes, stem in previews:
        d = ImageDraw.Draw(img)
        for b in boxes:
            x0, y0, x1, y1 = b["xyxy"]
            col = (255, 220, 0) if b["cls"] == len(CLASSES) - 1 else (0, 255, 80)
            d.rectangle([x0, y0, x1, y1], outline=col, width=2)
            d.text((x0 + 3, y0 + 1), CLASSES[b["cls"]], fill=col, font=load_font(13))
        img.save(out / "preview" / f"{stem}.jpg", quality=88)

    yaml = [
        f"path: {out.resolve()}",
        "train: images/train",
        "val: images/val",
        "",
        f"nc: {len(CLASSES)}",
        "names:",
    ]
    yaml += [f"  {i}: {c}" for i, c in enumerate(CLASSES)]
    (out / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")

    summary = {
        "images": {"train": args.images - n_val, "val": n_val},
        "boxes": boxes_total,
        "per_class": stats,
        "size": args.size,
        "seed": args.seed,
        "classes": CLASSES,
        "korean_names": KO_NAMES,
    }
    (out / "dataset_stats.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
