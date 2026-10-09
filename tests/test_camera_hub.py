import threading

import numpy as np
import pytest

from katrain.web.core.camera_hub import CameraHub, CameraHubConfig


class FakeCamera:
    def __init__(self):
        self.open_calls = 0
        self.close_calls = 0
        self.is_connected = False
        self.frame = np.zeros((4, 6, 3), np.uint8)

    def open(self):
        self.open_calls += 1
        self.is_connected = True
        return True

    def close(self):
        self.close_calls += 1
        self.is_connected = False

    def read_frame(self):
        return self.frame.copy()

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        return self.frame.copy(), 7, 123.0


def test_camera_hub_owns_one_camera_lifecycle():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=0, width=1920, height=1080), camera=camera)

    hub.start()
    hub.start()
    assert camera.open_calls == 1
    assert hub.is_connected() is True

    frame = hub.read_frame()
    fresh, seq, ts = hub.grab_fresh(after_ts=100.0, settle_ms=10)
    assert frame.shape == (4, 6, 3)
    assert fresh.shape == frame.shape and seq == 7 and ts == 123.0

    hub.stop()
    hub.stop()
    assert camera.close_calls == 1


class RecoveringCamera(FakeCamera):
    def __init__(self):
        super().__init__()
        self.available = False
        self.recovered = threading.Event()

    def open(self):
        self.open_calls += 1
        self.is_connected = self.available
        if self.is_connected:
            self.recovered.set()
        return self.is_connected

    def read_frame(self):
        if not self.is_connected and not self.open():
            return None
        return super().read_frame()


def test_camera_hub_default_start_still_rejects_missing_camera():
    camera = RecoveringCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    with pytest.raises(RuntimeError, match="Failed to open camera"):
        hub.start()
    assert not hub.is_started
    assert not hub.is_connected()


def test_camera_hub_recovers_initial_absence_and_idle_dropout_without_consumers(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01, raising=False)
    camera = RecoveringCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    try:
        hub.start(allow_unavailable=True)
        hub.start(allow_unavailable=True)
        assert hub.is_started and not hub.is_connected()
        camera.available = True
        assert camera.recovered.wait(1), "camera did not recover without frame consumers"
        assert hub.is_connected()

        camera.recovered.clear()
        camera.is_connected = False  # Reader observed USB disconnection.
        assert camera.recovered.wait(1), "idle camera did not reconnect"
        assert hub.is_connected()
    finally:
        hub.stop()
    attempts = camera.open_calls
    assert not hub.is_connected()
    assert hub.read_frame() is None
    assert hub.grab_fresh() == (None, 0, 0.0)
    assert camera.open_calls == attempts
    assert camera.close_calls == 1


def test_camera_hub_stop_waits_for_recovery_and_closes_its_result(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01, raising=False)
    entered, finish, stopped = threading.Event(), threading.Event(), threading.Event()

    class SlowRecoveryCamera(RecoveringCamera):
        def read_frame(self):
            entered.set()
            assert finish.wait(2)
            return super().read_frame()

    camera = SlowRecoveryCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    hub.start(allow_unavailable=True)
    camera.available = True
    assert entered.wait(1)

    def stop():
        hub.stop()
        stopped.set()

    closer = threading.Thread(target=stop)
    closer.start()
    try:
        assert not stopped.wait(0.03)
        finish.set()
        assert stopped.wait(1)
        assert not hub.is_connected()
        assert not camera.is_connected
    finally:
        finish.set()
        closer.join(2)
        hub.stop()


def test_camera_hub_grab_burst_uses_shared_frame_source():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    hub.start()

    frames = hub.grab_burst(n=3, interval=0)

    assert len(frames) == 3
    assert all(frame.shape == (4, 6, 3) for frame in frames)
    hub.stop()


class ControlCamera(FakeCamera):
    def __init__(self):
        super().__init__()
        self.control_calls = []
        self.controls_effective = True
        self.initial_exposure = 166.0
        self.current_auto_exposure = 1.0
        self.current_exposure = 120.0

    def request_controls(self, exposure=None, auto_exposure=None):
        self.control_calls.append((exposure, auto_exposure))


def test_camera_hub_forwards_runtime_controls_to_the_camera():
    camera = ControlCamera()
    hub = CameraHub(CameraHubConfig(device_id=0), camera=camera)
    hub.start()

    hub.request_controls(exposure=120.0, auto_exposure=0.25)

    assert camera.control_calls == [(120.0, 0.25)]
    assert hub.controls_effective is True
    assert hub.initial_exposure == 166.0
    assert hub.current_auto_exposure == 1.0
    assert hub.current_exposure == 120.0
    hub.stop()


def test_camera_hub_controls_are_inert_before_start():
    hub = CameraHub(CameraHubConfig(device_id=0), camera=None)

    hub.request_controls(exposure=120.0)

    assert hub.controls_effective is None
    assert hub.initial_exposure is None
    assert hub.current_auto_exposure is None
    assert hub.current_exposure is None
