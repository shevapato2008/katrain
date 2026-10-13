"""Server-owned configuration gates; no subprocess or GPU probes."""

import hashlib
import json

import pytest


@pytest.fixture
def configured(monkeypatch, tmp_path):
    from katrain.web.admin import vision_training_config as module

    root = tmp_path / "training"
    root.mkdir()
    (root / "weights").mkdir()
    weight = root / "weights" / "yolo11m.pt"
    weight.write_bytes(b"registered-test-weight")
    config = {
        "schema_version": 1,
        "verified": True,
        "root": str(root),
        "gpu_ids": ["1"],
        "weights": {"yolo11m": {"path": str(weight), "sha256": hashlib.sha256(weight.read_bytes()).hexdigest()}},
    }
    path = root / "training-config.json"
    path.write_text(json.dumps(config))
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_TRAINING", "1")
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_TRAINING_CONFIG", str(path))
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.importlib.metadata, "version", lambda package: "8.4.34")
    return module, path, config


@pytest.mark.parametrize(
    "environment,bind,switch,platform",
    [
        ("local", "127.0.0.1", "1", "linux"),
        ("prod", "127.0.0.1", "1", "linux"),
        ("test", "0.0.0.0", "1", "linux"),
        ("test", None, "1", "linux"),
        ("test", "127.0.0.1", "0", "linux"),
        ("test", "127.0.0.1", "1", "darwin"),
    ],
)
def test_unapproved_environment_never_creates_adapter(configured, monkeypatch, environment, bind, switch, platform):
    module, path, config = configured
    monkeypatch.setenv("KATRAIN_ADMIN_VISION_TRAINING", switch)
    monkeypatch.setattr(module.sys, "platform", platform)
    monkeypatch.setattr(module, "TrainingProcessAdapter", lambda: pytest.fail("disabled capability created adapter"))
    service = module.create_training_service(environment, bind)
    assert service.status()["enabled"] is False


def test_verified_fixed_local_config_can_enable_single_test_gpu_without_launch(configured):
    module, path, config = configured
    service = module.create_training_service("test", "127.0.0.1")
    assert service.status()["enabled"] is True
    assert service.status()["gpu_ids"] == ["1"]
    assert service.list_runs() == []
    service.close()


@pytest.mark.parametrize(
    "change",
    [{"verified": False}, {"schema_version": True}, {"gpu_ids": ["0,1"]}, {"root": "/"}, {"command": "unsafe"}],
)
def test_invalid_configuration_fails_closed(configured, change):
    module, path, config = configured
    path.write_text(json.dumps(config | change))
    assert module.create_training_service("test", "127.0.0.1").status()["enabled"] is False


def test_registered_weight_hash_is_checked_before_enabling(configured):
    module, path, config = configured
    config["weights"]["yolo11m"]["sha256"] = "0" * 64
    path.write_text(json.dumps(config))
    assert module.create_training_service("test", "127.0.0.1").status()["enabled"] is False
