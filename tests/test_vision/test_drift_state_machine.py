"""Task 5 (P12): rotation-aware drift detection + DriftStateMachine.

修订说明 #5: phaseCorrelate is translation-only; a pure rotation (the magnet detach/reattach
case) must still be flagged via an absolute-pose check.
修订说明 #6: on recalibration failure (ok=False / M=None) the machine must NOT update M, must
enter NEEDS_ATTENTION, and must pause captures; on success it re-baselines.
"""
import cv2
import numpy as np

from katrain.vision.calibration_strategy import CalibrationOutcome
from katrain.vision.drift_state_machine import DriftStateMachine, RotationAwareDrift, State


def _textured_frame():
    f = np.zeros((480, 640, 3), np.uint8)
    cv2.rectangle(f, (100, 80), (540, 400), (255, 255, 255), 3)
    cv2.line(f, (100, 240), (540, 240), (255, 255, 255), 2)
    return f


def _rot_homography(deg, center=(475, 475)):
    R = cv2.getRotationMatrix2D(center, deg, 1.0)
    return np.vstack([R, [0, 0, 1]]).astype(np.float64)


# --------------------------- RotationAwareDrift ----------------------------
def test_pure_rotation_is_flagged_even_with_zero_translation():
    ref = _textured_frame()
    det = RotationAwareDrift(
        ref, np.eye(3), cell_spacing_px=20.0, out_size=950,
        pose_fn=lambda frame: _rot_homography(5.0), threshold_cells=0.15, deg_threshold=1.0,
    )
    sig = det.update(ref)  # identical frame → translation ~0, but pose rotated 5deg
    assert sig.over_threshold is True
    assert sig.reason == "rotation"
    assert sig.deg > 1.0


def test_no_drift_when_pose_matches_reference():
    ref = _textured_frame()
    det = RotationAwareDrift(ref, np.eye(3), cell_spacing_px=20.0, pose_fn=lambda f: np.eye(3))
    sig = det.update(ref)
    assert sig.over_threshold is False


# --------------------------- DriftStateMachine -----------------------------
def _ok_outcome():
    M = _rot_homography(1.0)
    return CalibrationOutcome(ok=True, M=M, Minv=np.linalg.inv(M), confidence=0.9, strategy="outer_corner")


def _fail_outcome():
    return CalibrationOutcome(ok=False, strategy="outer_corner", reason="no_board_detected")


def test_sustained_drift_enters_moving_flicker_does_not():
    sm = DriftStateMachine(
        drift_fn=lambda f: True, motion_fn=lambda f: True, recalibrate_fn=lambda f: _ok_outcome(),
        enter_moving_frames=3, settle_frames=2,
    )
    sm.update(0)
    sm.update(0)
    assert sm.state is State.STABLE  # 2 < 3
    sm.update(0)
    assert sm.state is State.MOVING

    sm2 = DriftStateMachine(drift_fn=lambda f: f, motion_fn=lambda f: True, recalibrate_fn=lambda f: _ok_outcome(), enter_moving_frames=3)
    sm2.update(True)
    sm2.update(False)  # flicker resets streak
    sm2.update(True)
    assert sm2.state is State.STABLE


def test_settle_triggers_recalibrate_success_updates_M_and_rebaselines():
    rebaselined = {"n": 0}
    moving = {"v": True}
    sm = DriftStateMachine(
        drift_fn=lambda f: True,
        motion_fn=lambda f: moving["v"],
        recalibrate_fn=lambda f: _ok_outcome(),
        on_recalibrated=lambda f, M: rebaselined.__setitem__("n", rebaselined["n"] + 1),
        enter_moving_frames=1, settle_frames=2,
        initial_M=np.eye(3),
    )
    sm.update(0)  # drift → MOVING
    assert sm.state is State.MOVING and sm.capture_allowed is False
    moving["v"] = False
    sm.update(0)
    sm.update(0)  # 2 still frames → RECALIBRATE → ok → STABLE
    assert sm.state is State.STABLE and sm.capture_allowed is True
    assert not np.allclose(sm.M, np.eye(3))  # M updated
    assert rebaselined["n"] == 1


def test_recalibrate_failure_enters_needs_attention_keeps_M():
    moving = {"v": True}
    sm = DriftStateMachine(
        drift_fn=lambda f: True, motion_fn=lambda f: moving["v"], recalibrate_fn=lambda f: _fail_outcome(),
        enter_moving_frames=1, settle_frames=1, initial_M=np.eye(3),
    )
    sm.update(0)  # → MOVING
    moving["v"] = False
    sm.update(0)  # settle → RECALIBRATE → fail → NEEDS_ATTENTION
    assert sm.state is State.NEEDS_ATTENTION
    assert sm.capture_allowed is False
    assert np.allclose(sm.M, np.eye(3))  # M NOT updated on failure


def test_needs_attention_retries_on_settle():
    outcomes = [_fail_outcome(), _ok_outcome()]
    sm = DriftStateMachine(
        drift_fn=lambda f: True, motion_fn=lambda f: False, recalibrate_fn=lambda f: outcomes.pop(0),
        enter_moving_frames=1, settle_frames=1, initial_M=np.eye(3),
    )
    sm.update(0)  # → MOVING (drift, but motion False so settle too) ... drift→MOVING this frame
    sm.update(0)  # settle → recal fail → NEEDS_ATTENTION
    assert sm.state is State.NEEDS_ATTENTION
    sm.update(0)  # settle retry → ok → STABLE
    assert sm.state is State.STABLE
