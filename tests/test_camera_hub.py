import threading
import time
from types import SimpleNamespace

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
        self.fresh_timeouts = []

    def open(self):
        self.open_calls += 1
        self.is_connected = True
        return True

    def close(self):
        self.close_calls += 1
        self.is_connected = False

    def read_frame(self):
        return self.frame.copy()

    def grab_fresh(self, after_ts=None, settle_ms=150.0, timeout=2.0):
        self.fresh_timeouts.append(timeout)
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


@pytest.mark.parametrize("timeout", [None, 0.5])
def test_grab_fresh_waits_for_preview_and_only_spends_remaining_timeout(timeout):
    preview_entered, preview_release, captured = threading.Event(), threading.Event(), threading.Event()
    requested = threading.Event()

    class PreviewCamera(FakeCamera):
        def read_frame(self):
            preview_entered.set()
            assert preview_release.wait(2)
            return super().read_frame()

    camera = PreviewCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    preview = threading.Thread(target=hub.read_frame)
    results = []
    elapsed = []

    def capture():
        started = time.monotonic()
        requested.set()
        results.append(hub.grab_fresh(after_ts=100.0, settle_ms=10, timeout=timeout))
        elapsed.append(time.monotonic() - started)
        captured.set()

    fresh = threading.Thread(target=capture)
    try:
        preview.start()
        assert preview_entered.wait(1)
        fresh.start()
        assert requested.wait(1)
        assert not captured.wait(0.04), "fresh capture returned while preview still owned the camera"
        preview_release.set()
        assert captured.wait(1)
        assert results[0][1:] == (7, 123.0)
        assert results[0][0].shape == camera.frame.shape
        budget = 2.0 if timeout is None else timeout
        assert 0 < camera.fresh_timeouts[0] <= budget - 0.03
        assert camera.fresh_timeouts[0] == pytest.approx(budget - elapsed[0], abs=0.02)
    finally:
        preview_release.set()
        preview.join(2)
        if fresh.ident is not None:
            fresh.join(2)
        hub.stop()


def test_grab_fresh_times_out_waiting_for_lifecycle_lock():
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    try:
        with hub._lifecycle_lock:
            started = time.monotonic()
            result = hub.grab_fresh(timeout=0.04)
            elapsed = time.monotonic() - started
        assert result == (None, 0, 0.0)
        assert 0.03 <= elapsed < 0.3
        assert camera.fresh_timeouts == []
    finally:
        hub.stop()


def test_grab_fresh_does_not_call_camera_after_budget_is_exhausted(monkeypatch):
    from katrain.web.core import camera_hub

    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    clock = iter([10.0, 10.1])
    monkeypatch.setattr(camera_hub, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    try:
        frame, seq, ts = hub.grab_fresh(timeout=0.05)
        assert frame is None
        assert (seq, ts) == (0, 0.0)
        assert camera.fresh_timeouts == []
        assert hub._lifecycle_lock.acquire(blocking=False), "exhausted capture retained lifecycle lock"
        hub._lifecycle_lock.release()
    finally:
        hub.stop()


def test_grab_fresh_waiting_for_stop_does_not_read_closed_camera():
    close_entered, close_release, captured = threading.Event(), threading.Event(), threading.Event()

    class ClosingCamera(FakeCamera):
        def close(self):
            close_entered.set()
            assert close_release.wait(2)
            super().close()

    camera = ClosingCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    closer = threading.Thread(target=hub.stop)
    results = []

    def capture():
        results.append(hub.grab_fresh(timeout=0.5))
        captured.set()

    fresh = threading.Thread(target=capture)
    try:
        closer.start()
        assert close_entered.wait(1)
        fresh.start()
        assert not captured.wait(0.03), "capture bypassed the active lifecycle operation"
        close_release.set()
        assert captured.wait(1)
        assert results == [(None, 0, 0.0)]
        assert camera.fresh_timeouts == []
    finally:
        close_release.set()
        closer.join(2)
        if fresh.ident is not None:
            fresh.join(2)
        hub.stop()


def test_preview_reads_stay_nonblocking_while_lifecycle_lock_is_held():
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=FakeCamera())
    hub.start()
    try:
        with hub._lifecycle_lock:
            started = time.monotonic()
            assert hub.read_frame() is None
            assert hub.read_frame_identified() == (None, 0, 0.0)
            assert time.monotonic() - started < 0.1
    finally:
        hub.stop()


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


