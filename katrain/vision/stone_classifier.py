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


def sample_grid(warp, xs, ys, patch_ratio=PATCH_RATIO):
    """(19,19,3) median HSV at each intersection of the warped board.

    Vectorized: rows share y-bounds and columns share x-bounds, so the 361 patches
    collapse to a handful of distinct (height,width) sizes. Each size is medianed in
    ONE ``np.median`` call instead of 361 — the per-call Python/numpy overhead is the
    SBC hotspot (~0.5s/call on RK3562, invoked 16x per calibration). The clipped
    integer bounds are identical to the original per-point patch, so the output is
    bit-for-bit unchanged.
    """
    hsv = cv2.cvtColor(warp, cv2.COLOR_BGR2HSV)
    h_img, w_img = hsv.shape[:2]
    spacing = float(np.median(np.diff(xs)))
    r = max(3.0, spacing * patch_ratio)
    # int() truncates toward zero; xs,ys >= 0 for a warped board — identical clipped bounds.
    x0 = [max(0, int(x - r)) for x in xs]
    x1 = [min(w_img, int(x + r) + 1) for x in xs]
    y0 = [max(0, int(y - r)) for y in ys]
    y1 = [min(h_img, int(y + r) + 1) for y in ys]

    out = np.zeros((GRID_SIZE, GRID_SIZE, 3), np.float32)
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for ri in range(GRID_SIZE):
        ph = y1[ri] - y0[ri]
        for ci in range(GRID_SIZE):
            pw = x1[ci] - x0[ci]
            if ph <= 0 or pw <= 0:
                continue  # empty patch → leave zeros (matches the original guard)
            groups.setdefault((ph, pw), []).append((ri, ci))
    for (ph, pw), cells in groups.items():
        stack = np.empty((len(cells), ph, pw, 3), hsv.dtype)
        for k, (ri, ci) in enumerate(cells):
            stack[k] = hsv[y0[ri] : y1[ri], x0[ci] : x1[ci]]
        med = np.median(stack.reshape(len(cells), ph * pw, 3), axis=1).astype(np.float32)
        for k, (ri, ci) in enumerate(cells):
            out[ri, ci] = med[k]
    return out


def build_baseline_from_samples(samples):
    """Mean HSV per intersection over pre-sampled (19,19,3) grids.

    Lets a caller reuse one ``sample_grid`` pass across several baselines instead of
    re-sampling the same warp (calibration builds two baselines from the same burst)."""
    return np.mean(samples, axis=0).astype(np.float32)


def build_baseline(empty_warps, xs, ys, patch_ratio=PATCH_RATIO):
    """Empty-board reference HSV per intersection, averaged over one or more clean
    empty-board warps for stability. `empty_warps` may be a single warp or a list."""
    if isinstance(empty_warps, np.ndarray) and empty_warps.ndim == 3:
        empty_warps = [empty_warps]
    return build_baseline_from_samples([sample_grid(w, xs, ys, patch_ratio) for w in empty_warps])


def classify_from_sample(
    cur,
    baseline,
    black_dv=BLACK_DV,
    white_dv=WHITE_DV,
    white_s_max=WHITE_S_MAX,
    white_ds=WHITE_DS,
):
    """(19,19) board state in {EMPTY, BLACK, WHITE} from a pre-sampled (19,19,3) grid."""
    dV = cur[..., 2] - baseline[..., 2]
    dS = cur[..., 1] - baseline[..., 1]
    S = cur[..., 1]

    state = np.full((GRID_SIZE, GRID_SIZE), EMPTY, np.int32)
    is_white = (dV >= white_dv) & ((S <= white_s_max) | (dS <= white_ds))
    is_black = dV <= black_dv
    state[is_white] = WHITE
    state[is_black] = BLACK  # black guard wins ties (a dark patch is never white)
    return state


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
    state = classify_from_sample(
        cur, baseline, black_dv=black_dv, white_dv=white_dv, white_s_max=white_s_max, white_ds=white_ds
    )
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
