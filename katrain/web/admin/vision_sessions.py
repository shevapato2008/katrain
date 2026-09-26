"""Bounded pre-frame SGF drafts; a published capture always takes precedence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from katrain.web.admin.vision_capture_txn import CLASS_ORDERS, VisionCaptureError
from katrain.web.admin.vision_sgf import MAX_SGF_BYTES, prepare_vision_sgf

MAX_DRAFT_BYTES = 6 * MAX_SGF_BYTES + 65536
SESSION_LIST_LIMIT = 50


class VisionSessionStore:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.root = coordinator.root

    def _draft_path(self, game_id):
        # Use the same opaque-ID boundary as the coordinator before constructing
        # the independent draft filename; never accept a client filesystem path.
        self.coordinator._session_dir(game_id)
        drafts = self.root / "drafts"
        if drafts.is_symlink():
            raise VisionCaptureError(503, "Draft directory must not be a symlink")
        return drafts / f"{game_id}.json"

    def create(self, sgf, *, mode, geometry_revision, geometry_source, camera_device_id):
        game_id = str(uuid4())
        draft = {
            "schema_version": 1,
            "game_id": game_id,
            "original_sgf": sgf.original_sgf,
            "sgf_sha256": sgf.sgf_sha256,
            "mode": mode,
            "geometry_revision": geometry_revision,
            "geometry_source": geometry_source,
            "camera_device_id": camera_device_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self._draft_path(game_id)
        pending = None
        try:
            data = json.dumps(draft, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            if len(data) > MAX_DRAFT_BYTES:
                raise VisionCaptureError(422, "SGF draft exceeds its size limit")
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".draft-", delete=False) as handle:
                pending = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if pending.read_bytes() != data or path.exists() or path.is_symlink():
                raise OSError("Draft write validation failed")
            os.replace(pending, path)
            pending = None
        except OSError as exc:
            raise VisionCaptureError(507, "SGF draft publication failed") from exc
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
        return self.read(game_id)

    def read(self, game_id):
        try:
            return {**self.coordinator.load_session(game_id), "state": "captured"}
        except VisionCaptureError as exc:
            # Corrupt/incomplete published sessions are never treated as drafts.
            if exc.status_code != 404:
                raise
        path = self._draft_path(game_id)
        if not path.exists() and not path.is_symlink():
            raise VisionCaptureError(404, "Capture session does not exist")
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DRAFT_BYTES:
                raise ValueError("Unsafe or oversized SGF draft")
            draft = json.loads(path.read_bytes())
            sgf = prepare_vision_sgf(draft["original_sgf"])
            if (
                draft["schema_version"] != 1
                or draft["game_id"] != game_id
                or draft["sgf_sha256"] != sgf.sgf_sha256
                or draft["mode"] not in CLASS_ORDERS
                or not draft["geometry_revision"]
                or not draft["geometry_source"]
                or type(draft["camera_device_id"]) is not int
                or not 0 <= draft["camera_device_id"] <= 8
                or datetime.fromisoformat(draft["created_at"]).utcoffset() is None
            ):
                raise ValueError("SGF draft provenance is invalid")
            return {
                **draft,
                "state": "draft",
                "board_size": 19,
                "class_names": list(CLASS_ORDERS[draft["mode"]]),
                "total_steps": len(sgf.steps),
                "total_moves": len(sgf.placement_indices),
                "frames": [],
                "next_step": -1,
            }
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise VisionCaptureError(503, "SGF draft is corrupt or incomplete") from exc

    def list(self):
        drafts = self.root / "drafts"
        if drafts.is_symlink():
            raise VisionCaptureError(503, "Draft directory must not be a symlink")
        candidates = set()
        if drafts.exists():
            candidates.update(path.stem for path in drafts.glob("*.json"))
        if self.root.exists():
            candidates.update(
                path.name for path in self.root.iterdir() if path.is_dir() and (path / "manifest.json").exists()
            )
        sessions = []
        for game_id in sorted(candidates)[:SESSION_LIST_LIMIT]:
            try:
                session = self.read(game_id)
                sessions.append(
                    {
                        "game_id": game_id,
                        "state": session["state"],
                        "mode": session["mode"],
                        "count": len(session["frames"]),
                        "total_steps": session["total_steps"],
                        "next_step": session["next_step"],
                        "geometry_revision": session["geometry_revision"],
                        "error": None,
                    }
                )
            except VisionCaptureError as exc:
                sessions.append({"game_id": game_id, "state": "error", "error": str(exc)})
        return {"sessions": sessions, "limit": SESSION_LIST_LIMIT, "truncated": len(candidates) > SESSION_LIST_LIMIT}
