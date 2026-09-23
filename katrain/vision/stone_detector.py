"""
Go stone detector with pluggable inference backends.

Supports ultralytics (dev), ONNX Runtime (SBC), and RKNN NPU (experimental)
via the InferenceBackend protocol.
"""

import math
from dataclasses import dataclass

import numpy as np

from katrain.vision.classes import ID_TO_NAME as CLASS_NAMES  # {0:'black',1:'white',2:'led_red',3:'led_green'}
from katrain.vision.classes import STONE_CLASS_IDS


@dataclass
class Detection:
    """A single detected stone."""

    x_center: float
    y_center: float
    class_id: int
    confidence: float
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # (x1, y1, x2, y2)

    @property
    def class_name(self) -> str:
        return CLASS_NAMES.get(self.class_id, f"unknown_{self.class_id}")


# Shadow duplicates (RK3562 daylight game, 2026-09-23): side light makes the model box a stone together
# with its shadow a second time, centred 0.56-0.75 cells off the stone -- outside the centre-distance
# radius used below -- and that box then became a phantom on the neighbouring point (H5: 16 prompts in
# one game). Labelled against the game record on 12 board frames, two REAL stones' boxes overlap at
# most 0.233 of the smaller box (J2+J3; boxes are ~1.1 cells wide), while every shadow box that could
# become a phantom overlaps its stone by >= 0.326. See
# superpowers/tracks/vision-optimizations/shadow-dedup/design.md.
DEDUP_OVERLAP_MIN = 0.27
# ...but only between boxes of similar size: the overlap is measured against the SMALLER box, so a hand
# misread as one big box would otherwise swallow every stone under it. Measured: shadow pairs <= 1.58,
# neighbouring real stones <= 1.21.
DEDUP_MAX_SIDE_RATIO = 2.0


def _overlap_of_smaller(a: tuple, b: tuple) -> float:
    """Intersection area of two (x1, y1, x2, y2) boxes over the smaller box's area; 0.0 when either has none."""
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    smaller = area_a if area_a < area_b else area_b
    if smaller <= 0:
        return 0.0
    w = min(a[2], b[2]) - max(a[0], b[0])
    if w <= 0:
        return 0.0
    h = min(a[3], b[3]) - max(a[1], b[1])
    if h <= 0:
        return 0.0
    return w * h / smaller


