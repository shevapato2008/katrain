import logging
import re
import threading
from pathlib import Path

import numpy as np
import pytest

from katrain.vision.led_geometry_calibrator import CalibrationResult, check_frame_exposure
from katrain.web.core.geometry_calibration_service import (
    CAMERA_AUTO_EXPOSURE_OFF,
    CAMERA_AUTO_EXPOSURE_ON,
    CalibrationBusy,
    GeometryCalibrationService,
)
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


def test_success_persists_geometry_and_verified_manual_controls_together(tmp_path):
    lock = _synth()
    persisted = []

    def persist_state(geometry, auto_exposure, exposure, before_publish):
        before_publish()
        persisted.append((geometry, auto_exposure, exposure))

    class ManualCapture(FakeCapture):
        current_auto_exposure = CAMERA_AUTO_EXPOSURE_OFF
        current_exposure = 321.0

    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=ManualCapture(),
        save_path=tmp_path / "unused.npz",
        persist_state=persist_state,
        calibrator_factory=lambda **kwargs: ResultCalibrator(CalibrationResult(ok=True, lock=lock), **kwargs),
    )

    service.start(trigger="manual", empty_confirmed=True)
    service.wait(timeout=2)

    assert service.status()["phase"] == "ready"
    assert persisted == [(lock, CAMERA_AUTO_EXPOSURE_OFF, 321.0)]
    assert not (tmp_path / "unused.npz").exists()


@pytest.mark.parametrize(
    ("auto_exposure", "exposure"),
    [(CAMERA_AUTO_EXPOSURE_ON, 321.0), (CAMERA_AUTO_EXPOSURE_OFF, float("nan")), (None, 321.0)],
)
def test_success_refuses_to_persist_unverified_camera_controls(tmp_path, auto_exposure, exposure):
    lock = _synth()
    persisted = []

    class InvalidCapture(FakeCapture):
        current_auto_exposure = auto_exposure
        current_exposure = exposure

    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=InvalidCapture(),
        save_path=tmp_path / "unused.npz",
        persist_state=lambda *args: persisted.append(args),
        calibrator_factory=lambda **kwargs: ResultCalibrator(CalibrationResult(ok=True, lock=lock), **kwargs),
    )

    service.start(trigger="manual", empty_confirmed=True)
    service.wait(timeout=2)

    assert service.status()["phase"] == "failed"
    assert persisted == []
    assert service.current_lock is None


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


def test_failed_calibration_keeps_attempts_in_metrics():
    """失败时 attempts 必须留在 status 里 —— 它是唯一能分辨 low_signal /
    ambiguous_blobs / show_failed 的东西(见 spec §2.3)。"""
    led, capture = FakeLed(), FreshFakeCapture()
    attempts = (
        {
            "row": 0,
            "col": 0,
            "color": "green",
            "ok": False,
            "peak": 8.1,
            "area": 0,
            "margin": None,
            "reason": "low_signal",
        },
    )

    class FailingCalibrator:
        def __init__(self, **_kwargs):
            pass

        def calibrate(self):
            return CalibrationResult(ok=False, reason="anchor_not_found:0,0", attempts=attempts)

    service = GeometryCalibrationService(
        led=led,
        capture=capture,
        calibrator_factory=FailingCalibrator,
        save_path="/tmp/unused.npz",
    )
    service.start(trigger="manual", empty_confirmed=True)
    service.wait(5)

    status = service.status()
    assert status["phase"] == "failed"
    assert status["error"] == "anchor_not_found:0,0"
    assert status["metrics"]["attempts"] == [dict(attempts[0])]


def test_exposure_gate_stats_land_in_metrics_exposure_not_attempts():
    """闸拒绝时 metrics 里要有 exposure(供界面说清「摄像头没适应光线」),
    而 attempts 必须是空的 —— 消费方拿 attempts 的长度当真值判断。"""
    stats = {"median": 253.0, "clip_frac": 0.61, "shadow_frac": 0.0}

    class GatedCalibrator:
        def __init__(self, **_kwargs):
            pass

        def calibrate(self):
            return CalibrationResult(ok=False, reason="frame_overexposed", attempts=(), exposure_stats=stats)

    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=FreshFakeCapture(),
        save_path="/tmp/unused.npz",
        calibrator_factory=GatedCalibrator,
    )
    service.start(trigger="manual", empty_confirmed=True)
    service.wait(5)

    status = service.status()
    assert status["phase"] == "failed"
    assert status["error"] == "frame_overexposed"
    assert status["metrics"]["exposure"] == stats
    assert status["metrics"]["attempts"] == []
    service.stop()


