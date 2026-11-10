#!/usr/bin/env python3
"""거상(Gersang) 대규모 YOLO 학습용 데이터셋 생성기 (v2).

주요 개편 사항:
  1. 클래스 통합: 개별 몹 대신 단일 'monster'(0) 및 'item_drop'(1) 체계
  2. 인기 몬스터 대폭 확장: 50종 이상 (총 86종의 유명계·대둔산·얼음성·소림사·수미산·광려산·신선곡 몹)
  3. 전체 스프라이트 풀(360종)과 42종 드랍템, 148장 실제 배경 연계
  4. 몰이사냥 군집(클러스터), 보스 인카운터, 필드 드랍, 배경 단독 네거티브 장면 구현
  5. 연옥술 화염·빙결 이펙트, 피격 점멸, 그림자, HP 바, 데미지 폰트 오버레이

사용:
  python tools/generate_yolo_dataset.py --out datasets/gersang_yolo --images 3000 --preview 16
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

# 통합 클래스 체계
CLASSES = ["monster", "item_drop"]
KO_NAMES = {"monster": "몬스터", "item_drop": "드랍아이템"}

ITEM_SCALE_RANGE = (0.35, 0.62)

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
                 bright: float = 0.16, contrast: float = 0.16,
                 sat: float = 0.16, hue: float = 0.0) -> np.ndarray:
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
    if abs(degrees) < 0.5:
        return im
    import cv2
    u8 = np.clip(im, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_RGB2HSV).astype(np.int16)
    hsv[..., 0] = (hsv[..., 0] + int(degrees / 2)) % 180
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    return out


def tint(im: np.ndarray, rgb: tuple[int, int, int], amount: float) -> np.ndarray:
    t = np.array(rgb, np.float32)
    return np.clip(im * (1 - amount) + t * amount, 0, 255)


class Assets:
    def __init__(self, root: Path):
        self.popular_monsters: list[Image.Image] = []
        self.all_monsters: list[Image.Image] = []
        self.boss_monsters: list[Image.Image] = []
        self.items: list[Image.Image] = []
        self.backgrounds: list[Path] = []

        # 1. 인기 몬스터 메타데이터 로드
        pop_file = root / "data" / "popular_monsters.json"
        popular_paths = set()
        if pop_file.exists():
            with open(pop_file, encoding="utf-8") as f:
                pop_data = json.load(f)
            for item in pop_data:
                p = root / item["file"]
                if p.exists():
                    popular_paths.add(p.resolve())
                    im = Image.open(p).convert("RGBA")
                    self.popular_monsters.append(im)
                    # 대형 보스 판별
                    if any(boss in item.get("name", "") for boss in ["염라대왕", "천왕", "독룡", "인드라", "원망신", "절망신", "마룡"]):
                        self.boss_monsters.append(im)

        # 2. 전체 스프라이트 풀(assets/monsters + assets/negatives) 로드
        all_sprite_paths = list((root / "assets" / "monsters").glob("*/*.png")) + \
                           list((root / "assets" / "negatives").glob("*.png"))
        for p in sorted(all_sprite_paths):
            im = Image.open(p).convert("RGBA")
            self.all_monsters.append(im)
            if p.resolve() not in popular_paths:
                pass  # general pool

        if not self.popular_monsters:
            self.popular_monsters = self.all_monsters[:80]
        if not self.boss_monsters:
            self.boss_monsters = self.popular_monsters[:10]

        # 3. 드랍 아이템 로드
        for p in sorted((root / "assets" / "items").glob("*.png")):
            self.items.append(Image.open(p).convert("RGBA"))

        # 4. 배경 로드
        self.backgrounds = sorted((root / "assets" / "backgrounds").glob("*.jpg"))

        if not self.all_monsters:
            raise SystemExit("몬스터 스프라이트가 없습니다.")
        if not self.items:
            raise SystemExit("아이템 아이콘이 없습니다.")
        if len(self.backgrounds) < 5:
            raise SystemExit("배경 이미지가 부족합니다.")

        print(f"에셋 로드 완료: 인기 몬스터 {len(self.popular_monsters)}종, "
              f"전체 몬스터 {len(self.all_monsters)}종, 아이템 {len(self.items)}종, 배경 {len(self.backgrounds)}장")


def make_background(assets: Assets, size: int, rng: random.Random) -> Image.Image:
    p = rng.choice(assets.backgrounds)
    bg = Image.open(p).convert("RGB")
    w, h = bg.size
    side = int(min(w, h) * rng.uniform(0.65, 1.0))
    x = rng.randint(0, max(0, w - side))
    y = rng.randint(0, max(0, h - side))
    crop = bg.crop((x, y, x + side, y + side))
    out = crop.resize((size, size), Image.BILINEAR)
    if rng.random() < 0.35:
        out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    return out


def place_sprite(canvas: np.ndarray, owner: np.ndarray,
                 sprite: Image.Image, cx: int, cy: int, scale: float,
                 rng: random.Random, flip: bool, obj_id: int,
                 tint_rgb=None, tint_amount=0.0) -> tuple[int, int, int, int] | None:
    H, W = canvas.shape[:2]
    w = max(4, int(round(sprite.width * scale)))
    h = max(4, int(round(sprite.height * scale)))
    if rng.random() < 0.65:
        squash = rng.uniform(0.94, 1.06)
        w = max(4, int(round(w / squash)))
        h = max(4, int(round(h * squash)))
    spr = sprite
    if flip:
        spr = hflip(spr)
    spr = spr.resize((w, h), Image.NEAREST)
    if scale > 1.3 and rng.random() < 0.5:
        spr = spr.filter(ImageFilter.GaussianBlur(0.35))
    angle = rng.uniform(-4, 4)
    if abs(angle) > 0.8:
        spr = spr.rotate(angle, resample=Image.BICUBIC, expand=True)
    w, h = spr.size
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    arr = np.asarray(spr, np.float32)
    alpha = arr[..., 3] / 255.0
    if tint_amount > 0:
        arr[..., :3] = tint(arr[..., :3], tint_rgb, tint_amount)
    alpha = np.clip((alpha - 0.08) * 1.15, 0, 1)

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
    rw, rh = max(6, int(w * 0.46)), max(3, int(w * 0.16))
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
    by = max(0, y0 - h - rng.randint(2, 6))
    fill_ratio = rng.uniform(0.20, 1.0)
    col = (175, 30, 25) if rng.random() < 0.65 else (40, 40, 46)
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


def draw_damage_numbers(canvas: np.ndarray, boxes, rng: random.Random, font_cache: dict) -> None:
    if not boxes:
        return
    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(1, 4)):
        box = rng.choice(boxes)
        size = rng.randint(15, 28)
        if size not in font_cache:
            font_cache[size] = load_font(size)
        text = rng.choice([str(rng.randint(100, 9999)), str(rng.randint(1000, 99999)), "MISS"])
        col = rng.choice([(255, 255, 255), (255, 226, 120), (255, 150, 120), (140, 220, 255)])
        x = int((box[0] + box[2]) / 2 + rng.randint(-20, 20))
        y = int(box[1] + rng.uniform(-0.1, 0.7) * (box[3] - box[1]))
        for dx, dy, cc in ((2, 2, (0, 0, 0)), (0, 0, col)):
            d.text((x + dx, y + dy), text, font=font_cache[size], fill=cc)
    canvas[:] = np.asarray(img, np.float32)


def draw_skill_fx(canvas: np.ndarray, boxes, rng: random.Random) -> None:
    if not boxes or rng.random() > 0.45:
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


def compute_monster_scale(spr: Image.Image, size: int, rng: random.Random) -> float:
    base = size / 640.0
    max_dim = max(spr.width, spr.height)
    if max_dim < 65:
        # 소형 몬스터 (딱정벌레, 어린도철, 꼬마산적 등)
        return base * rng.uniform(1.05, 1.55)
    elif max_dim > 180:
        # 대형/보스 몬스터 (염라, 천왕, 독룡 등)
        return base * rng.uniform(0.65, 1.05)
    else:
        # 일반 중형 몬스터 (이무기, 삼문, 얼음게, 거북궁사 등)
        return base * rng.uniform(0.78, 1.25)


def build_scene(assets: Assets, size: int, rng: random.Random,
                scene_type: str) -> tuple[np.ndarray, list[dict]]:
    bg = make_background(assets, size, rng)
    canvas = np.asarray(bg, np.float32).copy()
    owner = np.zeros((size, size), np.int32)
    boxes_out: list[dict] = []
    font_cache: dict = {}

    if scene_type == "empty_bg":
        # 오탐 방지용 배경 단독 이미지
        return np.clip(canvas, 0, 255).astype(np.uint8), []

    items = []  # (cls_name, sprite, cx, cy, scale, flip, is_item)
    occupied: list[tuple[int, int, int]] = []

    def pick_pos(w: int, h: int, cluster_prob: float = 0.55) -> tuple[int, int]:
        # 몰이사냥 군집화 모사
        if occupied and rng.random() < cluster_prob:
            ox, oy, ow = rng.choice(occupied)
            for _ in range(12):
                cx = ox + int(rng.gauss(0, 0.42 * (w + ow) / 2))
                cy = oy + int(rng.gauss(0, 0.20 * (h + ow) / 2))
                cx = max(-w // 5, min(size + w // 5 - 1, cx))
                cy = max(int(size * 0.06), min(int(size * 0.96), cy))
                return cx, cy
        for _ in range(25):
            cx = rng.randint(-w // 6, size + w // 6 - 1)
            cy = rng.randint(int(size * 0.08), int(size * 0.95))
            if all(math.hypot(cx - ox, cy - oy) > 0.16 * (w + ow) / 2 + 4 for ox, oy, ow in occupied) or rng.random() < 0.15:
                return cx, cy
        return rng.randint(0, size - 1), rng.randint(int(size * 0.1), int(size * 0.95))

    # 장면 유형별 엔터티 구성
    if scene_type == "mobbing":
        # 대규모 몰이사냥 (6~14마리)
        n_mobs = rng.randint(6, 14)
        pool = assets.popular_monsters if rng.random() < 0.85 else assets.all_monsters
        primary_spr = rng.choice(pool)
        for _ in range(n_mobs):
            spr = primary_spr if rng.random() < 0.65 else rng.choice(pool)
            scale = compute_monster_scale(spr, size, rng)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h, cluster_prob=0.65)
            occupied.append((cx, cy, w))
            items.append(("monster", spr, cx, cy, scale, rng.random() < 0.5, False))
        if rng.random() < 0.45:
            # 드랍 아이템 1~3개 추가
            for _ in range(rng.randint(1, 3)):
                spr = rng.choice(assets.items)
                scale = rng.uniform(*ITEM_SCALE_RANGE) * (size / 640.0)
                w, h = int(spr.width * scale), int(spr.height * scale)
                cx, cy = pick_pos(w, h, cluster_prob=0.3)
                occupied.append((cx, cy, w))
                items.append(("item_drop", spr, cx, cy, scale, rng.random() < 0.5, True))

    elif scene_type == "boss_encounter":
        # 보스 1마리 + 호위 몬스터 3~7마리
        boss_spr = rng.choice(assets.boss_monsters)
        scale = compute_monster_scale(boss_spr, size, rng) * rng.uniform(1.15, 1.45)
        w, h = int(boss_spr.width * scale), int(boss_spr.height * scale)
        cx, cy = pick_pos(w, h, cluster_prob=0.0)
        occupied.append((cx, cy, w))
        items.append(("monster", boss_spr, cx, cy, scale, rng.random() < 0.5, False))
        for _ in range(rng.randint(3, 7)):
            spr = rng.choice(assets.popular_monsters)
            scale = compute_monster_scale(spr, size, rng)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h, cluster_prob=0.5)
            occupied.append((cx, cy, w))
            items.append(("monster", spr, cx, cy, scale, rng.random() < 0.5, False))

    elif scene_type == "field":
        # 일반 필드 소규모 사냥 (2~6마리)
        n_mobs = rng.randint(2, 6)
        for _ in range(n_mobs):
            spr = rng.choice(assets.popular_monsters if rng.random() < 0.8 else assets.all_monsters)
            scale = compute_monster_scale(spr, size, rng)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h, cluster_prob=0.35)
            occupied.append((cx, cy, w))
            items.append(("monster", spr, cx, cy, scale, rng.random() < 0.5, False))

    elif scene_type == "drop_field":
        # 아이템 회수 장면 (몬스터 0~3마리 + 아이템 3~8개)
        for _ in range(rng.randint(0, 3)):
            spr = rng.choice(assets.popular_monsters)
            scale = compute_monster_scale(spr, size, rng)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h, cluster_prob=0.3)
            occupied.append((cx, cy, w))
            items.append(("monster", spr, cx, cy, scale, rng.random() < 0.5, False))
        for _ in range(rng.randint(3, 8)):
            spr = rng.choice(assets.items)
            scale = rng.uniform(*ITEM_SCALE_RANGE) * (size / 640.0)
            w, h = int(spr.width * scale), int(spr.height * scale)
            cx, cy = pick_pos(w, h, cluster_prob=0.45)
            occupied.append((cx, cy, w))
            items.append(("item_drop", spr, cx, cy, scale, rng.random() < 0.5, True))

    # Y좌표 순(위->아래) 정렬하여 자연스러운 원근 겹침 합성
    entries = sorted([(cy, i) for i, (_, _, _, cy, _, _, _) in enumerate(items)])
    obj_boxes: dict[int, tuple[int, int, int, int]] = {}

    for _, idx in entries:
        cls, spr, cx, cy, scale, flip, is_item = items[idx]
        obj_id = idx + 1
        if not is_item:
            draw_shadow(canvas, cx, cy, int(spr.width * scale), int(spr.height * scale))
        if not is_item and rng.random() < 0.25:
            spr = spr.copy()
            a = np.asarray(spr, np.float32)
            a[..., :3] = shift_hue(a[..., :3], rng.uniform(-40, 40))
            spr = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        flash = None
        amount = 0.0
        if not is_item and rng.random() < 0.12:
            flash = rng.choice([(255, 255, 255), (255, 80, 80)])
            amount = rng.uniform(0.25, 0.55)
        box = place_sprite(canvas, owner, spr, cx, cy, scale, rng, flip, obj_id, tint_rgb=flash, tint_amount=amount)
        if box:
            obj_boxes[idx] = box
            if not is_item and rng.random() < 0.42:
                draw_hp_bar(canvas, box, rng)

    boxes_for_numbers = []
    for idx, box in obj_boxes.items():
        cls, spr, cx, cy, scale, flip, is_item = items[idx]
        obj_id = idx + 1
        x0, y0, x1, y1 = box
        own = owner[y0:y1, x0:x1] == obj_id
        visible = own.sum()
        bbox_px = (x1 - x0) * (y1 - y0)
        if visible < max(18, 0.28 * bbox_px):
            continue
        if (x1 - x0) < 6 or (y1 - y0) < 6:
            continue
        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(size, x1), min(size, y1)
        if (x1c - x0c) * (y1c - y0c) < 0.40 * bbox_px:
            continue
        xs = (x0c + x1c) / 2 / size
        ys = (y0c + y1c) / 2 / size
        ws = (x1c - x0c) / size
        hs = (y1c - y0c) / size
        cls_id = CLASSES.index(cls)
        boxes_out.append({"cls": cls_id, "xyxy": [x0c, y0c, x1c, y1c], "yolo": [xs, ys, ws, hs]})
        if not is_item:
            boxes_for_numbers.append((x0c, y0c, x1c, y1c))

    draw_skill_fx(canvas, boxes_for_numbers, rng)
    if rng.random() < 0.50 and boxes_for_numbers:
        draw_damage_numbers(canvas, boxes_for_numbers, rng, font_cache)

    if rng.random() < 0.35:
        canvas = shift_hue(canvas, rng.uniform(-30, 30))
    canvas = color_jitter(canvas, rng, bright=0.06, contrast=0.08, sat=0.10)
    if rng.random() < 0.40:
        img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.6)))
        canvas = np.asarray(img, np.float32)

    return np.clip(canvas, 0, 255).astype(np.uint8), boxes_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="datasets/gersang_yolo")
    ap.add_argument("--images", type=int, default=3000)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--seed", type=int, default=20261110)
    ap.add_argument("--preview", type=int, default=16)
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

    scene_types = ["mobbing", "mobbing", "boss_encounter", "field", "drop_field", "mobbing", "empty_bg"]
    stats = {c: {"train": 0, "val": 0} for c in CLASSES}
    boxes_total = {"train": 0, "val": 0}

    previews = []
    print(f"합성 데이터셋 생성 시작: 총 {args.images}장 (학습 {n_train}장 / 검증 {n_val}장)")

    for i in range(args.images):
        split = "val" if i in val_idx else "train"
        rng = random.Random(args.seed + i * 7919)
        scene_type = rng.choice(scene_types)
        arr, boxes = build_scene(assets, args.size, rng, scene_type)
        img = Image.fromarray(arr)
        stem = f"{split}_{i:05d}"
        img.save(out / "images" / split / f"{stem}.jpg", quality=rng.randint(75, 93))
        with open(out / "labels" / split / f"{stem}.txt", "w", encoding="utf-8") as f:
            for b in boxes:
                f.write(f"{b['cls']} " + " ".join(f"{v:.6f}" for v in b["yolo"]) + "\n")
        for b in boxes:
            stats[CLASSES[b["cls"]]][split] += 1
        boxes_total[split] += len(boxes)
        if args.preview and len(previews) < args.preview:
            previews.append((img.copy(), boxes, stem))
        if (i + 1) % 500 == 0 or (i + 1) == args.images:
            print(f"  진행률: {i + 1}/{args.images} ({(i + 1)/args.images*100:.1f}%)")

    # 미리보기 생성
    for img, boxes, stem in previews:
        d = ImageDraw.Draw(img)
        for b in boxes:
            x0, y0, x1, y1 = b["xyxy"]
            cls_name = CLASSES[b["cls"]]
            col = (255, 215, 0) if cls_name == "item_drop" else (0, 255, 80)
            d.rectangle([x0, y0, x1, y1], outline=col, width=2)
            label_text = f"{KO_NAMES.get(cls_name, cls_name)}"
            d.text((x0 + 3, y0 + 1), label_text, fill=col, font=load_font(13))
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
        "images": {"train": n_train, "val": n_val, "total": args.images},
        "boxes": boxes_total,
        "per_class": stats,
        "size": args.size,
        "seed": args.seed,
        "classes": CLASSES,
        "korean_names": KO_NAMES,
        "popular_monsters_count": len(assets.popular_monsters),
        "total_monsters_count": len(assets.all_monsters),
        "items_count": len(assets.items),
    }
    (out / "dataset_stats.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n생성 완료 요약:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
