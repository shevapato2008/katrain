"""Trusted local model registry: fixed root, operator-written trust list, explicit load-checked activation."""

import hashlib
import json

import pytest


def _json(value):
    from katrain.web.admin.vision_dataset import _json

    return _json(value)


def write_model(root, run_id="run-a", mode="stones2", best=b"fake checkpoint bytes", imgsz=960):
    """A trained-model directory in the format training publishes (test bytes, not a real YOLO file)."""
    class_names = ["black", "white"] if mode == "stones2" else ["black", "white", "led_red", "led_green"]
    schema = _json({"schema_version": 1, "mode": mode, "class_names": class_names})
    parameters = {
        "epochs": 100,
        "batch": 8,
        "imgsz": imgsz,
        "seed": 0,
        "device": "0",
        "amp": True,
        "plots": False,
        "workers": 2,
    }
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "dataset_id": "dataset-" + run_id,
        "dataset_manifest_sha256": "d" * 64,
        "mode": mode,
        "class_names": class_names,
        "weights_id": "yolo11m",
        "weights_sha256": "w" * 64,
        "augmentation": "stones-standard",
        "parameters": parameters,
        "ultralytics_version": "8.4.34",
        "checkpoint_readable": True,
        "best_pt_sha256": hashlib.sha256(best).hexdigest(),
        "schema_sha256": hashlib.sha256(schema).hexdigest(),
        "train_arguments": parameters,
        "augmentation_actual": {"hsv_h": 0.015},
    }
    raw = _json(manifest)
    digest = hashlib.sha256(raw).hexdigest()
    model_id = "model-" + hashlib.sha256(_json({"run_id": run_id, "manifest_sha256": digest})).hexdigest()
    directory = root / model_id
    directory.mkdir(parents=True)
    (directory / "best.pt").write_bytes(best)
    (directory / "schema.json").write_bytes(schema)
    (directory / "manifest.json").write_bytes(raw)
    return model_id, digest


def trust(root, *entries):
    (root / "trusted.json").write_text(
        json.dumps({"schema_version": 1, "models": [{"model_id": m, "manifest_sha256": d} for m, d in entries]})
    )


class Loaded:
    def __init__(self, names, imgsz):
        self.names, self.imgsz = names, imgsz


class Loader:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.names = None

    def __call__(self, best_path, info):
        self.calls.append(info["id"])
        if self.fail:
            raise RuntimeError(self.fail)
        return Loaded(self.names or list(info["class_names"]), info["parameters"]["imgsz"])


@pytest.fixture
def registry(tmp_path):
    from katrain.web.admin.vision_models import VisionModelRegistry

    root = tmp_path / "models"
    root.mkdir()
    loader = Loader()
    return VisionModelRegistry(root, loader=loader), root, loader


def test_listing_shows_only_trusted_models_and_never_loads(registry):
    reg, root, loader = registry
    a = write_model(root, "run-a")
    b = write_model(root, "run-b", mode="led4")
    write_model(root, "run-untrusted")
    trust(root, a, b, ("model-" + "0" * 64, "e" * 64))
    listed = reg.list()
    by_id = {item["id"]: item for item in listed["models"]}
    assert set(by_id) == {a[0], b[0], "model-" + "0" * 64}
    assert by_id[a[0]]["valid"] is True and by_id[a[0]]["mode"] == "stones2"
    assert by_id[b[0]]["class_names"] == ["black", "white", "led_red", "led_green"]
    assert by_id["model-" + "0" * 64]["valid"] is False and by_id["model-" + "0" * 64]["error"]
    assert listed["current"] is None and listed["loaded_id"] is None
    assert loader.calls == []
    assert "path" not in json.dumps(listed) and str(root) not in json.dumps(listed)


def test_trust_entry_must_match_the_manifest_digest(registry):
    reg, root, _ = registry
    model_id, _ = write_model(root, "run-a")
    trust(root, (model_id, "f" * 64))
    item = reg.list()["models"][0]
    assert item["valid"] is False