class FakeAutoExposureCapture(FakeCapture):
    """CameraHub 形状的假相机:曝光冻在开机那一刻的过曝值(spec §2.2 白天整帧 254),
    只有硬件 AE 被打开之后才回到带内。

    `converges=False` 模拟怎么调都回不来的相机(逆光/白纸打爆)。
    关回手动**不改变**已经收敛出来的曝光 —— 这是 V4L2 的常规行为,也是本方案的
    前提假设,待板上核实(假设不成立时不会假绿:曝光闸会重新量整帧并如实拒绝)。
    """

    def __init__(self, *, converges=True, initial_level=254, manual_lock_succeeds=True, events=None):
        self.events = events if events is not None else []
        self.converges = converges
        self.initial_level = initial_level
        self.manual_lock_succeeds = manual_lock_succeeds
        self.control_calls = []
        self.grab_calls = 0
        self._auto_on = False
        self.controls_effective = None

    def is_connected(self):
        return True

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        self.grab_calls += 1
        level = 150 if (self._auto_on and self.converges) else self.initial_level
        self.events.append(("grab", level))
        return np.full((64, 64, 3), level, np.uint8), self.grab_calls, float(self.grab_calls)

    def request_controls(self, exposure=None, auto_exposure=None):
        self.control_calls.append((exposure, auto_exposure))
        self.events.append(("controls", auto_exposure))
        if auto_exposure is not None and auto_exposure >= CAMERA_AUTO_EXPOSURE_ON:
            self._auto_on = True
            self.controls_effective = True
        elif auto_exposure == CAMERA_AUTO_EXPOSURE_OFF:
            self.controls_effective = self.manual_lock_succeeds


class RestoringFakeCapture(FakeCapture):
    """CaptureService-shaped fake with asynchronous control readback."""

    def __init__(
        self,
        *,
        current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF,
        current_exposure=320.0,
        initial_level=150,
        restore_succeeds=True,
    ):
        self.current_auto_exposure = current_auto_exposure
        self.current_exposure = current_exposure
        self.initial_exposure = current_exposure
        self.initial_level = initial_level
        self.restore_succeeds = restore_succeeds
        self.controls_effective = True
        self.control_calls = []
        self.grab_calls = 0
        self._pending_controls = None

    def is_connected(self):
        return True

    def request_controls(self, exposure=None, auto_exposure=None):
        self.control_calls.append((exposure, auto_exposure))
        self._pending_controls = (exposure, auto_exposure)
        self.controls_effective = None

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        self.grab_calls += 1
        if self._pending_controls is not None:
            exposure, auto_exposure = self._pending_controls
            self._pending_controls = None
            is_restore = exposure == self.initial_exposure and auto_exposure == CAMERA_AUTO_EXPOSURE_OFF
            if is_restore and not self.restore_succeeds:
                self.controls_effective = False
            else:
                if auto_exposure is not None:
                    self.current_auto_exposure = auto_exposure
                if exposure is not None:
                    self.current_exposure = exposure
                elif auto_exposure == CAMERA_AUTO_EXPOSURE_ON:
                    self.current_exposure = 140.0
                self.controls_effective = True
        level = 150 if self.current_auto_exposure == CAMERA_AUTO_EXPOSURE_ON else self.initial_level
        return np.full((64, 64, 3), level, np.uint8), self.grab_calls, float(self.grab_calls)


def _stopped_calibrator_factory(events):
    return lambda **kwargs: RecordingCalibrator(CalibrationResult(ok=False, reason="stopped"), events, **kwargs)


def _result_calibrator_factory(result):
    return lambda **kwargs: ResultCalibrator(result, **kwargs)


def test_failed_calibration_restores_original_manual_exposure(tmp_path):
    capture = RestoringFakeCapture(current_auto_exposure=1.005, current_exposure=320.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="anchor_not_found:0,0")),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["error"] == "anchor_not_found:0,0"
    assert capture.control_calls[-1] == (320.0, CAMERA_AUTO_EXPOSURE_OFF)
    assert capture.current_auto_exposure == CAMERA_AUTO_EXPOSURE_OFF
    assert capture.current_exposure == 320.0
    service.stop()


def test_cancelled_calibration_restores_original_exposure(tmp_path):
    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=321.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="cancelled")),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "cancelled"
    assert capture.control_calls[-1] == (321.0, CAMERA_AUTO_EXPOSURE_OFF)
    service.stop()


