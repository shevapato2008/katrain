import threading

import numpy as np
import pytest
import subprocess
import sys
import uuid

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


def test_same_camera_device_is_busy_until_owner_stops():
    device = f"camera-{uuid.uuid4().hex}"
    first_camera, second_camera = FakeCamera(), FakeCamera()
    first = CameraHub(CameraHubConfig(device_id=device), camera=first_camera)
    second = CameraHub(CameraHubConfig(device_id=device), camera=second_camera)
    first.start()
    try:
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            second.start()
        assert second_camera.open_calls == 0
    finally:
        first.stop()
    second.start()
    try:
        assert second_camera.open_calls == 1
    finally:
        second.stop()


def test_different_camera_devices_do_not_block_each_other():
    device = uuid.uuid4().hex
    first = CameraHub(CameraHubConfig(device_id=f"{device}-1"), camera=FakeCamera())
    second = CameraHub(CameraHubConfig(device_id=f"{device}-2"), camera=FakeCamera())
    first.start()
    try:
        second.start()
        assert second.is_started
    finally:
        second.stop()
        first.stop()


def test_camera_open_failure_releases_device_for_retry():
    device = f"camera-{uuid.uuid4().hex}"
    broken = FakeCamera()
    broken.open = lambda: False
    first = CameraHub(CameraHubConfig(device_id=device), camera=broken)
    with pytest.raises(RuntimeError, match="Failed to open camera"):
        first.start()
    second = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    second.start()
    second.stop()


def test_camera_open_exception_releases_device_for_retry():
    device = f"camera-{uuid.uuid4().hex}"
    broken = FakeCamera()

    def fail_open():
        raise OSError("camera unplugged")

    broken.open = fail_open
    first = CameraHub(CameraHubConfig(device_id=device), camera=broken)
    with pytest.raises(OSError, match="camera unplugged"):
        first.start()
    second = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    second.start()
    second.stop()


def test_partial_camera_open_is_closed_before_lease_is_released():
    device = f"camera-{uuid.uuid4().hex}"
    broken = FakeCamera()
    peer = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    original_close = broken.close

    def fail_after_open():
        broken.is_connected = True
        raise OSError("failed after opening")

    def close_while_owned():
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        original_close()

    broken.open = fail_after_open
    broken.close = close_while_owned
    first = CameraHub(CameraHubConfig(device_id=device), camera=broken)
    with pytest.raises(OSError, match="failed after opening"):
        first.start()
    assert broken.close_calls == 1
    assert broken.is_connected is False
    peer.start()
    peer.stop()


def test_real_camera_manager_thread_start_failure_releases_capture_before_lease(monkeypatch):
    from katrain.vision import camera as camera_module

    device = f"camera-{uuid.uuid4().hex}"
    peer = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())

    class Capture:
        released = False

        def isOpened(self):
            return not self.released

        def set(self, *_args):
            return True

        def get(self, *_args):
            return 0.0

        def release(self):
            with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
                peer.start()
            self.released = True

    capture = Capture()
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda _device: capture)
    original_start = camera_module.threading.Thread.start

    def fail_thread_start(_thread):
        if _thread.name == "cam-reader":
            raise RuntimeError("camera reader could not start")
        return original_start(_thread)

    monkeypatch.setattr(camera_module.threading.Thread, "start", fail_thread_start)
    camera = camera_module.CameraManager(device_id=device, warmup_seconds=0)
    hub = CameraHub(CameraHubConfig(device_id=device), camera=camera)
    with pytest.raises(RuntimeError, match="camera reader could not start"):
        hub.start()

    assert capture.released is True
    assert camera._cap is None
    assert camera.is_connected is False
    peer.start()
    peer.stop()


def test_linux_high_camera_index_and_device_path_share_a_lease(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    device = 10000 + int(uuid.uuid4().hex[:6], 16)
    first = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    peer = CameraHub(CameraHubConfig(device_id=f"/dev/video{device}"), camera=FakeCamera())
    first.start()
    try:
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
    finally:
        peer.stop()
        first.stop()


def test_camera_device_lease_blocks_another_process():
    device = f"camera-{uuid.uuid4().hex}"
    first = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    script = """import sys
from katrain.web.core.device_lease import DeviceBusy, DeviceLease
try:
    lease = DeviceLease.acquire('camera', sys.argv[1])
except DeviceBusy:
    sys.exit(0)
else:
    lease.release()
    sys.exit(1)
"""
    first.start()
    try:
        result = subprocess.run([sys.executable, "-c", script, device], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
    finally:
        first.stop()


def test_blocked_reader_retains_device_lease_until_it_exits(monkeypatch):
    device = f"camera-{uuid.uuid4().hex}"
    finish, released = threading.Event(), threading.Event()
    camera = FakeCamera()
    camera._reader_thread = threading.Thread(target=finish.wait, daemon=True)
    camera._reader_thread.start()
    owner = CameraHub(CameraHubConfig(device_id=device), camera=camera)
    peer = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    owner.start()
    lease = owner._device_lease
    original_release = lease.release

    def release():
        original_release()
        released.set()

    monkeypatch.setattr(lease, "release", release)
    try:
        owner.stop()
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        finish.set()
        assert released.wait(1)
        peer.start()
    finally:
        finish.set()
        camera._reader_thread.join(1)
        peer.stop()
        owner.stop()


def test_identified_frame_reads_do_not_reopen_a_stopped_hub():
    class IdentifiedCamera(FakeCamera):
        identified_reads = 0

        def read_frame_identified(self):
            self.identified_reads += 1
            return self.frame.copy(), 7, 3.0

    camera = IdentifiedCamera()
    hub = CameraHub(CameraHubConfig(device_id=f"camera-{uuid.uuid4().hex}"), camera=camera)
    hub.start()
    assert hub.read_frame_identified()[1:] == (7, 3.0)
    hub.stop()
    assert hub.read_frame_identified() == (None, 0, 0.0)
    assert camera.identified_reads == 1