def test_activation_verifies_weights_and_load_before_switching(registry):
    from katrain.web.admin.vision_models import VisionModelError

    reg, root, loader = registry
    a = write_model(root, "run-a")
    b = write_model(root, "run-b")
    trust(root, a, b)
    with pytest.raises(VisionModelError) as unknown:
        reg.activate("model-" + "1" * 64)
    assert unknown.value.status_code == 404
    reg.activate(a[0])
    assert reg.list()["current"] == a[0] and reg.loaded_id == a[0]

    (root / b[0] / "best.pt").chmod(0o644)
    (root / b[0] / "best.pt").write_bytes(b"tampered")
    with pytest.raises(VisionModelError) as tampered:
        reg.activate(b[0])
    assert tampered.value.status_code == 409
    assert reg.list()["current"] == a[0] and reg.loaded_id == a[0]
    assert loader.calls == [a[0]]  # tampered weights never reach the loader


def test_a_failed_load_keeps_current_previous_and_the_loaded_model(registry):
    from katrain.web.admin.vision_models import VisionModelError

    reg, root, loader = registry
    a, b, c = (write_model(root, run) for run in ("run-a", "run-b", "run-c"))
    trust(root, a, b, c)
    reg.activate(a[0])
    reg.activate(b[0])
    loader.names = ["white", "black"]  # checkpoint class order disagrees with its schema
    with pytest.raises(VisionModelError) as mismatch:
        reg.activate(c[0])
    assert mismatch.value.status_code == 409
    loader.names, loader.fail = None, "CUDA unavailable"
    with pytest.raises(VisionModelError):
        reg.activate(c[0])
    state = reg.list()
    assert (state["current"], state["previous"], state["loaded_id"]) == (b[0], a[0], b[0])
    assert state["load_error"]


def test_rollback_swaps_versions_and_state_survives_restart_without_loading(registry):
    from katrain.web.admin.vision_models import VisionModelError, VisionModelRegistry

    reg, root, loader = registry
    a, b = write_model(root, "run-a"), write_model(root, "run-b")
    trust(root, a, b)
    with pytest.raises(VisionModelError) as nothing:
        reg.rollback()
    assert nothing.value.status_code == 409
    reg.activate(a[0])
    reg.activate(b[0])
    reg.rollback()
    state = reg.list()
    assert (state["current"], state["previous"], state["loaded_id"]) == (a[0], b[0], a[0])
    fresh = VisionModelRegistry(root, loader=loader)
    restarted = fresh.list()
    assert (restarted["current"], restarted["previous"], restarted["loaded_id"]) == (a[0], b[0], None)


def test_symlinked_or_extra_files_are_not_trusted(registry, tmp_path):
    reg, root, _ = registry
    a = write_model(root, "run-a")
    (root / a[0] / "extra.txt").write_text("x")
    b = write_model(root, "run-b")
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"fake checkpoint bytes")
    (root / b[0] / "best.pt").unlink()
    (root / b[0] / "best.pt").symlink_to(outside)
    trust(root, a, b)
    assert [item["valid"] for item in reg.list()["models"]] == [False, False]


def test_model_routes_are_admin_only_confirmed_and_disabled_off_local(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.web_ui.test_admin_vision import PATH, headers, make_app

    monkeypatch.setenv("KATRAIN_MODE", "server")
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", "$2b$12$" + "a" * 53)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "vision-admin-secret-" * 3)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "local")
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LOCAL", "1")
    client = TestClient(make_app(tmp_path))
    runtime = client.app.state.vision_runtime
    runtime.out_dir = tmp_path / "vision"
    loader = Loader()
    runtime._model_loader = loader
    root = runtime.out_dir / "models"
    root.mkdir(parents=True)
    a = write_model(root, "run-a")
    trust(root, a)
    assert client.get(f"{PATH}/models").status_code == 401
    listed = client.get(f"{PATH}/models", headers=headers())
    assert listed.status_code == 200 and listed.headers["cache-control"] == "no-store"
    assert [item["id"] for item in listed.json()["models"]] == [a[0]]
    body = {"model_id": a[0], "confirmed": False}
    assert client.post(f"{PATH}/models/activate", json=body, headers=headers()).status_code == 409
    assert (
        client.post(
            f"{PATH}/models/activate", json={"model_id": "../x", "confirmed": True}, headers=headers()
        ).status_code
        == 422
    )
    activated = client.post(f"{PATH}/models/activate", json={**body, "confirmed": True}, headers=headers())
    assert activated.status_code == 200 and activated.json()["loaded_id"] == a[0]
    assert client.post(f"{PATH}/models/rollback", json={"confirmed": True}, headers=headers()).status_code == 409
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_LOCAL", "0")
    disabled = TestClient(make_app(tmp_path))
    assert disabled.get(f"{PATH}/models", headers=headers()).status_code == 403
