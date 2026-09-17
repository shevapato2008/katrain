"""Atomic persistence for one coherent hardware-vision generation.

Geometry and camera controls are committed together.  Readers follow only the
``current.json`` pointer, so they can never combine payloads from different
generations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, _auto_exposure_readback_matches
from katrain.vision.geometry_lock import NPZ_FIELDS, GeometryLock, load_geometry_lock, save_geometry_lock

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
GEOMETRY_FILENAME = "geometry_lock.npz"
GEOMETRY_SIDECAR_FILENAME = "geometry_lock.json"
PROFILE_FILENAME = "camera-profile.json"
MANIFEST_FILENAME = "manifest.json"
PAYLOAD_FILENAMES = (GEOMETRY_FILENAME, GEOMETRY_SIDECAR_FILENAME, PROFILE_FILENAME)

_GENERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GEOMETRY_ARRAY_SHAPES = {
    "corners": (4, 2),
    "points": (19, 19, 2),
    "xs": (19,),
    "ys": (19,),
    "M": (3, 3),
    "Minv": (3, 3),
    "baseline": (19, 19, 3),
}
_OPENCV_TRANSFORM_DTYPES = {np.dtype(np.float32), np.dtype(np.float64)}
_GEOMETRY_SIDECAR_FIELDS = {
    "confidence",
    "nmatch",
    "empty_black",
    "empty_white",
    "diag",
    "source_width",
    "source_height",
}


@dataclass(frozen=True)
class CameraProfile:
    """Camera identity, frame size, and verified native manual controls."""

    camera_device: str
    width: int
    height: int
    auto_exposure: float
    exposure: float
    schema_version: int = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "camera_device", _normalize_camera_device(self.camera_device))

        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

        auto_exposure = _finite_number("auto_exposure", self.auto_exposure)
        if not _auto_exposure_readback_matches(CAMERA_AUTO_EXPOSURE_MANUAL, auto_exposure):
            raise ValueError("auto_exposure must be native manual mode 1.0")
        object.__setattr__(self, "auto_exposure", CAMERA_AUTO_EXPOSURE_MANUAL)
        object.__setattr__(self, "exposure", _finite_number("exposure", self.exposure))

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "camera_device": self.camera_device,
            "width": self.width,
            "height": self.height,
            "auto_exposure": self.auto_exposure,
            "exposure": self.exposure,
        }

    @classmethod
    def from_json_dict(cls, value: Mapping[str, Any]) -> CameraProfile:
        expected = {
            "schema_version",
            "camera_device",
            "width",
            "height",
            "auto_exposure",
            "exposure",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("camera profile has unexpected fields")
        if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported camera profile schema")
        if not isinstance(value["camera_device"], str):
            raise ValueError("camera_device must be a string in persisted profiles")
        return cls(
            camera_device=value["camera_device"],
            width=value["width"],
            height=value["height"],
            auto_exposure=value["auto_exposure"],
            exposure=value["exposure"],
        )


@dataclass(frozen=True)
class HardwareVisionState:
    generation: str
    geometry: GeometryLock
    profile: CameraProfile


class HardwareVisionStateStore:
    """Store immutable generations and atomically select the current one."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.generations_dir = self.root / "generations"
        self.current_path = self.root / "current.json"

    def load_current(self, camera_device, width: int, height: int) -> HardwareVisionState | None:
        if not self.current_path.exists():
            return None
        try:
            pointer = _read_json_object(self.current_path)
            if set(pointer) != {"schema_version", "generation"}:
                raise ValueError("current pointer has unexpected fields")
            if type(pointer["schema_version"]) is not int or pointer["schema_version"] != SCHEMA_VERSION:
                raise ValueError("unsupported current pointer schema")
            generation = _validate_generation(pointer["generation"])
            expected_width, expected_height = _validate_dimensions(width, height)
            return self._load_generation(
                self.generations_dir / generation,
                generation,
                _normalize_camera_device(camera_device),
                expected_width,
                expected_height,
            )
        except Exception as exc:
            logger.warning("Ignoring invalid hardware vision state at %s: %s", self.root, exc)
            return None

    def commit(
        self,
        geometry: GeometryLock,
        profile: CameraProfile,
        generation: str | None = None,
        before_publish: Callable[[], None] | None = None,
    ) -> HardwareVisionState:
        if not isinstance(geometry, GeometryLock):
            raise TypeError("geometry must be a GeometryLock")
        if not isinstance(profile, CameraProfile):
            raise TypeError("profile must be a CameraProfile")

        generation = _validate_generation(generation if generation is not None else uuid.uuid4().hex)
        # Re-parse the public representation so commit never trusts a mutated or
        # manually-constructed profile instance.
        profile = CameraProfile.from_json_dict(profile.to_json_dict())

        self.generations_dir.mkdir(parents=True, exist_ok=True)
        final_dir = self.generations_dir / generation
        if final_dir.exists():
            raise FileExistsError(f"hardware vision generation already exists: {generation}")

        temp_dir = Path(tempfile.mkdtemp(prefix=f".{generation}.", suffix=".tmp", dir=self.generations_dir))
        promoted = False
        try:
            geometry_path = temp_dir / GEOMETRY_FILENAME
            save_geometry_lock(geometry, geometry_path)
            _fsync_file(geometry_path)
            _fsync_file(temp_dir / GEOMETRY_SIDECAR_FILENAME)

            profile_path = temp_dir / PROFILE_FILENAME
            _write_json_fsynced(profile_path, profile.to_json_dict())

            manifest = {
                "schema_version": SCHEMA_VERSION,
                "generation": generation,
                "sha256": {name: _sha256(temp_dir / name) for name in PAYLOAD_FILENAMES},
            }
            _write_json_fsynced(temp_dir / MANIFEST_FILENAME, manifest)

            verified = self._load_generation(
                temp_dir,
                generation,
                profile.camera_device,
                profile.width,
                profile.height,
            )
            _fsync_directory(temp_dir)
            os.replace(temp_dir, final_dir)
            promoted = True
            _fsync_directory(self.generations_dir)

            if before_publish is not None:
                before_publish()
            self._replace_current(generation)
            return verified
        finally:
            if not promoted:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _load_generation(
        self,
        generation_dir: Path,
        generation: str,
        camera_device: str,
        width: int,
        height: int,
    ) -> HardwareVisionState:
        if not generation_dir.is_dir():
            raise ValueError(f"generation directory is missing: {generation}")

        manifest = _read_json_object(generation_dir / MANIFEST_FILENAME)
        if set(manifest) != {"schema_version", "generation", "sha256"}:
            raise ValueError("manifest has unexpected fields")
        if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported manifest schema")
        if manifest["generation"] != generation or _validate_generation(manifest["generation"]) != generation:
            raise ValueError("manifest generation does not match current pointer")

        checksums = manifest["sha256"]
        if not isinstance(checksums, dict) or set(checksums) != set(PAYLOAD_FILENAMES):
            raise ValueError("manifest must hash exactly the generation payloads")
        for name in PAYLOAD_FILENAMES:
            expected_digest = checksums[name]
            if not isinstance(expected_digest, str) or not _SHA256_RE.fullmatch(expected_digest):
                raise ValueError(f"invalid sha256 for {name}")
            if _sha256(generation_dir / name) != expected_digest:
                raise ValueError(f"sha256 mismatch for {name}")

        profile = CameraProfile.from_json_dict(_read_json_object(generation_dir / PROFILE_FILENAME))
        if (profile.camera_device, profile.width, profile.height) != (camera_device, width, height):
            raise ValueError("camera profile does not match requested camera and resolution")
        geometry = _load_valid_geometry(generation_dir, profile)
        return HardwareVisionState(generation=generation, geometry=geometry, profile=profile)

    def _replace_current(self, generation: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".current.", suffix=".tmp", dir=self.root)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"schema_version": SCHEMA_VERSION, "generation": generation}, fh, sort_keys=True, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, self.current_path)
            temp_path = None
            try:
                _fsync_directory(self.root)
            except OSError as exc:
                # The pointer is already published.  Reporting this as a failed
                # commit would make callers roll runtime state back behind it.
                logger.warning("Hardware vision pointer published but directory fsync failed at %s: %s", self.root, exc)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _normalize_camera_device(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("camera_device must be an integer or string")
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("camera_device must not be empty")
    return normalized


def _validate_dimensions(width: Any, height: Any) -> tuple[int, int]:
    for name, value in (("width", width), ("height", height)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    return width, height


def _validate_generation(generation: Any) -> str:
    if not isinstance(generation, str) or not _GENERATION_RE.fullmatch(generation):
        raise ValueError("generation must be a safe basename")
    return generation


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _load_valid_geometry(generation_dir: Path, profile: CameraProfile) -> GeometryLock:
    geometry_path = generation_dir / GEOMETRY_FILENAME
    with np.load(geometry_path, allow_pickle=False) as archive:
        if set(archive.files) != set(NPZ_FIELDS):
            raise ValueError("geometry npz must contain exactly the expected fields")
        for name, expected_shape in _GEOMETRY_ARRAY_SHAPES.items():
            array = archive[name]
            if array.shape != expected_shape:
                raise ValueError(f"geometry field {name} has invalid shape")
            if name in {"M", "Minv"} and array.dtype not in _OPENCV_TRANSFORM_DTYPES:
                raise ValueError(f"geometry field {name} must be float32 or float64")
            if array.dtype.kind not in "iuf" or not np.isfinite(array).all():
                raise ValueError(f"geometry field {name} must contain finite numeric values")

        out_size = archive["out_size"]
        if out_size.shape != () or out_size.dtype.kind not in "iu" or int(out_size) <= 0:
            raise ValueError("geometry field out_size must be a positive integer")

    sidecar = _read_json_object(generation_dir / GEOMETRY_SIDECAR_FILENAME)
    if set(sidecar) != _GEOMETRY_SIDECAR_FIELDS:
        raise ValueError("geometry sidecar has unexpected fields")
    _finite_number("geometry sidecar confidence", sidecar["confidence"])
    for name in ("nmatch", "empty_black", "empty_white"):
        value = sidecar[name]
        if type(value) is not int or value < 0:
            raise ValueError(f"geometry sidecar {name} must be a non-negative integer")
    if not isinstance(sidecar["diag"], dict):
        raise ValueError("geometry sidecar diag must be an object")
    source_width, source_height = _validate_dimensions(sidecar["source_width"], sidecar["source_height"])
    if (source_width, source_height) != (profile.width, profile.height):
        raise ValueError("geometry source resolution does not match camera profile")

    return load_geometry_lock(geometry_path)


def _write_json_fsynced(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as fh:
        json.dump(value, fh, sort_keys=True, indent=2, allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as fh:
        os.fsync(fh.fileno())


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
