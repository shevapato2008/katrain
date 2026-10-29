from pathlib import Path

import cv2
import numpy as np

from katrain.vision.calibration_stability import CalibrationStabilityGate, find_visible_grid


FRAME = cv2.imread(str(Path(__file__).parents[1] / "data" / "rk3562_empty_board_20261013.jpg"))
AFTER_HAND = cv2.imread(str(Path(__file__).parents[1] / "data" / "rk3562_empty_board_after_hand_20261013.jpg"))


def test_real_white_board_is_detected_without_wood_color():
    result = find_visible_grid(FRAME)
    assert result is not None
    assert np.linalg.norm(result[3] - (168, 327)) < 18  # bottom-left grid intersection


def test_real_reflection_is_advisory_and_still_requires_stable_frames():
    frame = cv2.imread(str(Path(__file__).parents[1] / "data" / "rk3562_grid_reflection_20261029.png"))
    assert find_visible_grid(frame) is None  # unchanged detector reproduces the field failure
    gate = CalibrationStabilityGate()
    observations = [gate.observe(frame) for _ in range(5)]
    assert observations[-1] == (True, None)
    assert all(not ready for ready, _reason in observations[:-1])
    assert gate.grid_visible is False
    assert gate.anchor_roi(0, 0) is None
    assert gate.capture_reason(frame) is None
    assert gate.capture_reason(np.roll(frame, 20, axis=1)) == "board_motion"


def test_still_hand_covering_a_corner_or_center_blocks_grid():
    for center in ((170, 305), (100, 60), (315, 180)):
        covered = FRAME.copy()
        cv2.ellipse(covered, center, (55, 42), 20, 0, 360, (160, 175, 190), -1)
        assert find_visible_grid(covered) is None


def test_grid_recovers_after_small_camera_shift_when_hand_leaves():
    previous = find_visible_grid(FRAME)
    assert previous is not None
    recovered = find_visible_grid(AFTER_HAND, previous * 3)
    assert recovered is not None
    assert np.linalg.norm(recovered[0] - (247, 101)) < 25


def test_first_frame_does_not_release_and_motion_resets_count():
    gate = CalibrationStabilityGate(required_frames=3)
    assert gate.observe(FRAME)[0] is False
    assert gate.observe(FRAME)[0] is False
    assert gate.observe(FRAME)[0] is False
    assert gate.observe(FRAME)[0] is True
    moved = np.roll(FRAME, 20, axis=1)
    assert gate.observe(moved)[0] is False


def test_grid_roi_tracks_five_positions_and_a_lit_led_does_not_look_like_a_hand():
    gate = CalibrationStabilityGate()
    for _ in range(5):
        gate.observe(FRAME)
    x, y, radius = gate.anchor_roi(0, 0)
    assert abs(x - 168) < 10 and abs(y - 327) < 10
    assert 40 <= radius <= 80
    assert gate.capture_reason(FRAME) is None
    lit = FRAME.copy()
    cv2.circle(lit, (round(x), round(y)), 8, (80, 250, 80), -1)
    assert gate.capture_reason(lit) is None
    hand = FRAME.copy()
    cv2.ellipse(hand, (170, 305), (55, 42), 20, 0, 360, (160, 175, 190), -1)
    # Missing lines alone are now advisory, even for a stationary covering.
    assert gate.capture_reason(hand) is None
    assert gate.grid_visible is False


def test_motion_outside_the_board_does_not_pause_anchor_capture():
    gate = CalibrationStabilityGate()
    for _ in range(5):
        gate.observe(FRAME)
    assert gate.capture_reason(FRAME) is None
    outside = FRAME.copy()
    outside[40:340, :70] = 0
    assert find_visible_grid(outside) is not None
    assert gate.capture_reason(outside) is None


def test_real_moving_shadow_does_not_pause_calibration():
    folder = Path(__file__).parents[1] / "data"
    before = cv2.imread(str(folder / "rk3562_shadow_before_20261013.jpg"))
    shaded = cv2.imread(str(folder / "rk3562_shadow_during_20261013.jpg"))
    gate = CalibrationStabilityGate(required_frames=2)
    for _ in range(3):
        gate.observe(before)
    assert gate.stable_frames == 2
    assert gate.capture_reason(before) is None
    assert gate.observe(shaded) == (True, None)
    assert gate.capture_reason(shaded) is None
