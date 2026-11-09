#!/usr/bin/env python3
"""실제 거상 사냥 화면에서의 검수(recall/precision 측정).

라벨이 없는 실제 스크린샷에서는 정답을 사람이 일일이 그려야 한다.
여기서는 **인게임 스프라이트 템플릿 매칭**으로 정답 후보를 자동 생성한 뒤
(거상은 화면에 스프라이트 원본을 그대로 확대해 그리므로 매칭 정확도가 높다)
YOLO 예측과 IoU 기준으로 대조해 클래스별 precision/recall을 계산한다.

  python tools/eval_real.py --weights best.pt --images test_images \
      --assets assets --out eval --conf 0.25 --iou 0.35

산출물
  eval/summary.json                 클래스별 TP/FP/FN, precision, recall
  eval/summary.md                   사람이 읽는 표
  eval/gt/*.jpg                     템플릿 매칭 정답 시각화(검수용)
  eval/pred/*.jpg                   YOLO 예측 시각화
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["imugi", "yeomra", "docheol", "nue", "sammun", "item_drop"]
KO = {"imugi": "이무기", "yeomra": "염라대왕", "docheol": "어린도철",
      "nue": "누에", "sammun": "중독된삼문", "item_drop": "드랍아이템"}
# 이미지에 실제로 등장하는 클래스만 정답 후보로 쓴다(나머지는 오탐 계산용)
EXPECTED = {
    "myeonggye3_imugi_01": ["imugi", "item_drop"],
    "myeonggye3_imugi_02": ["imugi", "item_drop"],
    "myeonggye3_imugi_03": ["imugi", "item_drop"],
    "icecastle_crab_01": ["imugi"],
    "daedunsan_gi_01": ["docheol"],
    "daedunsan_gi_02": ["docheol"],
    "yeomrajon_02": ["yeomra"],
    "yeomrajon_03": ["yeomra"],
}


def iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / ua if ua > 0 else 0.0


def nms(boxes, scores, thr=0.35):
    order = np.argsort(scores)[::-1]
    keep = []
    for i in order:
        if all(iou(boxes[i], boxes[j]) < thr for j in keep):
            keep.append(i)
    return keep


def template_boxes(img_rgb: np.ndarray, sprite_paths, scales, thresh=0.62):
    """스프라이트(알파 포함)를 여러 배율로 매칭해 (box, score) 목록을 만든다."""
    H, W = img_rgb.shape[:2]
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    out = []
    for sp in sprite_paths:
        rgba = np.asarray(Image.open(sp).convert("RGBA"))
        alpha = rgba[..., 3]
        rgb = rgba[..., :3]
        for s in scales:
            w = int(rgba.shape[1] * s)
            h = int(rgba.shape[0] * s)
            if w < 12 or h < 12 or w >= W * 0.9 or h >= H * 0.95:
                continue
            t_rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_NEAREST)
            t_a = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_NEAREST)
            mask = (t_a > 100).astype(np.uint8)
            if mask.sum() < 0.15 * w * h:
                continue
            t_gray = cv2.cvtColor(t_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
            t_gray = cv2.GaussianBlur(t_gray, (3, 3), 0)
            try:
                res = cv2.matchTemplate(gray, t_gray, cv2.TM_CCORR_NORMED, mask=mask.astype(np.float32))
            except cv2.error:
                continue
            res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
            ys, xs = np.where(res >= thresh)
            for y, x in zip(ys, xs):
                out.append(([int(x), int(y), int(x + w), int(y + h)], float(res[y, x])))
    if not out:
        return []
    boxes = [b for b, _ in out]
    scores = [s for _, s in out]
    keep = nms(boxes, scores, 0.3)
    return [(boxes[i], scores[i]) for i in keep]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="runs/detect/train/weights/best.pt")
    ap.add_argument("--images", default="test_images")
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--out", default="eval")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.35)
    ap.add_argument("--tm-thresh", type=float, default=0.62)
    args = ap.parse_args()

    imgs = sorted([p for p in Path(args.images).glob("*")
                   if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
    out = Path(args.out)
    (out / "gt").mkdir(parents=True, exist_ok=True)
    (out / "pred").mkdir(parents=True, exist_ok=True)

    sprites = {c: sorted((Path(args.assets) / "monsters" / c).glob("*.png")) for c in CLASSES[:-1]}
    items = sorted((Path(args.assets) / "items").glob("*.png"))

    # ---- 1) 템플릿 매칭으로 정답 후보 생성
    gt_all = {}
    for p in imgs:
        key = p.stem
        cls_list = EXPECTED.get(key, [])
        pil = Image.open(p).convert("RGB")
        # 속도를 위해 최대 720px로 줄여서 매칭하고, 좌표는 원본 스케일로 되돌린다
        f = min(1.0, 720.0 / max(pil.size))
        small = pil.resize((max(1, int(pil.width * f)), max(1, int(pil.height * f))),
                           Image.BILINEAR)
        rgb = np.asarray(small)
        gts = []
        for c in cls_list:
            if c == "item_drop":
                paths, scales = items, np.array([0.45, 0.6, 0.75])
            else:
                paths, scales = sprites[c], np.arange(0.6, 2.0, 0.2)
            found = template_boxes(rgb, paths, scales, args.tm_thresh)
            # 아이템은 바닥 아이콘 크기만 인정(너무 큰 매칭 제외)
            if c == "item_drop":
                found = [(b, s) for b, s in found if (b[3] - b[1]) < 60]
            gts += [(c, [v / f for v in b], sc) for b, sc in found]
        gt_all[key] = gts
        im = Image.open(p).convert("RGB")
        d = ImageDraw.Draw(im)
        for c, b, s in gts:
            d.rectangle(b, outline=(0, 255, 120), width=2)
            d.text((b[0] + 3, b[1] + 1), f"{c} {s:.2f}", fill=(0, 255, 120))
        im.save(out / "gt" / f"{key}.jpg", quality=88)
        print(f"[GT] {key}: ", flush=True) if False else print(f"[GT] {key}: " + ", ".join(f"{c}x{sum(1 for g in gts if g[0]==c)}" for c in cls_list))

    # ---- 2) YOLO 예측
    from ultralytics import YOLO
    model = YOLO(args.weights)
    res = model.predict(source=[str(p) for p in imgs], imgsz=640, conf=args.conf,
                        iou=0.5, verbose=False)
    preds = {}
    for r in res:
        key = Path(r.path).stem
        boxes = []
        for b, c, cf in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(),
                            r.boxes.conf.cpu().numpy()):
            boxes.append((CLASSES[int(c)], [float(v) for v in b], float(cf)))
        preds[key] = boxes
        im = Image.open(r.path).convert("RGB")
        d = ImageDraw.Draw(im)
        for c, b, cf in boxes:
            d.rectangle(b, outline=(80, 160, 255), width=2)
            d.text((b[0] + 3, b[1] + 1), f"{c} {cf:.2f}", fill=(80, 200, 255))
        im.save(out / "pred" / f"{key}.jpg", quality=88)

    # ---- 3) 대조
    stats = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CLASSES}
    per_image = {}
    for key, gts in gt_all.items():
        used = set()
        rows = []
        for c, b, cf in preds.get(key, []):
            best, bj = 0.0, None
            for j, (gc, gb, gs) in enumerate(gts):
                if j in used or gc != c:
                    continue
                v = iou(b, gb)
                if v > best:
                    best, bj = v, j
            if bj is not None and best >= args.iou:
                used.add(bj)
                stats[c]["tp"] += 1
                rows.append(("TP", c, cf, best))
            else:
                stats[c]["fp"] += 1
                rows.append(("FP", c, cf, best))
        for j, (gc, gb, gs) in enumerate(gts):
            if j not in used:
                stats[gc]["fn"] += 1
                rows.append(("FN", gc, None, None))
        per_image[key] = rows

    summary = {}
    for c in CLASSES:
        s = stats[c]
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        summary[c] = {**s, "precision": prec, "recall": rec}

    (out / "summary.json").write_text(json.dumps(
        {"per_class": summary,
         "note": "정답은 스프라이트 템플릿 매칭으로 자동 생성(사람 검수용 시각화 포함). "
                 "실제 라벨이 아니므로 근사치다.",
         "per_image": {k: [[r[0], r[1], r[2], r[3]] for r in v] for k, v in per_image.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["| 클래스 | TP | FP | FN | Precision | Recall |", "|---|---|---|---|---|---|"]
    for c in CLASSES:
        s = summary[c]
        if s["tp"] + s["fp"] + s["fn"] == 0:
            continue
        pr = "-" if s["precision"] is None else f"{s['precision']*100:.1f}%"
        rc = "-" if s["recall"] is None else f"{s['recall']*100:.1f}%"
        lines.append(f"| {c} ({KO[c]}) | {s['tp']} | {s['fp']} | {s['fn']} | {pr} | {rc} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
