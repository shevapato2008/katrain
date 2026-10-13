"""Dedicated, explicitly launched training worker. Importing this module loads no CUDA.

Compatibility is pinned to the inspected Ultralytics version. OFFLINE is not an
OS network sandbox; only trusted local inputs are accepted here.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from katrain.vision.tools.train_model import LED_SAFE_AUG, build_train_kwargs

VERSION = "8.4.34"
MAX_MODEL_BYTES = 1024**3
MAX_JSON_BYTES = 64 * 1024


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_JSON_BYTES:
        raise RuntimeError("Invalid worker JSON input")
    return json.loads(path.read_bytes())


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def _atomic_json(path, value):
    data = _json_bytes(value)
    if len(data) > MAX_JSON_BYTES:
        raise RuntimeError("Worker JSON exceeds its size budget")
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _validate_input(path, spec):
    from katrain.web.admin.vision_transfer import prepare_frozen_dataset

    run = path.parent
    try:
        if str(UUID(spec["run_id"])) != run.name or spec["run_id"] != run.name:
            raise ValueError("Invalid run ID")
        parameters = spec["parameters"]
        for key, low, high in (("epochs", 1, 300), ("seed", 0, 2147483647)):
            if type(parameters[key]) is not int or not low <= parameters[key] <= high:
                raise ValueError("Invalid numeric parameter")
        if type(parameters["batch"]) is not int or parameters["batch"] not in (4, 8):
            raise ValueError("Invalid fixed batch")
        if type(parameters["imgsz"]) is not int or parameters["imgsz"] not in (640, 960):
            raise ValueError("Invalid image size")
        expected_augment = {"stones2": "default", "led4": "led-safe"}[spec["mode"]]
        expected_preset = {"stones2": "stones-standard", "led4": "led-safe"}[spec["mode"]]
        if (
            parameters["project"] != str(run / "worker")
            or parameters["name"] != "train"
            or parameters["amp"] is not False
            or parameters["plots"] is not False
            or type(parameters["workers"]) is not int
            or parameters["workers"] != 0
            or parameters["code_version"] != "admin-vision-training-1"
            or parameters["augment"] != expected_augment
            or spec["augmentation"] != expected_preset
            or not isinstance(parameters["device"], str)
            or not parameters["device"].isascii()
            or not parameters["device"].isdigit()
            or len(parameters["device"]) > 2
        ):
            raise ValueError("Invalid fixed worker parameters")
        dataset = Path(spec["dataset_path"])
        if not dataset.is_absolute() or str(dataset.resolve()) != str(dataset):
            raise ValueError("Invalid dataset path")
        plan = prepare_frozen_dataset(dataset.parent, spec["dataset_id"])
        manifest = json.loads((dataset / "manifest.json").read_bytes())
        if (
            plan.directory != dataset
            or plan.manifest_sha256 != spec["dataset_manifest_sha256"]
            or manifest["mode"] != spec["mode"]
            or manifest["class_names"] != spec["class_names"]
        ):
            raise ValueError("Dataset manifest differs from run input")
    except (KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
        raise RuntimeError("Worker dataset/parameter validation failed") from exc
    weights = Path(spec["weights_path"])
    if (
        not weights.is_absolute()
        or str(weights.resolve()) != str(weights)
        or not weights.is_file()
        or weights.suffix != ".pt"
        or not 0 < weights.stat().st_size <= MAX_MODEL_BYTES
        or _digest(weights) != spec["weights_sha256"]
    ):
        raise RuntimeError("Worker weight validation failed")


def _load_runtime(run, device):
    # This function runs only in the dedicated process, never in ASGI.
    if importlib.metadata.version("ultralytics") != VERSION:
        raise RuntimeError("Unverified Ultralytics version")
    os.environ.update(
        CUDA_VISIBLE_DEVICES=device,
        YOLO_CONFIG_DIR=str(run / "yolo-config"),
        YOLO_OFFLINE="true",
        YOLO_AUTOINSTALL="false",
    )
    from ultralytics.utils import callbacks
    from ultralytics.data import utils as data_utils

    callbacks.add_integration_callbacks = lambda instance: None
    data_utils.check_font = lambda *args, **kwargs: None  # plots=False; no font download needed
    import torch
    from ultralytics import YOLO

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Reserved CUDA device is unavailable; no CPU/MPS fallback")
    return VERSION, YOLO


def _metric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def run_worker(spec_path, *, runtime_factory=None):
    path = Path(spec_path).absolute()
    if path.name != "spec.json" or str(path.resolve()) != str(path):
        raise RuntimeError("Invalid worker spec path")
    spec = _read_json(path)
    _validate_input(path, spec)
    run, parameters = path.parent, spec["parameters"]
    version, model_factory = (runtime_factory or _load_runtime)(run, parameters["device"])
    if version != VERSION:
        raise RuntimeError("Unverified Ultralytics version")
    # Write a controlled local YAML without altering immutable dataset bytes.
    import yaml

    data = {
        "path": spec["dataset_path"],
        "train": "images/train",
        "val": "images/val",
        "nc": len(spec["class_names"]),
        "names": spec["class_names"],
    }
    yaml_path = run / "training-data.yaml"
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))
    args = SimpleNamespace(**parameters, data=str(yaml_path), patience=20, cache=False)
    kwargs = build_train_kwargs(args)
    kwargs.update(amp=False, plots=False, workers=0)
    model = model_factory(spec["weights_path"])

    def progress(trainer):
        metrics = trainer.metrics or {}
        _atomic_json(
            run / "progress.json",
            {
                "run_id": spec["run_id"],
                "epoch": int(trainer.epoch) + 1,
                "metrics": {
                    "map50": _metric(metrics.get("metrics/mAP50(B)")),
                    "precision": _metric(metrics.get("metrics/precision(B)")),
                    "recall": _metric(metrics.get("metrics/recall(B)")),
                },
            },
        )

    model.add_callback("on_fit_epoch_end", progress)
    model.train(**kwargs)
    trainer = model.trainer
    actual = vars(trainer.args)
    for key in ("epochs", "batch", "imgsz", "seed", "device", "project", "name", "amp", "plots", "workers"):
        if actual.get(key) != parameters[key]:
            raise RuntimeError(f"Actual training parameter mismatch: {key}")
    if parameters["augment"] == "led-safe" and any(actual.get(key) != value for key, value in LED_SAFE_AUG.items()):
        raise RuntimeError("Actual augmentation differs from selected preset")
    expected_dir = run / "worker" / "train"
    best = expected_dir / "weights" / "best.pt"
    if (
        Path(trainer.save_dir) != expected_dir
        or Path(trainer.best) != best
        or not best.is_file()
        or str(best.resolve()) != str(best)
        or not 0 < best.stat().st_size <= MAX_MODEL_BYTES
    ):
        raise RuntimeError("No verified best.pt at the fixed output location")
    checked = model_factory(str(best))
    if checked.names != dict(enumerate(spec["class_names"])):
        raise RuntimeError("Best checkpoint class schema mismatch")
    # Recheck input provenance before reporting completion.
    _validate_input(path, spec)
    output = run / "output"
    if output.exists() or output.is_symlink():
        raise RuntimeError("Worker output already exists")
    with tempfile.TemporaryDirectory(prefix=".output-", dir=run) as temporary:
        stage = Path(temporary)
        shutil.copyfile(best, stage / "best.pt")
        _atomic_json(
            stage / "schema.json", {"schema_version": 1, "mode": spec["mode"], "class_names": spec["class_names"]}
        )
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
        actual_json = {
            key: value if isinstance(value, (str, int, float, bool, list, dict, type(None))) else str(value)
            for key, value in actual.items()
        }
        manifest.update(
            schema_version=1,
            ultralytics_version=VERSION,
            checkpoint_readable=True,
            best_pt_sha256=_digest(stage / "best.pt"),
            schema_sha256=_digest(stage / "schema.json"),
            train_arguments=actual_json,
            augmentation_actual={key: actual.get(key) for key in LED_SAFE_AUG},
        )
        _atomic_json(stage / "manifest.json", manifest)
        stage.rename(output)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m katrain.web.admin.vision_training_worker <run>/spec.json")
    run_worker(sys.argv[1])


if __name__ == "__main__":
    main()
