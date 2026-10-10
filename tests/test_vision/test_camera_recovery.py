"""Camera lifecycle regressions independent of physical hardware."""

import threading
from types import SimpleNamespace

import cv2
import numpy as np

from katrain.vision import camera as camera_module
from katrain.vision.camera import CameraManager


def test_disconnect_invalidates_cached_capture_and_readiness():
    camera = CameraManager()
    camera._cap = SimpleNamespace(isOpened=lambda: True)
    camera._connected = True
    camera._latest_frame = np.ones((4, 6, 3), np.uint8)
    assert camera.is_connected
    camera._mark_disconnected()
    assert not camera.is_connected
    assert camera.grab_fresh(timeout=0)[0] is None


def test_open_handle_without_a_current_frame_is_not_ready():
    camera = CameraManager()
    camera._cap = SimpleNamespace(isOpened=lambda: True)
    camera._connected = True
    assert not camera.is_connected


def test_concurrent_reconnect_does_not_open_twice(monkeypatch):
    camera = CameraManager()
    entered, finish = threading.Event(), threading.Event()
    opens = []

    def open_camera():
        opens.append(1)
        entered.set()
        assert finish.wait(2)
        camera._connected = True
        return True

    monkeypatch.setattr(camera, "open", open_camera)
    first = threading.Thread(target=camera.read_frame)
    first.start()
    try:
        assert entered.wait(1)
        assert camera.read_frame() is None
        assert len(opens) == 1
    finally:
        finish.set()
        first.join(2)


class BlockingCapture:
    def __init__(self):
        self.entered = threading.Event()
        self.finish = threading.Event()
        self.released = threading.Event()

    def isOpened(self):
        return not self.released.is_set()

    def set(self, prop, value):
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_AUTO_EXPOSURE:
            return 3.0
        return 0.0

    def read(self):
        self.entered.set()
        assert self.finish.wait(3)
        return True, np.ones((4, 6, 3), np.uint8)

    def release(self):
        self.released.set()


def test_blocked_old_reader_prevents_replacement_and_cannot_publish_late_frame(monkeypatch):
    monkeypatch.setattr(CameraManager, "READER_JOIN_TIMEOUT_S", 0.01, raising=False)
    first, second = BlockingCapture(), BlockingCapture()
    captures = iter([first, second])
    opened = []

    def capture(arg):
        opened.append(arg)
        return next(captures)

    monkeypatch.setattr(camera_module.cv2, "VideoCapture", capture)
    camera = CameraManager(warmup_seconds=0)
    try:
        assert camera.open()
        assert first.entered.wait(1)
        reader = camera._reader_thread
        old_stop = camera._stop_event
        camera.close()
        assert old_stop.is_set()
        assert not camera.open(), "must not overlap a reader blocked in native capture"
        assert len(opened) == 1
        first.finish.set()
        reader.join(1)
        assert not reader.is_alive()
        assert first.released.is_set()
        assert camera.grab_fresh(timeout=0)[0] is None

        assert camera.open()
        assert camera._stop_event is not old_stop
        assert old_stop.is_set()
        assert second.entered.wait(1)
    finally:
        first.finish.set()
        second.finish.set()
        camera.close()


def test_stable_alias_identity_resolves_sysfs_node(monkeypatch):
    monkeypatch.setattr(camera_module.sys, "platform", "linux")
    monkeypatch.setattr(camera_module.os.path, "realpath", lambda path: "/dev/video7")
    paths = []

    class NameFile:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return "HBV HD CAMERA\n"

    def read_name(path):
        paths.append(path)
        return NameFile()

    monkeypatch.setattr("builtins.open", read_name)
    assert camera_module._get_camera_name("/dev/smartbox-cam") == "HBV HD CAMERA"
    assert paths == ["/sys/class/video4linux/video7/name"]


def test_failed_stable_alias_retry_preserves_configured_identity(monkeypatch):
    camera = CameraManager(device_id="/dev/smartbox-cam")
    camera._camera_name = "HBV HD CAMERA"
    monkeypatch.setattr(camera, "open", lambda: False)
    monkeypatch.setattr(camera_module, "_find_device_by_name", lambda *args: 7)
    camera.read_frame()
    assert camera._device_id == "/dev/smartbox-cam"
