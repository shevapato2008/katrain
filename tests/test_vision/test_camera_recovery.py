"""Camera lifecycle regressions independent of physical hardware."""

import threading
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from katrain.vision import camera as camera_module
from katrain.vision.camera import CameraManager


class MetadataCapture:
    """Synchronous reader fake with real control readback behavior."""

    def __init__(self, backend="V4L2"):
        self.values = {cv2.CAP_PROP_AUTO_EXPOSURE: 3.0, cv2.CAP_PROP_EXPOSURE: 100.0}
        self.backend = backend
        self.opened = True
        self.fail_controls = False

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        if self.fail_controls and prop in (cv2.CAP_PROP_AUTO_EXPOSURE, cv2.CAP_PROP_EXPOSURE):
            return False
        self.values[prop] = value
        return True

    def get(self, prop):
        return self.values.get(prop, 0.0)

    def getBackendName(self):
        return self.backend

    def release(self):
        self.opened = False


def publish_metadata_frame(camera, capture, value=17, during_read=None):
    frame = np.full((4, 6, 3), value, np.uint8)
    stop = threading.Event()
    reads = []

    def read():
        reads.append(1)
        if len(reads) == 1:
            if during_read is not None:
                during_read()
        else:
            stop.set()
        return True, frame

    capture.read = read
    camera._read_frames(capture, stop)
    # The second read only exits the synchronous fake loop; it is not published.
    return frame


def test_frame_metadata_keeps_completed_control_and_reopen_identity(monkeypatch):
    camera = CameraManager(warmup_seconds=0)
    first, reopened = MetadataCapture(), MetadataCapture()
    captures = iter([first, reopened])
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda _arg: next(captures))
    monkeypatch.setattr(camera, "_reader_loop", lambda: None)
    try:
        assert camera.open()
        original = publish_metadata_frame(camera, first)
        image, before = camera.read_frame_with_metadata()
        assert np.array_equal(image, original)
        assert before.stream_generation == 1
        assert before.frame_seq == 1
        assert before.controls_requested_generation == before.controls_applied_generation == 0
        assert before.controls_effective is True
        assert before.controls_completed_at <= before.camera_read_monotonic
        assert before.ownership_known is True
        assert before.advisory is False
        with pytest.raises(FrozenInstanceError):
            before.frame_seq = 100

        camera.request_controls(exposure=200.0)
        camera._apply_pending_controls()
        unchanged_image, unchanged = camera.read_frame_with_metadata()
        assert unchanged is before, "new global controls must not relabel the cached old image"
        assert np.array_equal(unchanged_image, original)
        publish_metadata_frame(camera, first, value=23)
        changed_image, changed = camera.read_frame_with_metadata()
        assert int(changed_image[0, 0, 0]) == 23
        assert changed.controls_requested_generation == changed.controls_applied_generation == 1
        assert changed.controls_completed_at > before.controls_completed_at
        assert changed.frame_seq == before.frame_seq + 1

        assert camera.open()
        assert camera.read_frame_with_metadata() == (None, None)
        publish_metadata_frame(camera, reopened, value=42)
        new_image, new = camera.read_frame_with_metadata()
        assert int(new_image[0, 0, 0]) == 42
        assert new.stream_generation == before.stream_generation + 1
        assert new.controls_requested_generation == new.controls_applied_generation == 1
        assert before.stream_generation == 1

        # The established APIs keep their array and three-value result contracts.
        identified, seq, ts = camera.read_frame_identified()
        assert np.array_equal(camera.read_frame(), new_image)
        assert np.array_equal(identified, new_image)
        assert (seq, ts) == (new.frame_seq, new.camera_read_monotonic)
        new_image[:] = 0
        assert int(camera.read_frame_with_metadata()[0][0, 0, 0]) == 42
    finally:
        camera.close()
    camera._last_reconnect_attempt = camera_module.time.monotonic()
    assert camera.read_frame_with_metadata() == (None, None)


@pytest.mark.parametrize("transition", ["pending", "completed", "stream"])
def test_frame_metadata_marks_ownership_unknown_when_owner_changes_during_read(transition):
    camera = CameraManager()
    capture = MetadataCapture()
    camera._cap = capture
    camera._connected = True
    camera.request_controls(exposure=100.0)
    camera._apply_pending_controls()

    def change_owner():
        if transition == "stream":
            with camera._frame_lock:
                camera._stream_generation += 1
        else:
            camera.request_controls(exposure=200.0)
            if transition == "completed":
                camera._apply_pending_controls()

    publish_metadata_frame(camera, capture, during_read=change_owner)
    image, metadata = camera.read_frame_with_metadata()
    assert image is not None
    assert metadata.ownership_known is False
    assert metadata.controls_requested_generation == 1
    assert metadata.controls_applied_generation == 1


@pytest.mark.parametrize("backend, advisory", [("AVFOUNDATION", True), ("V4L2", False), (None, False)])
def test_frame_metadata_advisory_requires_explicit_backend_and_completed_controls(monkeypatch, backend, advisory):
    monkeypatch.setattr(camera_module.sys, "platform", "darwin")
    camera = CameraManager()
    capture = MetadataCapture(backend)
    capture.fail_controls = True
    camera._cap = capture
    camera._connected = True
    camera.request_controls(exposure=200.0)
    camera._apply_pending_controls()
    publish_metadata_frame(camera, capture)
    _image, completed = camera.read_frame_with_metadata()
    assert completed.controls_effective is False
    assert completed.controls_requested_generation == completed.controls_applied_generation == 1
    assert completed.controls_completed_at is not None
    assert completed.ownership_known is True
    assert completed.advisory is advisory

    camera.request_controls(exposure=300.0)
    # Preserve a pending request through this read instead of applying it first.
    original_apply = camera._apply_pending_controls
    monkeypatch.setattr(camera, "_apply_pending_controls", lambda: None)
    publish_metadata_frame(camera, capture)
    _image, pending = camera.read_frame_with_metadata()
    assert pending.controls_effective is None
    assert pending.controls_requested_generation != pending.controls_applied_generation
    assert pending.advisory is False
    monkeypatch.setattr(camera, "_apply_pending_controls", original_apply)


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
