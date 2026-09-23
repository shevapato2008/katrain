"""Acceptance gate for the board-state shadow step (design.md §5) on the labelled set.

"Old" is the live order without the step: dedup_detections. "New" adds BoardStateExtractor.drop_shadow_boxes
after it -- both taken from the working tree on PYTHONPATH, i.e. the code being landed. The step only ever
removes boxes, so the new output is a subset of the old one, and old coverage minus new coverage is exactly
what the step costs. Coverage is a maximum one-to-one matching of boxes to YOLO labels (measure_labelled.match),
colour-agnostic and colour-aware.

Usage (repo root):
  PYTHONPATH=. python measure_shadow_step.py <dets.json> <labels_root> --expect-images N [--parallax FX,FY,K]
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from measure_labelled import labels_for, match, where  # noqa: E402

from katrain.vision.board_state import SHADOW_MIN_OFFSET, BoardStateExtractor  # noqa: E402
from katrain.vision.config import DEFAULT_MARGIN_CELLS, BoardConfig  # noqa: E402
from katrain.vision.parallax import ParallaxParams  # noqa: E402
from katrain.vision.stone_detector import Detection, dedup_detections  # noqa: E402

IMG = 1056
STONE = (0, 1)
GATE_MIN_RECALL = 0.95


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dets")
    ap.add_argument("labels_root", type=Path)
    ap.add_argument("--expect-images", type=int, required=True)
    ap.add_argument("--parallax", help="nadir_fx,nadir_fy,k of the board the images came from (default: none)")
    args = ap.parse_args()
    parallax = ParallaxParams(*map(float, args.parallax.split(","))) if args.parallax else None
    ex = BoardStateExtractor(BoardConfig(margin_cells=DEFAULT_MARGIN_CELLS), parallax=parallax)
    dets = json.load(open(args.dets))

    n_labels = seen_old = n_dropped = 0
    lost, recoloured, dropped_on_labels, real_offsets = [], [], [], []
    for name, fr in sorted(dets.items()):
        raw = [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in fr["raw"]]
        labels = labels_for(args.labels_root, name)
        n_labels += len(labels)
        old = dedup_detections(raw)
        new = ex.drop_shadow_boxes(old, IMG, IMG)
        kept_old = [d for d in old if d.class_id in STONE]
        kept_new = [d for d in new if d.class_id in STONE]
        new_ids = {id(d) for d in kept_new}
        m_old = match(kept_old, labels)
        seen_old += len(m_old)
        for li, bi in m_old.items():
            _, _, fx, fy, _ = ex._positions(kept_old[bi], IMG, IMG)
            real_offsets.append(math.hypot(fy - round(fy), fx - round(fx)))
            if id(kept_old[bi]) not in new_ids:
                dropped_on_labels.append((name, where(labels[li])))
        n_dropped += len(kept_old) - len(kept_new)
        m_new = match(kept_new, labels)
        if len(m_new) < len(m_old):
            lost.append((name, len(m_old) - len(m_new), [where(labels[li]) for li in sorted(set(m_old) - set(m_new))]))
        c_old, c_new = match(kept_old, labels, True), match(kept_new, labels, True)
        if len(c_new) < len(c_old):
            recoloured.append(
                (name, len(c_old) - len(c_new), [where(labels[li]) for li in sorted(set(c_old) - set(c_new))])
            )

    real_offsets.sort()
    n = len(real_offsets)
    q = lambda p: real_offsets[min(n - 1, int(p * n))] if n else float("nan")  # noqa: E731
    recall = seen_old / n_labels if n_labels else 0.0
    print(f"images {len(dets)} (expected {args.expect_images})  labelled stones {n_labels}  recall(old) {recall:.4f}")
    print(f"parallax {'on ' + args.parallax if args.parallax else 'off'}  SHADOW_MIN_OFFSET {SHADOW_MIN_OFFSET}")
    print(
        f"label-matched boxes, cells from their point: p50 {q(0.5):.2f} p90 {q(0.9):.2f} p99 {q(0.99):.2f} "
        f"p99.9 {q(0.999):.2f} max {q(1.0):.2f}  (at or above the threshold: {sum(o >= SHADOW_MIN_OFFSET for o in real_offsets)})"
    )
    print(
        f"boxes the shadow step dropped: {n_dropped}, of which label-matched before: {len(dropped_on_labels)} {dropped_on_labels[:20]}"
    )
    print(f"labels the shadow step costs: {sum(k for _, k, _ in lost)} {lost[:20]}")
    print(f"labels that lose their correct-colour box: {sum(k for _, k, _ in recoloured)} {recoloured[:20]}")
    valid = len(dets) == args.expect_images and recall >= GATE_MIN_RECALL
    ok = valid and not lost and not recoloured
    verdict = "PASS" if ok else ("FAIL" if valid else "INVALID")
    print(
        f"VERDICT: {verdict}  (valid: images == expected and recall >= {GATE_MIN_RECALL}; "
        f"pass: no label lost or recoloured by the shadow step)"
    )


if __name__ == "__main__":
    main()
