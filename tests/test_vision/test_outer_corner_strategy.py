"""Task 2 (P12): OuterCornerStrategy — no-LED, stateless outer-quad → homography.

修订说明 #1/#3/#10: uses the STATELESS detector (no lock-and-hold); detection failure
returns ok=False (never a stale quad); M/Minv non-None iff ok; Minv·M ≈ I; confidence in [0,1].
"""
import cv2
import numpy as np

import katrain.vision.geometry_detect as gd
from katrain.vision.calibration_strategy import CalibrationContext, Scenario
from katrain.vision.calibration_strategies import OuterCornerStrategy

OUT = 950
CANON = np.array([[0, 0], [OUT - 1, 0], [OUT - 1, OUT - 1], [0, OUT - 1]], np.float32)  # TL,TR,BR,BL


def _ctx(frames, **kw):
    return CalibrationContext(frames=frames, out_size=OUT, **kw)


def _frame():
    return np.zeros((720, 1280, 3), np.uint8)


def test_recovers_homography_from_detected_quad():
    cam = np.array([[120, 90], [560, 100], [580, 520], [90, 500]], np.float32)  # camera trapezoid
    strat = OuterCornerStrategy(detect_fn=lambda f: cam.copy())
    out = strat.calibrate(_ctx([_frame()]), allow_led=False)
    assert out.ok and out.strategy == "outer_corner"
    # M maps the detected camera corners onto the canonical outer-grid corners
    mapped = cv2.perspectiveTransform(cam.reshape(-1, 1, 2), out.M).reshape(-1, 2)
    assert np.allclose(mapped, CANON, atol=1.0)
    # Minv · M ≈ I
    assert np.allclose(out.Minv @ out.M, np.eye(3), atol=1e-6)
    assert 0.0 <= out.confidence <= 1.0


def test_detection_failure_returns_not_ok_never_stale():
    strat = OuterCornerStrategy(detect_fn=lambda f: None)
    out = strat.calibrate(_ctx([_frame()]), allow_led=False)
    assert out.ok is False and out.M is None and out.Minv is None
    assert "detect" in out.reason or "board" in out.reason


def test_no_state_leakage_between_different_boards():
    cam_a = np.array([[100, 80], [500, 90], [520, 480], [80, 460]], np.float32)
    cam_b = np.array([[200, 150], [620, 140], [640, 560], [180, 540]], np.float32)
    seq = [cam_a, cam_b]
    strat = OuterCornerStrategy(detect_fn=lambda f: seq.pop(0).copy())
    out_a = strat.calibrate(_ctx([_frame()]), allow_led=False)
    out_b = strat.calibrate(_ctx([_frame()]), allow_led=False)
    assert out_a.ok and out_b.ok
    assert not np.allclose(out_a.M, out_b.M)  # second result reflects board B, not A


def test_requires_led_false_and_crowded_true():
    strat = OuterCornerStrategy(detect_fn=lambda f: None)
    assert strat.requires_led is False
    assert strat.works_on_crowded_board is True


def test_stateless_wrapper_does_not_touch_globals():
    gd.reset_state()
    assert gd._locked is None
    gd.detect_board_raw(_frame())  # blank → None, but must not mutate lock-and-hold globals
    assert gd._locked is None and gd._acq_buf == []
