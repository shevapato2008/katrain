"""Tests for atomic, generation-based hardware vision state persistence."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from katrain.vision.geometry_lock import GeometryLock


def _state_module():
    try:
        return importlib.import_module("katrain.web.core.hardware_vision_state")
    except ModuleNotFoundError as exc:
        pytest.fail(f"hardware vision state store is not implemented: {exc}")


def _geometry() -> GeometryLock:
    return GeometryLock(
        corners=np.array([[0, 0], [639, 0], [639, 479], [0, 479]], dtype=np.float32),
        points=np.zeros((19, 19, 2), dtype=np.float32),
        xs=np.linspace(0, 639, 19, dtype=np.float32),
        ys=np.linspace(0, 479, 19, dtype=np.float32),
        M=np.eye(3, dtype=np.float64),
        Minv=np.eye(3, dtype=np.float64),
        out_size=950,
        baseline=np.zeros((19, 19, 3), dtype=np.float32),
        confidence=0.97,
        nmatch=18,
        source_width=640,
        source_height=480,
    )


def _profile(module, **overrides):
    values = {
        "camera_device": "/dev/video73",
        "width": 640,
        "height": 480,
        "auto_exposure": 1.005,
        "exposure": 432.0,
    }
    values.update(overrides)
    return module.CameraProfile(**values)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_round_trip_loads_one_complete_generation(tmp_path):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)

    committed = store.commit(_geometry(), _profile(module), generation="generation-1")
    loaded = store.load_current("/dev/video73", 640, 480)

    assert committed.generation == "generation-1"
    assert loaded is not None
    assert loaded.generation == committed.generation
    assert loaded.profile.camera_device == "/dev/video73"
    assert loaded.profile.auto_exposure == 1.0
    assert loaded.profile.exposure == 432.0
    assert loaded.geometry.confidence == pytest.approx(0.97)
    np.testing.assert_array_equal(loaded.geometry.corners, committed.geometry.corners)


@pytest.mark.parametrize(
    "device,width,height",
    [
        ("/dev/video74", 640, 480),
        ("/dev/video73", 1280, 480),
        ("/dev/video73", 640, 720),
        (73, 640, 480),
    ],
)
def test_load_requires_matching_normalized_device_and_resolution(tmp_path, device, width, height):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)
    store.commit(_geometry(), _profile(module), generation="generation-1")

    loaded = store.load_current(device, width, height)

    assert loaded is None  # Integer 73 normalizes to "73", distinct from "/dev/video73".


def test_integer_camera_device_is_normalized_to_string(tmp_path):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)
    profile = _profile(module, camera_device=73)
    store.commit(_geometry(), profile, generation="generation-1")

    loaded = store.load_current(73, 640, 480)

    assert loaded is not None
    assert loaded.profile.camera_device == "73"


@pytest.mark.parametrize("current_contents", ["not json", '{"schema_version": 1, "generation": "../escape"}'])
def test_corrupt_or_unsafe_current_pointer_is_rejected(tmp_path, current_contents):
    module = _state_module()
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "current.json").write_text(current_contents, encoding="utf-8")

    assert module.HardwareVisionStateStore(tmp_path).load_current("/dev/video73", 640, 480) is None


def test_payload_checksum_mismatch_is_rejected(tmp_path):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)
    committed = store.commit(_geometry(), _profile(module), generation="generation-1")
    profile_path = tmp_path / "generations" / committed.generation / "camera-profile.json"
    profile_path.write_text("{}", encoding="utf-8")

    assert store.load_current("/dev/video73", 640, 480) is None


def test_failed_current_pointer_replace_preserves_previous_generation(tmp_path, monkeypatch):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)
    first_profile = _profile(module, exposure=100.0)
    store.commit(_geometry(), first_profile, generation="generation-1")
    real_replace = module.os.replace

    def fail_pointer_replace(source, destination):
        if Path(destination) == tmp_path / "current.json":
            raise OSError("injected pointer replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_pointer_replace)

    with pytest.raises(OSError, match="injected pointer"):
        store.commit(_geometry(), _profile(module, exposure=200.0), generation="generation-2")

    loaded = store.load_current("/dev/video73", 640, 480)
    assert loaded is not None
    assert loaded.generation == "generation-1"
    assert loaded.profile.exposure == 100.0


def test_generation_contains_sidecar_and_manifest_hashes_all_payloads(tmp_path):
    module = _state_module()
    store = module.HardwareVisionStateStore(tmp_path)
    committed = store.commit(_geometry(), _profile(module), generation="generation-1")
    generation_dir = tmp_path / "generations" / committed.generation
    payload_names = {"geometry_lock.npz", "geometry_lock.json", "camera-profile.json"}

    assert payload_names <= {path.name for path in generation_dir.iterdir()}
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["generation"] == committed.generation
    assert set(manifest["sha256"]) == payload_names
    assert manifest["sha256"] == {name: _sha256(generation_dir / name) for name in payload_names}


@pytest.mark.parametrize(
    "overrides",
    [
        {"auto_exposure": 3.0},
        {"auto_exposure": float("nan")},
        {"exposure": float("inf")},
        {"width": 0},
        {"height": -1},
    ],
)
def test_camera_profile_rejects_invalid_controls_and_resolution(overrides):
    module = _state_module()

    with pytest.raises(ValueError):
        _profile(module, **overrides)


def test_camera_profile_json_is_strict():
    module = _state_module()
    valid = _profile(module).to_json_dict()

    with pytest.raises(ValueError):
        module.CameraProfile.from_json_dict({**valid, "unknown": True})
    with pytest.raises(ValueError):
        module.CameraProfile.from_json_dict({**valid, "schema_version": 2})


@pytest.mark.parametrize("generation", ["", ".", "..", "../escape", "nested/name", "/absolute"])
def test_commit_rejects_unsafe_generation_names(tmp_path, generation):
    module = _state_module()

    with pytest.raises(ValueError):
        module.HardwareVisionStateStore(tmp_path).commit(_geometry(), _profile(module), generation=generation)
