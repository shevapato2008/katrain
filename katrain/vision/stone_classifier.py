"""
Classical empty-board-differencing stone detector (the MVP path; YOLO comes later).

Pipeline per frame:
  locked corners -> warp board -> sample a patch at each of the 361 intersections
  -> compare each patch's V/S to the EMPTY-board baseline at that intersection
  -> classify {empty, black, white}.

Why empty-differencing instead of absolute thresholds: the new board's wood is a
bright orange (V up to ~205), so a white stone is not reliably separable from wood
by an absolute V/S threshold. But *relative to the empty baseline at that exact
intersection*, a black stone is much darker and a white stone is much brighter and
far less saturated. The empty board (fixed mount) gives us that per-point baseline
for free -- this is the whole reason we "start from the empty board".

State codes: 0 = empty, 1 = black, 2 = white.

This module is intentionally simple and fully classical (numpy + cv2 only, no torch).
It also doubles as the auto-labeler that will bootstrap the YOLO training set.
"""

import numpy as np
import cv2

GRID_SIZE = 19
EMPTY, BLACK, WHITE = 0, 1, 2

# Patch radius as a fraction of the grid spacing. A stone covers most of a cell;
# sampling the central ~40% avoids neighbouring lines/stones.
PATCH_RATIO = 0.40

# Classification thresholds on (patch - baseline) deltas, plus absolute guards.
# Tuned on real stones once placed; these are sensible starting points.
BLACK_DV = -45.0  # black stone: V at least this much BELOW empty baseline
WHITE_DV = 25.0  # white stone: V at least this much ABOVE empty baseline ...
WHITE_S_MAX = 70.0  # ... AND absolute saturation below this (desaturated highlight)
WHITE_DS = -35.0  # ... OR saturation at least this much BELOW baseline


def _patch_stats(hsv, cx, cy, r):
    """Median (H,S,V) over a square patch centred at (cx,cy)."""
    h, w = hsv.shape[:2]
    x0, x1 = max(0, int(cx - r)), min(w, int(cx + r) + 1)
    y0, y1 = max(0, int(cy - r)), min(h, int(cy + r) + 1)
    patch = hsv[y0:y1, x0:x1].reshape(-1, 3)
    if patch.size == 0:
        return np.array([0.0, 0.0, 0.0], np.float32)
    return np.median(patch, axis=0).astype(np.float32)


def sample_grid(warp, xs, ys, patch_ratio=PATCH_RATIO):
    """(19,19,3) median HSV at each intersection of the warped board."""
    hsv = cv2.cvtColor(warp, cv2.COLOR_BGR2HSV)
    spacing = float(np.median(np.diff(xs)))
    r = max(3.0, spacing * patch_ratio)
    out = np.zeros((GRID_SIZE, GRID_SIZE, 3), np.float32)
    for ri in range(GRID_SIZE):
        for ci in range(GRID_SIZE):
            out[ri, ci] = _patch_stats(hsv, xs[ci], ys[ri], r)
    return out


def build_baseline(empty_warps, xs, ys, patch_ratio=PATCH_RATIO):
    """Empty-board reference HSV per intersection, averaged over one or more clean
    empty-board warps for stability. `empty_warps` may be a single warp or a list."""
    if isinstance(empty_warps, np.ndarray) and empty_warps.ndim == 3:
        empty_warps = [empty_warps]
    samples = [sample_grid(w, xs, ys, patch_ratio) for w in empty_warps]
    return np.mean(samples, axis=0).astype(np.float32)


def classify(
    warp,
    xs,
    ys,
    baseline,
    patch_ratio=PATCH_RATIO,
    black_dv=BLACK_DV,
    white_dv=WHITE_DV,
    white_s_max=WHITE_S_MAX,
    white_ds=WHITE_DS,
):
    """(19,19) board state in {EMPTY, BLACK, WHITE} from one frame's warp."""
    cur = sample_grid(warp, xs, ys, patch_ratio)
    dV = cur[..., 2] - baseline[..., 2]
    dS = cur[..., 1] - baseline[..., 1]
    S = cur[..., 1]

    state = np.full((GRID_SIZE, GRID_SIZE), EMPTY, np.int32)
    is_white = (dV >= white_dv) & ((S <= white_s_max) | (dS <= white_ds))
    is_black = dV <= black_dv
    state[is_white] = WHITE
    state[is_black] = BLACK  # black guard wins ties (a dark patch is never white)
    return state, cur


def render(warp, xs, ys, state):
    """Visualize a board state over the warped board."""
    vis = warp.copy()
    spacing = float(np.median(np.diff(xs)))
    r = int(spacing * 0.42)
    for ri in range(GRID_SIZE):
        for ci in range(GRID_SIZE):
            c = (int(xs[ci]), int(ys[ri]))
            s = state[ri, ci]
            if s == BLACK:
                cv2.circle(vis, c, r, (0, 0, 255), 2)
            elif s == WHITE:
                cv2.circle(vis, c, r, (255, 0, 0), 2)
            else:
                cv2.circle(vis, c, 2, (0, 255, 0), -1)
    return vis
