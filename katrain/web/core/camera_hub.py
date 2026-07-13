"""Single-owner camera hub shared by capture, calibration, and recognition."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


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

    def __init__(self, config: CameraHubConfig, camera=None):
        self.config = config
        self._camera = camera
        self._started = False
        self._lifecycle_lock = threading.Lock()

    @property
    def is_started(self) -> bool:
        return self._started

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._started:
                return
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
                raise RuntimeError(f"Failed to open camera {self.config.device_id}")
            self._started = True

    def stop(self) -> None:
        with self._lifecycle_lock:
            if not self._started:
                return
            self._camera.close()
            self._started = False

    def is_connected(self) -> bool:
        return bool(self._started and self._camera is not None and getattr(self._camera, "is_connected", False))

    def read_frame(self):
        return self._camera.read_frame() if self._camera is not None else None

    def grab_fresh(self, after_ts=None, settle_ms: float = 150.0):
        if self._camera is None:
            return None, 0, 0.0
        return self._camera.grab_fresh(after_ts=after_ts, settle_ms=settle_ms)

    def grab_burst(self, n: int = 8, interval: float = 0.1):
        frames = []
        for _ in range(n):
            frame, _seq, _ts = self.grab_fresh(settle_ms=0.0)
            if frame is not None:
                frames.append(frame)
            time.sleep(interval)
        return frames
