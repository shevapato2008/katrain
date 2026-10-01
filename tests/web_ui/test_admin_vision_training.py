"""Local lifecycle and real frozen bytes; no process, network, torch or GPU."""

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from test_admin_vision_dataset import populate, session


class FakeWorker:
    def __init__(self):
        self.starts = []
        self.observation = None
        self.cancelled = []
        self.start_error = None

    def start(self, run_id, run_dir, spec):
        if self.start_error:
            raise self.start_error
        handle = object()
        self.starts.append((run_id, run_dir, spec, handle))
        return handle

    def observe(self, handle):
        from katrain.web.admin.vision_training import TrainingObservation

        return self.observation or TrainingObservation(self.starts[-1][0])

    def cancel(self, handle):
        self.cancelled.append(handle)


@pytest.fixture
def setup(session, tmp_path):
    from katrain.web.admin.vision_dataset import VisionDatasetBuilder
    from katrain.web.admin.vision_training import RegisteredWeights, TrainingConfig

    root = tmp_path / "training"
    root.mkdir()
    populate(session)
    version = VisionDatasetBuilder(session[0], output_root=root / "datasets").freeze(session[1]["game_id"])
    weights = root / "trusted.pt"
    weights.write_bytes(b"test registered weight; never a real checkpoint")
    config = TrainingConfig(
        root=root,
        enabled=True,
        environment="test",
        verified=True,
        gpu_ids=("0",),
        weights={"trusted": RegisteredWeights(weights, hashlib.sha256(weights.read_bytes()).hexdigest())},
    )
    request = dict(
        request_id=str(uuid.uuid4()),
        dataset_id=version["id"],
        dataset_manifest_sha256=version["manifest_sha256"],
        weights_id="trusted",
        augmentation="stones-standard",
        gpu_id="0",
        epochs=100,
        batch=8,
        imgsz=960,
        seed=0,
    )
    return config, request, FakeWorker(), version


def service(setup, **changes):
    from katrain.web.admin.vision_training import VisionTrainingCoordinator

    config, _, worker, _ = setup
    return VisionTrainingCoordinator(config=replace(config, **changes), adapter=worker)


def test_disabled_local_unverified_and_unconfirmed_never_start(setup):
    from katrain.web.admin.vision_training import VisionTrainingError

    for changes in ({"enabled": False}, {"environment": "local"}, {"verified": False}, {"gpu_ids": ()}):
        trainer = service(setup, **changes)
        assert trainer.status()["enabled"] is False
        assert trainer.status()["gpu_ids"] == []
        with pytest.raises(VisionTrainingError):
            trainer.start(setup[1], confirmed=True)
    with pytest.raises(VisionTrainingError):
        service(setup).start(setup[1], confirmed=False)
    assert setup[2].starts == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("dataset_id", "../outside"),
        ("weights_id", "/tmp/model.pt"),
        ("gpu_id", "0,1"),
        ("epochs", True),
        ("epochs", 301),
        ("batch", -1),
        ("imgsz", 1280),
        ("seed", -1),
        ("request_id", "not-uuid"),
        ("augmentation", "led-safe"),
        ("command", "train"),
    ],
)
def test_untrusted_input_refuses_before_start(setup, key, value):
    from katrain.web.admin.vision_training import VisionTrainingError

    with pytest.raises(VisionTrainingError):
        service(setup).start({**setup[1], key: value}, confirmed=True)
    assert setup[2].starts == []


def test_frozen_assets_and_final_registered_weight_hash_must_match(setup):
    from katrain.web.admin.vision_training import VisionTrainingError

    trainer = service(setup)
    with pytest.raises(VisionTrainingError):
        trainer.start({**setup[1], "dataset_manifest_sha256": "0" * 64}, confirmed=True)
    setup[0].weights["trusted"].path.write_bytes(b"changed")
    with pytest.raises(VisionTrainingError):
        trainer.start(setup[1], confirmed=True)
    setup[0].weights["trusted"].path.unlink()
    with pytest.raises(VisionTrainingError):
        trainer.start(setup[1], confirmed=True)
    assert setup[2].starts == []


def test_corrupt_yaml_and_capacity_refuse_before_start(setup, monkeypatch):
    from katrain.web.admin.vision_training import VisionTrainingError

    trainer = service(setup)
    monkeypatch.setattr(
        "katrain.web.admin.vision_training.shutil.disk_usage", lambda root: type("Usage", (), {"free": 1})()
    )
    with pytest.raises(VisionTrainingError):
        trainer.start(setup[1], confirmed=True)
    monkeypatch.undo()
    yaml = Path(setup[3]["path"]) / "data.yaml"
    yaml.chmod(0o644)
    yaml.write_text("download: https://invalid.example/file")
    with pytest.raises(VisionTrainingError):
        trainer.start(setup[1], confirmed=True)
    assert setup[2].starts == []


