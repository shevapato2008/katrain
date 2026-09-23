"""Shadow-dedup acceptance gate on the labelled set (design.md §5).

Measures the REAL code, not a copy of the rule: "new" is dedup_detections from the working tree on
PYTHONPATH, "old" is the same function as it was at --base. Truth stones come from the YOLO labels only.

Coverage is compared as maximum one-to-one matchings (a number that does not depend on which of several
equally good matchings is found). Boxes the new rule keeps are the old rule's survivors plus "revived"
ones (greedy suppression is not monotone, design.md §3); survivors are a subset of the old output, so
card(old) - card(survivors) is exactly how many labels the new rule's extra merges cost.

Usage (repo root): PYTHONPATH=. python measure_labelled.py <dets.json> <labels_root> --base <sha> --expect-images N
"""
import argparse
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from katrain.vision.stone_detector import Detection, dedup_detections

IMG = 1056
PAD, CELL = 53, 949 / 18
STONE = (0, 1)
GATE_REAL_MAX = 0.25
GATE_MIN_RECALL = 0.95


def load_old(base: str):
    src = subprocess.run(
        ["git", "show", f"{base}:katrain/vision/stone_detector.py"], capture_output=True, text=True, check=True
    ).stdout
    ns = {"__name__": "stone_detector_at_base"}
    exec(compile(src, f"{base}:stone_detector.py", "exec"), ns)
    return ns["dedup_detections"]


def iomin(a, b):
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    small = min(area_a, area_b)
    if small <= 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h) / small


def labels_for(labels_root: Path, image_name: str):
    hits = list(labels_root.rglob(Path(image_name).stem + ".txt"))
    if len(hits) != 1:
        raise SystemExit(f"label for {image_name}: expected 1 file, found {len(hits)}")
    out = []
    for line in hits[0].read_text().split("\n"):
        parts = line.split()
        if len(parts) == 5 and int(parts[0]) in STONE:
            c, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
            out.append({"cls": c, "x": cx * IMG, "y": cy * IMG, "side": (w + h) / 2 * IMG})
    return out


def match(boxes, labels, same_colour=False):
    """Maximum-cardinality one-to-one matching (augmenting paths). A label may take a box within half its
    side -- of its own colour when same_colour, else either (black/white are one dedup group); nearer boxes
    are tried first. Returns {label index: box index}."""
    adj = []
    for lab in labels:
        near = sorted(
            (math.hypot(d.x_center - lab["x"], d.y_center - lab["y"]), bi)
            for bi, d in enumerate(boxes)
            if not same_colour or d.class_id == lab["cls"]
        )
        adj.append([bi for dist, bi in near if dist <= 0.5 * lab["side"]])
    owner = {}  # box index -> label index

    def augment(li, visited):
        for bi in adj[li]:
            if bi not in visited:
                visited.add(bi)
                if bi not in owner or augment(owner[bi], visited):
                    owner[bi] = li
                    return True
        return False

    for li in range(len(labels)):
        augment(li, set())
    return {li: bi for bi, li in owner.items()}