class HotplugMonitor:
    instances = []
    available = True

    def __init__(self, path, callback):
        self.path, self.callback = path, callback
        self.started = False
        self.stopped = False
        self.instances.append(self)

    def start(self):
        self.started = True
        return self.available

    def stop(self):
        self.stopped = True


class HotplugCamera(RecoveringCamera):
    def __init__(self):
        super().__init__()
        self.events = []
        self.event_threads = []

    def handle_device_event(self, action):
        self.events.append(action)
        self.event_threads.append(threading.current_thread().name)
        if action == "remove":
            self.is_connected = False


@pytest.fixture
def hotplug_monitor(monkeypatch):
    from katrain.web.core import camera_hub

    HotplugMonitor.instances = []
    HotplugMonitor.available = True
    monkeypatch.setattr(camera_hub, "UdevDeviceMonitor", HotplugMonitor, raising=False)
    return HotplugMonitor


def test_hub_subscribes_before_initial_open_and_arrival_wakes_owner_within_500ms(hotplug_monitor):
    camera = HotplugCamera()
    original_open = camera.open

    def open_camera():
        assert hotplug_monitor.instances[0].started, "initial reconcile ran before subscribing"
        return original_open()

    camera.open = open_camera
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    try:
        hub.start(allow_unavailable=True)
        camera.available = True
        monitor = hotplug_monitor.instances[0]
        started = time.monotonic()
        monitor.callback("add")
        assert camera.recovered.wait(0.5)
        assert time.monotonic() - started < 0.5
        assert camera.events == ["add"]
        assert camera.event_threads == ["camera-recovery"]
    finally:
        hub.stop()
    assert monitor.stopped


def test_hub_coalesces_events_received_during_start_and_drops_late_events(hotplug_monitor):
    camera = HotplugCamera()
    original_open = camera.open

    def open_camera():
        monitor = hotplug_monitor.instances[0]
        if camera.open_calls == 0:
            monitor.callback("remove")
            monitor.callback("add")
            monitor.callback("add")
        camera.available = True
        return original_open()

    camera.open = open_camera
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start(allow_unavailable=True)
    try:
        deadline = time.monotonic() + 1
        while len(camera.events) < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert camera.events == ["remove", "add"]
    finally:
        hub.stop()
    attempts = camera.open_calls
    hotplug_monitor.instances[0].callback("add")
    assert camera.events == ["remove", "add"]
    assert camera.open_calls == attempts


@pytest.mark.parametrize("monitor_available", [False, True])
def test_monitor_failure_and_lost_events_retain_timer_recovery(monkeypatch, hotplug_monitor, monitor_available):
    hotplug_monitor.available = monitor_available
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    camera = HotplugCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    try:
        hub.start(allow_unavailable=True)
        camera.available = True
        assert camera.recovered.wait(1)
        assert camera.events == []
        assert len(hotplug_monitor.instances) == 1
    finally:
        hub.stop()


def test_stop_queued_event_does_not_reopen_closed_camera(hotplug_monitor):
    camera = HotplugCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start(allow_unavailable=True)
    with hub._lifecycle_lock:
        monitor = hotplug_monitor.instances[0]
        monitor.callback("add")
        # Withdraw pending recovery as shutdown does, before releasing lifecycle ownership.
        hub._recovery_stop.set()
    hub.stop()
    assert camera.open_calls == 1
    assert camera.events == []
    assert monitor.stopped


def test_idle_timer_reconciles_identity_even_while_cached_camera_is_ready(monkeypatch, hotplug_monitor):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    checked = threading.Event()
    camera = HotplugCamera()
    camera.available = True

    def reconcile_device():
        checked.set()
        camera.is_connected = False
        camera.available = False

    camera.reconcile_device = reconcile_device
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    try:
        hub.start()
        assert hub.is_connected()
        assert checked.wait(1)
        assert not hub.is_connected()
    finally:
        hub.stop()


