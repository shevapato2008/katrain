"""带灯拍 capture orchestration (plan §4): QA → strict LED → barrier grab → manifest.

One ``run_capture`` call corresponds to "the operator just placed move ``move_index``"
(``move_index == -1`` is the forced initial empty+LED frame). The sequence:

  1. L2 QA (decision ③): blackout LED, grab a no-LED frame, classify, diff vs the
     expected board (steps[0..move_index]). Mismatch + not override → QAMismatch.
  2. Light the NEXT physical move (strict, skipping passes) → ``shown_at``; or, if
     there is none, blackout (final, no-LED frame).
  3. Sync barrier: grab the frame read *after* ``shown_at + settle`` (timestamp
     gate) so the lit LED is in-frame and no pre-LED frame slips through.
  4. Write the frame + a rich manifest entry (atomic, idempotent, recoverable);
     on the first frame, freeze geometry.npz + game.sgf into the game folder.

Hardware (camera/LED/geometry) is injected so this is unit-testable with fakes.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from katrain.core.baipu import expected_board_from_steps, next_placement_index
from katrain.vision import board_qa

log = logging.getLogger("katrain_web")

_GAME_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_locks_guard = threading.Lock()
_game_locks: Dict[str, threading.Lock] = {}


class QAMismatch(Exception):
    def __init__(self, move_index: int, diffs: List[dict]):
        super().__init__("QA mismatch")
        self.move_index = move_index
        self.diffs = diffs


class LedUnavailable(Exception):
    pass


def _game_lock(game_id: str) -> threading.Lock:
    with _locks_guard:
        if game_id not in _game_locks:
            _game_locks[game_id] = threading.Lock()
        return _game_locks[game_id]


def _resolve_game_dir(out_dir: str, game_id: str) -> Path:
    if not _GAME_ID_RE.fullmatch(game_id):
        raise ValueError(f"invalid game_id: {game_id!r}")
    base = Path(out_dir).expanduser().resolve()
    game_dir = (base / game_id).resolve()
    if base not in game_dir.parents and game_dir != base:
        raise ValueError("game_id escapes out_dir")
    return game_dir


def _read_manifest(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _write_manifest_atomic(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_capture(
    *,
    led,
    capture,
    geometry,
    steps: List[Dict[str, Any]],
    board_size: int,
    out_dir: str,
    game_id: str,
    move_index: int,
    sgf: str,
    override: bool = False,
    capture_condition: Optional[dict] = None,
    settle_ms: float = 150.0,
) -> dict:
    """Run one capture step. Returns a result dict; raises QAMismatch / LedUnavailable /
    ValueError. Geometry must be locked (caller checks). LED is required (the frame must
    show the guidance LED unless it's the final frame)."""
    if not (-1 <= move_index < len(steps)):
        raise ValueError(f"move_index {move_index} out of range [-1, {len(steps) - 1}]")
    game_dir = _resolve_game_dir(out_dir, game_id)
    manifest_path = game_dir / "manifest.json"

    with _game_lock(game_id):
        manifest = _read_manifest(manifest_path) or {
            "game_id": game_id,
            "session_timestamp": _now_iso(),
            "board_size": board_size,
            "sgf_path": "game.sgf",
            "geometry_path": "geometry.npz",
            "total_moves": sum(1 for s in steps if s["kind"] != "pass"),
            "frames": [],
        }
        frames = manifest["frames"]

        # Idempotency: a frame for this move_index already exists → return it unchanged.
        for fr in frames:
            if fr["applied_move_index"] == move_index:
                return {
                    "ok": True,
                    "idempotent": True,
                    "path": str(game_dir / fr["file"]),
                    "qa_status": fr["qa_status"],
                    "frame_kind": fr["frame_kind"],
                    "next_guided_move_index": fr["next_guided_move_index"],
                }

        # 1. L2 QA against the expected board after move_index.
        expected = expected_board_from_steps(steps, move_index, board_size)
        if led is not None:
            led.clear(strict=True)
        qa_frame, _qseq, _qts = capture.grab_fresh(settle_ms=settle_ms)
        if qa_frame is None:
            raise LedUnavailable("no QA frame")
        classified = board_qa.classify_canonical(qa_frame, geometry)
        diffs = board_qa.diff_expected(expected, classified)
        if diffs and not override:
            raise QAMismatch(move_index, diffs)
        qa_status = "operator_override" if diffs else "ok"

        # 2. Light the next physical move (strict) or blackout for the final frame.
        next_idx = next_placement_index(steps, move_index)
        if next_idx is not None:
            ns = steps[next_idx]
            color = "black" if ns["color"] == "B" else "white"
            if led is None:
                raise LedUnavailable("LED service required for guided capture")
            show = led.set_points([{"row": ns["row"], "col": ns["col"], "color": color}], strict=True)
            if not show.get("ok"):
                raise LedUnavailable(f"LED SHOW failed: {show.get('errors')}")
            show_at = show.get("shown_at")
            led_point = {"row": ns["row"], "col": ns["col"], "color": color}
            frame_kind = "initial_led" if move_index < 0 else "after_move"
        else:
            if led is not None:
                led.clear(strict=True)
            show_at = None
            led_point = None
            frame_kind = "final_no_led"

        # 3. Sync barrier: grab the frame captured after the LED settled, then write it.
        ordinal = len(frames)
        frame_file = f"frame_{ordinal:03d}.jpg"
        frame_path = game_dir / frame_file
        path, fseq, _fts = capture.capture_to(str(frame_path), after_ts=show_at, settle_ms=settle_ms)

        # First frame: freeze geometry + SGF into the game folder (version pinning).
        if ordinal == 0:
            from katrain.vision.geometry_lock import save_geometry_lock

            save_geometry_lock(geometry, game_dir / "geometry.npz")
            with open(game_dir / "game.sgf", "w", encoding="utf-8") as fh:
                fh.write(sgf)

        board_hash = steps[move_index]["board_hash"] if 0 <= move_index < len(steps) else None
        entry = {
            "file": frame_file,
            "seq": fseq,
            "frame_kind": frame_kind,
            "applied_move_index": move_index,
            "next_guided_move_index": next_idx,
            "led_point": led_point,
            "board_through_index": move_index,
            "board_hash": board_hash,
            "qa_status": qa_status,
        }
        if capture_condition:
            entry["capture_condition"] = capture_condition
        frames.append(entry)
        _write_manifest_atomic(manifest_path, manifest)

        return {
            "ok": True,
            "idempotent": False,
            "path": path,
            "qa_status": qa_status,
            "frame_kind": frame_kind,
            "next_guided_move_index": next_idx,
        }
