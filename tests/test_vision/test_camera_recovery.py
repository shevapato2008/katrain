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


def test_hotplug_arrival_bypasses_cooldown_once_without_changing_timer(monkeypatch):
    camera = CameraManager(warmup_seconds=0)
    camera._last_reconnect_attempt = camera_module.time.monotonic()
    opened = []
    monkeypatch.setattr(camera, "open", lambda: opened.append(1) or False)
    camera.read_frame()
    assert opened == []
    camera.handle_device_event("add")
    assert opened == [], "event registration must not open a capture"
    camera.read_frame()
    assert opened == [1]
    camera.read_frame()
    assert opened == [1], "one arrival must not disable the normal retry cooldown"


def test_missing_linux_absolute_alias_never_opens_opencv_or_logs_retries(monkeypatch, caplog):
    monkeypatch.setattr(camera_module.sys, "platform", "linux")
    monkeypatch.setattr(camera_module.os.path, "exists", lambda _path: False)
    opened = []

    def unexpected_open(arg):
        opened.append(arg)
        raise AssertionError("missing Linux alias must not invoke OpenCV")

    monkeypatch.setattr(camera_module.cv2, "VideoCapture", unexpected_open)
    camera = CameraManager(device_id="/dev/smartbox-cam", warmup_seconds=0)
    assert not camera.open()
    camera.handle_device_event("add")
    assert camera.read_frame() is None
    assert opened == []
    assert "reconnect" not in caplog.text.lower()
    assert "Failed to open" not in caplog.text


def test_hotplug_removal_blocks_old_reader_and_arrival_waits_for_exit(monkeypatch):
    monkeypatch.setattr(CameraManager, "READER_JOIN_TIMEOUT_S", 0.01)
    first, second = BlockingCapture(), BlockingCapture()
    captures, opened = iter([first, second]), []

    def capture(arg):
        opened.append(arg)
        return next(captures)

    monkeypatch.setattr(camera_module.cv2, "VideoCapture", capture)
    camera = CameraManager(warmup_seconds=0)
    try:
        assert camera.open()
        assert first.entered.wait(1)
        reader = camera._reader_thread
        camera._latest_frame = np.ones((4, 6, 3), np.uint8)
        camera.handle_device_event("remove")
        assert not camera.is_connected
        assert camera.grab_fresh(timeout=0)[0] is None
        camera.handle_device_event("add")
        assert camera.read_frame() is None
        assert len(opened) == 1
        first.finish.set()
        reader.join(1)
        assert camera.grab_fresh(timeout=0)[0] is None
        # The arrival credit survives the blocked reader, rather than waiting another 5 s.
        camera.read_frame()
        assert len(opened) == 2
        assert second.entered.wait(1)
        assert not camera.is_connected, "a new capture handle alone is not ready"
    finally:
        first.finish.set()
        second.finish.set()
        camera.close()


def test_periodic_reconcile_invalidates_cached_frame_when_alias_disappears(monkeypatch):
    monkeypatch.setattr(camera_module.sys, "platform", "linux")
    monkeypatch.setattr(camera_module.os.path, "exists", lambda _path: False)
    camera = CameraManager(device_id="/dev/smartbox-cam", warmup_seconds=0)
    capture = SimpleNamespace(isOpened=lambda: True, release=lambda: None)
    camera._cap = capture
    camera._connected = True
    camera._latest_frame = np.ones((4, 6, 3), np.uint8)
    assert camera.is_connected
    camera.reconcile_device()
    assert not camera.is_connected
    assert camera.grab_fresh(timeout=0)[0] is None


def test_distinct_arrival_retires_connected_old_capture_and_grants_one_retry(monkeypatch):
    camera = CameraManager(warmup_seconds=0)
    released = threading.Event()
    camera._cap = SimpleNamespace(isOpened=lambda: True, release=released.set)
    camera._connected = True
    camera._latest_frame = np.ones((4, 6, 3), np.uint8)
    camera._last_reconnect_attempt = camera_module.time.monotonic()
    opened = []
    monkeypatch.setattr(camera, "open", lambda: opened.append(1) or False)
    camera.handle_device_event("add")
    assert released.is_set()
    assert not camera.is_connected
    camera.read_frame()
    assert opened == [1]


def test_missing_numbered_node_still_uses_recorded_name_to_find_new_node(monkeypatch):
    monkeypatch.setattr(camera_module.sys, "platform", "linux")
    monkeypatch.setattr(camera_module.os.path, "exists", lambda path: path == "/dev/video19")
    camera = CameraManager(device_id="/dev/video17", warmup_seconds=0)
    camera._camera_name = "HBV HD CAMERA"
    monkeypatch.setattr(camera_module, "_find_device_by_name", lambda *args: 19)
    opened = []

    def open_camera():
        opened.append(camera._capture_arg)
        return False

    monkeypatch.setattr(camera, "open", open_camera)
    camera.read_frame()
    assert camera._device_id == 19
    assert opened[-1] == "/dev/video19"


def test_periodic_reconcile_detects_replacement_at_same_alias(monkeypatch):
    monkeypatch.setattr(camera_module.sys, "platform", "linux")
    monkeypatch.setattr(camera_module.os.path, "exists", lambda _path: True)
    original_stat = camera_module.os.stat

    def stat(path, **kwargs):
        if path == "/dev/smartbox-cam":
            return SimpleNamespace(st_dev=1, st_ino=20, st_rdev=9)
        return original_stat(path, **kwargs)

    monkeypatch.setattr(camera_module.os, "stat", stat)
    camera = CameraManager(device_id="/dev/smartbox-cam", warmup_seconds=0)
    released = threading.Event()
    camera._capture_identity = (1, 10, 7)
    camera._cap = SimpleNamespace(isOpened=lambda: True, release=released.set)
    camera._connected = True
    camera._latest_frame = np.ones((4, 6, 3), np.uint8)
    camera.reconcile_device()
    assert released.is_set()
    assert not camera.is_connected