def test_usb_recovery_hides_frames_retains_lease_and_resumes_normal_reader(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    camera = RecoveringCamera()
    camera.available = True
    device = uuid.uuid4().hex
    hub = CameraHub(CameraHubConfig(device_id=device), camera=camera)
    peer = CameraHub(CameraHubConfig(device_id=device), camera=FakeCamera())
    hub.start()
    try:
        assert hub.begin_usb_recovery(timeout=0.5)
        assert not hub.is_connected()
        assert hub.read_frame() is None
        assert hub.read_frame_identified() == (None, 0, 0.0)
        assert hub.grab_fresh(timeout=0.01) == (None, 0, 0.0)
        calls = camera.open_calls
        time.sleep(0.03)
        assert camera.open_calls == calls
        with pytest.raises(RuntimeError, match="[Bb]usy|occupied"):
            peer.start()
        camera.recovered.clear()
        hub.end_usb_recovery()
        hub.end_usb_recovery()
        assert camera.recovered.wait(0.5)
        assert hub.is_connected()
    finally:
        peer.stop()
        hub.stop()
        hub.stop()


def test_usb_recovery_cannot_ack_a_blocked_reader_or_leave_a_late_pause(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    entered, finish = threading.Event(), threading.Event()
    camera = RecoveringCamera()
    camera.available = True
    original_close = camera.close

    def close():
        entered.set()
        assert finish.wait(1)
        original_close()

    camera.close = close
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    try:
        started = time.monotonic()
        assert not hub.begin_usb_recovery(timeout=0.03)
        assert time.monotonic() - started < 0.2
        assert entered.is_set()
        camera.recovered.clear()
        finish.set()
        assert camera.recovered.wait(0.5), "timed out pause was applied after its caller left"
        assert hub.is_connected()
    finally:
        finish.set()
        hub.stop()


def test_usb_recovery_requires_old_reader_to_really_exit(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    finish = threading.Event()
    camera = FakeCamera()
    camera._reader_thread = threading.Thread(target=finish.wait, daemon=True)
    camera._reader_thread.start()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()
    try:
        assert not hub.begin_usb_recovery(timeout=0.03)
    finally:
        finish.set()
        camera._reader_thread.join(1)
        hub.stop()


def test_startup_check_precedes_initial_open_and_reconnect(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    allowed = threading.Event()
    camera = RecoveringCamera()
    camera.available = True
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.set_usb_startup_check(allowed.is_set)
    try:
        hub.start(allow_unavailable=True)
        time.sleep(0.03)
        assert camera.open_calls == 0
        assert hub.read_frame() is None
        assert hub.grab_fresh(timeout=0.01) == (None, 0, 0.0)
        allowed.set()
        assert camera.recovered.wait(0.5)
        allowed.clear()
        camera.is_connected = False
        calls = camera.open_calls
        hub.read_frame()
        time.sleep(0.03)
        assert camera.open_calls == calls
    finally:
        hub.stop()


def test_device_recovery_ticks_healthy_camera_outside_lifecycle_lock_and_stops_first(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    ticked = threading.Event()
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)

    class Recovery:
        def tick(self):
            assert hub._lifecycle_lock.acquire(blocking=False)
            hub._lifecycle_lock.release()
            ticked.set()

        def stop(self, timeout=2.0):
            assert camera.close_calls == 0
            assert hub._lifecycle_lock.acquire(blocking=False)
            hub._lifecycle_lock.release()
            return True

    hub.set_device_recovery(Recovery())
    hub.start()
    assert ticked.wait(0.5)
    hub.stop()


def test_recovery_tick_can_pause_its_own_camera_and_keeps_ticking_while_paused(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 0.01)
    finished = threading.Event()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=FakeCamera())

    class Recovery:
        calls = 0

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                assert hub.begin_usb_recovery(timeout=0.1)
            else:
                hub.end_usb_recovery()
                finished.set()

        def stop(self, timeout=2.0):
            return True

    hub.set_device_recovery(Recovery())
    try:
        hub.start()
        assert finished.wait(0.5)
    finally:
        hub.stop()


def test_same_thread_pause_spends_timeout_waiting_for_lifecycle_without_late_close(monkeypatch):
    monkeypatch.setattr(CameraHub, "RECOVERY_INTERVAL_S", 10)
    owned, release, done = threading.Event(), threading.Event(), threading.Event()
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    hub.start()

    def hold_lifecycle():
        with hub._lifecycle_lock:
            owned.set()
            release.wait(1)

    holder = threading.Thread(target=hold_lifecycle)
    results = []

    def pause_as_owner():
        hub._recovery_thread = threading.current_thread()
        results.append(hub.begin_usb_recovery(timeout=0.03))
        done.set()

    pauser = threading.Thread(target=pause_as_owner)
    worker = hub._recovery_thread
    try:
        holder.start()
        assert owned.wait(0.5)
        pauser.start()
        assert done.wait(0.2), "same-thread pause ignored its lifecycle wait budget"
        assert results == [False]
        assert camera.close_calls == 0
    finally:
        release.set()
        holder.join(1)
        pauser.join(1)
        hub._recovery_thread = worker
        hub.stop()


def test_healthy_cached_frames_do_not_repeat_startup_operation_lock_check():
    checked = []
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=FakeCamera())
    hub.set_usb_startup_check(lambda: checked.append(True) or True)
    try:
        hub.start()
        assert len(checked) == 1
        hub.read_frame()
        hub.grab_fresh(timeout=0.1)
        assert len(checked) == 1
    finally:
        hub.stop()


def test_owner_loop_kills_usb_reset_at_eight_seconds_without_waiting_full_poll(tmp_path):
    from katrain.vision.hardware_recovery_gate import HardwareRecoveryGate
    from katrain.web.core.linux_usb_hub import HubSnapshot, PortSnapshot
    from katrain.web.core.usb_hub_recovery import UsbHubRecovery

    clock = SimpleNamespace(now=1000.0)
    stop = threading.Event()
    waits, launched, killed = [], [], []

    class AdvancingWake:
        def wait(self, delay):
            waits.append(delay)
            clock.now += delay
            return False

        def set(self):
            pass

        def clear(self):
            pass

    class Operation:
        returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            killed.append(clock.now)
            self.returncode = -9
            stop.set()

        def wait(self, timeout=None):
            return self.returncode

    ports = {
        i: PortSnapshot(
            i,
            i in (3, 4),
            True,
            i == 3,
            False,
            False,
            ("303a", "1001") if i == 3 else None,
            "1-1.3" if i == 3 else None,
        )
        for i in range(1, 5)
    }

    def start_reset(_lock, _candidates):
        launched.append(clock.now)
        return Operation()

    adapter = SimpleNamespace(
        snapshot=lambda: HubSnapshot(True, "1-1", ("1a40", "0101"), ports), start_reset=start_reset
    )
    quiet = SimpleNamespace(begin_usb_recovery=lambda timeout=2: True, end_usb_recovery=lambda: None)
    camera = FakeCamera()
    hub = CameraHub(CameraHubConfig(device_id=uuid.uuid4().hex), camera=camera)
    recovery = UsbHubRecovery(
        adapter,
        hub,
        quiet,
        quiet,
        HardwareRecoveryGate(),
        tmp_path / "state" / "state.json",
        clock=lambda: clock.now,
        wall_clock=lambda: clock.now,
    )
    hub.set_device_recovery(recovery)
    hub._started = True
    camera.is_connected = True
    hub._recovery_wake = AdvancingWake()
    worker = threading.Thread(target=hub._recover_loop, args=(stop,), name="camera-recovery")
    hub._recovery_thread = worker
    try:
        worker.start()
        worker.join(1)
        assert not worker.is_alive()
        assert len(launched) == len(killed) == 1
        assert killed[0] - launched[0] == pytest.approx(8.0)
        assert waits == [5.0, 5.0, 5.0, 5.0, 3.0]
    finally:
        stop.set()
        worker.join(1)
        hub.stop()
