#!/usr/bin/env python3
"""거상(Gersang) YOLO 학습용 원본 에셋 수집기.

소스: GoGo-Lap 거상 몬스터 도감 (https://gogolap.com/gersang/db/monster)
  - 몬스터 카드의 <img src="/gersang/characters/fullwait/<key>.webp"> 가
    인게임 대기(spawn) 스프라이트 원본과 동일한 RGBA 이미지다.
  - 드랍 아이템 아이콘은 /gersang/items/<key>.webp.

수집 결과물:
  assets/monsters/<class>/<key>.png    학습 대상 6클래스 스프라이트(투명 배경)
  assets/items/<name>.png              드랍 아이템 아이콘
  assets/negatives/*.png               학습 대상이 아닌 다른 몬스터 스프라이트(하드 네거티브)
  assets/manifest.json                 이름/출처 URL/크기 기록

사용:
  python tools/collect_assets.py --out assets --negatives 150
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ORIGIN = "https://gogolap.com"
BASE = f"{ORIGIN}/gersang"
LIST_URL = f"{BASE}/db/monster"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 클래스 정의 — data.yaml 과 반드시 같은 순서
CLASSES = ["imugi", "yeomra", "docheol", "nue", "sammun", "item_drop"]

# 클래스별 "정확히 이 몬스터" 의 도감 표기 이름
MONSTER_TARGETS = {
    "imugi": "이무기",            # 유명계 3층
    "yeomra": "염라대왕",          # 유명계 3층 염라존
    "docheol": "어린도철",         # 대둔산 은신처
    "nue": "누에",                # 일본 환수
    "sammun": "중독된삼문",        # 검은상단 주둔지
}

# item_drop 클래스로 묶을 드랍 아이템(유석/혼/상자/정수)
ITEM_TARGETS = [
    "유명계석",
    "흉수의혼",
    "환수의혼",
    "엽전상자",
    "일반 보급상자(거래불가)",
    "상급 보급상자(거래불가)",
    "생명의정수",
    "심연의정수",
]


def http_get(url: str, referer: str | None = None, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if referer:
            req.add_header("Referer", referer)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed: {url} ({last})")


def parse_catalog(html: str):
    """도감 페이지에서 (몬스터이름, 스프라이트경로) 목록을 뽑는다."""
    cards = re.findall(
        r'data-monster-card="([^"]+)".*?<img src="(/gersang/characters/fullwait/[^"]+)" alt="([^"]*)"',
        html, re.S)
    out = []
    for _cid, src, alt in cards:
        name = re.sub(r"\((火|水|風|雷|地|無|명|암|光|暗)\)$", "", alt).strip()
        out.append({"name": name, "alt": alt, "sprite": src})
    # 같은 이름/이미지 중복 제거
    seen, uniq = set(), []
    for m in out:
        k = (m["name"], m["sprite"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)
    return uniq


def parse_items(html: str):
    pairs = re.findall(r'<img src="(/gersang/items/[^"]+)" alt="([^"]*)"', html)
    out = {}
    for src, alt in pairs:
        out.setdefault(alt, src)
    return out


def save_webp(data: bytes, dest: Path) -> tuple[int, int]:
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    if max(im.size) < 8:
        raise ValueError("placeholder image")
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest)
    return im.size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    ap.add_argument("--negatives", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20261110)
    args = ap.parse_args()

    out = Path(args.out)
    print(f"[1/4] 도감 페이지 수집: {LIST_URL}")
    html = http_get(LIST_URL).decode("utf-8", "ignore")
    monsters = parse_catalog(html)
    items = parse_items(html)
    print(f"      몬스터 카드 {len(monsters)}개, 아이템 아이콘 {len(items)}개 파싱")

    manifest = {"classes": CLASSES, "generated_by": "tools/collect_assets.py",
                "source": LIST_URL, "monsters": [], "items": [], "negatives": []}

    print("[2/4] 클래스 스프라이트 다운로드")
    used_sprites = set()
    for cls, target in MONSTER_TARGETS.items():
        hits = [m for m in monsters if m["name"] == target]
        if not hits:
            print(f"  !! '{target}' 를 도감에서 찾지 못했습니다", file=sys.stderr)
            continue
        # 같은 스프라이트를 쓰는 중복 카드는 하나만
        for m in hits:
            if m["sprite"] in used_sprites:
                continue
            used_sprites.add(m["sprite"])
            key = Path(m["sprite"]).stem
            dest = out / "monsters" / cls / f"{key}.png"
            data = http_get(ORIGIN + m["sprite"], referer=LIST_URL)
            w, h = save_webp(data, dest)
            manifest["monsters"].append({
                "class": cls, "name": m["name"], "key": key,
                "file": str(dest.relative_to(out)), "size": [w, h],
                "url": ORIGIN + m["sprite"]})
            print(f"  {cls:9s} <- {m['name']:12s} {dest.name} {w}x{h}")
            break

    print("[3/4] 드랍 아이템 아이콘 다운로드")
    for name in ITEM_TARGETS:
        src = items.get(name) or next((v for k, v in items.items()
                                       if k.split("(")[0].strip() == name), None)
        if not src:
            print(f"  !! 아이템 '{name}' 없음", file=sys.stderr)
            continue
        key = Path(src).stem
        dest = out / "items" / f"{key}.png"
        data = http_get(ORIGIN + src, referer=LIST_URL)
        w, h = save_webp(data, dest)
        manifest["items"].append({"name": name, "key": key,
                                  "file": str(dest.relative_to(out)),
                                  "size": [w, h], "url": ORIGIN + src})
        print(f"  item_drop <- {name:16s} {dest.name} {w}x{h}")

    print(f"[4/4] 하드 네거티브 {args.negatives}종 다운로드 (학습 대상 제외)")
    rng = random.Random(args.seed)
    pool = [m for m in monsters
            if m["sprite"] not in used_sprites
            and not any(t in m["name"] for t in MONSTER_TARGETS.values())]
    rng.shuffle(pool)
    got = 0
    for m in pool:
        if got >= args.negatives:
            break
        key = Path(m["sprite"]).stem
        dest = out / "negatives" / f"{key}.png"
        if dest.exists():
            got += 1
            continue
        try:
            data = http_get(ORIGIN + m["sprite"], referer=LIST_URL)
            w, h = save_webp(data, dest)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {m['name']}: {e}", file=sys.stderr)
            continue
        manifest["negatives"].append({"name": m["name"], "key": key,
                                      "file": str(dest.relative_to(out)),
                                      "size": [w, h], "url": ORIGIN + m["sprite"]})
        got += 1
        if got % 25 == 0:
            print(f"  ... {got}")
    print(f"  네거티브 {got}종")

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {out}/manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
