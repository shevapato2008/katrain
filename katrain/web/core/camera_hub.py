"""Single-owner camera hub shared by capture, calibration, and recognition."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from katrain.vision.device_events import UdevDeviceMonitor
from katrain.web.core.device_lease import DeviceLease

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraHubConfig:
    device_id: int | str = 0
    width: int = 1280
    height: int = 720
    warmup_seconds: float = 2.0
    lock_exposure: bool = True
    exposure: float | None = None
    # Default OFF: locking WB on the HBV UVC camera leaves a red cast (no working manual WB).
    # Auto-WB gives neutral color; anti-LED-darkening is handled by exposure/software-AE, not WB.
    lock_awb: bool = False


class CameraHub:
    """Own exactly one CameraManager and expose its latest-frame API."""

    RECOVERY_INTERVAL_S = 5.0

    def __init__(self, config: CameraHubConfig, camera=None):
        self.config = config
        self._camera = camera
        self._started = False
        self._lifecycle_lock = threading.Lock()
        self._device_lease = None
        self._recovery_stop = threading.Event()
        self._recovery_thread: threading.Thread | None = None
        self._recovery_wake = threading.Event()
        self._device_event_lock = threading.Lock()
        self._pending_device_events: list[str] = []
        self._device_monitor = None
        self._device_recovery = None
        self._usb_startup_check = None
        self._usb_lock = threading.Lock()
        self._usb_request = None

    def set_usb_startup_check(self, callback) -> None:
        self._usb_startup_check = callback

    def set_device_recovery(self, recovery) -> None:
        self._device_recovery = recovery
        self._recovery_wake.set()

    def _usb_available(self) -> bool:
        with self._usb_lock:
            return self._usb_request is None

    def _startup_allowed(self) -> bool:
        try:
            return self._usb_startup_check is None or bool(self._usb_startup_check())
        except Exception:
            logger.exception("Camera USB startup check failed")
            return False

    def begin_usb_recovery(self, timeout=2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._usb_lock:
            if not self._started or self._recovery_stop.is_set():
                return False
            if self._usb_request is not None:
                return self._usb_request["acked"]
            request = {"event": threading.Event(), "deadline": deadline, "acked": False}
            self._usb_request = request
        # tick() runs on this thread too: it must never queue work to itself.
        if threading.current_thread() is self._recovery_thread:
            if self._lifecycle_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
                try:
                    self._ack_usb_recovery(request)
                finally:
                    self._lifecycle_lock.release()
        else:
            self._recovery_wake.set()
            request["event"].wait(max(0.0, deadline - time.monotonic()))
        with self._usb_lock:
            if self._usb_request is request and request["acked"]:
                return True
            if self._usb_request is request:
                self._usb_request = None
        self._recovery_wake.set()
        return False

    def _ack_usb_recovery(self, request) -> None:
        # Caller owns the hub lifecycle; close() keeps a blocked native reader
        # responsible for its capture. Its mere close request is not an ACK.
        with self._usb_lock:
            if self._usb_request is not request or request["acked"]:
                return
            if time.monotonic() >= request["deadline"]:
                self._usb_request = None
                request["event"].set()
                return
        try:
            self._camera.close()
            reader = getattr(self._camera, "_reader_thread", None)
            stopped = reader is None or not reader.is_alive()
        except Exception:
            logger.exception("Camera could not quiesce for USB recovery")
            stopped = False
        with self._usb_lock:
            if self._usb_request is request:
                request["acked"] = bool(
                    stopped
                    and self._started
                    and not self._recovery_stop.is_set()
                    and time.monotonic() <= request["deadline"]
                )
                if not request["acked"]:
                    self._usb_request = None
            request["event"].set()

    def end_usb_recovery(self) -> None:
        with self._usb_lock:
            request, self._usb_request = self._usb_request, None
            if request is not None:
                request["event"].set()
        self._recovery_wake.set()

    @property
    def is_started(self) -> bool:
        return self._started

    def start(self, *, allow_unavailable: bool = False) -> None:
        with self._lifecycle_lock:
            if self._started:
                return
            self._device_lease = DeviceLease.acquire("camera", self.config.device_id)
            try:
                if self._camera is None:
                    from katrain.vision.camera import CameraManager

                    self._camera = CameraManager(
                        device_id=self.config.device_id,
                        width=self.config.width,
                        height=self.config.height,
                        warmup_seconds=self.config.warmup_seconds,
                        lock_exposure=self.config.lock_exposure,
                        exposure=self.config.exposure,
                        lock_awb=self.config.lock_awb,
                    )
                self._recovery_stop = threading.Event()
                self._recovery_wake = threading.Event()
                with self._device_event_lock:
                    self._pending_device_events = []
                stop = self._recovery_stop
                self._device_monitor = UdevDeviceMonitor(
                    self.config.device_id, lambda action: self._queue_device_event(action, stop)
                )
                # Subscribe first so an event during initial open is reconciled too.
                self._device_monitor.start()
                if not self._startup_allowed() or not self._camera.open():
                    if not allow_unavailable:
                        raise RuntimeError(f"Failed to open camera {self.config.device_id}")
                    logger.warning(
                        "Camera unavailable; retaining shared services and retrying: %s", self.config.device_id
                    )
                self._started = True
                self._recovery_thread = threading.Thread(
                    target=self._recover_loop, args=(self._recovery_stop,), daemon=True, name="camera-recovery"
                )
                self._recovery_thread.start()
            except BaseException:
                self._started = False
                self._recovery_stop.set()
                self._recovery_wake.set()
                if self._device_monitor is not None:
                    self._device_monitor.stop()
                    self._device_monitor = None
                self._recovery_thread = None
                # Preserve the existing lease through partial-open cleanup.
                try:
                    if self._camera is not None:
                        try:
                            self._camera.close()
                        except Exception:
                            pass
                finally:
                    self._release_device_lease()
                raise

    def _queue_device_event(self, action: str, stop: threading.Event) -> None:
        # The monitor only registers work. It never waits for a capture or opens one.
        with self._device_event_lock:
            if stop is not self._recovery_stop or stop.is_set() or action not in {"add", "remove"}:
                return
            if action == "remove":
                self._pending_device_events = ["remove"]
            elif not self._pending_device_events or self._pending_device_events[-1] != "add":
                self._pending_device_events.append("add")
            self._recovery_wake.set()

    def _recover_loop(self, stop: threading.Event) -> None:
        while not stop.is_set():
            recovery = self._device_recovery
            next_tick_delay = getattr(recovery, "next_tick_delay", None)
            delay = self.RECOVERY_INTERVAL_S
            if next_tick_delay is not None:
                delay = next_tick_delay(default=delay)
            self._recovery_wake.wait(delay)
            self._recovery_wake.clear()
            with self._lifecycle_lock:
                if not self._started or stop.is_set():
                    return
                with self._usb_lock:
                    request = self._usb_request
                if request is not None:
                    if not request["acked"]:
                        self._ack_usb_recovery(request)
                    # Leave cached frames and queued hotplug events untouched
                    # until normal reconnect owns the device again.
                    paused = True
                else:
                    paused = False
                with self._device_event_lock:
                    events = [] if paused else self._pending_device_events
                    if not paused:
                        self._pending_device_events = []
                if not paused:
                    try:
                        handle_event = getattr(self._camera, "handle_device_event", None)
                        if handle_event is not None:
                            for action in events:
                                handle_event(action)
                        reconcile = getattr(self._camera, "reconcile_device", None)
                        if reconcile is not None:
                            reconcile()
                        if not self.is_connected() and self._startup_allowed():
                            # CameraManager owns cooldown/identity and reader startup.
                            # Timer reconciliation remains active when events are lost.
                            self._camera.read_frame()
                    except Exception:
                        logger.exception("Camera recovery failed for %s", self.config.device_id)
            recovery = self._device_recovery
            if recovery is not None and not stop.is_set():
                try:
                    recovery.tick()
                except Exception:
                    logger.exception("USB device recovery failed")

    def stop(self) -> None:
        # The coordinator may be waiting for this owner's lifecycle. Never hold
        # that lock while asking it to stop or waiting for its operation.
        device_recovery, self._device_recovery = self._device_recovery, None
        if device_recovery is not None:
            device_recovery.stop(timeout=2.0)
        recovery = None
        try:
            with self._lifecycle_lock:
                if not self._started:
                    return
                self._started = False
                self._recovery_stop.set()
                self._recovery_wake.set()
                self.end_usb_recovery()
                if self._device_monitor is not None:
                    self._device_monitor.stop()
                    self._device_monitor = None
                recovery, self._recovery_thread = self._recovery_thread, None
                try:
                    self._camera.close()
                finally:
                    self._release_device_lease()
        finally:
            if recovery is not None:
                if recovery is not threading.current_thread():
                    recovery.join(timeout=2.0)

    def _release_device_lease(self) -> None:
        lease, self._device_lease = self._device_lease, None
        if lease is None:
            return
        reader = getattr(self._camera, "_reader_thread", None)
        if reader is not None and reader.is_alive():
            # A blocked native read still owns its capture after bounded close().
            # Keep peers out until the reader's finally has released that capture.
            def release_after_reader():
                reader.join()
                lease.release()

            threading.Thread(target=release_after_reader, daemon=True, name="camera-lease-release").start()
        else:
            lease.release()

    def is_connected(self) -> bool:
        return bool(
            self._started
            and self._usb_available()
            and self._camera is not None
            and getattr(self._camera, "is_connected", False)
        )

    def read_frame(self):
        if not self._lifecycle_lock.acquire(blocking=False):
            return None
        try:
            return self._camera.read_frame() if self._can_read() else None
        finally:
            self._lifecycle_lock.release()

    def read_frame_identified(self):
        """(frame, seq, monotonic ts) from one locked read; diagnostics need the frame's identity."""
        if not self._lifecycle_lock.acquire(blocking=False):
            return None, 0, 0.0
        try:
            return self._camera.read_frame_identified() if self._can_read() else (None, 0, 0.0)
        finally:
            self._lifecycle_lock.release()

    def grab_fresh(self, after_ts=None, settle_ms: float = 150.0, timeout: float | None = None):
        # Lifecycle access and the frame wait share CameraManager's default budget.
        timeout = 2.0 if timeout is None else max(0.0, timeout)
        deadline = time.monotonic() + timeout
        if not self._lifecycle_lock.acquire(timeout=timeout):
            return None, 0, 0.0
        try:
            if not self._can_read():
                return None, 0, 0.0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, 0, 0.0
            return self._camera.grab_fresh(after_ts=after_ts, settle_ms=settle_ms, timeout=remaining)
        finally:
            self._lifecycle_lock.release()

    def _can_read(self) -> bool:
        # Disconnected CameraManager read/grab methods can reconnect internally.
        # Cached-frame reads need no filesystem operation-lock probe.
        return bool(
            self._started
            and self._camera is not None
            and self._usb_available()
            and (getattr(self._camera, "is_connected", False) or self._startup_allowed())
        )

    def grab_burst(self, n: int = 8, interval: float = 0.1):
        frames = []
        for _ in range(n):
            frame, _seq, _ts = self.grab_fresh(settle_ms=0.0)
            if frame is not None:
                frames.append(frame)
            time.sleep(interval)
        return frames

    # -- runtime camera controls (software AE) ------------------------------- #
    # worker_inprocess._run_ae 通过 getattr 发现这三个成员;缺任何一个都会让软件 AE
    # 永久落进 advisory 模式(见 worker_inprocess.py:222/229/233)。CameraHub 是
    # board 模式下真正传给 VisionService 的对象(server.py:546),所以转发必须在这里。

    def request_controls(self, exposure: float | None = None, auto_exposure: float | None = None) -> None:
        if self._camera is None:
            return
        self._camera.request_controls(exposure=exposure, auto_exposure=auto_exposure)

    @property
    def controls_effective(self) -> bool | None:
        return getattr(self._camera, "controls_effective", None) if self._camera is not None else None

    @property
    def initial_exposure(self) -> float | None:
        return getattr(self._camera, "initial_exposure", None) if self._camera is not None else None

    @property
    def current_auto_exposure(self) -> float | None:
        return getattr(self._camera, "current_auto_exposure", None) if self._camera is not None else None

    @property
    def current_exposure(self) -> float | None:
        return getattr(self._camera, "current_exposure", None) if self._camera is not None else None
