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
CLASSES = ["imugi", "yeomra", "docheol", "nue", "sammun", "icecrab", "tuttleman", "item_drop"]

# 클래스별 대상 몬스터 (이름 또는 포함 키워드) -> 해당 클래스 폴더에 복수 스프라이트 저장
MONSTER_TARGETS: dict[str, list[str]] = {
    "imugi": ["이무기", "사악한이무기", "연못이무기", "늪지이무기", "뿌리 이무기", "이무기氷"],
    "yeomra": ["염라대왕"],
    "docheol": ["어린도철", "도철", "흉포한 도철", "잠식된도철", "태초의 도철", "타락한도철"],
    "nue": ["누에", "조련된 누에", "얼음누에"],
    "sammun": ["중독된삼문", "삼문", "진보의 삼문", "각성한 삼문"],
    "icecrab": ["얼음게"],
    "tuttleman": ["거북궁사"],
}

# item_drop 클래스로 묶을 주요 드랍 아이템 키워드
ITEM_TARGETS = [
    "유명계석", "흉수의혼", "환수의혼", "생명의정수", "심연의정수",
    "엽전상자", "보급상자", "뇌정석", "뇌전이 깃든 여의주", "정기의구슬조각",
    "작은물의속성석", "물의속성석", "작은불의속성석", "불의속성석",
    "작은뇌전의속성석", "뇌전의속성석", "작은바람의속성석", "바람의속성석",
    "작은땅의속성석", "땅의속성석", "백색보주", "황색보주", "흑색보주",
    "단단한 뼈조각", "거북이등껍질", "집게발", "얼음결정", "눈의정수",
    "비늘조각", "이무기의비늘", "고대신검의자루", "주술 비법", "상급정수",
    "선조석", "결정조각", "영혼석", "상급 보급상자", "일반 보급상자",
    "봉인된힘의파편", "암흑석", "태양석", "오색가루", "영혼의조각",
    "황제의반지", "태황의반지", "신수의근원", "원통한원혼의비명",
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
    all_target_names = [name for targets in MONSTER_TARGETS.values() for name in targets]

    for cls, targets in MONSTER_TARGETS.items():
        cls_dir = out / "monsters" / cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for target in targets:
            hits = [m for m in monsters if target in m["name"] or target in m["alt"]]
            for m in hits:
                if m["sprite"] in used_sprites:
                    continue
                used_sprites.add(m["sprite"])
                key = Path(m["sprite"]).stem
                dest = cls_dir / f"{key}.png"
                if not dest.exists():
                    try:
                        data = http_get(ORIGIN + m["sprite"], referer=LIST_URL)
                        w, h = save_webp(data, dest)
                    except Exception as e:
                        print(f"  err {m['name']}: {e}", file=sys.stderr)
                        continue
                else:
                    from PIL import Image
                    im = Image.open(dest)
                    w, h = im.size
                manifest["monsters"].append({
                    "class": cls, "name": m["name"], "key": key,
                    "file": str(dest.relative_to(out)), "size": [w, h],
                    "url": ORIGIN + m["sprite"]})
                count += 1
                print(f"  {cls:9s} <- {m['name']:14s} {dest.name} {w}x{h}")
        print(f"  ==> [{cls}] 스프라이트 총 {count}개 확보")

    print("[3/4] 드랍 아이템 아이콘 다운로드")
    items_dir = out / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    item_count = 0
    for name in ITEM_TARGETS:
        hits = [(alt, src) for alt, src in items.items() if name in alt]
        for alt, src in hits[:3]: # 키워드당 최대 3개
            key = Path(src).stem
            dest = items_dir / f"{key}.png"
            if not dest.exists():
                try:
                    data = http_get(ORIGIN + src, referer=LIST_URL)
                    w, h = save_webp(data, dest)
                except Exception as e:
                    print(f"  err item {alt}: {e}", file=sys.stderr)
                    continue
            else:
                from PIL import Image
                im = Image.open(dest)
                w, h = im.size
            manifest["items"].append({"name": alt, "key": key,
                                      "file": str(dest.relative_to(out)),
                                      "size": [w, h], "url": ORIGIN + src})
            item_count += 1
            print(f"  item_drop <- {alt:18s} {dest.name} {w}x{h}")
    print(f"  ==> 드랍 아이템 총 {item_count}개 확보")

    print(f"[4/4] 하드 네거티브 {args.negatives}종 다운로드 (학습 대상 제외)")
    rng = random.Random(args.seed)
    pool = [m for m in monsters
            if m["sprite"] not in used_sprites
            and not any(t in m["name"] for t in all_target_names)]
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
