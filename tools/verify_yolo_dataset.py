#!/usr/bin/env python3
"""거상 YOLO 데이터셋 검수기.

합성 데이터셋을 배포하기 전에 파일 짝, 라벨 문법, 좌표 범위, 박스 크기 분포,
중복 이미지, 통계 일치 여부를 한 번에 확인한다. 종료 코드 0 = 통과.

사용:
  python tools/verify_yolo_dataset.py --data /workspace/gersang_yolo_dataset_v2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

IMG_EXT = {".jpg", ".jpeg", ".png"}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    root = Path(args.data)
    problems: list[str] = []
    warnings: list[str] = []

    yaml_path = root / "data.yaml"
    if not yaml_path.exists():
        problems.append("data.yaml 없음")
        names: list[str] = []
    else:
        text = yaml_path.read_text(encoding="utf-8")
        names = []
        in_names = False
        for line in text.splitlines():
            if line.strip().startswith("names:"):
                in_names = True
                continue
            if in_names and ":" in line:
                names.append(line.split(":", 1)[1].strip())
            elif in_names and line and not line.startswith(" "):
                in_names = False
        if not names:
            problems.append("data.yaml names 파싱 실패")

    report: dict = {"data": str(root.resolve()), "classes": names, "splits": {}}
    all_hashes: dict[str, list[str]] = defaultdict(list)
    overall_box_count = Counter()

    for split in ("train", "val"):
        img_dir = root / "images" / split
        lbl_dir = root / "labels" / split
        imgs = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXT) if img_dir.is_dir() else []
        lbls = sorted(lbl_dir.glob("*.txt")) if lbl_dir.is_dir() else []
        img_stems = {p.stem for p in imgs}
        lbl_stems = {p.stem for p in lbls}

        missing_labels = sorted(img_stems - lbl_stems)
        orphan_labels = sorted(lbl_stems - img_stems)
        if missing_labels:
            problems.append(f"[{split}] 라벨 없는 이미지 {len(missing_labels)}장 (예: {missing_labels[:3]})")
        if orphan_labels:
            problems.append(f"[{split}] 이미지 없는 라벨 {len(orphan_labels)}개 (예: {orphan_labels[:3]})")

        bad_size = []
        bad_labels: list[str] = []
        empty_labels: list[str] = []
        boxes_per_img: list[int] = []
        class_count = Counter()
        areas: list[float] = []
        sizes_px = Counter()
        unreadable: list[str] = []

        for img_path in imgs:
            try:
                with Image.open(img_path) as im:
                    sizes_px[im.size] += 1
                    if im.size[0] != im.size[1] or im.size[0] < 320:
                        bad_size.append(img_path.name)
            except Exception:  # noqa: BLE001
                unreadable.append(img_path.name)
                continue
            all_hashes[sha1(img_path)].append(f"{split}/{img_path.name}")

        for lbl in lbls:
            lines = [ln.strip() for ln in lbl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            boxes_per_img.append(len(lines))
            if not lines:
                empty_labels.append(lbl.stem)
            for ln in lines:
                parts = ln.split()
                if len(parts) != 5:
                    bad_labels.append(f"{lbl.name}: 필드 {len(parts)}개 '{ln}'")
                    continue
                try:
                    c = int(parts[0])
                    x, y, w, h = (float(v) for v in parts[1:])
                except ValueError:
                    bad_labels.append(f"{lbl.name}: 숫자 변환 실패 '{ln}'")
                    continue
                if names and not (0 <= c < len(names)):
                    bad_labels.append(f"{lbl.name}: 클래스 {c} 범위 밖")
                if not all(0.0 <= v <= 1.0 for v in (x, y, w, h)):
                    bad_labels.append(f"{lbl.name}: 좌표 범위 밖 '{ln}'")
                if w <= 0 or h <= 0:
                    bad_labels.append(f"{lbl.name}: 크기 0 이하 '{ln}'")
                    continue
                if x - w / 2 < -1e-6 or x + w / 2 > 1 + 1e-6 or y - h / 2 < -1e-6 or y + h / 2 > 1 + 1e-6:
                    bad_labels.append(f"{lbl.name}: 박스가 이미지 밖 '{ln}'")
                class_count[c] += 1
                overall_box_count[c] += 1
                areas.append(w * h)

        if bad_size:
            problems.append(f"[{split}] 크기 이상 이미지 {len(bad_size)}장 (예: {bad_size[:3]}, 크기분포 {dict(sizes_px)})")
        if bad_labels:
            problems.append(f"[{split}] 라벨 오류 {len(bad_labels)}건 (예: {bad_labels[:3]})")
        if unreadable:
            problems.append(f"[{split}] 열 수 없는 이미지 {len(unreadable)}장 (예: {unreadable[:3]})")

        nonempty = [n for n in boxes_per_img if n > 0]
        area_arr = np.array(areas) if areas else np.zeros(1)
        report["splits"][split] = {
            "images": len(imgs),
            "labels": len(lbls),
            "boxes": int(sum(boxes_per_img)),
            "empty_label_images": len(empty_labels),
            "per_class": {(names[c] if names and c < len(names) else str(c)): int(v) for c, v in sorted(class_count.items())},
            "boxes_per_image": {
                "mean": round(float(np.mean(boxes_per_img)), 2) if boxes_per_img else 0,
                "max": int(max(boxes_per_img)) if boxes_per_img else 0,
                "nonempty_mean": round(float(np.mean(nonempty)), 2) if nonempty else 0,
            },
            "box_area_pct": {
                "min": round(float(area_arr.min() * 100), 3),
                "median": round(float(np.median(area_arr) * 100), 3),
                "max": round(float(area_arr.max() * 100), 3),
            },
            "image_sizes": {f"{w}x{h}": n for (w, h), n in sizes_px.items()},
        }

        if nonempty and np.mean(nonempty) < 1.0:
            warnings.append(f"[{split}] 이미지당 박스 평균이 1개 미만")

    dupes = {h: v for h, v in all_hashes.items() if len(v) > 1}
    if dupes:
        problems.append(f"중복 이미지 {len(dupes)}쌍 (예: {list(dupes.values())[:2]})")

    stats_path = root / "dataset_stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        for split in ("train", "val"):
            declared_imgs = stats.get("images", {}).get(split)
            actual = report["splits"].get(split, {}).get("images")
            if declared_imgs != actual:
                problems.append(f"dataset_stats.json {split} 이미지 수 불일치: 선언 {declared_imgs} / 실제 {actual}")
            declared_boxes = stats.get("boxes", {}).get(split)
            actual_boxes = report["splits"].get(split, {}).get("boxes")
            if declared_boxes != actual_boxes:
                problems.append(f"dataset_stats.json {split} 박스 수 불일치: 선언 {declared_boxes} / 실제 {actual_boxes}")
        declared_classes = stats.get("classes")
        if declared_classes and names and declared_classes != names:
            problems.append(f"dataset_stats.json 클래스 불일치: {declared_classes} vs data.yaml {names}")
    else:
        warnings.append("dataset_stats.json 없음")

    if report["splits"].get("train", {}).get("images", 0) > 0 and \
            report["splits"].get("val", {}).get("images", 0) > 0:
        tr = report["splits"]["train"]; va = report["splits"]["val"]
        ratio = va["images"] / (tr["images"] + va["images"])
        report["val_ratio"] = round(ratio, 4)
        if not 0.1 <= ratio <= 0.3:
            warnings.append(f"검증 비율 {ratio:.1%} — 통상 10~30% 범위 밖")

    # 클래스 균형
    tot = sum(overall_box_count.values()) or 1
    report["class_balance_pct"] = {
        (names[c] if names and c < len(names) else str(c)): round(v / tot * 100, 2)
        for c, v in sorted(overall_box_count.items())
    }
    for c, v in overall_box_count.items():
        share = v / tot
        if share < 0.05:
            warnings.append(f"클래스 {c} 비중 {share:.1%} — 희소 클래스")

    report["problems"] = problems
    report["warnings"] = warnings
    report["passed"] = not problems

    print(f"검수 대상: {report['data']}")
    for split, s in report["splits"].items():
        print(f"  [{split}] 이미지 {s['images']} / 라벨 {s['labels']} / 박스 {s['boxes']} "
              f"(빈 라벨 {s['empty_label_images']}장, 이미지당 평균 {s['boxes_per_image']['nonempty_mean']}개)")
        print(f"         클래스 {s['per_class']} · 박스 면적 {s['box_area_pct']} %")
    print(f"  클래스 비율: {report['class_balance_pct']}")
    if warnings:
        print("경고:")
        for w in warnings:
            print("  -", w)
    if problems:
        print("문제:")
        for p in problems:
            print("  -", p)
    print("판정:", "통과" if report["passed"] else "실패")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("검수 리포트 저장:", args.json_out)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
