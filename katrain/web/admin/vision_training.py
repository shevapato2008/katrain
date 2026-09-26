"""Disabled-by-default, local single-run training lifecycle; no CUDA or subprocess."""

import copy
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from katrain.web.admin.vision_dataset import _json
from katrain.web.admin.vision_transfer import VisionTransferError, _digest, prepare_frozen_dataset

CODE_VERSION = "admin-vision-training-1"
MAX_MODEL_BYTES = 1024**3
MAX_LOG_BYTES = 8 * 1024**2
LOG_TAIL_BYTES = 16 * 1024
ACTIVE_STATES = {"starting", "running", "cancelling", "interrupted"}
REQUEST_KEYS = {
    "request_id",
    "dataset_id",
    "dataset_manifest_sha256",
    "weights_id",
    "augmentation",
    "gpu_id",
    "epochs",
    "batch",
    "imgsz",
    "seed",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _safe_path(path):
    path = Path(path)
    return (
        path.is_absolute()
        and path != Path("/")
        and path.resolve() == path
        and not any(p.is_symlink() for p in (path, *path.parents))
    )


def _atomic_json(path, value):
    raw = _json(value)
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class VisionTrainingError(RuntimeError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class TrainingStartError(RuntimeError):
    def __init__(self, message, *, group_exited=False):
        super().__init__(message)
        self.group_exited = group_exited


@dataclass(frozen=True)
class RegisteredWeights:
    path: Path
    sha256: str


@dataclass(frozen=True)
class TrainingConfig:
    root: Path | None = None
    enabled: bool = False
    environment: str = "local"
    verified: bool = False
    gpu_ids: tuple[str, ...] = ()
    weights: dict[str, RegisteredWeights] = field(default_factory=dict)
    reserve_bytes: int = 1024**3


@dataclass(frozen=True)
class TrainingObservation:
    run_id: str
    epoch: int | None = None
    metrics: dict | None = None
    log_chunk: str = ""
    exit_code: int | None = None
    group_exited: bool = False


class VisionTrainingCoordinator:
    def __init__(self, *, config=None, adapter=None):
        self.config = config or TrainingConfig()
        self.adapter = adapter
        self.lock = RLock()
        self.runs = {}
        self.handles = {}
        self.active_run_id = None
        self.recovery_error = None
        self.lease_error = None
        self._lease_file = None
        config = self.config
        self.enabled = (
            config.enabled is True
            and config.environment == "test"
            and config.verified is True
            and adapter is not None
            and config.root is not None
            and _safe_path(config.root)
            and Path(config.root).is_dir()
            and bool(config.weights)
            and bool(config.gpu_ids)
            and all(isinstance(gpu, str) and re.fullmatch(r"[0-9]+", gpu) for gpu in config.gpu_ids)
            and len(set(config.gpu_ids)) == len(config.gpu_ids)
            and isinstance(config.weights, dict)
            and all(
                isinstance(key, str) and isinstance(value, RegisteredWeights) for key, value in config.weights.items()
            )
            and type(config.reserve_bytes) is int
            and config.reserve_bytes >= 1024**3
        )
        if self.enabled:
            self.root = Path(config.root)
            try:
                lease = self.root / ".training.lock"
                if not _safe_path(lease):
                    raise ValueError("Unsafe lease path")
                self._lease_file = lease.open("a+b")
                try:
                    fcntl.flock(self._lease_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self._lease_file.close()
                    self._lease_file = None
                    self.lease_error = "Training root lease is held by another coordinator"
                    return
                for name in ("datasets", "runs", "models"):
                    directory = self.root / name
                    if directory.exists() and (not _safe_path(directory) or not directory.is_dir()):
                        raise ValueError("Unsafe training root")
                    directory.mkdir(exist_ok=True)
                for directory in (self.root / "runs").iterdir():
                    if not _uuid(directory.name) or not _safe_path(directory):
                        raise ValueError("Invalid persisted run directory")
                    path = directory / "state.json"
                    if not _safe_path(path) or not 0 < path.stat().st_size < 1024**2:
                        raise ValueError("Invalid persisted state")
                    run = json.loads(path.read_bytes())
                    if (
                        run["id"] != directory.name
                        or set(run["request"]) != REQUEST_KEYS
                        or run["state"] not in ACTIVE_STATES | {"failed", "cancelled", "completed"}
                    ):
                        raise ValueError("Invalid persisted identity")
                    self.runs[run["id"]] = run
                    if run["state"] in ACTIVE_STATES:
                        run.update(
                            state="interrupted", error="Previous process-group exit is unverified", observed_at=_now()
                        )
                        self._save(run)
                        self.active_run_id = run["id"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.recovery_error = "Persisted training state requires operator verification"

    def _require_enabled(self, confirmed=None):
        if not self.enabled or (confirmed is not None and confirmed is not True):
            raise VisionTrainingError(
                403, "Training requires test environment, verified configuration and explicit confirmation"
            )
        if self.lease_error:
            raise VisionTrainingError(409, self.lease_error)
        if self.recovery_error:
            raise VisionTrainingError(503, self.recovery_error)

    def _save(self, run):
        _atomic_json(self.root / "runs" / run["id"] / "state.json", run)

    def status(self):
        with self.lock:
            return {
                "enabled": self.enabled,
                "state": (
                    "unknown"
                    if not self.enabled or self.recovery_error
                    else (
                        "busy"
                        if self.lease_error
                        else self.runs[self.active_run_id]["state"] if self.active_run_id else "idle"
                    )
                ),
                "reason": self.lease_error
                or self.recovery_error
                or (None if self.enabled else "Training capability disabled or configuration unverified"),
                "observed_at": _now(),
                "active_run_id": self.active_run_id,
                "gpu_ids": list(self.config.gpu_ids) if self.enabled else [],
            }

    def _validate_request(self, request):
        if not isinstance(request, dict) or set(request) != REQUEST_KEYS or not _uuid(request["request_id"]):
            raise VisionTrainingError(422, "Invalid training request")
        if any(
            not isinstance(request[key], str)
            for key in ("dataset_id", "dataset_manifest_sha256", "weights_id", "augmentation", "gpu_id")
        ):
            raise VisionTrainingError(422, "Training input IDs must be strings")
        for key, valid in (
            ("epochs", lambda x: 1 <= x <= 300),
            ("batch", lambda x: x in (4, 8)),
            ("imgsz", lambda x: x in (640, 960)),
            ("seed", lambda x: 0 <= x <= 2147483647),
        ):
            if type(request[key]) is not int or not valid(request[key]):
                raise VisionTrainingError(422, "Invalid bounded training parameters")
        if request["gpu_id"] not in self.config.gpu_ids or request["weights_id"] not in self.config.weights:
            raise VisionTrainingError(422, "GPU or weights ID is not registered")

    def _weight(self, weights_id):
        weight = self.config.weights[weights_id]
        try:
            path = Path(weight.path)
            if (
                not _safe_path(path)
                or not path.is_file()
                or path.suffix != ".pt"
                or not 0 < path.stat().st_size <= MAX_MODEL_BYTES
                or _digest(path) != weight.sha256
            ):
                raise ValueError("Untrusted final local weight")
        except (OSError, ValueError, TypeError) as exc:
            raise VisionTrainingError(
                503, "Registered final local weights are missing or hash mismatched; no download fallback"
            ) from exc
        return path, weight

    def _input(self, request):
        self._validate_request(request)
        try:
            plan = prepare_frozen_dataset(self.root / "datasets", request["dataset_id"])
        except VisionTransferError as exc:
            raise VisionTrainingError(exc.status_code, str(exc)) from exc
        if plan.manifest_sha256 != request["dataset_manifest_sha256"]:
            raise VisionTrainingError(503, "Frozen dataset manifest hash differs")
        manifest = json.loads((plan.directory / "manifest.json").read_bytes())
        augmentation = "stones-standard" if manifest["mode"] == "stones2" else "led-safe"
        if request["augmentation"] != augmentation:
            raise VisionTrainingError(422, "Augmentation is incompatible with dataset class mode")
        path, weight = self._weight(request["weights_id"])
        if shutil.disk_usage(self.root).free < self.config.reserve_bytes:
            raise VisionTrainingError(507, "Training capacity is below the reserved minimum")
        return plan, manifest, path, weight

    def start(self, request, *, confirmed=False):
        with self.lock:
            self._require_enabled(confirmed)
            # Validate the request shape before replay lookup, including booleans.
            self._validate_request(request)
            for run in self.runs.values():
                if run["request"]["request_id"] == request["request_id"]:
                    if _json(run["request"]) != _json(request):
                        raise VisionTrainingError(409, "Idempotency request UUID binds different parameters")
                    return copy.deepcopy(run)
            if self.active_run_id:
                raise VisionTrainingError(409, "Training is busy with an unexited run")
            plan, manifest, weights_path, weight = self._input(request)
            run_id = str(uuid.uuid4())
            directory = self.root / "runs" / run_id
            directory.mkdir()
            params = {key: request[key] for key in ("epochs", "batch", "imgsz", "seed")}
            params.update(
                device=request["gpu_id"],
                project=str(directory / "worker"),
                name="train",
                augment="default" if manifest["mode"] == "stones2" else "led-safe",
                amp=False,
                plots=False,
                workers=0,
                code_version=CODE_VERSION,
            )
            spec = {
                "run_id": run_id,
                "dataset_id": plan.dataset_id,
                "dataset_path": str(plan.directory),
                "dataset_manifest_sha256": plan.manifest_sha256,
                "mode": manifest["mode"],
                "class_names": manifest["class_names"],
                "weights_id": request["weights_id"],
                "weights_path": str(weights_path),
                "weights_sha256": weight.sha256,
                "augmentation": request["augmentation"],
                "parameters": params,
            }
            now = _now()
            run = {
                "id": run_id,
                "state": "starting",
                "request": copy.deepcopy(request),
                "spec": spec,
                "created_at": now,
                "started_at": None,
                "ended_at": None,
                "observed_at": now,
                "epoch": 0,
                "total_epochs": request["epochs"],
                "metrics": {"map50": None, "precision": None, "recall": None},
                "log_tail": "",
                "error": None,
                "model_id": None,
            }
            self._save(run)
            _atomic_json(directory / "spec.json", spec)
            self.runs[run_id] = run
            self.active_run_id = run_id
            try:
                self.handles[run_id] = self.adapter.start(run_id, directory, copy.deepcopy(spec))
                run.update(state="running", started_at=_now())
            except Exception as exc:
                proven_exit = isinstance(exc, TrainingStartError) and exc.group_exited is True
                run.update(
                    state="failed" if proven_exit else "interrupted",
                    error=(
                        "Worker launch failed"
                        if proven_exit
                        else "Worker launch result or process-group exit unverified"
                    ),
                    ended_at=_now() if proven_exit else None,
                )
                if proven_exit:
                    self.active_run_id = None
            try:
                self._save(run)
            except OSError as exc:
                # Retain the live handle and busy identity even if post-launch persistence fails.
                run["error"] = "Worker state persistence failed; run exit remains unverified"
                raise VisionTrainingError(503, "Worker state persistence failed; run exit remains unverified") from exc
            return copy.deepcopy(run)

    def get_run(self, run_id):
        with self.lock:
            self._require_enabled()
            if not _uuid(run_id) or run_id not in self.runs:
                raise VisionTrainingError(404, "Training run does not exist")
            run = self.runs[run_id]
            if run["state"] in ACTIVE_STATES and run_id in self.handles:
                run = copy.deepcopy(run)
                try:
                    observation = self.adapter.observe(self.handles[run_id])
                except Exception as exc:
                    raise VisionTrainingError(
                        503, "Worker observation unavailable; process-group exit remains unverified"
                    ) from exc
                if not isinstance(observation, TrainingObservation) or observation.run_id != run_id:
                    raise VisionTrainingError(503, "Worker observation belongs to a different run")
                epoch = observation.epoch
                if epoch is not None:
                    if type(epoch) is not int or not run["epoch"] <= epoch <= run["total_epochs"]:
                        raise VisionTrainingError(503, "Worker epoch is invalid or regressed")
                    run["epoch"] = epoch
                metrics = observation.metrics
                if metrics is not None:
                    if (
                        not isinstance(metrics, dict)
                        or set(metrics) != {"map50", "precision", "recall"}
                        or any(
                            value is not None
                            and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1)
                            for value in metrics.values()
                        )
                    ):
                        raise VisionTrainingError(503, "Worker validation metrics are invalid")
                    run["metrics"] = dict(metrics)
                if not isinstance(observation.log_chunk, str):
                    raise VisionTrainingError(503, "Worker log is invalid")
                raw = observation.log_chunk.encode("utf-8")
                log = self.root / "runs" / run_id / "worker.log"
                if not _safe_path(log):
                    raise VisionTrainingError(503, "Unsafe worker log path")
                if raw:
                    remaining = MAX_LOG_BYTES - (log.stat().st_size if log.exists() else 0)
                    if getattr(self.adapter, "persists_log", False) is not True and remaining > 0:
                        with log.open("ab") as handle:
                            handle.write(raw[:remaining])
                    run["log_tail"] = (run["log_tail"].encode("utf-8") + raw)[-LOG_TAIL_BYTES:].decode(
                        "utf-8", errors="ignore"
                    )
                run["observed_at"] = _now()
                if observation.group_exited is True:
                    if run["state"] == "cancelling":
                        run["state"] = "cancelled"
                    elif type(observation.exit_code) is not int:
                        run.update(state="interrupted", error="Exited worker status is unverified")
                    elif observation.exit_code != 0:
                        run.update(state="failed", error="Training worker exited unsuccessfully")
                    else:
                        try:
                            model = self._publish(run)
                            run.update(state="completed", model_id=model["id"])
                        except (OSError, ValueError, TypeError, KeyError, VisionTrainingError) as exc:
                            run.update(
                                state="failed", error="Worker output integrity or atomic model publication failed"
                            )
                    if run["state"] not in ACTIVE_STATES:
                        run["ended_at"] = _now()
                try:
                    self._save(run)
                except OSError as exc:
                    raise VisionTrainingError(
                        503, "Observed worker state could not be persisted; run remains reserved"
                    ) from exc
                self.runs[run_id] = run
                if run["state"] not in ACTIVE_STATES:
                    self.handles.pop(run_id)
                    self.active_run_id = None
            return copy.deepcopy(run)

    def cancel(self, run_id, *, confirmed=False):
        with self.lock:
            self._require_enabled(confirmed)
            if run_id != self.active_run_id or run_id not in self.handles:
                raise VisionTrainingError(409, "No owned active worker handle; process-group exit remains unverified")
            run = self.runs[run_id]
            if run["state"] != "cancelling":
                run = copy.deepcopy(run)
                run.update(state="cancelling", observed_at=_now())
                try:
                    self._save(run)
                except OSError as exc:
                    raise VisionTrainingError(
                        503, "Cancellation intent could not be persisted; run remains reserved"
                    ) from exc
                self.runs[run_id] = run
                try:
                    self.adapter.cancel(self.handles[run_id])
                except Exception as exc:
                    run["error"] = "Cancellation result unverified; worker remains busy"
                    try:
                        self._save(run)
                    except OSError:
                        pass  # The already-persisted cancellation still keeps this run reserved.
                    raise VisionTrainingError(503, run["error"]) from exc
            return copy.deepcopy(run)

    def _artifact_info(self, directory, spec):
        if (
            not _safe_path(directory)
            or not directory.is_dir()
            or {p.name for p in directory.iterdir()} != {"best.pt", "schema.json", "manifest.json"}
        ):
            raise ValueError("Invalid model output file set")
        best, schema_path, manifest_path = (directory / name for name in ("best.pt", "schema.json", "manifest.json"))
        for path, maximum in ((best, MAX_MODEL_BYTES), (schema_path, 64 * 1024), (manifest_path, 64 * 1024)):
            if not _safe_path(path) or not path.is_file() or not 0 < path.stat().st_size <= maximum:
                raise ValueError("Invalid model artifact")
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        schema = json.loads(schema_path.read_bytes())
        expected_schema = {"schema_version": 1, "mode": spec["mode"], "class_names": spec["class_names"]}
        if _json(schema) != _json(expected_schema):
            raise ValueError("Model schema differs from frozen input")
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
        ):
            if _json(manifest[key]) != _json(spec[key]):
                raise ValueError("Actual worker provenance differs from planned input")
        if (
            type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1
            or manifest["ultralytics_version"] != "8.4.34"
            or manifest["checkpoint_readable"] is not True
            or manifest["best_pt_sha256"] != _digest(best)
            or manifest["schema_sha256"] != _digest(schema_path)
        ):
            raise ValueError("Checkpoint attestation or hashes failed")
        actual = manifest["train_arguments"]
        augmentation = manifest["augmentation_actual"]
        if not isinstance(actual, dict) or not isinstance(augmentation, dict) or not augmentation:
            raise ValueError("Actual arguments and augmentation must be recorded")
        for key in ("epochs", "batch", "imgsz", "seed", "device", "project", "name", "amp", "plots", "workers"):
            if _json(actual[key]) != _json(spec["parameters"][key]):
                raise ValueError("Actual trainer arguments differ")
        if spec["mode"] == "led4":
            from katrain.vision.tools.train_model import LED_SAFE_AUG

            if any(_json(augmentation.get(key)) != _json(value) for key, value in LED_SAFE_AUG.items()):
                raise ValueError("Actual LED augmentation differs")
        digest = hashlib.sha256(raw).hexdigest()
        model_id = "model-" + hashlib.sha256(_json({"run_id": spec["run_id"], "manifest_sha256": digest})).hexdigest()
        return {
            "id": model_id,
            "run_id": spec["run_id"],
            "dataset_id": spec["dataset_id"],
            "dataset_manifest_sha256": spec["dataset_manifest_sha256"],
            "mode": spec["mode"],
            "class_names": spec["class_names"],
            "weights_sha256": manifest["best_pt_sha256"],
            "weights_bytes": best.stat().st_size,
            "manifest_sha256": digest,
            "parameters": spec["parameters"],
        }

    def _publish(self, run):
        source = self.root / "runs" / run["id"] / "output"
        info = self._artifact_info(source, run["spec"])
        final = self.root / "models" / info["id"]
        if final.exists():
            if self._artifact_info(final, run["spec"]) != info:
                raise ValueError("Existing model version conflicts")
            return info
        with tempfile.TemporaryDirectory(prefix=".model-", dir=self.root / "models") as temporary:
            stage = Path(temporary)
            for name in ("best.pt", "schema.json", "manifest.json"):
                with (source / name).open("rb") as incoming, (stage / name).open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
            if self._artifact_info(stage, run["spec"]) != info:
                raise ValueError("Model copy verification failed")
            for path in stage.iterdir():
                path.chmod(0o444)
            os.rename(stage, final)
        final.chmod(0o555)
        return info

    def list_models(self):
        with self.lock:
            self._require_enabled()
            models = []
            for directory in (self.root / "models").iterdir():
                if directory.name.startswith(".model-"):
                    continue
                try:
                    path = directory / "manifest.json"
                    if not _safe_path(path) or not 0 < path.stat().st_size <= 64 * 1024:
                        raise ValueError("Invalid model manifest")
                    run_id = json.loads(path.read_bytes())["run_id"]
                    info = self._artifact_info(directory, self.runs[run_id]["spec"])
                    if info["id"] != directory.name:
                        raise ValueError("Model version identity differs")
                    info["created_at"] = self.runs[run_id]["ended_at"]
                    models.append(info)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    raise VisionTrainingError(503, "Saved model integrity failed") from exc
            return sorted(models, key=lambda item: item["created_at"] or "", reverse=True)[:100]

    def list_datasets(self):
        with self.lock:
            self._require_enabled()
            datasets = []
            for directory in sorted((self.root / "datasets").iterdir()):
                if not directory.name.startswith("dataset-"):
                    continue
                try:
                    plan = prepare_frozen_dataset(self.root / "datasets", directory.name)
                    manifest = json.loads((plan.directory / "manifest.json").read_bytes())
                    datasets.append(
                        {
                            "id": plan.dataset_id,
                            "manifest_sha256": plan.manifest_sha256,
                            "mode": manifest["mode"],
                            "class_names": manifest["class_names"],
                            "train_count": sum(sample["split"] == "train" for sample in manifest["samples"]),
                            "val_count": sum(sample["split"] == "val" for sample in manifest["samples"]),
                        }
                    )
                except (OSError, ValueError, KeyError, TypeError, VisionTransferError) as exc:
                    raise VisionTrainingError(503, "Frozen dataset listing integrity failed") from exc
                if len(datasets) == 100:
                    break
            return datasets

    def presets(self):
        with self.lock:
            self._require_enabled()
            weights = []
            for weights_id in sorted(self.config.weights):
                _, weight = self._weight(weights_id)
                weights.append({"id": weights_id, "sha256": weight.sha256})
            return {
                "weights": weights,
                "augmentations": [{"id": "stones-standard", "mode": "stones2"}, {"id": "led-safe", "mode": "led4"}],
                "limits": {"epochs": [1, 300], "batch": [4, 8], "imgsz": [640, 960], "seed": [0, 2147483647]},
            }

    def list_runs(self):
        with self.lock:
            self._require_enabled()
            return copy.deepcopy(sorted(self.runs.values(), key=lambda run: run["created_at"], reverse=True)[:100])

    def close(self):
        """Release this coordinator, never claim or adopt a process-group exit."""
        with self.lock:
            if self.enabled and self.active_run_id:
                run = self.runs[self.active_run_id]
                run.update(
                    state="interrupted",
                    error="Coordinator closed; previous process-group exit remains unverified",
                    observed_at=_now(),
                )
                # On a failed write keep the lease: another instance must not bypass the reservation.
                self._save(run)
            self.enabled = False
            if self._lease_file is not None:
                self._lease_file.close()
                self._lease_file = None
