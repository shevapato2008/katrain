"""Trusted local YOLO models for the admin vision lab.

Trust comes only from ``trusted.json`` in the fixed model root, written by the operator on this
Mac (``{"schema_version": 1, "models": [{"model_id", "manifest_sha256"}]}``). The browser can only
name a registered ID; it never supplies paths or uploads weights. Listing never imports torch.
Activation hashes the weights, loads them, and checks the loaded class order and input size before
current/previous change. Nothing is loaded at startup.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from katrain.web.admin.vision_dataset import _json
from katrain.web.admin.vision_model_artifact import read_model_artifact, safe_path

MAX_TRUSTED = 100
_SHA = frozenset("0123456789abcdef")


class VisionModelError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _is_sha(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _SHA


def load_ultralytics(best_path: Path, info: dict):
    """Real loader: one StoneDetector per activation, reporting what the checkpoint actually contains."""
    from katrain.vision.stone_detector import StoneDetector

    detector = StoneDetector(str(best_path), backend="ultralytics", imgsz=int(info["parameters"]["imgsz"]))
    names = detector.backend_impl._model.names
    detector.names = [names[index] for index in sorted(names)] if isinstance(names, dict) else list(names)
    return detector


class VisionModelRegistry:
    def __init__(self, root: Path | str, *, loader=load_ultralytics):
        self.root = Path(root).expanduser().resolve()
        self.loader = loader
        self.lock = threading.RLock()
        self.loaded_id: str | None = None
        self.loaded = None
        self.load_error: str | None = None

    # -- trust and state files ---------------------------------------------------------------
    def _trusted(self) -> list[dict]:
        path = self.root / "trusted.json"
        if not path.exists():
            return []
        try:
            if not safe_path(path) or path.stat().st_size > 64 * 1024:
                raise ValueError("Unsafe trust list")
            data = json.loads(path.read_bytes())
            entries = data["models"]
            if data["schema_version"] != 1 or not isinstance(entries, list) or len(entries) > MAX_TRUSTED:
                raise ValueError("Invalid trust list")
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or set(entry) != {"model_id", "manifest_sha256"}
                    or not isinstance(entry["model_id"], str)
                    or not entry["model_id"].startswith("model-")
                    or not _is_sha(entry["model_id"][6:])
                    or not _is_sha(entry["manifest_sha256"])
                ):
                    raise ValueError("Invalid trust entry")
            return entries
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise VisionModelError(503, "Local model trust list is unreadable or invalid") from exc

    def _state(self) -> dict:
        path = self.root / "state.json"
        if not path.exists():
            return {"current": None, "previous": None}
        try:
            state = json.loads(path.read_bytes())
            if set(state) != {"current", "previous"}:
                raise ValueError("Invalid state")
            return state
        except (OSError, ValueError) as exc:
            raise VisionModelError(503, "Local model state is unreadable") from exc

    def _save_state(self, state: dict) -> None:
        fd, name = tempfile.mkstemp(prefix=".state-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(_json(state))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.root / "state.json")
        except OSError as exc:
            raise VisionModelError(507, "Local model state could not be saved") from exc
        finally:
            Path(name).unlink(missing_ok=True)

    # -- verification ------------------------------------------------------------------------
    def _verify(self, entry: dict, *, verify_weights: bool) -> dict:
        directory = self.root / entry["model_id"]
        artifact = read_model_artifact(directory, verify_weights=verify_weights)
        if artifact["manifest_sha256"] != entry["manifest_sha256"] or artifact["id"] != entry["model_id"]:
            raise ValueError("Model differs from its trust entry")
        manifest = artifact["manifest"]
        return {
            "id": artifact["id"],
            "run_id": manifest["run_id"],
            "dataset_id": manifest.get("dataset_id"),
            "mode": manifest["mode"],
            "class_names": manifest["class_names"],
            "weights_sha256": manifest["best_pt_sha256"],
            "weights_bytes": artifact["weights_bytes"],
            "manifest_sha256": artifact["manifest_sha256"],
            "parameters": manifest.get("parameters", {}),
        }

    def _entry(self, model_id: str) -> dict:
        entry = next((item for item in self._trusted() if item["model_id"] == model_id), None)
        if entry is None:
            raise VisionModelError(404, "Model is not registered on this machine")
        return entry

    # -- public API --------------------------------------------------------------------------
    def list(self) -> dict:
        with self.lock:
            models = []
            for entry in self._trusted():
                try:
                    models.append({**self._verify(entry, verify_weights=False), "valid": True, "error": None})
                except (OSError, ValueError, KeyError, TypeError):
                    models.append(
                        {"id": entry["model_id"], "valid": False, "error": "Model files missing or inconsistent"}
                    )
            state = self._state()
            return {**state, "models": models, "loaded_id": self.loaded_id, "load_error": self.load_error}

    def _load(self, model_id: str):
        entry = self._entry(model_id)
        try:
            info = self._verify(entry, verify_weights=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.load_error = "Model files failed verification"
            raise VisionModelError(409, self.load_error) from exc
        try:
            loaded = self.loader(self.root / model_id / "best.pt", info)
        except Exception as exc:
            self.load_error = f"Model load failed: {type(exc).__name__}"
            raise VisionModelError(409, self.load_error) from exc
        imgsz = info["parameters"].get("imgsz")
        if list(getattr(loaded, "names", [])) != list(info["class_names"]) or getattr(loaded, "imgsz", None) != imgsz:
            self.load_error = "Loaded model classes or input size differ from its manifest"
            raise VisionModelError(409, self.load_error)
        return loaded

    def activate(self, model_id: str) -> dict:
        with self.lock:
            loaded = self._load(model_id)
            state = self._state()
            if state["current"] != model_id:
                state = {"current": model_id, "previous": state["current"]}
                self._save_state(state)
            self.loaded_id, self.loaded, self.load_error = model_id, loaded, None
            return self.list()

    def rollback(self) -> dict:
        with self.lock:
            state = self._state()
            if not state["previous"]:
                raise VisionModelError(409, "There is no previous model to roll back to")
            loaded = self._load(state["previous"])
            self._save_state({"current": state["previous"], "previous": state["current"]})
            self.loaded_id, self.loaded, self.load_error = state["previous"], loaded, None
            return self.list()
