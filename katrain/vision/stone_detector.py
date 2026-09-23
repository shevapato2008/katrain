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


def dedup_detections(detections: list["Detection"]) -> list["Detection"]:
    """Suppress duplicate boxes that NMS misses: size-variant boxes on the SAME stone
    (a tight box nested in a loose one) can have mutual IoU below the NMS threshold, so
    one stone yields several boxes. Two detections whose centers are closer than half
    the smaller box's mean side are the same object — keep the higher confidence.

    Grouping: black/white dedup against each other (one stone misread as both colors
    must not yield two stones — the loser would otherwise spill to a neighbouring empty
    point and manufacture a phantom); LED classes only dedup within their own class, so
    a lamp halo overlapping a stone never suppresses the stone itself.

    Detections without a real bbox (the (0,0,0,0) default) are never deduped.

    The scan is greedy and order-dependent, so it stays a loop; what changed is WHAT it
    scans.  It used to compare every detection against every detection kept so far —
    O(k^2) in interpreted Python, measured on the RK3562 kiosk at 6 / 31 / 86 ms for
    60 / 130 / 213 stones, i.e. the single largest reason recognition slowed down as a
    game filled up.  Duplicates are by definition local (a pair can only clash within
    ``0.5 * min_side``), so candidates are now looked up in a uniform spatial grid and
    only the few genuine neighbours are tested.

    Grid cell = ``0.5 * max_side`` over the whole batch, which is an upper bound on any
    pair's clash radius — so two detections closer than their radius always land in the
    same or an adjacent cell, and scanning the 3x3 neighbourhood can never miss a pair.
    The arithmetic inside the test is untouched (same ``math.hypot``, same ``min``, same
    ordering), so this is bit-identical to the previous implementation, not merely
    equivalent.
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

    cell = 0.5 * max_side
    # (cell_x, cell_y) -> indices of KEPT detections with a positive side.  A detection
    # with side <= 0 makes min_side <= 0 against everything, so it can neither be a
    # duplicate nor suppress one — it is never queried and never inserted.
    buckets: dict[tuple[int, int], list[int]] = {}
    neighbourhood = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1))

    kept: list[Detection] = []
    for i, det in enumerate(dets):
        d_side = sides[i]
        is_dup = False
        if d_side > 0:
            bx, by = int(det.x_center // cell), int(det.y_center // cell)
            det_is_stone = det.class_id in STONE_CLASS_IDS
            for dx, dy in neighbourhood:
                for j in buckets.get((bx + dx, by + dy), ()):
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
                if is_dup:
                    break
        if not is_dup:
            kept.append(det)
            if d_side > 0:
                buckets.setdefault((int(det.x_center // cell), int(det.y_center // cell)), []).append(i)
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