def test_calibrator_exception_restores_original_exposure(tmp_path):
    class ExplodingCalibrator:
        def __init__(self, **_kwargs):
            pass

        def calibrate(self):
            raise RuntimeError("calibrator exploded")

    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=322.0)
    service = GeometryCalibrationService(
        led=FakeLed(), capture=capture, save_path=tmp_path / "geometry.npz", calibrator_factory=ExplodingCalibrator
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["error"] == "calibrator exploded"
    assert capture.control_calls[-1] == (322.0, CAMERA_AUTO_EXPOSURE_OFF)
    service.stop()


def test_success_keeps_new_manual_exposure(tmp_path):
    capture = RestoringFakeCapture(
        current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=320.0, initial_level=254
    )
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=_synth())),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "ready"
    assert capture.control_calls == [
        (None, CAMERA_AUTO_EXPOSURE_ON),
        (None, CAMERA_AUTO_EXPOSURE_OFF),
    ]
    assert capture.current_auto_exposure == CAMERA_AUTO_EXPOSURE_OFF
    assert capture.current_exposure == 140.0
    service.stop()


def test_failed_calibration_restores_original_hardware_auto_mode_only(tmp_path):
    capture = RestoringFakeCapture(current_auto_exposure=3.005, current_exposure=323.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="stopped")),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert capture.control_calls[-1] == (None, CAMERA_AUTO_EXPOSURE_ON)
    assert capture.current_auto_exposure == CAMERA_AUTO_EXPOSURE_ON
    service.stop()


@pytest.mark.parametrize(
    ("auto_exposure", "exposure"),
    [(2.0, 320.0), (float("nan"), 320.0), (CAMERA_AUTO_EXPOSURE_OFF, float("nan"))],
)
def test_invalid_or_unknown_exposure_snapshot_is_not_restored(tmp_path, auto_exposure, exposure):
    capture = RestoringFakeCapture(current_auto_exposure=auto_exposure, current_exposure=exposure)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="stopped")),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert capture.control_calls == [(None, CAMERA_AUTO_EXPOSURE_OFF)]
    service.stop()


def test_restore_readback_failure_preserves_calibration_failure(tmp_path, caplog):
    capture = RestoringFakeCapture(
        current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF,
        current_exposure=324.0,
        restore_succeeds=False,
    )
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="original failure")),
    )

    with caplog.at_level(logging.WARNING, logger="katrain.web.core.geometry_calibration_service"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "failed"
    assert service.status()["error"] == "original failure"
    assert any("restore" in record.getMessage() for record in caplog.records)
    service.stop()


@pytest.mark.parametrize(
    ("competing_auto_exposure", "competing_exposure"),
    [(CAMERA_AUTO_EXPOSURE_ON, 327.0), (CAMERA_AUTO_EXPOSURE_OFF, 999.0)],
)
def test_restore_rejects_success_readback_for_competing_control_request(
    tmp_path, caplog, competing_auto_exposure, competing_exposure
):
    class CompetingControlCapture(RestoringFakeCapture):
        def grab_fresh(self, after_ts=None, settle_ms=150.0):
            result = super().grab_fresh(after_ts=after_ts, settle_ms=settle_ms)
            if self.control_calls and self.control_calls[-1] == (327.0, CAMERA_AUTO_EXPOSURE_OFF):
                self.current_auto_exposure = competing_auto_exposure
                self.current_exposure = competing_exposure
                self.controls_effective = True
            return result

    capture = CompetingControlCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=327.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=False, reason="original failure")),
    )

    with caplog.at_level(logging.WARNING, logger="katrain.web.core.geometry_calibration_service"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True

    assert service.status()["error"] == "original failure"
    assert any("restore readback failed" in record.getMessage() for record in caplog.records)
    service.stop()


def test_cancel_before_store_pointer_swap_keeps_old_generation_and_restores_exposure(tmp_path):
    from katrain.web.core.hardware_vision_state import CameraProfile, HardwareVisionStateStore

    store = HardwareVisionStateStore(tmp_path / "hardware-vision")
    old_lock = _synth()
    old_lock.source_width = 640
    old_lock.source_height = 480
    new_lock = _synth()
    new_lock.source_width = 640
    new_lock.source_height = 480
    store.commit(
        old_lock,
        CameraProfile(camera_device="/dev/video73", width=640, height=480, auto_exposure=1.0, exposure=100.0),
        generation="old",
    )
    entered = threading.Event()
    release = threading.Event()
    promoted = []

    def persist_state(lock, auto_exposure, exposure, before_publish):
        profile = CameraProfile(
            camera_device="/dev/video73",
            width=640,
            height=480,
            auto_exposure=auto_exposure,
            exposure=exposure,
        )

        def blocking_before_publish():
            entered.set()
            release.wait(timeout=2)
            before_publish()

        store.commit(lock, profile, generation="new", before_publish=blocking_before_publish)

    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=328.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        persist_state=persist_state,
        initial_lock=old_lock,
        on_success=promoted.append,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=new_lock)),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert entered.wait(timeout=1) is True
    service.cancel()
    release.set()
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "cancelled"
    assert service.current_lock is old_lock
    assert promoted == []
    assert capture.control_calls[-1] == (328.0, CAMERA_AUTO_EXPOSURE_OFF)
    current = store.load_current("/dev/video73", 640, 480)
    assert current is not None
    assert current.generation == "old"
    assert current.profile.exposure == 100.0
    np.testing.assert_array_equal(current.geometry.baseline, old_lock.baseline)
    assert (tmp_path / "hardware-vision" / "generations" / "new").is_dir()
    service.stop()


