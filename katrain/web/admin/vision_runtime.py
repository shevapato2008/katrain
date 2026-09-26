"""Explicit, local-only ownership of the admin camera and optional LED board."""

from __future__ import annotations

import base64
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from katrain.web.admin.settings import AdminConfig, local_vision_requested
from katrain.web.core.device_lease import DeviceBusy

log = logging.getLogger(__name__)
PREVIEW_MAX_EDGE = 960
PREVIEW_INTERVAL = 0.5


class VisionError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def create_camera(device_id: int):
    from katrain.web.core.camera_hub import CameraHub, CameraHubConfig

    return CameraHub(CameraHubConfig(device_id=device_id))


def create_led(serial_port: str):
    from katrain.web.core.led_service import LedService, LedServiceConfig

    return LedService(LedServiceConfig(enabled=True, serial_port=serial_port))


def _now():
    return datetime.now(timezone.utc)


def _jpeg(frame) -> str:
    import cv2

    height, width = frame.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError("Empty image")
    scale = min(1.0, PREVIEW_MAX_EDGE / max(height, width))
    if scale < 1:
        frame = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))))
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return base64.b64encode(encoded).decode("ascii")


class AdminVisionRuntime:
    def __init__(self, config: AdminConfig, *, bind_host: str | None = None):
        # An unverified factory launch must never silently enable local hardware.
        self.enabled = config.env == "local" and local_vision_requested() and bind_host == "127.0.0.1"
        self.out_dir = Path.home() / ".katrain" / "admin-vision"
        self.led_port = os.getenv("KATRAIN_ADMIN_VISION_LED_PORT", "").strip()
        self.camera = None
        self.led = None
        self.mode = None
        self.device_id = None
        self.geometry = None
        self.geometry_revision = None
        self.geometry_source = None
        self._camera_state = "unknown"
        self._camera_error = None
        self._led_state = "unknown"
        self._led_error = None
        self._updated_at = _now()
        self._last_preview = None
        self._lock = threading.RLock()

    def require_enabled(self):
        if not self.enabled:
            raise VisionError(403, "Local vision requires explicit enablement and a 127.0.0.1 process bind")

    def status(self) -> dict:
        with self._lock:
            observed_at = _now()
            if self.camera is not None and self._camera_state == "connected" and not self.camera.is_connected():
                self._camera_state = "disconnected"
                self._camera_error = "Camera connection lost"
                self._updated_at = observed_at
            led_state = self._led_state
            if self.led is not None:
                led_state = "connected" if self.led.is_connected() else "disconnected"
            provenance = {"source": "admin_runtime", "updated_at": self._updated_at}
            return {
                "enabled": self.enabled,
                "local_only": True,
                "observed_at": observed_at,
                "mode": self.mode,
                "camera": {
                    **provenance,
                    "state": self._camera_state,
                    "device_id": self.device_id,
                    "error": self._camera_error,
                },
                "led": {**provenance, "state": led_state, "error": self._led_error},
                "geometry": {
                    **provenance,
                    "state": "ready" if self.geometry is not None else "required",
                    "revision": self.geometry_revision,
                    "source": self.geometry_source,
                    "confidence": getattr(self.geometry, "confidence", None),
                },
                "sgf": {**provenance, "state": "none", "game_id": None, "total_steps": 0, "next_step": None},
                "dataset": {**provenance, "state": "none", "id": None, "count": 0},
            }

    def devices(self) -> dict:
        self.require_enabled()
        return {
            "candidates": [{"device_id": n, "label": f"Local camera candidate {n}", "probed": False} for n in range(9)]
        }

    def connect(self, device_id: int, mode: str) -> dict:
        self.require_enabled()
        with self._lock:
            if self.camera is not None:
                raise VisionError(409, "Disconnect the existing camera before connecting")
            if mode == "led4" and not self.led_port:
                raise VisionError(503, "LED serial port is not configured locally")
            self.device_id = device_id
            self._camera_state, self._camera_error = "connecting", None
            self._led_state, self._led_error = ("unknown" if mode == "led4" else "disabled"), None
            self._updated_at = _now()
            stage = "camera"
            try:
                self.camera = create_camera(device_id)
                self.camera.start()
                if not self.camera.is_connected():
                    raise RuntimeError("Camera did not connect")
                if mode == "led4":
                    stage = "led"
                    self.led = create_led(self.led_port)
                    self.led.start()
                    if not self.led.is_connected():
                        raise RuntimeError("LED did not connect")
                self.mode = mode
                self._camera_state = "connected"
                self._led_state = "connected" if self.led else "disabled"
            except Exception as exc:
                self._release_devices()
                busy = isinstance(exc, DeviceBusy)
                message = f"{stage.capitalize()} device occupied" if busy else f"{stage.capitalize()} connection failed"
                self._camera_state = ("occupied" if busy else "error") if stage == "camera" else "disconnected"
                self._camera_error = message if stage == "camera" else None
                if stage == "led":
                    self._led_state, self._led_error = ("occupied" if busy else "error"), message
                self._updated_at = _now()
                raise VisionError(409 if busy else 503, message) from exc
            self._updated_at = _now()
            return self.status()

    def _release_devices(self):
        errors = []
        for name in ("led", "camera"):
            device = getattr(self, name)
            if device is not None:
                try:
                    device.stop()
                except Exception:
                    log.exception("Admin vision %s cleanup failed", name)
                    errors.append(name)
                finally:
                    setattr(self, name, None)
        self.geometry = self.geometry_revision = self.geometry_source = None
        self.mode = None
        self._last_preview = None
        return errors

    def disconnect(self) -> dict:
        self.require_enabled()
        return self.shutdown()

    def shutdown(self) -> dict:
        with self._lock:
            errors = self._release_devices()
            self.device_id = None
            self._camera_state = "error" if "camera" in errors else "disconnected"
            self._camera_error = "Camera cleanup failed" if "camera" in errors else None
            self._led_state = "error" if "led" in errors else "disconnected"
            self._led_error = "LED cleanup failed" if "led" in errors else None
            self._updated_at = _now()
            return self.status()

    def preview(self) -> dict:
        self.require_enabled()
        with self._lock:
            if self.camera is None or not self.camera.is_connected():
                raise VisionError(409, "Camera is not connected")
            barrier = time.monotonic()
            if self._last_preview is not None and barrier - self._last_preview < PREVIEW_INTERVAL:
                raise VisionError(429, "Preview rate limit exceeded")
            self._last_preview = barrier
            try:
                # One atomic acquisition provides image and camera freshness metadata.
                frame, seq, ts = self.camera.grab_fresh(after_ts=barrier, settle_ms=0.0)
                if frame is None or not math.isfinite(ts) or ts <= barrier or seq <= 0:
                    raise ValueError("Fresh camera frame unavailable")
                observed_at = _now()
                warped = None
                if self.geometry is not None:
                    from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin

                    geometry = self.geometry
                    matrix = adjust_M_for_resolution(
                        geometry.M, (geometry.source_width, geometry.source_height), (frame.shape[1], frame.shape[0])
                    )
                    if not 1 <= geometry.out_size <= 2048:
                        raise ValueError("Geometry preview size is out of bounds")
                    warped = warp_with_margin(frame, matrix, geometry.out_size)
                return {
                    "frame_id": str(uuid4()),
                    "captured_at": observed_at,
                    "captured_at_source": "runtime_observed_at",
                    "camera_seq": seq,
                    "camera_monotonic_ts": ts,
                    "geometry_revision": self.geometry_revision,
                    "raw_jpeg_base64": _jpeg(frame),
                    "warped_jpeg_base64": _jpeg(warped) if warped is not None else None,
                }
            except Exception as exc:
                raise VisionError(503, "Fresh camera preview unavailable") from exc
