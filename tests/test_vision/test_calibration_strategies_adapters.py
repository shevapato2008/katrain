"""Task 3 (P12): Strategy adapters over existing algorithms.

EmptyBoardAutocal (no-LED, empty-only, full lock), LedAnchor (LED, golden lock),
LedFiducial (LED, per-frame M). Verifies flags, is_applicable veto, the LED self-guard
(no led calls when allow_led=False), and a synthetic LedFiducial happy path.
"""
from types import SimpleNamespace

import cv2
import numpy as np

from katrain.vision.calibration_strategy import CalibrationContext
from katrain.vision.calibration_strategies import (
    EmptyBoardAutocalStrategy,
    LedAnchorStrategy,
    LedFiducialStrategy,
)

OUT = 950


def _fake_lock():
    M = np.eye(3, dtype=np.float64)
    return SimpleNamespace(
        M=M, Minv=M, corners=np.zeros((4, 2)), confidence=0.91, out_size=OUT,
        points=np.zeros((19, 19, 2)), xs=np.arange(19.0), ys=np.arange(19.0), baseline=np.zeros((19, 19, 3)),
    )


def _frame():
    return np.zeros((1000, 1000, 3), np.uint8)


class _SpyLed:
    def __init__(self):
        self.rgb_calls = 0

    def clear(self, *, strict=False):
        return {"ok": True}

    def set_rgb_points(self, points, *, strict=False):
        self.rgb_calls += 1
        return {"ok": True, "shown_at": 1.0}


# ----------------------------- EmptyBoardAutocal -----------------------------
def test_autocal_produces_full_lock_outcome():
    strat = EmptyBoardAutocalStrategy(lock_fn=lambda frames, *, conf_min, out_size: _fake_lock())
    out = strat.calibrate(CalibrationContext(frames=[_frame()], board=None, out_size=OUT), allow_led=False)
    assert out.ok and out.strategy == "empty_board_autocal"
    assert out.baseline is not None and out.points is not None and out.xs is not None
    assert strat.requires_led is False and strat.works_on_crowded_board is False


def test_autocal_none_is_not_ok_and_empty_only():
    strat = EmptyBoardAutocalStrategy(lock_fn=lambda *a, **k: None)
    out = strat.calibrate(CalibrationContext(frames=[_frame()], board=None, out_size=OUT), allow_led=False)
    assert out.ok is False and out.M is None
    assert strat.is_applicable(CalibrationContext(frames=[_frame()], board=None)) is True
    assert strat.is_applicable(CalibrationContext(frames=[_frame()], board=[[None] * 19] * 19)) is False


# ------------------------------- LedAnchor ----------------------------------
def test_led_anchor_self_guard_no_led_calls_when_forbidden():
    called = {"calibrate": False}

    def factory(*, led, capture, out_size):
        def cal():
            called["calibrate"] = True
            return SimpleNamespace(ok=True, lock=_fake_lock(), reason=None)
        return SimpleNamespace(calibrate=cal)

    strat = LedAnchorStrategy(calibrator_factory=factory)
    led = _SpyLed()
    ctx = CalibrationContext(frames=[_frame()], board=None, led=led, capture=object(), out_size=OUT)
    out = strat.calibrate(ctx, allow_led=False)
    assert out.ok is False and out.reason == "led_forbidden"
    assert called["calibrate"] is False and led.rgb_calls == 0  # nothing lit
    assert strat.requires_led is True


def test_led_anchor_success_when_allowed():
    factory = lambda *, led, capture, out_size: SimpleNamespace(  # noqa: E731
        calibrate=lambda: SimpleNamespace(ok=True, lock=_fake_lock(), reason=None)
    )
    strat = LedAnchorStrategy(calibrator_factory=factory)
    ctx = CalibrationContext(frames=[_frame()], board=None, led=_SpyLed(), capture=object(), out_size=OUT)
    out = strat.calibrate(ctx, allow_led=True)
    assert out.ok and out.strategy == "led_anchor" and out.baseline is not None


# ------------------------------ LedFiducial ---------------------------------
def _grid_points():
    pts = np.zeros((19, 19, 2), np.float64)
    for r in range(19):
        for c in range(19):
            pts[r][c] = (50 + c * 48, 50 + r * 48)
    return pts


class _FiducialCapture:
    """grab_fresh: dark frame when after_ts is None, lit (green blobs) otherwise."""

    def __init__(self, lit):
        self._lit = lit

    def grab_fresh(self, after_ts=None, settle_ms=0.0):
        if after_ts is None:
            return np.zeros_like(self._lit), 1, 1.0
        return self._lit.copy(), 2, 2.0


def _build_led_fiducial_ctx():
    points = _grid_points()
    geometry = SimpleNamespace(out_size=OUT, points=points, M=np.eye(3))
    board = [[None] * 19 for _ in range(19)]
    from katrain.vision.fiducial_recalibrate import predict_camera_positions, select_fiducials

    F = select_fiducials(board, None, target=13, min_count=8)
    lit = np.zeros((1000, 1000, 3), np.uint8)
    for (r, c), (x, y) in predict_camera_positions(F, points).items():
        cv2.circle(lit, (int(x), int(y)), 6, (0, 255, 0), -1)  # green blob (BGR)
    ctx = CalibrationContext(
        frames=[lit], board=board, geometry=geometry, led=_SpyLed(), capture=_FiducialCapture(lit), out_size=OUT
    )
    return ctx


def test_led_fiducial_self_guard_no_led_when_forbidden():
    ctx = _build_led_fiducial_ctx()
    out = LedFiducialStrategy().calibrate(ctx, allow_led=False)
    assert out.ok is False and out.reason == "led_forbidden" and ctx.led.rgb_calls == 0


def test_led_fiducial_vetoes_without_board_or_geometry():
    strat = LedFiducialStrategy()
    assert strat.is_applicable(CalibrationContext(frames=[_frame()], board=None)) is False
    full = _build_led_fiducial_ctx()
    assert strat.is_applicable(full) is True


def test_led_fiducial_happy_path_solves_M():
    ctx = _build_led_fiducial_ctx()
    out = LedFiducialStrategy().calibrate(ctx, allow_led=True)
    assert out.ok and out.strategy == "led_fiducial"
    assert out.M is not None and out.Minv is not None and ctx.led.rgb_calls == 1
