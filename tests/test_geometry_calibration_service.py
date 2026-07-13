import threading

import numpy as np
import pytest

from katrain.vision.led_geometry_calibrator import CalibrationResult
from katrain.web.core.geometry_calibration_service import CalibrationBusy, GeometryCalibrationService
from tests.test_geometry_lock import _synth


class FakeLed:
    def __init__(self):
        self.clear_calls = 0

    def clear(self, *, strict=False):
        self.clear_calls += 1
        return {"ok": True, "shown_at": 1.0, "errors": []}

    def is_connected(self):
        return True


class FakeCapture:
    def is_connected(self):
        return True


class FreshFakeCapture(FakeCapture):
    def __init__(self, connected=True):
        self.connected = connected
        self.grab_calls = 0

    def is_connected(self):
        return self.connected

    def grab_fresh(self, settle_ms=0.0):
        self.grab_calls += 1
        return np.zeros((32, 32, 3), np.uint8), self.grab_calls, 1.0


class ResultCalibrator:
    def __init__(self, result, **_kwargs):
        self.result = result

    def calibrate(self):
        return self.result


class RecordingCalibrator:
    """Records 'calibrate' into a shared list so tests can assert ordering
    relative to the on_suspend/on_resume vision hooks."""

    def __init__(self, result, events, **_kwargs):
        self.result = result
        self.events = events

    def calibrate(self):
        self.events.append("calibrate")
        return self.result


class FakeDrift:
    def __init__(self, degraded, shift_cells=0.5, response=0.9):
        self.degraded = degraded
        self.shift_cells = shift_cells
        self.response = response


def test_success_atomically_promotes_new_lock(tmp_path):
    lock = _synth()
    promoted = []
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        on_success=promoted.append,
        calibrator_factory=lambda **kwargs: ResultCalibrator(CalibrationResult(ok=True, lock=lock), **kwargs),
    )

    service.start(trigger="auto", empty_confirmed=True)
    service.wait(timeout=2)

    status = service.status()
    assert status["phase"] == "ready"
    assert status["session_calibrated"] is True
    assert promoted == [lock]
    assert (tmp_path / "geometry.npz").exists()


def test_failure_preserves_last_valid_lock(tmp_path):
    old = _synth()
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        initial_lock=old,
        calibrator_factory=lambda **kwargs: ResultCalibrator(
            CalibrationResult(ok=False, reason="anchor_not_found:0,0"), **kwargs
        ),
    )

    service.start(trigger="manual", empty_confirmed=True)
    service.wait(timeout=2)

    status = service.status()
    assert status["phase"] == "failed"
    assert status["session_calibrated"] is False
    assert status["last_valid"] is True
    assert service.current_lock is old
    assert not (tmp_path / "geometry.npz").exists()


def test_vision_is_suspended_before_calibrate_and_resumed_after_success(tmp_path):
    # The RKNN worker burns ~1 core continuously (warp+CLAHE+detect). Recognising a board
    # that is being re-calibrated is pointless AND starves the calibration/status/UI, so the
    # worker must be suspended for the whole run and resumed after.
    events = []
    lock = _synth()
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        on_suspend=lambda: events.append("suspend"),
        on_resume=lambda: events.append("resume"),
        calibrator_factory=lambda **kwargs: RecordingCalibrator(
            CalibrationResult(ok=True, lock=lock), events, **kwargs
        ),
    )

    service.start(trigger="auto", empty_confirmed=True)
    service.wait(timeout=2)

    assert events == ["suspend", "calibrate", "resume"]
    assert service.status()["phase"] == "ready"


def test_vision_is_resumed_even_when_calibration_fails(tmp_path):
    # On failure/cancel the worker must be un-suspended so recognition resumes on the previous
    # lock — otherwise a failed recal leaves the box permanently blind.
    events = []
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        initial_lock=_synth(),
        on_suspend=lambda: events.append("suspend"),
        on_resume=lambda: events.append("resume"),
        calibrator_factory=lambda **kwargs: RecordingCalibrator(
            CalibrationResult(ok=False, reason="anchor_not_found:0,0"), events, **kwargs
        ),
    )

    service.start(trigger="manual", empty_confirmed=True)
    service.wait(timeout=2)

    assert events == ["suspend", "calibrate", "resume"]
    assert service.status()["phase"] == "failed"


def test_rejects_concurrent_start_and_cancel_clears_led(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    led = FakeLed()

    class BlockingCalibrator:
        def __init__(self, cancel_event, **_kwargs):
            self.cancel_event = cancel_event

        def calibrate(self):
            entered.set()
            release.wait(timeout=2)
            return CalibrationResult(ok=False, reason="cancelled" if self.cancel_event.is_set() else "failed")

    service = GeometryCalibrationService(
        led=led,
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=BlockingCalibrator,
    )
    service.start(trigger="auto", empty_confirmed=True)
    assert entered.wait(timeout=1)

    try:
        service.start(trigger="manual", empty_confirmed=True)
        raise AssertionError("expected CalibrationBusy")
    except CalibrationBusy:
        pass
    service.cancel()
    release.set()
    service.wait(timeout=2)

    assert service.status()["phase"] == "cancelled"
    assert led.clear_calls >= 1


def test_requires_explicit_empty_board_confirmation(tmp_path):
    service = GeometryCalibrationService(led=FakeLed(), capture=FakeCapture(), save_path=tmp_path / "g.npz")

    try:
        service.start(trigger="auto", empty_confirmed=False)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "empty" in str(exc)


def test_confirm_existing_promotes_loaded_lock_without_recalibration(tmp_path):
    old = _synth()
    promoted = []
    capture = FreshFakeCapture()
    save_path = tmp_path / "geometry.npz"
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=save_path,
        initial_lock=old,
        on_success=promoted.append,
    )

    status = service.confirm_existing()

    assert status["phase"] == "ready"
    assert status["session_calibrated"] is True
    assert status["capabilities"]["geometry_ready"] is True
    assert status["trigger"] == "operator_reuse"
    assert status["geometry_revision"] == 1
    assert promoted == [old]
    assert capture.grab_calls == 1
    assert service._drift_monitor is not None
    assert not save_path.exists()