def test_cancel_after_store_publish_boundary_does_not_abort_commit(tmp_path):
    from katrain.web.core.hardware_vision_state import CameraProfile, HardwareVisionStateStore

    store = HardwareVisionStateStore(tmp_path / "hardware-vision")
    old_lock = _synth()
    old_lock.source_width = 640
    old_lock.source_height = 480
    new_lock = _synth()
    new_lock.source_width = 640
    new_lock.source_height = 480
    store.commit(
        old_lock,
        CameraProfile(camera_device="/dev/video73", width=640, height=480, auto_exposure=1.0, exposure=100.0),
        generation="old",
    )
    boundary_started = threading.Event()
    release = threading.Event()

    def persist_state(lock, auto_exposure, exposure, before_publish):
        profile = CameraProfile(
            camera_device="/dev/video73",
            width=640,
            height=480,
            auto_exposure=auto_exposure,
            exposure=exposure,
        )

        def blocking_before_publish():
            before_publish()
            boundary_started.set()
            release.wait(timeout=2)

        store.commit(lock, profile, generation="new", before_publish=blocking_before_publish)

    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=331.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        persist_state=persist_state,
        initial_lock=old_lock,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=new_lock)),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert boundary_started.wait(timeout=1) is True
    service.cancel()
    assert service._cancel_event.is_set() is False
    release.set()
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "ready"
    assert service.current_lock is new_lock
    assert capture.current_exposure == 331.0
    current = store.load_current("/dev/video73", 640, 480)
    assert current is not None
    assert current.generation == "new"
    assert current.profile.exposure == 331.0
    np.testing.assert_array_equal(current.geometry.baseline, new_lock.baseline)
    service.stop()


def test_cancel_during_legacy_staging_preserves_old_file_and_restores_exposure(tmp_path, monkeypatch):
    import katrain.web.core.geometry_calibration_service as calibration_module
    from katrain.vision.geometry_lock import load_geometry_lock, save_geometry_lock

    old_lock = _synth()
    new_lock = _synth()
    entered = threading.Event()
    release = threading.Event()
    promoted = []
    save_path = tmp_path / "geometry.npz"
    save_geometry_lock(old_lock, save_path)
    real_save = calibration_module.save_geometry_lock

    def blocking_save(lock, path):
        real_save(lock, path)
        entered.set()
        release.wait(timeout=2)

    monkeypatch.setattr(calibration_module, "save_geometry_lock", blocking_save)
    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=329.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=save_path,
        initial_lock=old_lock,
        on_success=promoted.append,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=new_lock)),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert entered.wait(timeout=1) is True
    service.cancel()
    release.set()
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "cancelled"
    assert service.current_lock is old_lock
    assert promoted == []
    assert capture.control_calls[-1] == (329.0, CAMERA_AUTO_EXPOSURE_OFF)
    persisted = load_geometry_lock(save_path)
    np.testing.assert_array_equal(persisted.baseline, old_lock.baseline)
    assert persisted.confidence == old_lock.confidence
    service.stop()


def test_drift_setup_failure_happens_before_persist_and_promotion(tmp_path):
    class DriftSetupFailureCapture(RestoringFakeCapture):
        def grab_fresh(self, after_ts=None, settle_ms=150.0):
            if self.grab_calls == 2 and self._pending_controls is None:
                self.grab_calls += 1
                raise RuntimeError("drift setup failed")
            return super().grab_fresh(after_ts=after_ts, settle_ms=settle_ms)

    old_lock = _synth()
    persisted = []
    promoted = []
    capture = DriftSetupFailureCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=330.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        persist_state=lambda *args: persisted.append(args),
        initial_lock=old_lock,
        on_success=promoted.append,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=_synth())),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "failed"
    assert service.status()["error"] == "drift setup failed"
    assert persisted == []
    assert service.current_lock is old_lock
    assert promoted == []
    assert capture.control_calls[-1] == (330.0, CAMERA_AUTO_EXPOSURE_OFF)
    service.stop()


