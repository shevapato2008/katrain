"""Single-owner camera hub shared by capture, calibration, and recognition."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

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
                if not self._camera.open():
                    if not allow_unavailable:
                        raise RuntimeError(f"Failed to open camera {self.config.device_id}")
                    logger.warning(
                        "Camera unavailable; retaining shared services and retrying: %s", self.config.device_id
                    )
                self._started = True
                self._recovery_stop = threading.Event()
                self._recovery_thread = threading.Thread(
                    target=self._recover_loop, args=(self._recovery_stop,), daemon=True, name="camera-recovery"
                )
                self._recovery_thread.start()
            except BaseException:
                self._started = False
                self._recovery_stop.set()
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

    def _recover_loop(self, stop: threading.Event) -> None:
        while not stop.wait(self.RECOVERY_INTERVAL_S):
            with self._lifecycle_lock:
                if not self._started or stop.is_set():
                    return
                if not self.is_connected():
                    try:
                        # CameraManager owns reconnect cooldown/identity and reader startup.
                        # This runs even when vision is idle and no consumer requests frames.
                        self._camera.read_frame()
                    except Exception:
                        logger.exception("Camera recovery failed for %s", self.config.device_id)

    def stop(self) -> None:
        recovery = None
        try:
            with self._lifecycle_lock:
                if not self._started:
                    return
                self._started = False
                self._recovery_stop.set()
                recovery, self._recovery_thread = self._recovery_thread, None
                try:
                    self._camera.close()
                finally:
                    self._release_device_lease()
        finally:
            if recovery is not None:
                recovery.join()

    def _release_device_lease(self) -> None:
        lease, self._device_lease = self._device_lease, None
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
        return bool(self._started and self._camera is not None and getattr(self._camera, "is_connected", False))

    def read_frame(self):
        if not self._lifecycle_lock.acquire(blocking=False):
            return None
        try:
            return self._camera.read_frame() if self._started else None
        finally:
            self._lifecycle_lock.release()

    def read_frame_identified(self):
        """(frame, seq, monotonic ts) from one locked read; diagnostics need the frame's identity."""
        if not self._lifecycle_lock.acquire(blocking=False):
            return None, 0, 0.0
        try:
            return (
                self._camera.read_frame_identified() if self._started and self._camera is not None else (None, 0, 0.0)
            )
        finally:
            self._lifecycle_lock.release()

    def grab_fresh(self, after_ts=None, settle_ms: float = 150.0):
        if not self._lifecycle_lock.acquire(blocking=False):
            return None, 0, 0.0
        try:
            if not self._started:
                return None, 0, 0.0
            return self._camera.grab_fresh(after_ts=after_ts, settle_ms=settle_ms)
        finally:
            self._lifecycle_lock.release()

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
