from pathlib import Path
import os
import numpy as np
import pytest
import cv2

from katrain.vision.tools import baipu_autolabel as bal

GAME = Path(os.path.expanduser("~/.katrain/baipu_captures/kifu_24171"))
# Decorate ONLY the SGF-parse / real-data tests with this — NOT a module-level pytestmark,
# so the synthetic pure-CV tests below always run in CI.
requires_capture = pytest.mark.skipif(
    not GAME.exists(), reason="baipu capture fixture not present (real-data integration)"
)

# Synthetic grid — faithful to kifu_24171 (out_size 950, spacing ~52.72).
SYNTH_XS = np.linspace(0.0, 949.0, 19)
SYNTH_YS = np.linspace(0.0, 949.0, 19)


# ---------- pure-CV unit tests (CI: no fixture, no .mo) ----------


def test_grid_point_corner_and_topright():
    x0, y0 = bal.grid_point(0, 0, SYNTH_XS, SYNTH_YS)
    assert (round(x0), round(y0)) == (0, 0)
    x, y = bal.grid_point(0, 18, SYNTH_XS, SYNTH_YS)
    assert round(x) == 949 and round(y) == 0  # row=0 top, col=18 right


def test_mean_grid_spacing():
    assert abs(bal.mean_grid_spacing(SYNTH_XS, SYNTH_YS) - 52.72) < 0.5


# ---------- real-data integration tests (skip without fixture; need .mo) ----------


@requires_capture
def test_load_capture_shapes():
    cap = bal.load_capture(GAME)
    assert cap.out_size == 950
    assert cap.xs.shape == (19,) and cap.ys.shape == (19,)
    assert cap.M.shape == (3, 3)
    assert cap.manifest["board_size"] == 19
    assert len(cap.steps) >= cap.manifest["total_moves"]


@requires_capture
def test_reconstruct_board_matches_move_index_minus_captures():
    cap = bal.load_capture(GAME)
    # frame_040: applied_move_index=39 -> 40 placements minus captures.
    board = bal.reconstruct_board(cap.steps, 39)
    n_black = sum(c == "B" for row in board for c in row)
    n_white = sum(c == "W" for row in board for c in row)
    assert (n_black, n_white) == (20, 20)  # 40 moves, no captures yet at move 40


@requires_capture
def test_reconstruct_board_handles_captures_by_final_move():
    cap = bal.load_capture(GAME)
    board = bal.reconstruct_board(cap.steps, 210)  # final position of a 211-move game
    total = sum(c is not None for row in board for c in row)
    assert total == 205  # 211 placements - 6 captured (verified)
