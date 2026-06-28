"""P12 — concrete calibration strategies (adapters over the repo's existing algorithms).

Each class implements the ``CalibrationStrategy`` protocol from ``calibration_strategy``.
This file starts with ``OuterCornerStrategy`` (Task 2); LED/autocal adapters land in Task 3.
"""
from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np

from katrain.vision import geometry_detect as _gd
from katrain.vision.calibration_strategy import CalibrationContext, CalibrationOutcome


class OuterCornerStrategy:
    """No-LED, crowded-board geometry via the board's OUTER-grid quad.

    Reuses the STATELESS detector ``geometry_detect.detect_board_raw`` (not the lock-and-hold
    ``detect_board``), maps the detected 4 corners onto the canonical outer-grid corners, and
    solves a 4-point homography. Stones never occlude the outer frame, so this works mid-game;
    on detection failure it returns ``ok=False`` (never a stale quad). Confidence is a
    stability/plausibility proxy here — true accuracy is gated in Task 9.
    """

    name = "outer_corner"
    requires_led = False
    works_on_crowded_board = True

    def __init__(
        self,
        detect_fn: Optional[Callable[[np.ndarray], Optional[np.ndarray]]] = None,
        *,
        max_error_cells: float = 0.12,
        disp_tol_px: float = 8.0,
        min_confidence: float = 0.2,
    ):
        self._detect = detect_fn or _gd.detect_board_raw
        self.max_error_cells = max_error_cells
        self._disp_tol_px = disp_tol_px
        self._min_confidence = min_confidence

    def is_applicable(self, ctx: CalibrationContext) -> bool:
        return bool(ctx.frames)

    def calibrate(self, ctx: CalibrationContext, *, allow_led: bool) -> CalibrationOutcome:
        quads = []
        for frame in ctx.frames:
            q = self._detect(frame)
            if q is not None:
                quads.append(np.asarray(q, np.float64).reshape(4, 2))
        if not quads:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="no_board_detected")

        stack = np.stack(quads)
        quad = np.asarray(_gd.sort_corners(np.median(stack, axis=0)), np.float64)
        h, w = ctx.frames[0].shape[:2]
        if not _gd._plausible_quad(quad.astype(np.float32), w, h):
            return CalibrationOutcome(ok=False, strategy=self.name, reason="implausible_quad")

        # confidence: inter-frame stability (if >1 frame) gated by single-frame uncertainty.
        dispersion = 0.0 if len(quads) < 2 else float(np.sqrt(((stack - quad) ** 2).sum(axis=2)).max())
        base = 1.0 if len(quads) >= 2 else 0.8
        confidence = base * float(np.clip(1.0 - dispersion / self._disp_tol_px, 0.0, 1.0))
        if confidence < self._min_confidence:
            return CalibrationOutcome(ok=False, strategy=self.name, reason=f"low_confidence:{confidence:.2f}")

        s = int(ctx.out_size)
        dst = np.array([[0, 0], [s - 1, 0], [s - 1, s - 1], [0, s - 1]], np.float32)  # TL,TR,BR,BL
        M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst).astype(np.float64)
        try:
            Minv = np.linalg.inv(M)
        except np.linalg.LinAlgError:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="singular_homography")
        return CalibrationOutcome(
            ok=True, M=M, Minv=Minv, corners=quad, confidence=confidence, strategy=self.name
        )
