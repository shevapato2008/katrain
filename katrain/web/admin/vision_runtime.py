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
CALIBRATION_BURST_SIZE = 8
GEOMETRY_VERIFY_TTL = 30.0


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
        self._geometry_error = None
        self._camera_state = "unknown"
        self._camera_error = None
        self._led_state = "unknown"
        self._led_error = None
        self._updated_at = _now()
        self._last_preview = None
        self._lock = threading.RLock()
        self._active_id = None
        self._geometry_stale = False
        self._verification_preview = None
        self._frozen = None

    def _coordinator(self):
        from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator

        return VisionCaptureCoordinator(self.out_dir, lock=self._lock)

    def _sessions(self):
        from katrain.web.admin.vision_sessions import VisionSessionStore

        return VisionSessionStore(self._coordinator())

    def _session_sgf(self, session):
        from katrain.web.admin.vision_sgf import prepare_vision_sgf

        text = (
            session["original_sgf"]
            if session["state"] == "draft"
            else (self.out_dir / session["game_id"] / session["sgf_path"]).read_bytes().decode("utf-8")
        )
        return prepare_vision_sgf(text)

    def _stale_geometry(self):
        self._geometry_stale = self.geometry is not None
        self._verification_preview = None

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
                self._stale_geometry()
            led_state = self._led_state
            if self.led is not None:
                led_state = "connected" if self.led.is_connected() else "disconnected"
                if led_state != self._led_state:
                    self._led_state = led_state
                    self._updated_at = observed_at
            provenance = {"source": "admin_runtime", "updated_at": self._updated_at}
            session = self.get_session(self._active_id) if self._active_id is not None else None
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
                    "state": (
                        ("stale" if self._geometry_stale else "ready") if self.geometry is not None else "required"
                    ),
                    "revision": self.geometry_revision,
                    "source": self.geometry_source,
                    "confidence": getattr(self.geometry, "confidence", None),
                    "error": self._geometry_error,
                },
                "sgf": {
                    **provenance,
                    "state": "loaded" if session else "none",
                    "game_id": session["game_id"] if session else None,
                    "total_steps": session["total_steps"] if session else 0,
                    "next_step": session["next_step"] if session else None,
                },
                "dataset": {
                    **provenance,
                    "state": "frozen" if self._frozen else "draft" if session else "none",
                    "id": self._frozen["id"] if self._frozen else session["game_id"] if session else None,
                    "count": len(session["frames"]) if session else 0,
                },
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
                self._stale_geometry()
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
        self._stale_geometry()
        if self._active_id is None:
            self.geometry = self.geometry_revision = self.geometry_source = None
            self._geometry_stale = False
        self._geometry_error = None
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

    def calibrate(self, empty_confirmed: bool) -> dict:
        self.require_enabled()
        with self._lock:
            try:
                if not empty_confirmed:
                    raise VisionError(409, "Confirm the board is empty before calibrating")
                if self.camera is None or not self.camera.is_connected():
                    raise VisionError(409, "Camera is not connected")
                if self.mode == "led4":
                    if self.led is None or not self.led.is_connected():
                        raise VisionError(409, "LED is not connected; reconnect in stones2 mode without LED")
                    cleared = self.led.clear(strict=True)
                    if not cleared.get("ok") or not cleared.get("connected") or cleared.get("errors"):
                        raise VisionError(409, "LED clear failed")
                # The barrier is observed after strict LED clear has completed.
                # Camera.grab_fresh can return an old frame on timeout: verify every sample.
                barrier, previous_seq = time.monotonic(), 0
                frames = []
                for _ in range(CALIBRATION_BURST_SIZE):
                    if not self.camera.is_connected():
                        raise VisionError(409, "Camera connection lost during calibration")
                    frame, seq, ts = self.camera.grab_fresh(after_ts=barrier, settle_ms=0.0)
                    if not self.camera.is_connected():
                        raise VisionError(409, "Camera connection lost during calibration")
                    if frame is None or not math.isfinite(ts) or ts <= barrier or seq <= previous_seq:
                        raise VisionError(422, "Fresh calibration burst unavailable")
                    frames.append(frame.copy())
                    previous_seq = seq
                    barrier = max(ts, time.monotonic())
                from katrain.vision.geometry_autocal import CONF_MIN
                from katrain.vision.geometry_lock import lock_geometry_from_frames

                geometry = lock_geometry_from_frames(frames)
                if geometry is None:
                    raise VisionError(422, "Empty board geometry detection failed")
                if not math.isfinite(geometry.confidence) or geometry.confidence < CONF_MIN:
                    raise VisionError(422, "Calibration confidence is too low")
                if not geometry.empty_self_check_ok:
                    raise VisionError(422, "Board empty self-check failed")
                # A baseline built from this burst can absorb stationary stones.
                # Independently check absolute colors before accepting that baseline.
                import cv2
                from katrain.vision.tools.auto_label import label_board_image

                for frame in frames:
                    rectified = cv2.warpPerspective(frame, geometry.M, (geometry.out_size, geometry.out_size))
                    if label_board_image(rectified):
                        raise VisionError(422, "Board is not empty; remove all stones before calibration")
                if not self.camera.is_connected():
                    raise VisionError(409, "Camera connection lost during calibration")
            except Exception as exc:
                error = exc if isinstance(exc, VisionError) else VisionError(422, "Empty board calibration failed")
                self._geometry_error = str(error)
                self._updated_at = _now()
                if error is exc:
                    raise
                raise error from exc
            # Publish only the validated lock. Rejection retains the previous revision.
            self.geometry = geometry
            self.geometry_revision = str(uuid4())
            self.geometry_source = "opencv_empty_board"
            self._geometry_stale = False
            self._verification_preview = None
            self._geometry_error = None
            self._updated_at = _now()
            return self.status()["geometry"]

    def import_sgf(self, original_sgf: str) -> dict:
        self.require_enabled()
        with self._lock:
            if (
                self.geometry is None
                or self._geometry_stale
                or self.mode not in ("stones2", "led4")
                or self.camera is None
                or not self.camera.is_connected()
            ):
                raise VisionError(409, "Current calibration and connected capture mode are required")
            from katrain.web.admin.vision_capture_txn import VisionCaptureError
            from katrain.web.admin.vision_sgf import VisionSgfError, prepare_vision_sgf
            from dataclasses import asdict

            try:
                sgf = prepare_vision_sgf(original_sgf)
                session = self._sessions().create(
                    sgf,
                    mode=self.mode,
                    geometry_revision=self.geometry_revision,
                    geometry_source=self.geometry_source,
                    camera_device_id=self.device_id,
                )
            except VisionSgfError as exc:
                raise VisionError(422, str(exc)) from exc
            except VisionCaptureError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc
            self._active_id = session["game_id"]
            self._frozen = None
            self._verification_preview = None
            self._updated_at = _now()
            return {
                "game_id": self._active_id,
                "sgf_sha256": sgf.sgf_sha256,
                "total_steps": len(sgf.steps),
                "next_step": -1,
                "steps": [asdict(step) for step in sgf.steps],
                "mode": session["mode"],
            }

    def get_session(self, game_id: str) -> dict:
        self.require_enabled()
        with self._lock:
            from dataclasses import asdict
            from katrain.web.admin.vision_capture_txn import VisionCaptureError

            try:
                session = self._sessions().read(game_id)
                return {**session, "steps": [asdict(step) for step in self._session_sgf(session).steps]}
            except VisionCaptureError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc
            except (OSError, ValueError) as exc:
                raise VisionError(503, "Saved SGF source is corrupt or unavailable") from exc

    def list_sessions(self) -> dict:
        self.require_enabled()
        with self._lock:
            from katrain.web.admin.vision_capture_txn import VisionCaptureError

            try:
                return self._sessions().list()
            except VisionCaptureError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc

    def resume_session(self, game_id: str) -> dict:
        self.require_enabled()
        with self._lock:
            session = self.get_session(game_id)
            if session["state"] == "captured":
                from katrain.vision.geometry_lock import load_geometry_lock

                geometry = load_geometry_lock(self.out_dir / game_id / session["geometry_path"])
                self.geometry = geometry
                self.geometry_revision = session["geometry_revision"]
                self.geometry_source = session["geometry_source"]
                self._geometry_stale = True
            elif self._geometry_stale:
                # Drafts contain no persisted lock. Keep only a current fresh calibration.
                self.geometry = self.geometry_revision = self.geometry_source = None
                self._geometry_stale = False
            self._active_id = game_id
            self._frozen = None
            self._verification_preview = None
            self._last_preview = None
            self._geometry_error = None
            self._updated_at = _now()
            return self.status()

    def _check_session_camera(self, session):
        if self.camera is None or not self.camera.is_connected():
            raise VisionError(409, "Camera is not connected")
        if self.mode != session["mode"]:
            raise VisionError(409, "Capture mode differs from saved session; import a new session")
        devices = (
            [session["camera_device_id"]]
            if session["state"] == "draft"
            else [
                (
                    frame["capture_condition"].get("camera_device_id")
                    if isinstance(frame.get("capture_condition"), dict)
                    else None
                )
                for frame in session["frames"]
            ]
        )
        if any(type(device) is not int or device != self.device_id for device in devices):
            raise VisionError(409, "Camera device differs from saved session; calibrate and import a new session")

    def verify_geometry(self, game_id: str, frame_id: str, overlay_confirmed: bool) -> dict:
        self.require_enabled()
        with self._lock:
            if not overlay_confirmed or game_id != self._active_id:
                raise VisionError(409, "Confirm the saved geometry overlay for the active session")
            session = self.get_session(game_id)
            self._check_session_camera(session)
            preview = self._verification_preview
            if (
                session["state"] != "captured"
                or self.geometry_revision != session["geometry_revision"]
                or preview is None
                or preview["frame_id"] != frame_id
                or preview["game_id"] != game_id
                or preview["geometry_revision"] != self.geometry_revision
                or preview["device_id"] != self.device_id
                or preview["mode"] != self.mode
                or time.monotonic() - preview["observed_monotonic"] > GEOMETRY_VERIFY_TTL
            ):
                raise VisionError(409, "A recent saved-geometry preview is required; new view needs a new session")
            self._geometry_stale = False
            self._verification_preview = None
            self._geometry_error = None
            self._updated_at = _now()
            return self.status()["geometry"]

    def capture(
        self,
        game_id: str,
        move_index: int,
        operator_confirmed: bool,
        overwrite_existing: bool = False,
        capture_condition: dict | None = None,
    ) -> dict:
        self.require_enabled()
        with self._lock:
            if game_id != self._active_id:
                raise VisionError(409, "Resume the requested capture session first")
            session = self.get_session(game_id)
            self._check_session_camera(session)
            if self.geometry is None or self._geometry_stale:
                raise VisionError(409, "Current geometry must be calibrated or explicitly verified")
            if session["state"] == "captured" and self.geometry_revision != session["geometry_revision"]:
                raise VisionError(409, "New calibration requires a new capture session")
            from katrain.web.admin.vision_capture_txn import VisionCaptureError

            conditions = {**(capture_condition or {}), "camera_device_id": self.device_id}
            try:
                result = self._coordinator().capture(
                    sgf=self._session_sgf(session),
                    game_id=game_id,
                    mode=self.mode,
                    geometry=self.geometry,
                    geometry_revision=self.geometry_revision,
                    geometry_source=self.geometry_source,
                    camera=self.camera,
                    led=self.led,
                    move_index=move_index,
                    operator_confirmed=operator_confirmed,
                    overwrite_existing=overwrite_existing,
                    capture_condition=conditions,
                )
            except VisionCaptureError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc
            if not result["idempotent"]:
                self._frozen = None
                self._updated_at = _now()
            return result

    def review_sample(self, game_id: str, frame_id: str) -> dict:
        self.require_enabled()
        with self._lock:
            import cv2
            import numpy as np
            from katrain.web.admin.vision_dataset import VisionDatasetBuilder, VisionDatasetError

            session = self.get_session(game_id)
            try:
                sample = VisionDatasetBuilder(self._coordinator()).review_sample(game_id, frame_id)
                png = sample.pop("overlay_png")
                overlay = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                frame = next(frame for frame in session["frames"] if frame["frame_id"] == frame_id)
                return {
                    **sample,
                    "overlay_jpeg_base64": _jpeg(overlay),
                    "captured_at": frame["captured_at"],
                    "camera_seq": frame["camera_seq"],
                    "applied_move_index": frame["applied_move_index"],
                }
            except VisionDatasetError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc
            except (cv2.error, ValueError, OSError) as exc:
                raise VisionError(503, "Sample review image unavailable") from exc

    def freeze_dataset(self, game_id: str, **parameters) -> dict:
        self.require_enabled()
        with self._lock:
            from katrain.web.admin.vision_dataset import VisionDatasetBuilder, VisionDatasetError

            try:
                version = VisionDatasetBuilder(self._coordinator()).freeze(game_id, **parameters)
            except VisionDatasetError as exc:
                raise VisionError(exc.status_code, str(exc)) from exc
            if game_id == self._active_id:
                self._frozen = version
                self._updated_at = _now()
            return version

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
                overlay = None
                if self.geometry is not None:
                    from katrain.vision.warp import adjust_M_for_resolution, warp_with_margin

                    geometry = self.geometry
                    matrix = adjust_M_for_resolution(
                        geometry.M, (geometry.source_width, geometry.source_height), (frame.shape[1], frame.shape[0])
                    )
                    if not 1 <= geometry.out_size <= 2048:
                        raise ValueError("Geometry preview size is out of bounds")
                    warped = warp_with_margin(frame, matrix, geometry.out_size)
                    if hasattr(geometry, "xs") and hasattr(geometry, "ys"):
                        import cv2
                        import numpy as np

                        overlay = frame.copy()
                        xs, ys = np.meshgrid(geometry.xs, geometry.ys)
                        canonical = np.stack((xs, ys), axis=-1).astype(np.float32)
                        points = cv2.perspectiveTransform(canonical.reshape(-1, 1, 2), np.linalg.inv(matrix)).reshape(
                            19, 19, 2
                        )
                        if not np.isfinite(points).all():
                            raise ValueError("Invalid overlay projection")
                        for grid in (points, points.transpose(1, 0, 2)):
                            cv2.polylines(overlay, [line.astype(np.int32) for line in grid], False, (0, 220, 255), 1)
                frame_id = str(uuid4())
                result = {
                    "frame_id": frame_id,
                    "captured_at": observed_at,
                    "captured_at_source": "runtime_observed_at",
                    "camera_seq": seq,
                    "camera_monotonic_ts": ts,
                    "geometry_revision": self.geometry_revision,
                    "raw_jpeg_base64": _jpeg(frame),
                    "warped_jpeg_base64": _jpeg(warped) if warped is not None else None,
                    "geometry_overlay_jpeg_base64": _jpeg(overlay) if overlay is not None else None,
                }
                self._verification_preview = (
                    {
                        "frame_id": frame_id,
                        "game_id": self._active_id,
                        "geometry_revision": self.geometry_revision,
                        "device_id": self.device_id,
                        "mode": self.mode,
                        "observed_monotonic": time.monotonic(),
                    }
                    if overlay is not None
                    else None
                )
                return result
            except Exception as exc:
                raise VisionError(503, "Fresh camera preview unavailable") from exc