def test_save_failure_restores_original_exposure(tmp_path, monkeypatch):
    def fail_save(_lock, _path):
        raise OSError("disk full")

    monkeypatch.setattr("katrain.web.core.geometry_calibration_service.save_geometry_lock", fail_save)
    capture = RestoringFakeCapture(current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF, current_exposure=325.0)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path=tmp_path / "geometry.npz",
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=_synth())),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert service.status()["error"] == "disk full"
    assert capture.control_calls[-1] == (325.0, CAMERA_AUTO_EXPOSURE_OFF)
    service.stop()


def test_on_success_failure_after_durable_commit_stays_ready_and_keeps_new_exposure(tmp_path, caplog):
    from katrain.web.core.hardware_vision_state import CameraProfile, HardwareVisionStateStore

    store = HardwareVisionStateStore(tmp_path / "hardware-vision")
    old_lock = _synth()
    old_lock.source_width = 640
    old_lock.source_height = 480
    new_lock = _synth()
    new_lock.source_width = 640
    new_lock.source_height = 480
    store.commit(
        old_lock,
        CameraProfile(camera_device="/dev/video73", width=640, height=480, auto_exposure=1.0, exposure=326.0),
        generation="old",
    )
    observed = []

    def persist_state(lock, auto_exposure, exposure, before_publish):
        store.commit(
            lock,
            CameraProfile(
                camera_device="/dev/video73",
                width=640,
                height=480,
                auto_exposure=auto_exposure,
                exposure=exposure,
            ),
            generation="new",
            before_publish=before_publish,
        )

    def fail_promotion(lock):
        observed.append((service.current_lock, service.status()["phase"], capture.current_exposure, lock))
        raise RuntimeError("promotion failed")

    capture = RestoringFakeCapture(
        current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF,
        current_exposure=326.0,
        initial_level=254,
    )
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        persist_state=persist_state,
        initial_lock=old_lock,
        on_success=fail_promotion,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=new_lock)),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    with caplog.at_level(logging.WARNING, logger="katrain.web.core.geometry_calibration_service"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "ready"
    assert service.status()["error"] is None
    assert service.current_lock is new_lock
    assert service._drift_monitor is not None
    assert capture.current_auto_exposure == CAMERA_AUTO_EXPOSURE_OFF
    assert capture.current_exposure == 140.0
    assert observed == [(new_lock, "ready", 140.0, new_lock)]
    assert any("on_success failed" in record.getMessage() for record in caplog.records)
    current = store.load_current("/dev/video73", 640, 480)
    assert current is not None
    assert current.generation == "new"
    assert current.profile.exposure == 140.0
    np.testing.assert_array_equal(current.geometry.baseline, new_lock.baseline)
    service.stop()


def test_post_pointer_fsync_failure_keeps_store_service_and_exposure_committed(tmp_path, monkeypatch, caplog):
    import katrain.web.core.hardware_vision_state as state_module

    store = state_module.HardwareVisionStateStore(tmp_path / "hardware-vision")
    old_lock = _synth()
    old_lock.source_width = 640
    old_lock.source_height = 480
    new_lock = _synth()
    new_lock.source_width = 640
    new_lock.source_height = 480
    store.commit(
        old_lock,
        state_module.CameraProfile(
            camera_device="/dev/video73", width=640, height=480, auto_exposure=1.0, exposure=326.0
        ),
        generation="old",
    )
    real_fsync_directory = state_module._fsync_directory

    def fail_root_fsync_after_pointer_swap(path):
        if Path(path) == store.root and store.current_path.exists():
            raise OSError("injected root directory fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(state_module, "_fsync_directory", fail_root_fsync_after_pointer_swap)

    def persist_state(lock, auto_exposure, exposure, before_publish):
        store.commit(
            lock,
            state_module.CameraProfile(
                camera_device="/dev/video73",
                width=640,
                height=480,
                auto_exposure=auto_exposure,
                exposure=exposure,
            ),
            generation="new",
            before_publish=before_publish,
        )

    capture = RestoringFakeCapture(
        current_auto_exposure=CAMERA_AUTO_EXPOSURE_OFF,
        current_exposure=326.0,
        initial_level=254,
    )
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        persist_state=persist_state,
        initial_lock=old_lock,
        calibrator_factory=_result_calibrator_factory(CalibrationResult(ok=True, lock=new_lock)),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    with caplog.at_level(logging.WARNING, logger="katrain.web.core.hardware_vision_state"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True

    assert service.status()["phase"] == "ready"
    assert service.current_lock is new_lock
    assert capture.current_auto_exposure == CAMERA_AUTO_EXPOSURE_OFF
    assert capture.current_exposure == 140.0
    current = store.load_current("/dev/video73", 640, 480)
    assert current is not None
    assert current.generation == "new"
    assert current.profile.exposure == 140.0
    np.testing.assert_array_equal(current.geometry.baseline, new_lock.baseline)
    assert any("pointer published" in record.getMessage() for record in caplog.records)
    service.stop()


def test_in_band_exposure_is_still_locked_to_manual_before_calibration():
    events = []
    capture = FakeAutoExposureCapture(initial_level=150, events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert capture.control_calls == [(None, CAMERA_AUTO_EXPOSURE_OFF)]
    assert events.index(("controls", CAMERA_AUTO_EXPOSURE_OFF)) < events.index("calibrate")
    service.stop()


def test_calibration_stops_when_manual_exposure_readback_fails():
    events = []
    capture = FakeAutoExposureCapture(initial_level=150, manual_lock_succeeds=False, events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    status = service.status()
    assert status["phase"] == "failed"
    assert status["error"] == "manual exposure lock readback failed"
    assert "calibrate" not in events
    service.stop()


def test_manual_exposure_readback_waits_for_the_reader_thread():
    events = []

    class DelayedReadbackCapture(FakeAutoExposureCapture):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._readback_frames_remaining = 0

        def request_controls(self, exposure=None, auto_exposure=None):
            super().request_controls(exposure=exposure, auto_exposure=auto_exposure)
            if auto_exposure == CAMERA_AUTO_EXPOSURE_OFF:
                self.controls_effective = None
                self._readback_frames_remaining = 2

        def grab_fresh(self, after_ts=None, settle_ms=150.0):
            result = super().grab_fresh(after_ts=after_ts, settle_ms=settle_ms)
            if self._readback_frames_remaining:
                self._readback_frames_remaining -= 1
                if self._readback_frames_remaining == 0:
                    self.controls_effective = True
            return result

    capture = DelayedReadbackCapture(initial_level=150, events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert "calibrate" in events
    assert capture.grab_calls == 3  # initial meter + two frames before readback arrived
    service.stop()


def test_exposure_is_actuated_before_calibration_when_there_is_no_geometry_lock():
    """无几何锁时软件 AE 那条线整条不可达(worker `_warp_frame` 返回 (None, False)
    ⇒ `_run_ae` 一次都进不去),曝光停在开机那一刻。「棋盘被挪了、请重新标定」之后
    正好是这个状态,所以标定入口必须自己作动一次,否则白天标定永远停在曝光闸上。"""
    events = []
    capture = FakeAutoExposureCapture(events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    assert capture.control_calls, "过曝态下 request_controls 一次都没被调用 —— 曝光还是冻着的"
    assert any(auto == CAMERA_AUTO_EXPOSURE_ON for _exp, auto in capture.control_calls)
    # spec §2.1 实测:exposure_auto_priority=0 把积分时间钳在帧周期内,exposure_absolute
    # 只调得下、调不上(166→10000 无效)。往「更亮」的方向只能靠硬件 AE。
    assert all(exp is None for exp, _auto in capture.control_calls), (
        f"不许用 exposure_absolute 调亮(实测无效),实际: {capture.control_calls}"
    )
    service.stop()


def test_exposure_convergence_is_bounded_when_the_camera_never_comes_back(caplog):
    """收不回来的相机不许把标定卡死:收敛在上限内退出,标定照样往下走,
    最后由曝光闸诚实拒绝(而不是界面永远停在 waiting_empty)。"""
    events = []
    capture = FakeAutoExposureCapture(converges=False, events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    with caplog.at_level(logging.INFO, logger="katrain.web.core.geometry_calibration_service"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True, "收敛循环没有上限 —— 标定线程挂住了"
    assert "calibrate" in events, "收敛失败之后必须继续跑标定,不能就地返回失败"
    assert service.status()["phase"] == "failed"
    # 字面上限(**故意**不拿被测常量当期望值,否则把上限改大这条断言会跟着变松,
    # 就抓不到「压根没有上限」了)。当前预算是 1 次初测 + 20 次轮询 + 1 次交接后复测
    # = 22;取 30 留点余量。抬 MAX_STEPS 时这个数要跟着人工确认一次,这是刻意的摩擦。
    assert capture.grab_calls <= 30, f"取帧次数没有封顶: {capture.grab_calls}"

    # 撞上限退出 = 带着**没收敛完的曝光**继续往下跑。这条路不该静默:级别必须是
    # warning,而且要说清撞的是上限。
    handover = [r for r in caplog.records if "-> manual, median now" in r.getMessage()]
    assert len(handover) == 1, f"交接那行日志没有出现: {[r.getMessage() for r in caplog.records]}"
    message = handover[0].getMessage()
    assert handover[0].levelno == logging.WARNING, f"撞上限却只是 info: {message}"
    assert "capped=True" in message, message
    assert "outcome=max_steps" in message, message
    # 钉的是关系式「真的走到上限了」,不是某个具体数 —— 上限改成别的值这条照样成立。
    cap = service.EXPOSURE_CONVERGE_MAX_STEPS
    assert f"steps={cap}/{cap}" in message, message
    service.stop()


def test_exposure_gate_probe_is_taken_after_convergence_not_before():
    """顺序判据:T3 的曝光闸探针必须取在收敛**之后**。

    两者都发生过证明不了什么 —— 顺序反了的话闸量到的还是开机冻住的那一帧,
    标定在自己的门口被拒。这里跑的是生产的 check_frame_exposure,不自写判据。"""
    events = []
    capture = FakeAutoExposureCapture(events=events)

    class GateProbingCalibrator:
        """复刻 LedGeometryCalibrator.calibrate() 开头那几行的真实形状。"""

        def __init__(self, capture, **_kwargs):
            self.capture = capture

        def calibrate(self):
            probe, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
            ok, reason, stats = check_frame_exposure(probe)
            events.append(("gate", ok))
            if not ok:
                return CalibrationResult(ok=False, reason=reason, exposure_stats=stats)
            return CalibrationResult(ok=False, reason="stopped")

    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=GateProbingCalibrator,
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    gate_index = events.index(("gate", True))  # 闸没过就根本没有这一项 ⇒ 直接 ValueError
    control_indices = [i for i, event in enumerate(events) if event[0] == "controls"]
    assert control_indices, "一次都没作动曝光"
    assert max(control_indices) < gate_index, f"曝光闸的探针取在收敛之前了: {events}"
    assert service.status()["error"] != "frame_overexposed"
    service.stop()


def test_converge_logs_both_medians_across_the_manual_handover(caplog):
    """交接前后各量一次,两个 median 并排写进 journal。

    「关回手动时驱动保不保留 AE 收敛值」本机验不了,也没有实时回读曝光值的口
    (controls_effective 是 bool,initial_exposure 是 open() 那一刻的读数)。
    两个数并排就把这条板上事实从「要专门安排一次测量」变成「跑一次标定读一行 journal」:
    接近 ⇒ 保留了;后一个跳回高位 ⇒ 弹回 default 的指纹。
    不为「弹回」造场景 —— 那是驱动行为,本机造出来的也是假的。"""
    events = []
    capture = FakeAutoExposureCapture(events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    with caplog.at_level(logging.INFO, logger="katrain.web.core.geometry_calibration_service"):
        service.start(trigger="manual", empty_confirmed=True)
        assert service.wait(timeout=5) is True

    lines = [record.getMessage() for record in caplog.records]
    handover = [line for line in lines if "-> manual, median now" in line]
    assert len(handover) == 1, f"交接那行日志没有出现(或出现多次): {lines}"
    # 两个数都要真的印出来,而且都要是数 —— 只有一个数的话看不出「弹没弹回去」。
    numbers = [int(n) for n in re.findall(r"median (?:now )?(\d+)", handover[0])]
    assert len(numbers) == 2, f"这行要并排写两个 median,实际: {handover[0]}"
    assert all(120 <= number <= 170 for number in numbers), handover[0]
    # 顺利收敛这条路:级别是 info,而且要说清走了几步 —— 这两个数是用来核实
    # POLL_S/MAX_STEPS 那个 6 秒上限拍得对不对的(本机拍的,板上跑一次就知道)。
    record = next(r for r in caplog.records if "-> manual, median now" in r.getMessage())
    assert record.levelno == logging.INFO, f"顺利收敛却报了 warning: {handover[0]}"
    assert "capped=False" in handover[0], handover[0]
    assert "outcome=converged" in handover[0], handover[0]
    # 这个假相机开了硬件 AE 之后下一帧就在带内 ⇒ 第一步就该收敛。
    assert f"steps=1/{service.EXPOSURE_CONVERGE_MAX_STEPS}" in handover[0], handover[0]
    # 顺序:先有收敛开始那行,再有交接这行。
    assert lines.index(handover[0]) > next(i for i, line in enumerate(lines) if "converge: start" in line)
    # 后一个数必须来自**交接之后的一次真取帧**。光看日志里有两个数分不出「重新量了」
    # 和「把同一次的 stats 印了两遍」—— 后者永远相等,弹没弹回去照样看不出来。
    restore = max(i for i, e in enumerate(events) if e[0] == "controls" and e[1] == CAMERA_AUTO_EXPOSURE_OFF)
    assert any(e[0] == "grab" for e in events[restore + 1:]), (
        f"关回手动之后一帧都没再量 —— 两个数会是同一次测量: {events}"
    )
    service.stop()


def test_hardware_ae_is_handed_back_to_manual_even_when_convergence_raises():
    """收敛中途抛异常时,硬件 AE 不许被留在开着的状态。

    这条异常路径**不是让本次标定失败,是让下一次标定悄悄地测错**:锚点定位是差分测量
    (lit - dark),AE 连续作动会让同一颗锚点的 dark 帧和 lit 帧落在两个不同曝光上,
    污染整条链上唯一的信号来源。本次失败是响的(phase=failed),下一次测错是哑的。

    两条都要:只断言 ① 的话,一个「捕获并吞掉异常」的实现照样能过 —— 而吞掉异常会把
    一次真实的相机故障伪装成一次普通的标定失败。"""
    events = []

    class ExplodingCapture(FakeAutoExposureCapture):
        """在 AE 已经打开、正要量收敛结果的那一刻炸 —— 正好落在 ON 与 OFF 之间。

        **只炸一次**(之后恢复正常)。这一点是判据的一部分,不是省事:一直炸的话,
        「吞掉异常」的实现会在关回手动之后取 settled 那一帧时**再炸一次**,新异常照样
        进到 status 里,断言 ② 就会因为一个错误的理由变绿 —— 变异实测撞到过。
        只炸一次,吞掉异常的实现就会一路跑到底,status 里留下的是 "stopped"。"""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.explosions = 0

        def grab_fresh(self, after_ts=None, settle_ms=150.0):
            if self._auto_on and not self.explosions:
                self.explosions += 1
                raise RuntimeError("camera exploded mid-convergence")
            return super().grab_fresh(after_ts=after_ts, settle_ms=settle_ms)

    capture = ExplodingCapture(events=events)
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture,
        save_path="/tmp/unused.npz",
        calibrator_factory=_stopped_calibrator_factory(events),
    )
    service.EXPOSURE_CONVERGE_POLL_S = 0.0

    service.start(trigger="manual", empty_confirmed=True)
    assert service.wait(timeout=5) is True

    # ① AE 关回手动了 —— 不是停在 3.0 上跨到下一次标定。
    assert capture.control_calls, "一次都没作动"
    assert capture.control_calls[-1] == (None, CAMERA_AUTO_EXPOSURE_OFF), (
        f"硬件 AE 被留在开着的状态: {capture.control_calls}"
    )
    # ② 异常照旧往上抛,没被 finally 吃掉 —— 它只能经由 _run 的 except 进到 status 里。
    status = service.status()
    assert status["phase"] == "failed"
    assert status["error"] == "camera exploded mid-convergence", (
        f"异常被吞了,一次相机故障被伪装成普通标定失败: {status['error']}"
    )
    assert "calibrate" not in events, "异常被吞掉之后还接着跑了标定"

    # ③ 守住上面那个「只炸一次」的前提本身。断言 ② 的**全部判别力都寄生在它身上**,
    # 而它长得恰好像一句可以顺手简化掉的条件(`and not self.explosions`)。
    # 注意这里**不能**只写 `assert capture.explosions == 1`:生产代码正确时异常会在取
    # settled 那一帧**之前**就抛出去,所以「一直炸」的假相机在这一轮里也只炸得成一次
    # —— 那条断言两种 fixture 下都是 1,挡不住任何东西。有判别力的是**再问一次**:
    # 一次性的假相机不会再炸,「一直炸」的会。
    assert capture.explosions == 1, f"这一轮该正好炸一次,实际 {capture.explosions}"
    try:
        capture.grab_fresh()
    except RuntimeError as exc:
        raise AssertionError(
            f"假相机不是一次性的 —— 它会一直炸。这样「吞掉异常」的实现会在取 settled "
            f"那一帧时再炸一次,新异常照样进 status,断言 ② 就会因为一个错误的理由变绿:{exc}"
        ) from exc
    service.stop()