def test_confirm_existing_recovers_from_failed_calibration_when_lock_is_valid(tmp_path):
    old = _synth()
    promoted = []
    capture = FreshFakeCapture()
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        initial_lock=old,
        on_success=promoted.append,
    )
    service._status["phase"] = "failed"
    service._status["error"] = "anchor_not_found:15,15"

    status = service.confirm_existing()

    assert status["phase"] == "ready"
    assert status["session_calibrated"] is True
    assert status["trigger"] == "operator_reuse"
    assert status["error"] is None
    assert promoted == [old]
    assert capture.grab_calls == 1


def test_confirm_existing_rejects_missing_lock(tmp_path):
    service = GeometryCalibrationService(led=FakeLed(), capture=FreshFakeCapture(), save_path=tmp_path / "geometry.npz")

    with pytest.raises(ValueError, match="no existing geometry"):
        service.confirm_existing()


def test_confirm_existing_rejects_disconnected_camera(tmp_path):
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FreshFakeCapture(connected=False),
        save_path=tmp_path / "geometry.npz",
        initial_lock=_synth(),
    )

    with pytest.raises(ValueError, match="camera is not ready"):
        service.confirm_existing()


def test_confirm_existing_cannot_override_degraded_state(tmp_path):
    service = GeometryCalibrationService(
        led=FakeLed(), capture=FreshFakeCapture(), save_path=tmp_path / "geometry.npz", initial_lock=_synth()
    )
    service._status["phase"] = "degraded"

    with pytest.raises(ValueError, match="only be confirmed after restart"):
        service.confirm_existing()
    assert service.status()["phase"] == "degraded"


def test_drift_degraded_invalidates_downstream_geometry(tmp_path):
    # Board bump mid-session must (a) flip to degraded AND (b) invalidate the vision worker,
    # else recognition keeps warping on the stale matrix and judges on a wrong grid.
    invalidated = []
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        initial_lock=_synth(),
        on_degraded=lambda: invalidated.append(True),
    )
    service._status["phase"] = "ready"

    service._apply_drift(FakeDrift(degraded=True))

    assert service.status()["phase"] == "degraded"
    assert service.status()["error"] == "board_moved"
    assert invalidated == [True]
    service.stop()


def test_drift_below_threshold_is_noop(tmp_path):
    invalidated = []
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        initial_lock=_synth(),
        on_degraded=lambda: invalidated.append(True),
    )
    service._status["phase"] = "ready"

    service._apply_drift(FakeDrift(degraded=False))

    assert service.status()["phase"] == "ready"
    assert invalidated == []
    service.stop()


def test_confirm_existing_promotes_without_led(tmp_path):
    # No-LED config: a persisted lock must still be promotable (recognition_ready otherwise
    # sticks false forever, and confirm-existing 404s, stranding physical tsumego).
    old = _synth()
    promoted = []
    service = GeometryCalibrationService(
        led=None,
        capture=FreshFakeCapture(),
        save_path=tmp_path / "geometry.npz",
        initial_lock=old,
        on_success=promoted.append,
    )

    status = service.confirm_existing()

    assert status["phase"] == "ready"
    assert status["session_calibrated"] is True
    assert status["capabilities"]["geometry_ready"] is True
    assert promoted == [old]
    service.stop()  # must not crash with led=None


def test_calibration_requires_led(tmp_path):
    service = GeometryCalibrationService(led=None, capture=FreshFakeCapture(), save_path=tmp_path / "geometry.npz")

    with pytest.raises(ValueError, match="LED is required"):
        service.start(trigger="manual", empty_confirmed=True)
    service.stop()  # cancel() must tolerate led=None


def test_status_publishes_anchor_snapshot_and_resets_it_on_new_start(tmp_path):
    lock = _synth()
    entered_second = threading.Event()
    release_second = threading.Event()
    calls = 0

    class ObservingCalibrator:
        def __init__(self, anchor_observer, **_kwargs):
            nonlocal calls
            calls += 1
            self.call = calls
            self.anchor_observer = anchor_observer

        def calibrate(self):
            if self.call == 1:
                self.anchor_observer(0, 0, (12.5, 34.5), "green")
                return CalibrationResult(ok=True, lock=lock)
            entered_second.set()
            release_second.wait(timeout=2)
            return CalibrationResult(ok=False, reason="stopped")

    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FakeCapture(),
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=ObservingCalibrator,
    )

    service.start(trigger="manual", empty_confirmed=True)
    service.wait(timeout=2)
    first = service.status()
    assert first["detected_anchors"] == [{"row": 0, "col": 0, "x": 12.5, "y": 34.5, "color": "green"}]
    assert first["geometry_revision"] == 1

    service.start(trigger="manual", empty_confirmed=True)
    assert entered_second.wait(timeout=1)
    second = service.status()
    assert second["detected_anchors"] == []
    assert second["geometry_revision"] == 1

    release_second.set()
    service.wait(timeout=2)