def where(lab):
    return f"r{round((lab['y'] - PAD) / CELL)}c{round((lab['x'] - PAD) / CELL)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dets")
    ap.add_argument("labels_root", type=Path)
    ap.add_argument("--base", required=True)
    ap.add_argument("--expect-images", type=int, required=True)
    args = ap.parse_args()
    old_dedup = load_old(args.base)
    dets = json.load(open(args.dets))

    real_pairs, extra_best, lost, recoloured, revived_extra = [], [], [], [], []
    n_labels = seen_old = n_revived = 0
    max_extent = 0.0
    for name, fr in sorted(dets.items()):
        raw = [Detection(d["x"], d["y"], d["cls"], d["conf"], tuple(d["bbox"])) for d in fr["raw"]]
        labels = labels_for(args.labels_root, name)
        n_labels += len(labels)
        stones = [d for d in raw if d.class_id in STONE]
        for d in stones:
            max_extent = max(max_extent, d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1])

        own = match(stones, labels)  # label -> its real box in the raw output
        real = {bi: li for li, bi in own.items()}
        ids = sorted(real)
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                v = iomin(stones[ids[x]].bbox, stones[ids[y]].bbox)
                if v > 0:
                    real_pairs.append((v, name, where(labels[real[ids[x]]]), where(labels[real[ids[y]]])))
        for e, d in enumerate(stones):
            if e not in real:
                extra_best.append(max((iomin(d.bbox, stones[r].bbox) for r in real), default=0.0))

        kept_old = [d for d in old_dedup(raw) if d.class_id in STONE]
        kept_new = [d for d in dedup_detections(raw) if d.class_id in STONE]
        old_ids = {id(d) for d in kept_old}
        survivors = [d for d in kept_new if id(d) in old_ids]
        m_old, m_surv = match(kept_old, labels), match(survivors, labels)
        seen_old += len(m_old)
        if len(m_surv) < len(m_old):
            gone = [where(labels[li]) for li in sorted(set(m_old) - set(m_surv))]
            lost.append((name, len(m_old) - len(m_surv), gone))
        c_old, c_surv = match(kept_old, labels, True), match(survivors, labels, True)
        if len(c_surv) < len(c_old):
            gone = [where(labels[li]) for li in sorted(set(c_old) - set(c_surv))]
            recoloured.append((name, len(c_old) - len(c_surv), gone))
        m_new = match(kept_new, labels)
        matched_new = {id(kept_new[bi]) for bi in m_new.values()}
        for d in kept_new:
            if id(d) not in old_ids:
                n_revived += 1
                if id(d) not in matched_new:
                    revived_extra.append((name, round(d.x_center), round(d.y_center), d.confidence))

    real_pairs.sort(reverse=True)
    real_max = real_pairs[0][0] if real_pairs else 0.0
    recall = seen_old / n_labels if n_labels else 0.0
    print(f"images {len(dets)} (expected {args.expect_images})  labelled stones {n_labels}  recall(old) {recall:.4f}")
    print(f"largest raw stone box side {max_extent:.1f} px")
    print(
        f"real-vs-real overlapping pairs {len(real_pairs)}  IoMin max {real_max:.3f}  above 0.20: "
        f"{sum(v > 0.20 for v, *_ in real_pairs)}"
    )
    for v, name, a, b in real_pairs[:10]:
        print(f"  {v:.3f}  {name}  {a} {b}")
    bins = [0, 0.1, 0.2, 0.27, 0.3, 0.4, 0.5, 0.7, 1.01]
    hist = Counter(next(k for k in range(len(bins) - 1) if bins[k] <= v < bins[k + 1]) for v in extra_best)
    print("extra boxes, best IoMin with a real box:", {f"{bins[k]}-{bins[k+1]}": hist.get(k, 0) for k in range(len(bins) - 1)})
    print(f"labels the new rule's merges cost: {sum(n for _, n, _ in lost)} {lost[:20]}")
    print(f"labels that lose their correct-colour box: {sum(n for _, n, _ in recoloured)} {recoloured[:20]}")
    print(
        f"boxes the new rule keeps but the old one dropped: {n_revived}, of which on no label: {len(revived_extra)} "
        f"{revived_extra[:20]}"
    )
    valid = len(dets) == args.expect_images and recall >= GATE_MIN_RECALL
    ok = valid and real_max <= GATE_REAL_MAX and not lost and not recoloured and not revived_extra
    verdict = "PASS" if ok else ("FAIL" if valid else "INVALID")
    print(
        f"VERDICT: {verdict}  (valid: images == expected and recall >= {GATE_MIN_RECALL}; pass: real max <= "
        f"{GATE_REAL_MAX}, no label lost or recoloured by the new merges, no revived box on an empty point)"
    )


if __name__ == "__main__":
    main()
