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


def test_camera_hub_grab_burst_uses_shared_frame_source():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(), camera=camera)
    hub.start()

    frames = hub.grab_burst(n=3, interval=0)

    assert len(frames) == 3
    assert all(frame.shape == (4, 6, 3) for frame in frames)


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