def test_request_uuid_binds_exact_input_and_one_active_run(setup):
    from katrain.web.admin.vision_training import VisionTrainingError

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    assert run["state"] == "running"
    assert trainer.start(setup[1], confirmed=True)["id"] == run["id"]
    assert len(setup[2].starts) == 1
    with pytest.raises(VisionTrainingError, match="request"):
        trainer.start({**setup[1], "batch": 4}, confirmed=True)
    with pytest.raises(VisionTrainingError, match="busy"):
        trainer.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)
    spec = setup[2].starts[0][2]
    assert Path(spec["weights_path"]).is_absolute()
    assert spec["parameters"]["device"] == "0" and spec["parameters"]["amp"] is False


def test_start_failure_is_persisted_and_unknown_group_stays_busy(setup):
    from katrain.web.admin.vision_training import TrainingStartError, VisionTrainingError

    setup[2].start_error = TrainingStartError("not launched", group_exited=True)
    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    assert run["state"] == "failed" and trainer.status()["active_run_id"] is None
    setup[2].start_error = OSError("launch result unknown")
    run = trainer.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)
    assert run["state"] == "interrupted"
    with pytest.raises(VisionTrainingError, match="busy"):
        trainer.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)


def test_prepare_is_pure_and_needs_no_capture_coordinator(setup):
    from katrain.web.admin.vision_transfer import prepare_frozen_dataset

    plan = prepare_frozen_dataset(setup[0].root / "datasets", setup[1]["dataset_id"])
    assert plan.manifest_sha256 == setup[1]["dataset_manifest_sha256"]


def output(worker):
    """A fake adapter attestation, not a claim these bytes are a real YOLO model."""
    from katrain.web.admin.vision_dataset import _json

    run_id, directory, spec, _ = worker.starts[-1]
    target = directory / "output"
    target.mkdir()
    best = b"fake adapter checked this test-only checkpoint"
    schema = _json({"schema_version": 1, "mode": spec["mode"], "class_names": spec["class_names"]})
    (target / "best.pt").write_bytes(best)
    (target / "schema.json").write_bytes(schema)
    manifest = {
        key: spec[key]
        for key in (
            "run_id",
            "dataset_id",
            "dataset_manifest_sha256",
            "mode",
            "class_names",
            "weights_id",
            "weights_sha256",
            "augmentation",
            "parameters",
        )
    }
    manifest.update(
        schema_version=1,
        ultralytics_version="8.4.34",
        checkpoint_readable=True,
        best_pt_sha256=hashlib.sha256(best).hexdigest(),
        schema_sha256=hashlib.sha256(schema).hexdigest(),
        train_arguments={
            key: value for key, value in spec["parameters"].items() if key not in ("augment", "code_version")
        },
        augmentation_actual={"hsv_h": 0.015},
    )
    (target / "manifest.json").write_bytes(_json(manifest))
    return target, manifest


def test_same_run_metrics_and_bounded_log_are_real_observations(setup):
    from katrain.web.admin.vision_training import (
        TrainingObservation,
        VisionTrainingError,
        MAX_LOG_BYTES,
        LOG_TAIL_BYTES,
    )

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    setup[2].observation = TrainingObservation(
        str(uuid.uuid4()), epoch=12, metrics={"map50": 0.9, "precision": 0.8, "recall": 0.7}
    )
    with pytest.raises(VisionTrainingError):
        trainer.get_run(run["id"])
    setup[2].observation = TrainingObservation(
        run["id"],
        epoch=12,
        metrics={"map50": 0.9, "precision": 0.8, "recall": 0.7},
        log_chunk="x" * (MAX_LOG_BYTES + 99) + "END",
    )
    observed = trainer.get_run(run["id"])
    assert observed["epoch"] == 12 and observed["metrics"]["map50"] == 0.9
    assert len(observed["log_tail"].encode()) <= LOG_TAIL_BYTES
    assert (setup[0].root / "runs" / run["id"] / "worker.log").stat().st_size <= MAX_LOG_BYTES


def test_cancel_does_not_release_until_owned_group_confirmed_exited(setup):
    from katrain.web.admin.vision_training import TrainingObservation, VisionTrainingError

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    with pytest.raises(VisionTrainingError):
        trainer.cancel(run["id"], confirmed=False)
    assert trainer.cancel(run["id"], confirmed=True)["state"] == "cancelling"
    assert setup[2].cancelled == [setup[2].starts[-1][3]]
    setup[2].observation = TrainingObservation(run["id"], exit_code=0, group_exited=False)
    assert trainer.get_run(run["id"])["state"] == "cancelling"
    with pytest.raises(VisionTrainingError, match="busy"):
        trainer.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)
    setup[2].observation = TrainingObservation(run["id"], exit_code=0, group_exited=True)
    assert trainer.get_run(run["id"])["state"] == "cancelled"
    assert trainer.status()["active_run_id"] is None
    assert trainer.list_models() == []


