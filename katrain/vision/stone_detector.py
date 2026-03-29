"""
Go stone detector with pluggable inference backends.

Supports ultralytics (dev), ONNX Runtime (SBC), and RKNN NPU (experimental)
via the InferenceBackend protocol.
"""

from dataclasses import dataclass

import numpy as np

CLASS_NAMES = {0: "black", 1: "white"}


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


class StoneDetector:
    """Wraps an inference backend for stone detection.

    Args:
        model_path: Path to model weights (.pt, .onnx, or .rknn).
        backend: Backend name — "ultralytics", "onnx", or "rknn".
        confidence_threshold: Minimum detection confidence.
        imgsz: Input image size (used by ultralytics backend; ONNX reads from meta.json).
    """

    def __init__(
        self,
        model_path: str,
        backend: str = "ultralytics",
        confidence_threshold: float = 0.5,
        imgsz: int = 960,
    ):
        from katrain.vision.inference import create_backend

        self.confidence_threshold = confidence_threshold
        self.imgsz = imgsz
        self.backend_impl = create_backend(backend)
        self.backend_impl.load(model_path)

    def detect(self, image: np.ndarray) -> list[Detection]:
        """Run inference on a perspective-corrected board image."""
        return self.backend_impl.detect(image, self.confidence_threshold)
