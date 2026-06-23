"""Auto-label baipu capture frames for 4-class YOLO training.

Unlike auto_label.py (HSV-guess on warped images, 2 classes), this uses the
SGF GROUND TRUTH + frozen board geometry to place exact 4-class boxes
(black, white, led_red, led_green) in the rectified 950x950 board space that
worker.py feeds the detector. See superpowers/tracks/yolo-train/plan.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# NOTE: katrain.core.baipu is imported LAZILY inside load_capture / reconstruct_board.
# Importing it at module top would pull in katrain.core.game -> katrain.core.lang, which
# instantiates gettext at import and raises FileNotFoundError when the i18n .mo files are
# absent — breaking the pure-CV unit tests that never parse an SGF. Keep it lazy.


@dataclass
class Capture:
    game_dir: Path
    manifest: dict
    steps: list[dict]
    M: np.ndarray
    out_size: int
    xs: np.ndarray
    ys: np.ndarray


def load_capture(game_dir: Path) -> Capture:
    from katrain.core.baipu import build_steps_from_sgf  # lazy: avoids i18n import at module load

    game_dir = Path(game_dir)
    manifest = json.loads((game_dir / "manifest.json").read_text())
    sgf = (game_dir / (manifest.get("sgf_path") or "game.sgf")).read_text()
    steps = build_steps_from_sgf(sgf)["steps"]
    geo = np.load(game_dir / (manifest.get("geometry_path") or "geometry.npz"), allow_pickle=True)
    return Capture(
        game_dir=game_dir,
        manifest=manifest,
        steps=steps,
        M=np.asarray(geo["M"], dtype=np.float64),
        out_size=int(geo["out_size"]),
        xs=np.asarray(geo["xs"], dtype=np.float64),
        ys=np.asarray(geo["ys"], dtype=np.float64),
    )


def warp_frame(frame_bgr: np.ndarray, M: np.ndarray, out_size: int) -> np.ndarray:
    """Rectify a raw camera frame to the out_size square board (deployment space)."""
    return cv2.warpPerspective(frame_bgr, M, (out_size, out_size))


def grid_point(row: int, col: int, xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Warped-image (x, y) of canonical intersection (row, col). Direct, no flip."""
    return float(xs[col]), float(ys[row])


def reconstruct_board(steps: list[dict], applied_move_index: int) -> list[list[str | None]]:
    """19x19 of 'B'/'W'/None after applying steps[0..applied_move_index] (capture-aware)."""
    from katrain.core.baipu import expected_board_from_steps  # lazy: avoids i18n import at module load

    return expected_board_from_steps(steps, applied_move_index, 19)


def mean_grid_spacing(xs: np.ndarray, ys: np.ndarray) -> float:
    return float(np.mean([np.mean(np.diff(xs)), np.mean(np.diff(ys))]))