def dedup_detections(detections: list["Detection"]) -> list["Detection"]:
    """Suppress duplicate boxes that NMS misses. Two detections are the same object when their centres
    are closer than half the smaller box's mean side (size-variant boxes on one stone -- a tight box
    nested in a loose one -- can have mutual IoU below the NMS threshold), or, for two STONE boxes of
    similar size (larger mean side <= DEDUP_MAX_SIDE_RATIO x smaller), when they overlap by at least
    DEDUP_OVERLAP_MIN of the smaller box (a stone boxed a second time together with its shadow).
    Keep the higher confidence.

    Grouping: black/white dedup against each other (one stone misread as both colors
    must not yield two stones — the loser would otherwise spill to a neighbouring empty
    point and manufacture a phantom); LED classes only dedup within their own class, so
    a lamp halo overlapping a stone never suppresses the stone itself.

    Detections without a real bbox (the (0,0,0,0) default) are never deduped.

    The scan is greedy and order-dependent, so it stays a loop; what changed is WHAT it
    scans.  It used to compare every detection against every detection kept so far —
    O(k^2) in interpreted Python, measured on the RK3562 kiosk at 6 / 31 / 86 ms for
    60 / 130 / 213 stones, i.e. the single largest reason recognition slowed down as a
    game filled up.  Duplicates are by definition local, so candidates are now looked up
    in a uniform spatial grid and only the few genuine neighbours are tested.

    Grid: each box's reach -- half its larger bbox extent plus how far its centre sits from the bbox
    midpoint -- bounds, per axis, how far the centre of any box it can merge with may be (the centre rule's
    radius is always inside it). The cell is twice the largest reach, so the 3x3 scan never misses a pair and
    the result is identical to the scalar O(k^2) scan. A box reaching further than twice the median (a hand
    or sleeve read as one big box, a non-finite coordinate) stays out of the grid and is checked against
    every kept box instead, so one such box cannot turn the whole scan back into O(k^2).

    The overlap clause only ever ADDS merges, but the greedy output is not monotone: a box that the
    centre rule alone drops because B was kept survives once B itself is merged into A by the overlap
    clause.
    """
    n = len(detections)
    if n < 2:
        return list(detections)

    # Descending confidence; sorted() is stable, so equal confidences keep input order.
    # The greedy rule below depends on this exact ordering.
    dets = sorted(detections, key=lambda d: -d.confidence)
    sides = [(d.bbox[2] - d.bbox[0] + d.bbox[3] - d.bbox[1]) / 2.0 for d in dets]

    max_side = max(sides)
    if max_side <= 0:
        return dets  # every min_side would be <= 0: nothing can dedup anything

    # How far apart, on each axis, the centres of two boxes that either rule can merge may be: at most the sum
    # of their reaches, where reach = half the larger bbox extent + how far (x_center, y_center) sits from the
    # bbox midpoint (0 for every backend, but Detection does not enforce it). The centre rule's radius,
    # 0.5 * min_side, is always inside that sum.
    reach = [
        (
            max(d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1]) / 2.0
            + max(abs(d.x_center - (d.bbox[0] + d.bbox[2]) / 2.0), abs(d.y_center - (d.bbox[1] + d.bbox[3]) / 2.0))
            if s > 0
            else 0.0
        )
        for d, s in zip(dets, sides)
    ]
    # A box reaching further than twice the median (a hand or sleeve read as one big box; a non-finite
    # coordinate) stays out of the grid and is checked linearly, so it cannot size the grid for every other
    # box -- one 1056 px box would otherwise put the whole board in one bucket.
    finite = sorted(r for r in reach if 0 < r < math.inf)
    limit = 2.0 * finite[len(finite) // 2] if finite else 0.0
    # Two gridded boxes that can clash are closer than 2 * max(reach) on each axis, so with this cell they
    # land in the same or an adjacent bucket and the 3x3 scan never misses one.
    cell = 2.0 * max((r for r in reach if 0 < r <= limit), default=1.0)
    # (cell_x, cell_y) -> indices of KEPT gridded detections.  A detection with side <= 0 makes min_side <= 0
    # against everything, so it can neither be a duplicate nor suppress one — it is never queried and never
    # inserted.
    buckets: dict[tuple[int, int], list[int]] = {}
    neighbourhood = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1))
    wide: list[int] = []  # KEPT detections outside the grid
    boxed: list[int] = []  # every KEPT detection with a positive side

    kept: list[Detection] = []
    for i, det in enumerate(dets):
        d_side = sides[i]
        is_dup = False
        if d_side > 0:
            gridded = reach[i] <= limit  # False for NaN too
            if gridded:
                bx, by = int(det.x_center // cell), int(det.y_center // cell)
                candidates = [j for dx, dy in neighbourhood for j in buckets.get((bx + dx, by + dy), ())] + wide
            else:
                candidates = boxed
            det_is_stone = det.class_id in STONE_CLASS_IDS
            for j in candidates:
                other = dets[j]
                if (other.class_id in STONE_CLASS_IDS) != det_is_stone:
                    continue  # stone vs LED: different groups
                if not det_is_stone and det.class_id != other.class_id:
                    continue  # LED classes: same-class only
                min_side = d_side if d_side < sides[j] else sides[j]
                if min_side <= 0:
                    continue
                if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                    is_dup = True
                    break
                if det_is_stone:
                    max_pair_side = d_side if d_side > sides[j] else sides[j]
                    if (
                        max_pair_side <= DEDUP_MAX_SIDE_RATIO * min_side
                        and _overlap_of_smaller(det.bbox, other.bbox) >= DEDUP_OVERLAP_MIN
                    ):
                        is_dup = True
                        break
        if not is_dup:
            kept.append(det)
            if d_side > 0:
                boxed.append(i)
                if gridded:
                    buckets.setdefault((bx, by), []).append(i)
                else:
                    wide.append(i)
    return kept


class StoneDetector:
    """Wraps an inference backend for stone detection.

    Args:
        model_path: Path to model weights (.pt, .onnx, or .rknn).
        backend: Backend name — "ultralytics", "onnx", or "rknn".
        confidence_threshold: Minimum detection confidence.
        imgsz: Input image size (used by ultralytics backend; ONNX reads from meta.json).
        iou_threshold: Agnostic-NMS IoU override. None uses the backend default (0.5). Lower
            (e.g. 0.5) merges size-variant duplicate boxes on blurry far-side stones.
    """

    def __init__(
        self,
        model_path: str,
        backend: str = "ultralytics",
        confidence_threshold: float = 0.5,
        imgsz: int = 960,
        iou_threshold: float | None = None,
    ):
        from katrain.vision.inference import create_backend

        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz
        self.iou_threshold = iou_threshold
        self.backend_impl = create_backend(backend)
        self.backend_impl.load(model_path)

    def detect(self, image: np.ndarray) -> list[Detection]:
        """Run inference on a perspective-corrected board image."""
        return dedup_detections(self.backend_impl.detect(image, self.confidence_threshold, self.iou_threshold))
