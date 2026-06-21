import threading

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


class ResultCalibrator:
    def __init__(self, result, **_kwargs):
        self.result = result

    def calibrate(self):
        return self.result


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