def test_restart_interrupted_cannot_take_over_or_release_unknown_group(setup):
    from katrain.web.admin.vision_training import VisionTrainingError

    run = service(setup).start(setup[1], confirmed=True)
    recovered = service(setup)
    assert recovered.get_run(run["id"])["state"] == "interrupted"
    with pytest.raises(VisionTrainingError, match="busy"):
        recovered.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)
    with pytest.raises(VisionTrainingError):
        recovered.cancel(run["id"], confirmed=True)
    assert setup[2].cancelled == []


def test_success_requires_attested_schema_parameters_and_atomic_hashed_model(setup):
    from katrain.web.admin.vision_training import TrainingObservation

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    source, manifest = output(setup[2])
    setup[2].observation = TrainingObservation(run["id"], epoch=100, exit_code=0, group_exited=True)
    finished = trainer.get_run(run["id"])
    assert finished["state"] == "completed" and finished["model_id"]
    model = trainer.list_models()[0]
    assert (
        model["run_id"] == run["id"]
        and model["manifest_sha256"] == hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    )
    directory = setup[0].root / "models" / model["id"]
    assert (directory / "best.pt").read_bytes() == (source / "best.pt").read_bytes()
    assert model["weights_sha256"] == manifest["best_pt_sha256"]
    assert all(path.stat().st_mode & 0o222 == 0 for path in directory.iterdir())
    # A later failed run never alters the immutable previous version.
    old = {p.name: p.read_bytes() for p in directory.iterdir()}
    second = trainer.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)
    setup[2].observation = TrainingObservation(second["id"], exit_code=1, group_exited=True)
    assert trainer.get_run(second["id"])["state"] == "failed"
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == old


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "checkpoint_readable",
        "imgsz",
        "class_names",
        "weights_sha256",
        "augmentation_actual",
        "train_arguments",
        "symlink",
        "schema_version",
    ],
)
def test_exit_zero_never_bypasses_artifact_and_actual_parameter_checks(setup, damage):
    from katrain.web.admin.vision_training import TrainingObservation

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    target, manifest = output(setup[2])
    if damage == "missing":
        (target / "best.pt").unlink()
    elif damage == "symlink":
        (target / "best.pt").unlink()
        (target / "best.pt").symlink_to(setup[0].weights["trusted"].path)
    else:
        if damage == "imgsz":
            manifest["parameters"]["imgsz"] = 640
        elif damage == "train_arguments":
            manifest["train_arguments"]["batch"] = 4
        elif damage == "schema_version":
            manifest["schema_version"] = True
        else:
            manifest[damage] = (
                False
                if damage == "checkpoint_readable"
                else [] if damage in ("class_names", "augmentation_actual") else "bad"
            )
        (target / "manifest.json").write_text(json.dumps(manifest))
    setup[2].observation = TrainingObservation(run["id"], exit_code=0, group_exited=True, log_chunk="training complete")
    assert trainer.get_run(run["id"])["state"] == "failed"
    assert trainer.list_models() == []


def test_failed_atomic_publication_preserves_worker_artifacts(setup, monkeypatch):
    from katrain.web.admin.vision_training import TrainingObservation

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    target, _ = output(setup[2])
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    monkeypatch.setattr(
        "katrain.web.admin.vision_training.os.rename", lambda *args: (_ for _ in ()).throw(OSError("publish failed"))
    )
    setup[2].observation = TrainingObservation(run["id"], exit_code=0, group_exited=True)
    assert trainer.get_run(run["id"])["state"] == "failed"
    assert trainer.list_models() == []
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before


def test_root_lease_excludes_second_coordinator_and_post_launch_save_failure_stays_busy(setup, monkeypatch):
    from katrain.web.admin.vision_training import VisionTrainingError

    owner = service(setup)
    second = service(setup)
    with pytest.raises(VisionTrainingError, match="lease"):
        second.start(setup[1], confirmed=True)
    save = owner._save

    def fail_after_launch(run):
        if run["state"] == "running":
            raise OSError("state disk failure")
        save(run)

    monkeypatch.setattr(owner, "_save", fail_after_launch)
    with pytest.raises(VisionTrainingError):
        owner.start(setup[1], confirmed=True)
    assert owner.active_run_id in owner.handles
    with pytest.raises(VisionTrainingError, match="busy"):
        owner.start({**setup[1], "request_id": str(uuid.uuid4())}, confirmed=True)


