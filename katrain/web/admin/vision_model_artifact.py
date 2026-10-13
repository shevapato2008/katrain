"""Self-consistency of one trained-model directory, shared by training publication and the local registry.

It proves only that the three files agree with each other and with their recorded hashes. Who is
allowed to vouch for a model (a frozen training spec, or an operator-written trust entry) is the
caller's decision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from katrain.web.admin.vision_dataset import _json
from katrain.web.admin.vision_transfer import _digest

MODEL_FILES = frozenset({"best.pt", "schema.json", "manifest.json"})
MAX_MODEL_BYTES = 1024**3
MAX_SIDECAR_BYTES = 64 * 1024
ULTRALYTICS_VERSION = "8.4.34"


def safe_path(path) -> bool:
    path = Path(path)
    return (
        path.is_absolute()
        and path != Path("/")
        and path.resolve() == path
        and not any(p.is_symlink() for p in (path, *path.parents))
    )


def model_id_for(run_id: str, manifest_sha256: str) -> str:
    return "model-" + hashlib.sha256(_json({"run_id": run_id, "manifest_sha256": manifest_sha256})).hexdigest()


def read_model_artifact(directory: Path, *, verify_weights: bool = True) -> dict:
    """Return the manifest, schema and derived identity, or raise ValueError.

    verify_weights=False skips hashing best.pt (up to 1 GiB) for cheap listings; activation and
    publication always verify it.
    """
    directory = Path(directory)
    if not safe_path(directory) or not directory.is_dir() or {p.name for p in directory.iterdir()} != MODEL_FILES:
        raise ValueError("Invalid model output file set")
    best, schema_path, manifest_path = (directory / name for name in ("best.pt", "schema.json", "manifest.json"))
    for path, maximum in (
        (best, MAX_MODEL_BYTES),
        (schema_path, MAX_SIDECAR_BYTES),
        (manifest_path, MAX_SIDECAR_BYTES),
    ):
        if not safe_path(path) or not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise ValueError("Invalid model artifact")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    schema = json.loads(schema_path.read_bytes())
    if not isinstance(manifest, dict) or not isinstance(schema, dict):
        raise ValueError("Model manifest and schema must be objects")
    expected_schema = {"schema_version": 1, "mode": manifest.get("mode"), "class_names": manifest.get("class_names")}
    if _json(schema) != _json(expected_schema):
        raise ValueError("Model schema differs from its manifest")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
        or manifest.get("ultralytics_version") != ULTRALYTICS_VERSION
        or manifest.get("checkpoint_readable") is not True
        or manifest.get("schema_sha256") != _digest(schema_path)
        or not isinstance(manifest.get("run_id"), str)
        or (verify_weights and manifest.get("best_pt_sha256") != _digest(best))
    ):
        raise ValueError("Checkpoint attestation or hashes failed")
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "manifest": manifest,
        "schema": schema,
        "manifest_sha256": digest,
        "id": model_id_for(manifest["run_id"], digest),
        "weights_bytes": best.stat().st_size,
    }
