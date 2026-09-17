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
from typing import Any, Mapping

from katrain.vision.camera import CAMERA_AUTO_EXPOSURE_MANUAL, _auto_exposure_readback_matches
from katrain.vision.geometry_lock import GeometryLock, load_geometry_lock, save_geometry_lock

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
GEOMETRY_FILENAME = "geometry_lock.npz"
GEOMETRY_SIDECAR_FILENAME = "geometry_lock.json"
PROFILE_FILENAME = "camera-profile.json"
MANIFEST_FILENAME = "manifest.json"
PAYLOAD_FILENAMES = (GEOMETRY_FILENAME, GEOMETRY_SIDECAR_FILENAME, PROFILE_FILENAME)

_GENERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


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
        if self.camera_device is None or isinstance(self.camera_device, bool):
            raise ValueError("camera_device must identify a camera")
        camera_device = str(self.camera_device)
        if not camera_device:
            raise ValueError("camera_device must not be empty")
        object.__setattr__(self, "camera_device", camera_device)

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
                str(camera_device),
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

        # The geometry loader intentionally tolerates old/broken sidecars.  A
        # generation sidecar is mandatory, so parse it explicitly before load.
        _read_json_object(generation_dir / GEOMETRY_SIDECAR_FILENAME)
        profile = CameraProfile.from_json_dict(_read_json_object(generation_dir / PROFILE_FILENAME))
        if (profile.camera_device, profile.width, profile.height) != (camera_device, width, height):
            raise ValueError("camera profile does not match requested camera and resolution")
        geometry = load_geometry_lock(generation_dir / GEOMETRY_FILENAME)
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
            _fsync_directory(self.root)
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
