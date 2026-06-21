"""CaptureService — the single owner of the camera in 摆谱 capture mode.

Wraps ``CameraManager`` and exposes the operations the 带灯拍 pipeline needs:
fresh-frame grabs gated on a timestamp (so we never photograph a pre-LED frame),
burst grabs for geometry locking, and atomic frame writes.

Camera exclusivity (plan §3.1): only ONE owner may hold the camera. The server
gate refuses to start CaptureService and VisionService together (RuntimeError);
this class just assumes it owns the device while running.

Hardware-free testability: a ``camera`` instance can be injected, so tests use a
fake camera (no cv2 device). Real-camera capture is verified on hardware day.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("katrain_web")


@dataclass
class CaptureServiceConfig:
    enabled: bool = False
    camera_device: int | str = 0
    width: int = 1280
    height: int = 720
    out_dir: str = "~/.katrain/baipu_captures"
    lock_exposure: bool = True
    exposure: Optional[float] = None
    lock_awb: bool = True


class CaptureService:
    def __init__(self, config: CaptureServiceConfig, camera=None, hub=None):
        self.config = config
        self.out_dir = Path(config.out_dir).expanduser()
        self._owns_hub = hub is None
        if hub is None:
            from katrain.web.core.camera_hub import CameraHub, CameraHubConfig

            hub = CameraHub(
                CameraHubConfig(
                    device_id=config.camera_device,
                    width=config.width,
                    height=config.height,
                    lock_exposure=config.lock_exposure,
                    exposure=config.exposure,
                    lock_awb=config.lock_awb,
                ),
                camera=camera,
            )
        self._hub = hub

    # -- lifecycle --------------------------------------------------------- #
    def start(self) -> None:
        if self._owns_hub:
            self._hub.start()
        log.info("CaptureService started (camera=%s, out_dir=%s)", self.config.camera_device, self.out_dir)

    def stop(self) -> None:
        if self._owns_hub:
            self._hub.stop()

    def is_connected(self) -> bool:
        return self._hub.is_connected() if callable(getattr(self._hub, "is_connected", None)) else bool(
            getattr(self._hub, "is_connected", False)
        )

    # -- frame access ------------------------------------------------------ #
    def grab_fresh(self, after_ts: Optional[float] = None, settle_ms: float = 150.0):
        """Return ``(frame, seq, ts)`` of a frame read after ``after_ts + settle``."""
        return self._hub.grab_fresh(after_ts=after_ts, settle_ms=settle_ms)

    def read_frame(self):
        return self._hub.read_frame()

    def grab_burst(self, n: int = 8, interval: float = 0.1):
        """Grab ``n`` frames (for empty-board geometry locking)."""
        if hasattr(self._hub, "grab_burst"):
            return self._hub.grab_burst(n=n, interval=interval)
        frames = []
        for _ in range(n):
            frame, _seq, _ts = self._hub.grab_fresh(settle_ms=0.0)
            if frame is not None:
                frames.append(frame)
            time.sleep(interval)
        return frames

    def capture_to(
        self, path: str, after_ts: Optional[float] = None, settle_ms: float = 150.0
    ) -> Tuple[str, int, float]:
        """Grab a fresh frame and write it to ``path`` (creating parents). Atomic-ish
        via tmp+rename. Returns ``(path, seq, ts)``; raises on no-frame / write failure."""
        import cv2

        frame, seq, ts = self.grab_fresh(after_ts=after_ts, settle_ms=settle_ms)
        if frame is None:
            raise RuntimeError("capture_to: no frame available")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # tmp must keep the image suffix — cv2 picks the encoder from the extension.
        tmp = p.with_name(f".{p.stem}.tmp{p.suffix}")
        if not cv2.imwrite(str(tmp), frame):
            raise RuntimeError(f"capture_to: imwrite failed for {tmp}")
        tmp.replace(p)
        return str(p), seq, ts
