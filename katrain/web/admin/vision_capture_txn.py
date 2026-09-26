"""Capture into staging, verify immutable assets, then publish one manifest.

The runtime must pass its lifecycle RLock here and use it for SGF import,
calibration and disconnect too. This coordinator never owns or opens devices.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from katrain.vision.classes import CLASS_NAMES
from katrain.web.admin.vision_sgf import PreparedVisionSgf, prepare_vision_sgf

SCHEMA_VERSION = 1
CLASS_ORDERS = {"stones2": ("black", "white"), "led4": tuple(CLASS_NAMES)}
EMPTY_BOARD_HASH = hashlib.sha1(b"[]").hexdigest()[:16]
_GAME_ID = re.compile(r"sgf-[0-9a-f]{64}")


class VisionCaptureError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def _geometry_assets(geometry) -> tuple[bytes, bytes]:
    import numpy as np

    shapes = {
        "corners": (4, 2),
        "points": (19, 19, 2),
        "xs": (19,),
        "ys": (19,),
        "M": (3, 3),
        "Minv": (3, 3),
        "baseline": (19, 19, 3),
    }
    arrays = {name: np.asarray(getattr(geometry, name)) for name in shapes}
    if any(value.shape != shapes[name] or not np.isfinite(value).all() for name, value in arrays.items()):
        raise ValueError("Invalid geometry arrays")
    if not 1 <= geometry.out_size <= 2048:
        raise ValueError("Geometry size is out of bounds")
    stream = io.BytesIO()
    np.savez(stream, **arrays, out_size=np.int64(geometry.out_size))
    sidecar = {
        name: getattr(geometry, name)
        for name in ("confidence", "nmatch", "empty_black", "empty_white", "diag", "source_width", "source_height")
    }
    # Calibration diagnostics may contain numpy scalars.
    sidecar_bytes = json.dumps(
        sidecar, sort_keys=True, indent=2, allow_nan=False, default=lambda value: value.item()
    ).encode("utf-8")
    return stream.getvalue(), sidecar_bytes


def _write_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != data:
        raise OSError("Written asset verification failed")


def _write_image(path: Path, frame) -> str:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise OSError("JPEG write failed")
    if cv2.imread(str(path)) is None:
        raise OSError("Written JPEG is unreadable")
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
    return _sha(path.read_bytes())


class _FreshCapture:
    """The legacy LED writer can access only this freshness-checked adapter."""

    def __init__(self, camera, confirmation_barrier: float, sequence_floor: int):
        self.camera = camera
        self.barrier = confirmation_barrier
        self.led_barrier = confirmation_barrier
        self.sequence_floor = sequence_floor
        self.observed = None

    def capture_to(self, path, after_ts=None, settle_ms=150.0):
        import cv2

        if after_ts is not None and (not isinstance(after_ts, (int, float)) or not math.isfinite(after_ts)):
            raise VisionCaptureError(503, "Invalid LED guidance timestamp")
        barrier = max(self.barrier, self.led_barrier, after_ts or self.barrier)
        try:
            frame, seq, ts = self.camera.grab_fresh(after_ts=barrier, settle_ms=settle_ms)
            if (
                frame is None
                or type(seq) is not int
                or seq <= self.sequence_floor
                or not math.isfinite(ts)
                or ts <= barrier + settle_ms / 1000
            ):
                raise ValueError("Camera returned a stale frame")
            if not self.camera.is_connected():
                raise ValueError("Camera disconnected during acquisition")
        except Exception as exc:
            raise VisionCaptureError(503, "Fresh camera frame unavailable") from exc
        self.observed = {
            "camera_seq": seq,
            "seq": seq,
            "camera_monotonic_ts": ts,
            "confirmation_monotonic_ts": self.barrier,
            "acquisition_barrier_monotonic_ts": barrier,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "captured_at_source": "runtime_observed_at",
        }
        try:
            _write_image(Path(path), frame)
        except (OSError, cv2.error) as exc:
            raise VisionCaptureError(507, "Capture image write failed") from exc
        return str(path), seq, ts


class _GuidedLed:
    """Legacy final-frame capture drops clear()'s timestamp; retain its barrier."""

    def __init__(self, led, capture: _FreshCapture):
        self.led = led
        self.capture = capture

    def _command(self, operation, *args, **kwargs):
        try:
            result = operation(*args, **kwargs)
            if not result.get("ok"):
                raise ValueError("LED command failed")
            # Completion is a conservative barrier even if the service supplies
            # no shown_at (notably blackout) or an earlier timestamp.
            self.capture.led_barrier = time.monotonic()
            return result
        except Exception as exc:
            raise VisionCaptureError(503, "LED guidance failed") from exc

    def set_points(self, points, *, strict=False):
        return self._command(self.led.set_points, points, strict=strict)

    def clear(self, *, strict=False):
        return self._command(self.led.clear, strict=strict)


