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
    """
    kept: list[Detection] = []
    for det in sorted(detections, key=lambda d: -d.confidence):
        d_side = (det.bbox[2] - det.bbox[0] + det.bbox[3] - det.bbox[1]) / 2.0
        is_dup = False
        for other in kept:
            if (det.class_id in STONE_CLASS_IDS) != (other.class_id in STONE_CLASS_IDS):
                continue  # stone vs LED: different groups
            if det.class_id not in STONE_CLASS_IDS and det.class_id != other.class_id:
                continue  # LED classes: same-class only
            o_side = (other.bbox[2] - other.bbox[0] + other.bbox[3] - other.bbox[1]) / 2.0
            min_side = min(d_side, o_side)
            if min_side <= 0:
                continue
            if math.hypot(det.x_center - other.x_center, det.y_center - other.y_center) < 0.5 * min_side:
                is_dup = True
                break
        if not is_dup:
            kept.append(det)
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
