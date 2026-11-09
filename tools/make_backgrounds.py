#!/usr/bin/env python3
"""배경 패치 생성기 — 합성 데이터셋의 '바탕'이 되는 인게임 지형 텍스처를 만든다.

두 가지 소스를 섞는다.

1) 실제 스크린샷 크롭 (sources.json)
   거상 사냥 화면 스크린샷에서 UI(좌측 파티바·하단 채팅/스킬바·우측 미니맵)를 피해
   화면 중앙 영역만 잘라 384x384 패치로 저장한다. 출처는 assets/screenshots/<파일>.
   ※ 테스트 이미지로 쓰는 스크린샷은 여기에 넣지 않는다(학습/평가 분리).

2) 절차적 텍스처
   유명계(용암)·얼음성(설원)·신선곡(풀숲)·소림사(물가)·대둔산(용암암반) 같은
   지형 팔레트를 코드로 합성한다. 실제 화면을 구하지 못한 지역도 도메인을 덮기 위해서다.

사용:
  python tools/make_backgrounds.py --out assets/backgrounds --patches-per-shot 6
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SHOT_DIR = ROOT / "assets/screenshots"
PATCH = 384

# 지형별 팔레트 (어두운 바탕 + 밝은 결)
PALETTES = {
    "lava":   [(28, 10, 8), (52, 18, 12), (86, 30, 14), (150, 58, 22), (210, 96, 40)],
    "ice":    [(28, 44, 60), (50, 74, 96), (86, 116, 140), (150, 176, 196), (222, 236, 246)],
    "grass":  [(22, 34, 18), (38, 56, 26), (58, 82, 38), (92, 116, 54), (140, 158, 88)],
    "water":  [(12, 30, 34), (24, 52, 58), (40, 82, 88), (72, 118, 124), (130, 170, 172)],
    "stone":  [(30, 30, 34), (52, 52, 58), (78, 78, 86), (110, 110, 118), (150, 150, 158)],
    "sand":   [(46, 36, 24), (74, 58, 38), (104, 84, 56), (140, 116, 80), (180, 156, 116)],
}


def fbm(size: int, octaves: int, rng: np.random.Generator) -> np.ndarray:
    """간단한 프랙탈 노이즈(값 노이즈 업샘플)."""
    out = np.zeros((size, size), np.float32)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        n = max(2, size // (2 ** (octaves - o)))
        grid = rng.random((n, n)).astype(np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        out += amp * (np.asarray(img, np.float32) / 255.0)
        total += amp
        amp *= 0.55
    return out / total


def procedural(archetype: str, rng: np.random.Generator) -> Image.Image:
    pal = np.array(PALETTES[archetype], np.float32)
    n1 = fbm(PATCH, 7, rng)
    n2 = fbm(PATCH, 5, rng)
    n3 = fbm(PATCH, 3, rng)
    fine = rng.random((PATCH, PATCH)).astype(np.float32)
    base = 0.42 * n1 + 0.28 * n2 + 0.18 * n3 + 0.12 * fine
    base = np.clip((base - 0.5) * 1.45 + 0.5, 0, 1)  # 대비 강화

    # 팔레트 보간
    idx = np.clip(base, 0, 1) * (len(pal) - 1)
    lo = np.floor(idx).astype(int)
    hi = np.minimum(lo + 1, len(pal) - 1)
    frac = (idx - lo)[..., None]
    img = pal[lo] * (1 - frac) + pal[hi] * frac

    # 이음매(바둑판 돌·얼음 균열) 느낌
    if archetype in ("ice", "stone", "lava"):
        step = int(rng.integers(28, 64))
        yy, xx = np.mgrid[0:PATCH, 0:PATCH]
        edge = (((xx // step) + (yy // step)) % 2).astype(np.float32)
        img *= (0.90 + 0.12 * edge)[..., None]

    # 용암 발광 반점
    if archetype == "lava":
        mask = (n2 > rng.uniform(0.62, 0.78)).astype(np.float32)
        glow = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(2.2)), np.float32) / 255.0
        img += glow[..., None] * np.array([190, 90, 30], np.float32) * rng.uniform(0.5, 1.0)

    # 암반 알갱이
    speck = rng.random((PATCH, PATCH, 1)).astype(np.float32)
    img *= (0.92 + 0.16 * speck)
    img += rng.normal(0, 6.0, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def crops_from_shots(spec_path: Path, per_shot: int, rng: random.Random):
    """스크린샷 중앙 영역에서 패치를 잘라낸다."""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out = []
    for item in spec["sources"]:
        p = Path(item["file"])
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print(f"  !! 배경 소스 없음: {p}")
            continue
        im = Image.open(p).convert("RGB")
        w, h = im.size
        x0, y0, x1, y1 = item["crop"]  # 0~1 비율
        cx0, cy0 = int(w * x0), int(h * y0)
        cw, ch = int(w * (x1 - x0)), int(h * (y1 - y0))
        for _ in range(per_shot):
            if cw <= PATCH or ch <= PATCH:
                patch = im.crop((cx0, cy0, cx0 + cw, cy0 + ch)).resize((PATCH, PATCH), Image.BICUBIC)
            else:
                px = rng.randint(cx0, cx0 + cw - PATCH)
                py = rng.randint(cy0, cy0 + ch - PATCH)
                patch = im.crop((px, py, px + PATCH, py + PATCH))
            out.append((patch, item.get("label", p.stem)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/backgrounds")
    ap.add_argument("--spec", default="assets/screenshots/sources.json")
    ap.add_argument("--patches-per-shot", type=int, default=6)
    ap.add_argument("--procedural", type=int, default=8, help="지형별 절차적 패치 수")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    nrng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    made = 0
    if Path(args.spec).exists():
        for patch, label in crops_from_shots(Path(args.spec), args.patches_per_shot, rng):
            name = f"shot_{label}_{made:03d}.jpg"
            patch.save(out / name, quality=92)
            made += 1
    print(f"스크린샷 크롭 {made}장")

    n = 0
    for arch in PALETTES:
        for i in range(args.procedural):
            img = procedural(arch, nrng)
            img.save(out / f"proc_{arch}_{i:02d}.jpg", quality=92)
            n += 1
    print(f"절차적 텍스처 {n}장")
    print(f"총 {made + n}장 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
