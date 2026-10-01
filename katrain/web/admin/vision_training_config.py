"""Fail-closed server-owned test-machine configuration. No GPU probes or launch."""

import importlib.metadata
import json
import os
import re
import sys
from pathlib import Path

from katrain.web.admin.vision_training import (
    MAX_MODEL_BYTES,
    RegisteredWeights,
    TrainingConfig,
    VisionTrainingCoordinator,
    _safe_path,
)
from katrain.web.admin.vision_training_process import TrainingProcessAdapter
from katrain.web.admin.vision_transfer import _digest


def create_training_service(environment, bind_host):
    if (
        environment != "test"
        or sys.platform != "linux"
        or bind_host not in ("127.0.0.1", "::1", "localhost")
        or os.getenv("KATRAIN_ADMIN_VISION_TRAINING") != "1"
    ):
        return VisionTrainingCoordinator()
    try:
        path = Path(os.environ["KATRAIN_ADMIN_VISION_TRAINING_CONFIG"])
        if not _safe_path(path) or not path.is_file() or not 0 < path.stat().st_size <= 64 * 1024:
            raise ValueError("Invalid configuration file")
        raw = json.loads(path.read_bytes())
        if (
            set(raw) != {"schema_version", "verified", "root", "gpu_ids", "weights"}
            or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1
            or raw["verified"] is not True
            or not isinstance(raw["root"], str)
            or not isinstance(raw["gpu_ids"], list)
            or not 0 < len(raw["gpu_ids"]) <= 2
            or any(not isinstance(gpu, str) or not re.fullmatch(r"[0-9]{1,2}", gpu) for gpu in raw["gpu_ids"])
            or not isinstance(raw["weights"], dict)
            or not 0 < len(raw["weights"]) <= 16
            or importlib.metadata.version("ultralytics") != "8.4.34"
        ):
            raise ValueError("Unverified training configuration")
        root = Path(raw["root"])
        if not _safe_path(root) or not root.is_dir():
            raise ValueError("Unverified training root")
        weights = {}
        for identifier, item in raw["weights"].items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier) or set(item) != {"path", "sha256"}:
                raise ValueError("Invalid registered weight entry")
            source = Path(item["path"])
            digest = item["sha256"]
            if (
                not _safe_path(source)
                or source.parent != root / "weights"
                or source.suffix != ".pt"
                or not source.is_file()
                or not 0 < source.stat().st_size <= MAX_MODEL_BYTES
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or _digest(source) != digest
            ):
                raise ValueError("Untrusted registered local weight")
            weights[identifier] = RegisteredWeights(source, digest)
        return VisionTrainingCoordinator(
            config=TrainingConfig(
                root=root,
                enabled=True,
                environment="test",
                verified=True,
                gpu_ids=tuple(raw["gpu_ids"]),
                weights=weights,
            ),
            adapter=TrainingProcessAdapter(),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError, importlib.metadata.PackageNotFoundError):
        service = VisionTrainingCoordinator()
        service.recovery_error = "Training configuration/dependencies are unverified; capability remains disabled"
        return service
