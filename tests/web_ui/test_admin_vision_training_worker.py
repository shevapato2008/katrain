"""Real frozen files, injected model boundary; never load CUDA or start training."""

import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_admin_vision_dataset import builder, populate, session


@pytest.fixture
def worker_input(session, tmp_path):
    populate(session)
    dataset = builder(session).freeze(session[1]["game_id"])
    run_id = str(uuid4())
    run = tmp_path / "runs" / run_id
    run.mkdir(parents=True)
    weights = tmp_path / "registered.pt"
    weights.write_bytes(b"trusted-test-input")
    spec = {
        "run_id": run_id,
        "dataset_id": dataset["id"],
        "dataset_path": dataset["path"],
        "dataset_manifest_sha256": dataset["manifest_sha256"],
        "mode": "stones2",
        "class_names": ["black", "white"],
        "weights_id": "registered",
        "weights_path": str(weights),
        "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
        "augmentation": "stones-standard",
        "parameters": {
            "epochs": 2,
            "batch": 4,
            "imgsz": 640,
            "seed": 0,
            "device": "0",
            "project": str(run / "worker"),
            "name": "train",
            "augment": "default",
            "amp": False,
            "plots": False,
            "workers": 0,
            "code_version": "admin-vision-training-1",
        },
    }
    path = run / "spec.json"
    path.write_text(json.dumps(spec))
    return path, spec


class ModelBoundary:
    def __init__(self, *, bad_names=False, change_batch=False):
        self.calls = []
        self.bad_names = bad_names
        self.change_batch = change_batch

    def runtime(self, run, device):
        boundary = self

        class Model:
            def __init__(self, path):
                boundary.calls.append(str(path))
                self.names = {0: "black", 1: "wrong" if boundary.bad_names else "white"}
                self.callback = None

            def add_callback(self, event, callback):
                assert event == "on_fit_epoch_end"
                self.callback = callback

            def train(self, **kwargs):
                boundary.kwargs = kwargs
                assert kwargs["device"] == "0" and kwargs["batch"] == 4
                assert kwargs["amp"] is False and kwargs["plots"] is False and kwargs["workers"] == 0
                saved = Path(kwargs["project"]) / kwargs["name"]
                (saved / "weights").mkdir(parents=True)
                best = saved / "weights" / "best.pt"
                best.write_bytes(b"fake-readable-at-injected-model-boundary")
                actual = dict(kwargs)
                if boundary.change_batch:
                    actual["batch"] = 2
                self.trainer = SimpleNamespace(
                    args=SimpleNamespace(**actual),
                    epoch=0,
                    best=best,
                    save_dir=saved,
                    metrics={"metrics/mAP50(B)": 0.7},
                )
                self.callback(self.trainer)

        return "8.4.34", Model


def test_worker_validates_inputs_before_loading_any_model(worker_input):
    from katrain.web.admin.vision_training_worker import run_worker

    path, spec = worker_input
    Path(spec["weights_path"]).write_bytes(b"changed")
    boundary = ModelBoundary()
    with pytest.raises(RuntimeError, match="weight"):
        run_worker(path, runtime_factory=boundary.runtime)
    assert not boundary.calls
    assert not (path.parent / "output").exists()


def test_worker_publishes_only_verified_best_and_same_run_progress(worker_input):
    from katrain.web.admin.vision_training_worker import run_worker

    path, spec = worker_input
    boundary = ModelBoundary()
    run_worker(path, runtime_factory=boundary.runtime)
    output = path.parent / "output"
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["checkpoint_readable"] is True
    assert manifest["parameters"] == spec["parameters"]
    assert manifest["best_pt_sha256"] == hashlib.sha256((output / "best.pt").read_bytes()).hexdigest()
    assert manifest["schema_sha256"] == hashlib.sha256((output / "schema.json").read_bytes()).hexdigest()
    assert manifest["train_arguments"]["batch"] == 4
    progress = json.loads((path.parent / "progress.json").read_text())
    assert progress["run_id"] == spec["run_id"] and progress["epoch"] == 1
    assert progress["metrics"] == {"map50": 0.7, "precision": None, "recall": None}
    assert boundary.calls[0] == spec["weights_path"]
    assert boundary.calls[1].endswith("/worker/train/weights/best.pt")


@pytest.mark.parametrize("change", ["schema", "batch", "version", "dataset"])
def test_worker_never_writes_completion_for_mismatch(worker_input, change):
    from katrain.web.admin.vision_training_worker import run_worker

    path, spec = worker_input
    boundary = ModelBoundary(bad_names=change == "schema", change_batch=change == "batch")
    factory = boundary.runtime
    if change == "version":
        factory = lambda *args: ("9.0.0", boundary.runtime(*args)[1])
    if change == "dataset":
        Path(spec["dataset_path"]).joinpath("data.yaml").chmod(0o644)
        Path(spec["dataset_path"]).joinpath("data.yaml").write_text("download: https://untrusted.invalid/data\n")
    with pytest.raises(RuntimeError):
        run_worker(path, runtime_factory=factory)
    assert not (path.parent / "output" / "manifest.json").exists()


def test_physical_gpu_is_locked_before_first_cuda_query(monkeypatch, tmp_path):
    from katrain.web.admin import vision_training_worker as worker

    observed = []

    def cuda_ready():
        observed.append(os.environ.get("CUDA_VISIBLE_DEVICES"))
        assert observed[-1] == "1"
        return True

    callbacks = SimpleNamespace(add_integration_callbacks=lambda instance: None)
    data = SimpleNamespace(check_font=lambda *args: None)
    monkeypatch.setattr(worker.importlib.metadata, "version", lambda package: "8.4.34")
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=object))
    monkeypatch.setitem(sys.modules, "ultralytics.utils", SimpleNamespace(callbacks=callbacks))
    monkeypatch.setitem(sys.modules, "ultralytics.data", SimpleNamespace(utils=data))
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=cuda_ready, device_count=lambda: 1))
    )
    for key in ("CUDA_VISIBLE_DEVICES", "YOLO_CONFIG_DIR", "YOLO_OFFLINE", "YOLO_AUTOINSTALL"):
        monkeypatch.setenv(key, "unverified")
    assert worker._load_runtime(tmp_path, "1")[0] == "8.4.34"
    assert observed == ["1"]
