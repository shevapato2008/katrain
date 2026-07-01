"""带灯拍 capture orchestration: operator confirm → strict LED → barrier grab → manifest.

One ``run_capture`` call corresponds to "the operator just placed move ``move_index``"
(``move_index == -1`` is the forced initial empty+LED frame). The sequence:

  1. Trust the operator confirmation as the placement ground truth.
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

from katrain.core.baipu import next_placement_index

log = logging.getLogger("katrain_web")

_GAME_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_locks_guard = threading.Lock()
_game_locks: Dict[str, threading.Lock] = {}


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


def _safe_unlink(game_dir: Path, rel: str) -> None:
    if not isinstance(rel, str):
        return
    path = (game_dir / rel).resolve()
    if game_dir not in path.parents:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _unlink_manifest_frame(game_dir: Path, frame: dict) -> None:
    """Remove a frame's training image AND its isolated diagnostic artifacts
    (warped/grid_overlay/fiducial), so overwrite/repair leaves no orphans."""
    file_name = frame.get("file")
    if isinstance(file_name, str):
        _safe_unlink(game_dir, file_name)
    for rel in (frame.get("artifacts") or {}).values():
        _safe_unlink(game_dir, rel)


_FIDUCIAL_RGB = (0, 96, 0)  # low-brightness green; detected on channel 1
_FIDUCIAL_CHANNEL = 1


def _last_good_mf(frames: List[dict]):
    """Most recent successfully-corrected M_f from the manifest, or None.

    Carried forward when the current frame cannot re-solve (so we never silently
    fall back to the frozen M_0, which is the wrong geometry after a bump)."""
    import numpy as np

    for fr in reversed(frames):
        gc = fr.get("geometry_correction")
        if gc and gc.get("status") == "corrected" and gc.get("M") is not None:
            return np.asarray(gc["M"], dtype=np.float64)
    return None


def _draw_grid_overlay(raw_bgr, M_f, xs, ys, fiducials):
    import cv2
    import numpy as np

    Minv = np.linalg.inv(np.asarray(M_f, np.float64))
    vis = raw_bgr.copy()
    canon = np.array([[float(xs[c]), float(ys[r])] for r in range(19) for c in range(19)], np.float64).reshape(-1, 1, 2)
    cam = cv2.perspectiveTransform(canon, Minv).reshape(19, 19, 2)
    for r in range(19):
        cv2.polylines(vis, [cam[r].astype(np.int32)], False, (60, 60, 60), 1)
        cv2.polylines(vis, [cam[:, r].astype(np.int32)], False, (60, 60, 60), 1)
    for f in fiducials:
        det = f.get("detected")
        if det:
            cv2.circle(vis, (int(det[0]), int(det[1])), 5, (0, 0, 255), 2)
    return vis


def _run_fiducial_calibration(
    *,
    led,
    capture,
    geometry,
    board,
    guidance_point,
    last_good_M,
    settle_ms,
    drift_threshold_cells,
    game_dir,
    frame_file,
):
    """Light known empty intersections, re-solve the camera->canonical homography
    M_f for THIS frame. Returns (correction_dict, fiducials_meta, fiducial_rel, M_used).
    Falls back to last_good_M ('stale') or frozen M_0 ('frozen'); never blocks."""
    import cv2
    import numpy as np

    from katrain.vision.fiducial_recalibrate import (
        detect_led_centroids,
        drift_from_homography,
        predict_camera_positions,
        select_fiducials,
        solve_frame_homography,
    )

    out_size = int(geometry.out_size)
    spacing = (out_size - 1) / 18.0
    M0 = np.asarray(geometry.M, np.float64)

    fiducials_meta: list[dict] = []
    fiducial_rel = None
    status = source = None
    reason = None
    inlier_count = 0
    rms_cells = None
    M_used = None

    F = select_fiducials(board, guidance_point, target=13, min_count=8)
    if len(F) >= 8:
        expected = predict_camera_positions(F, geometry.points)
        led.clear(strict=True)
        dark, _seq, _ts = capture.grab_fresh(settle_ms=settle_ms)
        show = led.set_rgb_points([{"row": r, "col": c, "rgb": list(_FIDUCIAL_RGB)} for (r, c) in F], strict=True)
        lit, _seq, _ts = capture.grab_fresh(after_ts=show.get("shown_at"), settle_ms=settle_ms)
        led.clear(strict=True)
        det = detect_led_centroids(dark, lit, expected, channel=_FIDUCIAL_CHANNEL, search_px=0.7 * spacing)
        ok_pts = []
        for r, c in F:
            res = det[(r, c)]
            fiducials_meta.append(
                {
                    "row": r,
                    "col": c,
                    "rgb": list(_FIDUCIAL_RGB),
                    "detected": [float(res.centroid[0]), float(res.centroid[1])] if res.ok else None,
                    "ok": bool(res.ok),
                }
            )
            if res.ok:
                ok_pts.append(((r, c), res.centroid))
        fiducial_rel = f"fiducial/{Path(frame_file).stem}.jpg"
        (game_dir / "fiducial").mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(game_dir / fiducial_rel), lit)
        if len(ok_pts) >= 8:
            fit = solve_frame_homography(ok_pts, out_size=out_size, min_inliers=6)
            if fit.ok:
                M_used = np.asarray(fit.M, np.float64)
                status, source = "corrected", "fiducial"
                inlier_count = int(fit.inlier_count)
                rms_cells = float(fit.rms_residual) / spacing if fit.rms_residual else 0.0
            else:
                reason = fit.reason
        else:
            reason = "insufficient_detections"
    else:
        reason = "insufficient_fiducials"

    if M_used is None:
        if last_good_M is not None:
            M_used, status, source = np.asarray(last_good_M, np.float64), "stale", "last_good"
        else:
            M_used, status, source = M0, "frozen", "frozen"

    drift = drift_from_homography(M_used, M0, out_size=out_size)
    median_cells = drift.median_px / spacing
    correction = {
        "status": status,
        "source": source,
        "reason": reason,
        "M": M_used.tolist(),
        "inlier_count": inlier_count,
        "rms_residual_cells": rms_cells,
        "drift": {
            "dx": drift.dx,
            "dy": drift.dy,
            "deg": drift.deg,
            "scale": drift.scale,
            "median_cells": median_cells,
            "over_threshold": bool(median_cells > drift_threshold_cells),
        },
    }
    return correction, fiducials_meta, fiducial_rel, M_used


def _run_auto_geometry(*, geometry, capture, board, last_good_M, drift_threshold_cells, settle_ms):
    """No-LED per-move geometry check (P12 'auto' mode): grab a frame and run the RUNTIME
    scenario through the calibration selector (OuterCorner only — never lights an LED).
    Falls back to last_good ('stale') or frozen M_0 ('frozen'). Returns (correction, M_used)."""
    import numpy as np

    from katrain.vision.calibration_registry import build_default_selector
    from katrain.vision.calibration_strategy import CalibrationContext, Scenario
    from katrain.vision.fiducial_recalibrate import drift_from_homography

    out_size = int(geometry.out_size)
    spacing = (out_size - 1) / 18.0
    M0 = np.asarray(geometry.M, np.float64)

    frame, _seq, _ts = capture.grab_fresh(settle_ms=settle_ms)
    ctx = CalibrationContext(
        frames=[frame], board=board, geometry=geometry, led=None, capture=capture, out_size=out_size
    )
    out = build_default_selector().calibrate(Scenario.RUNTIME_RECALIBRATION, ctx)

    if out.ok and out.M is not None:
        M_used, status, source, reason = np.asarray(out.M, np.float64), "corrected", "outer_corner", None
    elif last_good_M is not None:
        M_used, status, source, reason = np.asarray(last_good_M, np.float64), "stale", "last_good", out.reason
    else:
        M_used, status, source, reason = M0, "frozen", "frozen", out.reason

    drift = drift_from_homography(M_used, M0, out_size=out_size)
    median_cells = drift.median_px / spacing
    correction = {
        "status": status,
        "source": source,
        "reason": reason,
        "M": M_used.tolist(),
        "inlier_count": 0,
        "rms_residual_cells": None,
        "drift": {
            "dx": drift.dx,
            "dy": drift.dy,
            "deg": drift.deg,
            "scale": drift.scale,
            "median_cells": median_cells,
            "over_threshold": bool(median_cells > drift_threshold_cells),
        },
    }
    return correction, M_used


def _write_warp_artifacts(game_dir: Path, frame_file: str, M_used, geometry, fiducials_meta) -> dict:
    """Warp the (clean) training frame with M_f and write isolated diagnostic
    artifacts. Returns the artifact path map (relative to game_dir)."""
    import cv2

    from katrain.vision.config import DEFAULT_MARGIN_CELLS
    from katrain.vision.warp import warp_with_margin

    raw = cv2.imread(str(game_dir / frame_file))
    if raw is None:
        return {}
    stem = Path(frame_file).stem
    out_size = int(geometry.out_size)
    # 1-cell margin around the grid so edge/corner stones aren't clipped — same shared warp the
    # training labeler and the geometry-lock inference path use (train == serve == this preview).
    warped = warp_with_margin(raw, M_used, out_size, margin_cells=DEFAULT_MARGIN_CELLS)
    (game_dir / "warped").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(game_dir / f"warped/{stem}.jpg"), warped)
    (game_dir / "grid_overlay").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(
        str(game_dir / f"grid_overlay/{stem}.jpg"),
        _draw_grid_overlay(raw, M_used, geometry.xs, geometry.ys, fiducials_meta),
    )
    return {"warped": f"warped/{stem}.jpg", "grid_overlay": f"grid_overlay/{stem}.jpg"}


def resolve_fiducial_mode(cli=None, env=None, *, default="auto"):
    """Pick the baipu geometry mode: CLI flag > env var > default. Invalid values fall through.
    Modes: 'auto' (no-LED OuterCorner, live play) | 'every-move' (LED fiducial, best for
    TRAINING capture) | 'off'."""
    valid = ("auto", "every-move", "off")
    for value in (cli, env):
        if value in valid:
            return value
    return default


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
    capture_condition: Optional[dict] = None,
    settle_ms: float = 150.0,
    overwrite_existing: bool = False,
    fiducial_mode: str = "off",
    drift_threshold_cells: float = 0.15,
) -> dict:
    """Run one operator-confirmed capture step.

    Raises LedUnavailable / ValueError. Geometry must be locked (caller checks).
    LED is required when the saved frame must show the next guidance point.
    """
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

        # Idempotency requires both the manifest entry and its captured file. If
        # an operator removes a bad frame, re-capture that slot in place.
        repair_index = None
        for index, fr in enumerate(frames):
            if fr["applied_move_index"] == move_index:
                existing_path = game_dir / fr["file"]
                if existing_path.is_file() and existing_path.stat().st_size > 0 and not overwrite_existing:
                    return {
                        "ok": True,
                        "idempotent": True,
                        "path": str(existing_path),
                        "qa_status": fr["qa_status"],
                        "frame_kind": fr["frame_kind"],
                        "next_guided_move_index": fr["next_guided_move_index"],
                    }
                repair_index = index
                if overwrite_existing:
                    for stale in frames[index + 1 :]:
                        _unlink_manifest_frame(game_dir, stale)
                    del frames[index + 1 :]
                break

        # Collection bootstrap: the explicit operator confirmation is ground truth.
        # Machine recognition is deliberately outside this capture decision path.
        qa_status = "operator_confirmed"

        next_idx = next_placement_index(steps, move_index)
        guidance_point = (
            {"row": steps[next_idx]["row"], "col": steps[next_idx]["col"]} if next_idx is not None else None
        )

        # 1b. Fiducial recalibration (every-move): light known empty intersections and
        # re-solve THIS frame's camera->canonical homography BEFORE the guidance LED, so
        # the training frame stays clean. Failures fall back to last-good/M_0, never block.
        correction = fiducials_meta = fiducial_rel = None
        M_used = None
        if fiducial_mode == "every-move":
            from katrain.core.baipu import expected_board_from_steps

            board = expected_board_from_steps(steps, move_index, 19)
            frame_file_pred = (
                frames[repair_index]["file"] if repair_index is not None else f"frame_{len(frames):03d}.jpg"
            )
            correction, fiducials_meta, fiducial_rel, M_used = _run_fiducial_calibration(
                led=led,
                capture=capture,
                geometry=geometry,
                board=board,
                guidance_point=guidance_point,
                last_good_M=_last_good_mf(frames),
                settle_ms=settle_ms,
                drift_threshold_cells=drift_threshold_cells,
                game_dir=game_dir,
                frame_file=frame_file_pred,
            )
        elif fiducial_mode == "auto":
            from katrain.core.baipu import expected_board_from_steps

            board = expected_board_from_steps(steps, move_index, 19)
            correction, M_used = _run_auto_geometry(
                geometry=geometry,
                capture=capture,
                board=board,
                last_good_M=_last_good_mf(frames),
                drift_threshold_cells=drift_threshold_cells,
                settle_ms=settle_ms,
            )
            fiducials_meta, fiducial_rel = [], None

        # 2. Light the next physical move (strict) or blackout for the final frame.
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
        ordinal = repair_index if repair_index is not None else len(frames)
        frame_file = frames[repair_index]["file"] if repair_index is not None else f"frame_{ordinal:03d}.jpg"
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
        if correction is not None:
            artifacts = _write_warp_artifacts(game_dir, frame_file, M_used, geometry, fiducials_meta)
            if fiducial_rel:
                artifacts["fiducial"] = fiducial_rel
            entry["geometry_correction"] = correction
            entry["fiducials"] = fiducials_meta
            entry["artifacts"] = artifacts
        if repair_index is None:
            frames.append(entry)
        else:
            frames[repair_index] = entry
        _write_manifest_atomic(manifest_path, manifest)

        result = {
            "ok": True,
            "idempotent": False,
            "repaired": repair_index is not None,
            "overwritten": bool(overwrite_existing and repair_index is not None),
            "path": path,
            "qa_status": qa_status,
            "frame_kind": frame_kind,
            "next_guided_move_index": next_idx,
        }
        if correction is not None:
            result["geometry_correction"] = correction
        return result
