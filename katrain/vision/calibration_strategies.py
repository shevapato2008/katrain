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


# Fiducial colour (full green; raised from 0,96,0 — wood-veneer covers attenuate LEDs).
FIDUCIAL_RGB = (0, 255, 0)
FIDUCIAL_CHANNEL = 1


class EmptyBoardAutocalStrategy:
    """No-LED full-grid lock via the empty-board autocal (geometry_lock). Produces a FULL
    GeometryLock (incl. baseline/points/xs/ys). EMPTY board only — vetoes otherwise."""

    name = "empty_board_autocal"
    requires_led = False
    works_on_crowded_board = False

    def __init__(self, lock_fn: Optional[Callable] = None, *, conf_min: float = 0.80):
        self._lock_fn = lock_fn
        self._conf_min = conf_min

    def _lock(self):
        if self._lock_fn is not None:
            return self._lock_fn
        from katrain.vision.geometry_lock import lock_geometry_from_frames

        return lock_geometry_from_frames

    def is_applicable(self, ctx: CalibrationContext) -> bool:
        return bool(ctx.frames) and ctx.board is None  # empty board only

    def calibrate(self, ctx: CalibrationContext, *, allow_led: bool) -> CalibrationOutcome:
        lock = self._lock()(ctx.frames, conf_min=self._conf_min, out_size=ctx.out_size)
        if lock is None:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="autocal_failed")
        return CalibrationOutcome(
            ok=True,
            M=np.asarray(lock.M, np.float64),
            Minv=np.asarray(lock.Minv, np.float64),
            corners=np.asarray(lock.corners, np.float64),
            confidence=float(lock.confidence),
            strategy=self.name,
            points=np.asarray(lock.points),
            xs=np.asarray(lock.xs),
            ys=np.asarray(lock.ys),
            baseline=np.asarray(lock.baseline),
        )


class LedAnchorStrategy:
    """LED-anchor full calibration (LedGeometryCalibrator) — golden reference, EMPTY board,
    user-initiated only (requires_led). Produces a full GeometryLock."""

    name = "led_anchor"
    requires_led = True
    works_on_crowded_board = False

    def __init__(self, calibrator_factory: Optional[Callable] = None):
        self._factory = calibrator_factory

    def _make(self, ctx):
        if self._factory is not None:
            return self._factory(led=ctx.led, capture=ctx.capture, out_size=ctx.out_size)
        from katrain.vision.led_geometry_calibrator import LedGeometryCalibrator

        return LedGeometryCalibrator(led=ctx.led, capture=ctx.capture, out_size=ctx.out_size)

    def is_applicable(self, ctx: CalibrationContext) -> bool:
        return ctx.led is not None and ctx.capture is not None and ctx.board is None

    def calibrate(self, ctx: CalibrationContext, *, allow_led: bool) -> CalibrationOutcome:
        if not allow_led:  # defense-in-depth self-guard (修订说明 #2b)
            return CalibrationOutcome(ok=False, strategy=self.name, reason="led_forbidden")
        result = self._make(ctx).calibrate()
        lock = getattr(result, "lock", None)
        if not getattr(result, "ok", False) or lock is None:
            return CalibrationOutcome(ok=False, strategy=self.name, reason=getattr(result, "reason", None) or "led_anchor_failed")
        return CalibrationOutcome(
            ok=True,
            M=np.asarray(lock.M, np.float64),
            Minv=np.asarray(lock.Minv, np.float64),
            corners=np.asarray(lock.corners, np.float64),
            confidence=float(lock.confidence),
            strategy=self.name,
            points=np.asarray(lock.points),
            xs=np.asarray(lock.xs),
            ys=np.asarray(lock.ys),
            baseline=np.asarray(lock.baseline),
        )


class LedFiducialStrategy:
    """P11 per-frame LED-fiducial homography (select empty intersections → light → detect →
    solve). LED + user-initiated only; needs >=min_count empty non-occupied intersections,
    so it vetoes on a too-crowded board. Returns a frame homography M (no full lock)."""

    name = "led_fiducial"
    requires_led = True
    works_on_crowded_board = False

    def __init__(self, *, settle_ms: float = 120.0, min_count: int = 8):
        self._settle_ms = settle_ms
        self._min_count = min_count

    def _select(self, ctx):
        from katrain.vision.fiducial_recalibrate import select_fiducials

        return select_fiducials(ctx.board, ctx.next_point, target=13, min_count=self._min_count)

    def is_applicable(self, ctx: CalibrationContext) -> bool:
        if ctx.led is None or ctx.capture is None or ctx.geometry is None or ctx.board is None:
            return False
        return len(self._select(ctx)) >= self._min_count

    def calibrate(self, ctx: CalibrationContext, *, allow_led: bool) -> CalibrationOutcome:
        if not allow_led:  # defense-in-depth self-guard
            return CalibrationOutcome(ok=False, strategy=self.name, reason="led_forbidden")
        from katrain.vision.fiducial_recalibrate import (
            detect_led_centroids,
            predict_camera_positions,
            solve_frame_homography,
        )

        F = self._select(ctx)
        if len(F) < self._min_count:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="insufficient_fiducials")
        out_size = int(ctx.geometry.out_size)
        spacing = (out_size - 1) / 18.0
        expected = predict_camera_positions(F, ctx.geometry.points)
        ctx.led.clear(strict=True)
        dark, _s, _t = ctx.capture.grab_fresh(settle_ms=self._settle_ms)
        show = ctx.led.set_rgb_points([{"row": r, "col": c, "rgb": list(FIDUCIAL_RGB)} for (r, c) in F], strict=True)
        lit, _s, _t = ctx.capture.grab_fresh(after_ts=show.get("shown_at"), settle_ms=self._settle_ms)
        ctx.led.clear(strict=True)
        det = detect_led_centroids(dark, lit, expected, channel=FIDUCIAL_CHANNEL, search_px=0.7 * spacing)
        ok_pts = [((r, c), det[(r, c)].centroid) for (r, c) in F if det[(r, c)].ok]
        if len(ok_pts) < self._min_count:
            return CalibrationOutcome(ok=False, strategy=self.name, reason="insufficient_detections")
        fit = solve_frame_homography(ok_pts, out_size=out_size, min_inliers=6)
        if not fit.ok:
            return CalibrationOutcome(ok=False, strategy=self.name, reason=fit.reason)
        return CalibrationOutcome(
            ok=True,
            M=np.asarray(fit.M, np.float64),
            Minv=np.asarray(fit.Minv, np.float64),
            corners=None,
            confidence=min(1.0, fit.inlier_count / 13.0),
            strategy=self.name,
        )
