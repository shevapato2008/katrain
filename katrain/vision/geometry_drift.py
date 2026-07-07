"""Lighting-tolerant displacement monitor for a locked physical board."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DriftResult:
    degraded: bool
    shift_px: float
    shift_cells: float
    response: float
    consecutive: int


class GeometryDriftMonitor:
    def __init__(
        self, reference, *, cell_spacing_px: float, threshold_cells: float = 0.10, consecutive_frames: int = 3
    ):
        self.reference = self._features(reference)
        self.cell_spacing_px = float(cell_spacing_px)
        self.threshold_cells = float(threshold_cells)
        self.consecutive_frames = int(consecutive_frames)
        self._over_threshold = 0

    @staticmethod
    def _features(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        gray = gray.astype(np.float32)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(gx, gy)
        magnitude -= magnitude.mean()
        return magnitude

    def update(self, frame) -> DriftResult:
        current = self._features(frame)
        if current.shape != self.reference.shape:
            self._over_threshold += 1
            return DriftResult(
                degraded=self._over_threshold >= self.consecutive_frames,
                shift_px=float("inf"),
                shift_cells=float("inf"),
                response=0.0,
                consecutive=self._over_threshold,
            )
        (dx, dy), response = cv2.phaseCorrelate(self.reference, current)
        shift_px = float(np.hypot(dx, dy))
        shift_cells = shift_px / max(self.cell_spacing_px, 1.0)
        if response >= 0.05 and shift_cells > self.threshold_cells:
            self._over_threshold += 1
        else:
            self._over_threshold = 0
        return DriftResult(
            degraded=self._over_threshold >= self.consecutive_frames,
            shift_px=shift_px,
            shift_cells=shift_cells,
            response=float(response),
            consecutive=self._over_threshold,
        )
