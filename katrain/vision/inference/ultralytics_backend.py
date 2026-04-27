"""Ultralytics YOLO inference backend for dev/training use."""

from __future__ import annotations

import json
import logging

import numpy as np

from katrain.vision.stone_detector import Detection

logger = logging.getLogger(__name__)


class UltralyticsBackend:
    """Wraps the ultralytics YOLO library.  Implements the InferenceBackend protocol."""

    def __init__(self) -> None:
        self._model = None
        self._imgsz: int = 960

    # -- InferenceBackend protocol ------------------------------------------------

    def load(self, model_path: str, meta_path: str | None = None) -> None:
        """Import and instantiate a YOLO model from *model_path*.

        *meta_path* is an optional ``meta.json`` sidecar.  If it contains an
        ``imgsz`` key the value is used as the inference image size; otherwise
        the default of 960 is kept.
        """
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError(
                "The ultralytics package is required for UltralyticsBackend. "
                "Install it with: pip install ultralytics"
            ) from exc

        if meta_path is not None:
            try:
                with open(meta_path, "r") as fh:
                    meta = json.load(fh)
                self._imgsz = int(meta.get("imgsz", self._imgsz))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to read meta file %s: %s", meta_path, exc)

        self._model = YOLO(model_path)
        logger.info("UltralyticsBackend loaded model %s (imgsz=%d)", model_path, self._imgsz)

    def detect(self, image: np.ndarray, confidence_threshold: float) -> list[Detection]:
        """Run YOLO inference and return detections above *confidence_threshold*."""
        if self._model is None:
            raise RuntimeError("Model not loaded – call load() first")

        results = self._model(image, verbose=False, imgsz=self._imgsz, agnostic_nms=True)
        detections: list[Detection] = []
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < confidence_threshold:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        x_center=(x1 + x2) / 2,
                        y_center=(y1 + y2) / 2,
                        class_id=int(box.cls[0]),
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                    )
                )
        return detections

    def unload(self) -> None:
        """Release the model reference."""
        self._model = None

    @property
    def is_loaded(self) -> bool:
        """Whether a model is currently loaded."""
        return self._model is not None
