"""P12 — passive drift detection (rotation-aware) + the recalibration state machine.

Two pieces:
  * ``RotationAwareDrift`` — combines translation (GeometryDriftMonitor / phaseCorrelate) with
    an ABSOLUTE-POSE check (a pose_fn returning the current camera->canonical homography),
    so a pure rotation (the magnet detach/reattach case) is flagged even when translation ≈ 0.
  * ``DriftStateMachine`` — STABLE → MOVING → (settle) → recalibrate → STABLE / NEEDS_ATTENTION.
    On recalibration failure it never updates M (keeps last-good) and pauses captures.

Both take injected callables so they're testable without hardware. See plan.md "P12 修订说明".
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from katrain.vision.fiducial_recalibrate import drift_from_homography
from katrain.vision.geometry_drift import GeometryDriftMonitor


@dataclass(frozen=True)
class DriftSignal:
    over_threshold: bool
    shift_cells: float
    deg: float
    reason: str  # "translation" | "rotation" | ""


class RotationAwareDrift:
    """Translation (phaseCorrelate) OR absolute-pose rotation/scale exceeds threshold."""

    def __init__(
        self,
        reference_frame,
        reference_M,
        *,
        cell_spacing_px: float,
        pose_fn: Optional[Callable[[object], Optional[np.ndarray]]] = None,
        out_size: int = 950,
        threshold_cells: float = 0.15,
        deg_threshold: float = 1.0,
    ):
        self._mon = GeometryDriftMonitor(
            reference_frame, cell_spacing_px=cell_spacing_px, threshold_cells=threshold_cells, consecutive_frames=1
        )
        self._ref_M = np.asarray(reference_M, np.float64)
        self._pose_fn = pose_fn
        self._out_size = int(out_size)
        self._thr = float(threshold_cells)
        self._deg = float(deg_threshold)
        self._spacing = (self._out_size - 1) / 18.0

    def update(self, frame) -> DriftSignal:
        d = self._mon.update(frame)
        trans_over = bool(d.shift_cells > self._thr)
        deg = 0.0
        pose_over = False
        M = self._pose_fn(frame) if self._pose_fn is not None else None
        if M is not None:
            dr = drift_from_homography(np.asarray(M, np.float64), self._ref_M, out_size=self._out_size)
            deg = abs(float(dr.deg))
            pose_cells = dr.median_px / self._spacing
            pose_over = deg > self._deg or pose_cells > self._thr
        over = trans_over or pose_over
        reason = "rotation" if (pose_over and not trans_over) else ("translation" if trans_over else "")
        return DriftSignal(over_threshold=over, shift_cells=float(d.shift_cells), deg=deg, reason=reason)


class State(enum.Enum):
    STABLE = "stable"
    MOVING = "moving"
    NEEDS_ATTENTION = "needs_attention"


class DriftStateMachine:
    """Drives passive detect → settle-gated no-LED recalibration. Captures are only allowed
    in STABLE. ``recalibrate_fn(frame)`` returns a CalibrationOutcome (it must use a no-LED
    scenario); on failure the machine keeps the last-good M and flags NEEDS_ATTENTION."""

    def __init__(
        self,
        *,
        drift_fn: Callable[[object], bool],
        motion_fn: Callable[[object], bool],
        recalibrate_fn: Callable[[object], object],
        on_recalibrated: Optional[Callable[[object, np.ndarray], None]] = None,
        enter_moving_frames: int = 3,
        settle_frames: int = 3,
        initial_M: Optional[np.ndarray] = None,
    ):
        self.state = State.STABLE
        self._drift = drift_fn
        self._motion = motion_fn
        self._recal = recalibrate_fn
        self._on_recal = on_recalibrated or (lambda frame, M: None)
        self._enter = int(enter_moving_frames)
        self._settle = int(settle_frames)
        self.M = None if initial_M is None else np.asarray(initial_M, np.float64)
        self._over = 0
        self._still = 0

    @property
    def capture_allowed(self) -> bool:
        return self.state is State.STABLE

    def _do_recalibrate(self, frame):
        out = self._recal(frame)
        if getattr(out, "ok", False) and getattr(out, "M", None) is not None:
            self.M = np.asarray(out.M, np.float64)
            self.state = State.STABLE
            self._over = 0
            self._still = 0
            self._on_recal(frame, self.M)  # re-baseline the drift reference
        else:
            self.state = State.NEEDS_ATTENTION
            self._still = 0
        return out

    def update(self, frame) -> State:
        if self.state is State.STABLE:
            self._over = self._over + 1 if self._drift(frame) else 0
            if self._over >= self._enter:
                self.state = State.MOVING
                self._over = 0
                self._still = 0
        elif self.state is State.MOVING:
            self._still = 0 if self._motion(frame) else self._still + 1
            if self._still >= self._settle:
                self._do_recalibrate(frame)
        elif self.state is State.NEEDS_ATTENTION:
            self._still = 0 if self._motion(frame) else self._still + 1
            if self._still >= self._settle:
                self._do_recalibrate(frame)
        return self.state

    def manual_recalibrate(self, frame):
        """User-initiated recovery (MANUAL_FALLBACK at the call site — may use LED)."""
        return self._do_recalibrate(frame)