class VisionCaptureCoordinator:
    def __init__(self, root: Path | str, *, lock=None):
        self.root = Path(root).expanduser().resolve()
        self.lock = lock if lock is not None else threading.RLock()

    def _session_dir(self, game_id: str) -> Path:
        if not isinstance(game_id, str) or not _GAME_ID.fullmatch(game_id):
            raise VisionCaptureError(422, "Invalid capture game ID")
        path = self.root / game_id
        if path.is_symlink():
            raise VisionCaptureError(503, "Capture session must not be a symlink")
        return path

    @staticmethod
    def _asset(directory: Path, name: str, digest: str) -> Path:
        if not isinstance(name, str) or Path(name).name != name or name in ("", ".", ".."):
            raise ValueError("Unsafe manifest asset path")
        path = directory / name
        if path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != digest:
            raise ValueError("Manifest asset integrity failed")
        return path

    def _read_session(self, directory: Path) -> dict | None:
        import cv2
        from katrain.vision.geometry_lock import load_geometry_lock

        path = directory / "manifest.json"
        if not path.exists():
            if directory.exists():
                raise VisionCaptureError(503, "Existing session has no manifest")
            return None
        try:
            if path.is_symlink():
                raise ValueError("Manifest must not be a symlink")
            manifest = json.loads(path.read_bytes())
            if (
                manifest["schema_version"] != SCHEMA_VERSION
                or manifest["board_size"] != 19
                or manifest["game_id"] != directory.name
                or manifest["class_names"] != list(CLASS_ORDERS[manifest["mode"]])
                or not manifest["geometry_revision"]
                or not manifest["geometry_source"]
            ):
                raise ValueError("Invalid manifest identity/schema")
            sgf_path = self._asset(directory, manifest["sgf_path"], manifest["sgf_sha256"])
            sgf = prepare_vision_sgf(sgf_path.read_text(encoding="utf-8"))
            if sgf.game_id != manifest["game_id"] or sgf.sgf_sha256 != manifest["sgf_sha256"]:
                raise ValueError("SGF identity mismatch")
            geometry_path = self._asset(directory, manifest["geometry_path"], manifest["geometry_sha256"])
            self._asset(directory, manifest["geometry_sidecar_path"], manifest["geometry_sidecar_sha256"])
            geometry = load_geometry_lock(geometry_path)
            _geometry_assets(geometry)
            if not isinstance(manifest["frames"], list) or not manifest["frames"]:
                raise ValueError("Published session must have an initial frame")
            expected = -1
            frame_ids, frame_files = set(), set()
            for frame in manifest["frames"]:
                if type(frame["applied_move_index"]) is not int or frame["applied_move_index"] != expected:
                    raise ValueError("Manifest frames violate SGF order")
                board_hash = EMPTY_BOARD_HASH if expected == -1 else sgf.steps[expected].board_hash
                if (
                    frame["board_hash"] != board_hash
                    or frame["mode"] != manifest["mode"]
                    or frame["geometry_revision"] != manifest["geometry_revision"]
                    or frame["geometry_source"] != manifest["geometry_source"]
                    or frame["qa_status"] != "operator_confirmed"
                    or frame["board_through_index"] != expected
                    or frame["next_guided_move_index"] != sgf.next_placement_index(expected)
                    or frame["captured_at_source"] != "runtime_observed_at"
                    or frame["frame_id"] in frame_ids
                    or frame["file"] in frame_files
                ):
                    raise ValueError("Invalid frame provenance")
                frame_ids.add(frame["frame_id"])
                frame_files.add(frame["file"])
                if (
                    type(frame["camera_seq"]) is not int
                    or frame["camera_seq"] <= 0
                    or not math.isfinite(frame["camera_monotonic_ts"])
                    or not math.isfinite(frame["confirmation_monotonic_ts"])
                    or not math.isfinite(frame["acquisition_barrier_monotonic_ts"])
                    or frame["camera_monotonic_ts"] <= frame["acquisition_barrier_monotonic_ts"]
                    or frame["acquisition_barrier_monotonic_ts"] < frame["confirmation_monotonic_ts"]
                    or datetime.fromisoformat(frame["captured_at"]).utcoffset() is None
                ):
                    raise ValueError("Invalid camera freshness evidence")
                next_index = sgf.next_placement_index(expected)
                if manifest["mode"] == "stones2":
                    if frame["led_point"] is not None or frame["frame_kind"] != (
                        "initial_empty" if expected == -1 else "after_move"
                    ):
                        raise ValueError("Stone-only frame contains LED guidance")
                else:
                    point = (
                        None
                        if next_index is None
                        else {
                            "row": sgf.steps[next_index].row,
                            "col": sgf.steps[next_index].col,
                            "color": "black" if sgf.steps[next_index].color == "B" else "white",
                        }
                    )
                    if frame["led_point"] != point:
                        raise ValueError("LED guidance contradicts SGF")
                image = self._asset(directory, frame["file"], frame["sha256"])
                if cv2.imread(str(image)) is None:
                    raise ValueError("Manifest JPEG is unreadable")
                expected = next_index
            if manifest["next_step"] != expected or manifest["total_steps"] != len(sgf.steps):
                raise ValueError("Invalid manifest progress")
            return manifest
        except Exception as exc:
            raise VisionCaptureError(503, "Capture session manifest is corrupt or incomplete") from exc

    def load_session(self, game_id: str) -> dict:
        with self.lock:
            manifest = self._read_session(self._session_dir(game_id))
            if manifest is None:
                raise VisionCaptureError(404, "Capture session does not exist")
            return manifest

    def capture(
        self,
        *,
        sgf: PreparedVisionSgf,
        game_id: str,
        mode: str,
        geometry,
        geometry_revision: str,
        geometry_source: str,
        camera,
        move_index: int,
        operator_confirmed: bool,
        overwrite_existing: bool = False,
        led=None,
        capture_condition: dict | None = None,
        settle_ms: float = 150.0,
    ) -> dict:
        with self.lock:
            directory = self._session_dir(game_id)
            if mode not in CLASS_ORDERS:
                raise VisionCaptureError(422, "Unsupported capture mode")
            if operator_confirmed is not True:
                raise VisionCaptureError(409, "Operator placement confirmation is required")
            if type(move_index) is not int or type(overwrite_existing) is not bool:
                raise VisionCaptureError(422, "Invalid capture step or overwrite flag")
            if geometry is None or not geometry_revision or not geometry_source:
                raise VisionCaptureError(409, "Locked geometry is required")
            try:
                if not isinstance(sgf, PreparedVisionSgf) or prepare_vision_sgf(sgf.original_sgf) != sgf:
                    raise ValueError("Prepared SGF truth was changed")
                if sgf.game_id != game_id:
                    raise ValueError("SGF game identity mismatch")
                if move_index != -1 and move_index not in sgf.placement_indices:
                    raise ValueError("Only initial or physical placement steps can be captured")
                if not math.isfinite(settle_ms) or not 0 <= settle_ms <= 1000:
                    raise ValueError("Invalid frame settle interval")
                conditions = json.loads(_json(capture_condition if capture_condition is not None else {}))
                if not isinstance(conditions, dict) or len(_json(conditions)) > 16384:
                    raise ValueError("Capture conditions must be a bounded object")
                npz_bytes, sidecar_bytes = _geometry_assets(geometry)
            except Exception as exc:
                raise VisionCaptureError(422, "Invalid SGF, geometry or capture parameters") from exc
            manifest = self._read_session(directory)
            if manifest is not None:
                if (
                    manifest["sgf_sha256"] != sgf.sgf_sha256
                    or manifest["mode"] != mode
                    or manifest["geometry_revision"] != geometry_revision
                    or manifest["geometry_source"] != geometry_source
                    or manifest["geometry_sha256"] != _sha(npz_bytes)
                    or manifest["geometry_sidecar_sha256"] != _sha(sidecar_bytes)
                ):
                    raise VisionCaptureError(409, "Session SGF, mode or geometry changed")
            frames = manifest["frames"] if manifest else []
            existing = next((i for i, frame in enumerate(frames) if frame["applied_move_index"] == move_index), None)
            if existing is not None and not overwrite_existing:
                return {**frames[existing], "idempotent": True}
            if existing is None and move_index != (manifest["next_step"] if manifest else -1):
                raise VisionCaptureError(409, "Capture must follow SGF placement order")
            if camera is None or not camera.is_connected():
                raise VisionCaptureError(409, "Camera is not connected")
            if mode == "led4" and (led is None or not led.is_connected()):
                raise VisionCaptureError(409, "Connected LED service is required")
            try:
                # Query the current frame sequence before establishing the confirmation
                # barrier. after_ts=0 returns the existing frame without waiting.
                _, sequence_floor, _ = camera.grab_fresh(after_ts=0, settle_ms=0)
                if type(sequence_floor) is not int or sequence_floor < 0:
                    raise ValueError("Invalid camera sequence")
            except Exception as exc:
                raise VisionCaptureError(503, "Camera sequence unavailable") from exc
            confirmation_barrier = time.monotonic()
            adapter = _FreshCapture(camera, confirmation_barrier, sequence_floor)
            try:
                self.root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".capture-", dir=self.root) as temporary:
                    stage_root = Path(temporary)
                    stage = stage_root / game_id
                    stage.mkdir()
                    next_index = sgf.next_placement_index(move_index)
                    led_point = None
                    frame_kind = "initial_empty" if move_index == -1 else "after_move"
                    if mode == "led4":
                        from katrain.web.core.baipu_capture import LedUnavailable, run_capture

                        try:
                            run_capture(
                                led=_GuidedLed(led, adapter),
                                capture=adapter,
                                geometry=geometry,
                                steps=[asdict(step) for step in sgf.steps],
                                board_size=19,
                                out_dir=str(stage_root),
                                game_id=game_id,
                                move_index=move_index,
                                sgf=sgf.original_sgf,
                                capture_condition=conditions,
                                settle_ms=settle_ms,
                                fiducial_mode="off",
                            )
                        except LedUnavailable as exc:
                            raise VisionCaptureError(503, "LED guidance failed") from exc
                        legacy = json.loads((stage / "manifest.json").read_bytes())["frames"][0]
                        image_path = stage / legacy["file"]
                        led_point, frame_kind = legacy["led_point"], legacy["frame_kind"]
                    else:
                        image_path = stage / "frame.jpg"
                        adapter.capture_to(image_path, settle_ms=settle_ms)
                    frame_id = str(uuid4())
                    file_name = f"frame-{frame_id}.jpg"
                    new_image = stage / file_name
                    os.replace(image_path, new_image)
                    entry = {
                        **adapter.observed,
                        "frame_id": frame_id,
                        "file": file_name,
                        "sha256": _sha(new_image.read_bytes()),
                        "mode": mode,
                        "frame_kind": frame_kind,
                        "applied_move_index": move_index,
                        "next_guided_move_index": next_index,
                        "led_point": led_point,
                        "board_through_index": move_index,
                        "board_hash": EMPTY_BOARD_HASH if move_index == -1 else sgf.steps[move_index].board_hash,
                        "geometry_revision": geometry_revision,
                        "geometry_source": geometry_source,
                        "capture_condition": conditions,
                        "qa_status": "operator_confirmed",
                    }
                    updated = (
                        dict(manifest)
                        if manifest
                        else {
                            "schema_version": SCHEMA_VERSION,
                            "game_id": game_id,
                            "board_size": 19,
                            "mode": mode,
                            "class_names": list(CLASS_ORDERS[mode]),
                            "session_timestamp": entry["captured_at"],
                            "sgf_path": "game.sgf",
                            "sgf_sha256": sgf.sgf_sha256,
                            "geometry_path": "geometry.npz",
                            "geometry_sha256": _sha(npz_bytes),
                            "geometry_sidecar_path": "geometry.json",
                            "geometry_sidecar_sha256": _sha(sidecar_bytes),
                            "geometry_revision": geometry_revision,
                            "geometry_source": geometry_source,
                            "total_steps": len(sgf.steps),
                            "total_moves": len(sgf.placement_indices),
                        }
                    )
                    updated_frames = list(frames)
                    if existing is None:
                        updated_frames.append(entry)
                    else:
                        updated_frames[existing] = entry
                    updated["frames"] = updated_frames
                    updated["next_step"] = sgf.next_placement_index(updated_frames[-1]["applied_move_index"])
                    if manifest is None:
                        # Replace legacy staging assets with the exact bytes already
                        # hashed at preflight. No durable asset exists yet.
                        for name in ("manifest.json", "game.sgf", "geometry.npz", "geometry.json"):
                            (stage / name).unlink(missing_ok=True)
                        _write_bytes(stage / "game.sgf", sgf.original_sgf.encode("utf-8"))
                        _write_bytes(stage / "geometry.npz", npz_bytes)
                        _write_bytes(stage / "geometry.json", sidecar_bytes)
                    _write_bytes(stage / ".manifest.pending", _json(updated))
                    if manifest is None:
                        os.replace(stage / ".manifest.pending", stage / "manifest.json")
                        os.replace(stage, directory)
                    else:
                        # A same-volume exclusive hard link makes the complete
                        # image visible without ever overwriting an old reference,
                        # even in the unlikely event of a frame-ID collision.
                        published_image = directory / file_name
                        os.link(new_image, published_image)
                        try:
                            os.replace(stage / ".manifest.pending", directory / "manifest.json")
                        except OSError:
                            # Only this transaction's unreferenced image is eligible
                            # for cleanup. A failed cleanup leaves a harmless orphan.
                            try:
                                published_image.unlink()
                            except OSError:
                                pass
                            raise
                    return {**entry, "idempotent": False}
            except VisionCaptureError:
                raise
            except OSError as exc:
                raise VisionCaptureError(507, "Capture publication failed") from exc