def test_read_methods_use_verified_metadata_and_close_does_not_claim_process_exit(setup):
    from katrain.web.admin.vision_training import VisionTrainingCoordinator, VisionTrainingError

    disabled = VisionTrainingCoordinator()
    assert disabled.status()["state"] == "unknown"
    with pytest.raises(VisionTrainingError):
        disabled.list_datasets()
    trainer = service(setup)
    dataset = trainer.list_datasets()[0]
    assert dataset["manifest_sha256"] == setup[1]["dataset_manifest_sha256"]
    assert dataset["train_count"] == 2 and dataset["val_count"] == 1
    assert dataset["class_names"] == ["black", "white"]
    presets = trainer.presets()
    assert presets["weights"][0]["id"] == "trusted"
    assert "path" not in presets["weights"][0]
    run = trainer.start(setup[1], confirmed=True)
    assert trainer.list_runs()[0]["id"] == run["id"]
    trainer.close()
    with pytest.raises(VisionTrainingError):
        trainer.start(setup[1], confirmed=True)
    restarted = service(setup)
    assert restarted.get_run(run["id"])["state"] == "interrupted"
    assert restarted.status()["active_run_id"] == run["id"]
    assert setup[2].cancelled == []


def test_replay_types_observation_failure_and_adapter_owned_log_fail_closed(setup, monkeypatch):
    from katrain.web.admin.vision_training import TrainingObservation, VisionTrainingError

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    with pytest.raises(VisionTrainingError):
        trainer.start({**setup[1], "seed": False}, confirmed=True)
    setup[2].persists_log = True
    log = setup[0].root / "runs" / run["id"] / "worker.log"
    log.write_text("adapter saved once")
    setup[2].observation = TrainingObservation(run["id"], log_chunk="adapter saved once")
    assert trainer.get_run(run["id"])["log_tail"] == "adapter saved once"
    assert log.read_text() == "adapter saved once"
    monkeypatch.setattr(setup[2], "observe", lambda handle: (_ for _ in ()).throw(RuntimeError("unverified process")))
    with pytest.raises(VisionTrainingError) as error:
        trainer.get_run(run["id"])
    assert error.value.status_code == 503 and trainer.status()["active_run_id"] == run["id"]


def test_invalid_persisted_lifecycle_stays_unverified_and_concurrent_starts_have_one_owner(setup):
    from concurrent.futures import ThreadPoolExecutor
    from katrain.web.admin.vision_training import VisionTrainingError

    trainer = service(setup)

    def start(request_id):
        try:
            return trainer.start({**setup[1], "request_id": request_id}, confirmed=True)
        except VisionTrainingError as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, [str(uuid.uuid4()), str(uuid.uuid4())]))
    assert len(setup[2].starts) == 1 and results.count(409) == 1
    trainer.close()
    path = setup[0].root / "runs" / setup[2].starts[0][0] / "state.json"
    record = json.loads(path.read_bytes())
    record["state"] = "unknown-invalid-state"
    path.write_text(json.dumps(record))
    recovered = service(setup)
    with pytest.raises(VisionTrainingError) as error:
        recovered.start(setup[1], confirmed=True)
    assert error.value.status_code == 503


def test_cancel_persistence_failure_retains_running_and_retry_reaches_owned_adapter(setup, monkeypatch):
    from katrain.web.admin.vision_training import VisionTrainingError

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    save = trainer._save
    monkeypatch.setattr(trainer, "_save", lambda run: (_ for _ in ()).throw(OSError("disk error")))
    with pytest.raises(VisionTrainingError) as error:
        trainer.cancel(run["id"], confirmed=True)
    assert error.value.status_code == 503
    assert trainer.runs[run["id"]]["state"] == "running"
    assert setup[2].cancelled == [] and trainer.active_run_id == run["id"]
    monkeypatch.setattr(trainer, "_save", save)
    assert trainer.cancel(run["id"], confirmed=True)["state"] == "cancelling"
    assert setup[2].cancelled == [setup[2].starts[-1][3]]


def test_terminal_persistence_failure_does_not_claim_exit_and_retry_can_release(setup, monkeypatch):
    from katrain.web.admin.vision_training import TrainingObservation, VisionTrainingError

    trainer = service(setup)
    run = trainer.start(setup[1], confirmed=True)
    trainer.cancel(run["id"], confirmed=True)
    setup[2].observation = TrainingObservation(run["id"], exit_code=0, group_exited=True)
    save = trainer._save
    monkeypatch.setattr(trainer, "_save", lambda run: (_ for _ in ()).throw(OSError("disk error")))
    with pytest.raises(VisionTrainingError) as error:
        trainer.get_run(run["id"])
    assert error.value.status_code == 503 and trainer.runs[run["id"]]["state"] == "cancelling"
    assert trainer.active_run_id == run["id"] and run["id"] in trainer.handles
    with pytest.raises(VisionTrainingError):
        trainer.get_run(run["id"])
    monkeypatch.setattr(trainer, "_save", save)
    assert trainer.get_run(run["id"])["state"] == "cancelled"
    assert trainer.active_run_id is None and run["id"] not in trainer.handles
