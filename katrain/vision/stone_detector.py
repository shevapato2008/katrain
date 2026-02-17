"""
YOLO11-based Go stone detector.

Uses ultralytics YOLO for detecting black and white stones.
Enables agnostic_nms to prevent overlapping black/white boxes at same position.
"""

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

CLASS_NAMES = {0: "black", 1: "white"}


@dataclass
class Detection:
    """A single detected stone."""

    x_center: float
    y_center: float
    class_id: int
    confidence: float

    @property
    def class_name(self) -> str:
        return CLASS_NAMES.get(self.class_id, f"unknown_{self.class_id}")


class StoneDetector:
    """Wraps ultralytics YOLO model for stone detection."""

    def __init__(self, model_path: str, confidence_threshold: float = 0.5, imgsz: int = 960):
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz

    def detect(self, image: np.ndarray) -> list[Detection]:
        """Run YOLO inference on a perspective-corrected board image."""
        results = self.model(image, verbose=False, imgsz=self.imgsz, agnostic_nms=True)
        detections = []
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        x_center=(x1 + x2) / 2,
                        y_center=(y1 + y2) / 2,
                        class_id=int(box.cls[0]),
                        confidence=conf,
                    )
                )
        return detections
