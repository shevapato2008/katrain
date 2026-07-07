"""
Empty-board grid calibration for a fixed-mount camera.

detect.py finds the board's 4 corners robustly, but loosely -- they sit on the
wooden frame and can be off by a cell or two, and the rough warp can clip the far
columns. This module refines that into the precise 19x19 lattice on a CLEAN EMPTY
board, where every grid line is visible:

  rough corners -> padded warp (whole board + margin always fits)
               -> wood mask (drop tile/background lines that mimic grid lines)
               -> black-hat line response -> comb-to-peaks fit (exactly 19 evenly
                  spaced lines per axis) -> map lattice back to the original image
               -> iterate the homography so the corners converge onto the grid.

Pure-auto gets ~90% but cannot always tell the outer GRID line from the wooden
FRAME edge (same colour). For a fixed mount the robust answer is a one-time human
confirm (see calibrate_ui.py): this module supplies the auto PROPOSAL, the UI lets
you approve / nudge it, and the result is locked for the whole game.

Geometry is represented by the 4 outer grid-intersection corners (TL,TR,BR,BL).
grid_points_from_corners() expands them to the 361 points via a homography
(perspective-correct, unlike a plain bilinear interpolation).
"""

import numpy as np
import cv2

GRID_SIZE = 19

# Wood-region HSV (the new board's orange wood). Lenient: isolates board from the
# white tiles / bowls / dark background that would otherwise add spurious lines.
WOOD_LO = np.array([0, 30, 40])
WOOD_HI = np.array([22, 220, 220])

BLACKHAT_KSIZE = 15


# --------------------------------------------------------------------------- #
# Line detection in the rectified (warped) board
# --------------------------------------------------------------------------- #


def _padded_warp(corners, size, pad):
    """Map the rough board quad to the centred [pad, size-pad] square so the whole
    board PLUS a margin always fits, even when the rough corners clip a few columns
    (the clipped area lands in the padding instead of being lost)."""
    src = np.asarray(corners, np.float32)
    dst = np.array([[pad, pad], [size - pad, pad], [size - pad, size - pad], [pad, size - pad]], np.float32)
    return cv2.getPerspectiveTransform(src, dst), cv2.getPerspectiveTransform(dst, src)


def _wood_mask(warp):
    """Largest orange-wood blob in the warp -> the board region. Excludes tile
    grout, bowls and background whose lines would masquerade as grid lines."""
    hsv = cv2.cvtColor(cv2.GaussianBlur(warp, (5, 5), 0), cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, WOOD_LO, WOOD_HI)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (41, 41))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        m = np.uint8(lab == big) * 255
    return m


def _profiles(warp, mask, ksize=BLACKHAT_KSIZE):
    """Vertical/horizontal line-response profiles, restricted to the board."""
    gray = cv2.GaussianBlur(cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))).astype(
        np.float32
    )
    bh[mask == 0] = 0
    return bh.sum(axis=0), bh.sum(axis=1)


def _find_peaks(prof, min_dist, thr_ratio=0.20):
    """Local maxima above thr_ratio*max, greedily de-duplicated by strength."""
    thr = prof.max() * thr_ratio
    cand = [i for i in range(1, len(prof) - 1) if prof[i] >= thr and prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1]]
    cand.sort(key=lambda p: -prof[p])
    kept = []
    for p in cand:
        if all(abs(p - q) >= min_dist for q in kept):
            kept.append(p)
    return sorted(kept)


def _fit_comb(prof, size, n=GRID_SIZE, dmin=28.0, dmax=50.0, tol_frac=0.20):
    """Fit exactly n evenly-spaced lines (a rigid comb) to the strongest peaks,
    maximizing matched teeth. Rejects off-grid spurious peaks and reconstructs any
    undetected (faint) outer line from the regular spacing. Returns (lines, nmatch)."""
    pk = np.array(_find_peaks(prof, min_dist=dmin * 0.6), float)
    if len(pk) < 3:
        return None, 0
    best = None
    for d10 in range(int(dmin * 10), int(dmax * 10), 5):
        d = d10 / 10.0
        tol = d * tol_frac
        for anchor in pk:
            for k0 in range(n):
                x0 = anchor - k0 * d
                teeth = x0 + d * np.arange(n)
                if teeth[0] < -tol or teeth[-1] > size - 1 + tol:
                    continue
                diffs = np.abs(teeth[:, None] - pk[None, :]).min(axis=1)
                m = int((diffs <= tol).sum())
                serr = float(diffs[diffs <= tol].sum())
                if best is None or (m, -serr) > (best[0], -best[1]):
                    best = (m, serr, x0, d)
    m, serr, x0, d = best
    tol = d * tol_frac
    lines = x0 + d * np.arange(n)
    out = []
    for t in lines:
        j = int(np.argmin(np.abs(pk - t)))
        out.append(pk[j] if abs(pk[j] - t) <= tol else t)  # snap if supported, else model
    return np.array(out, np.float32), m


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def grid_points_from_corners(corners, n=GRID_SIZE, size=1000):
    """(n,n,2) intersection pixel coords in the original image from the 4 outer
    grid corners, via a homography (perspective-correct)."""
    src = np.asarray(corners, np.float32)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    Minv = cv2.getPerspectiveTransform(dst, src)
    lin = np.linspace(0, size - 1, n)
    gx, gy = np.meshgrid(lin, lin)
    pts = np.stack([gx, gy], axis=-1).astype(np.float32)
    return cv2.perspectiveTransform(pts.reshape(-1, 1, 2), Minv).reshape(n, n, 2)


def propose_corners(image, rough_corners, size=1000, pad=180, iters=3):
    """Auto-refine rough corners to the grid via wood-masked line detection,
    iterating the homography. Returns refined (4,2) TL,TR,BR,BL or None. This is a
    PROPOSAL for the one-time human confirm; the outer line may be ~1 cell off when
    the wooden frame edge is ambiguous."""
    cur = np.asarray(rough_corners, np.float32)
    last = None
    for _ in range(iters):
        M, Minv = _padded_warp(cur, size, pad)
        warp = cv2.warpPerspective(image, M, (size, size))
        mask = _wood_mask(warp)
        cp, rp = _profiles(warp, mask)
        xs, mv = _fit_comb(cp, size)
        ys, mh = _fit_comb(rp, size)
        if xs is None or ys is None:
            return None
        gx, gy = np.meshgrid(xs, ys)
        wpts = np.stack([gx, gy], axis=-1).astype(np.float32)
        opts = cv2.perspectiveTransform(wpts.reshape(-1, 1, 2), Minv).reshape(GRID_SIZE, GRID_SIZE, 2)
        cur = np.array([opts[0, 0], opts[0, -1], opts[-1, -1], opts[-1, 0]], np.float32)
        last = (mv, mh)
    return cur


def refine(image, corners, **kw):
    """Convenience: propose corners + expand to 361 points. Returns dict with
    'corners' (4,2) and 'points' (19,19,2), or None."""
    c = propose_corners(image, corners, **kw)
    if c is None:
        return None
    return {"corners": c, "points": grid_points_from_corners(c)}
