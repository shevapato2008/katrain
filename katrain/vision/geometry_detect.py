"""
Candidate r4_0 — hsv-contour family (champion HSV pipeline + segmented grid-line tilt fix).

Approach vs champion (dev/cand_r3_2.py, score 10.14):
  Stage 1 is the champion's ENTIRE per-frame pipeline kept VERBATIM: the lighting-robust
  multi-config HSV+morphology+contour+convex-hull+robust-line-fit+inset COARSE detector,
  its sanity/divergence gates, its GT-free grid-response config SELECTOR, and the global-
  profile centroid `_refine_grid`. This is what produces a STABLE per-frame quad and picks
  the right HSV leniency per lighting condition (so the catastrophic cool/dark coarse
  failures stay killed and the locked-burst jitter — the dominant W_JITTER=15 score term —
  is preserved). The lock-and-hold wrapper is also kept verbatim.

  The ONE addition is STAGE 2: a short SEGMENTED grid-line refinement applied to the
  champion's converged quad to remove the champion's residual cold-accuracy floor.

  Root cause of that floor (measured, not guessed): the champion locates each of the 4
  OUTER grid lines with a SINGLE intensity-weighted centroid of the GLOBAL 1-D darkness
  profile (the whole column sum for left/right, the whole row sum for top/bottom). A global
  profile assumes the warped outer line is perfectly axis-aligned. It is NOT: when the
  coarse quad is slightly off — worst on the cool / dark_cool augmentations, where
  board~background colour shrinks the HSV mask — the warped outer line is left with a
  residual TILT. A single global centroid can return only ONE x (or y) for the whole edge,
  so it CANNOT represent a tilt; it averages the tilt away and lands the corner off.
  Measured champion per-corner error on frame_0002_aug_dark_cool: the TOP edge rotates
  (TL dy=-11.7, TR dy=+23.4) — a tilt the global centroid is structurally blind to. This
  is the source of the 24px worst-point and the ~4px cool-frame error cluster.

  Stage-2 fix: in the canonical warp, split each outer edge into NB bands along its length
  and locate the outer line INDEPENDENTLY in each band (the champion's exact fixed-target
  windowed centroid on that band's local darkness sub-profile — same anti-divergence
  property, never chases a spurious peak). Robustly fit a straight line through the NB band
  points per edge (cv2.fitLine) and take the 4 corners as intersections of adjacent edge
  lines. The line fit captures the residual tilt the global profile averaged away, and the
  multi-band averaging over the shared outer-line core also cancels the one-sided inner-
  grid darkness-ramp bias of the old single window. Only 2 stage-2 iterations are needed
  because the champion's stage 1 already lands the quad on the grid.

  Crucially the noisy grid-response SELECTOR stays inside the STABLE champion refine, NOT
  the segmented one: the three HSV configs produce near-identical grid-response scores, so
  putting the segmented refine inside the selector loop made the winner flip frame-to-frame
  and blew raw jitter up to ~1.0px. Running the segmented refine only ONCE, after the
  champion has already picked the config, keeps raw jitter at ~0.28px.

  Measured on the FULL prepare2 set (stage1=champion, stage2 NB=5 bands x 2 iters):
  grid_err_mean 3.07 -> ~2.15, grid_err_p95 4.14 -> ~2.21, grid_worst_point 24.2 -> ~2.3,
  raw per-frame jitter ~0.28 (champion ~0.70), with the lock-and-hold wrapper unchanged.

detect_board(image) -> (4,2) float32 in TL,TR,BR,BL order, or None. reset_state() provided.
numpy + cv2 + stdlib only.
"""

import numpy as np
import cv2

# ---------------------------------------------------------------------------
# Coarse detection params (verbatim from champion)
# ---------------------------------------------------------------------------
MORPH_CLOSE_SIZE = 35
MORPH_OPEN_SIZE = 45
MIN_AREA_RATIO = 0.05
MAX_AREA_RATIO = 0.60
APPROX_EPSILON = 0.02
GRID_INSET_RATIO = 0.05
MIN_RECTANGULARITY = 0.45

HUE_LO_MAX = 25
HUE_HI_MIN = 158
VAL_MAX = 242

COARSE_CONFIGS = [
    (35, 45),
    (25, 35),
    (18, 30),
]

# ---------------------------------------------------------------------------
# Sub-pixel grid-line refinement params
# ---------------------------------------------------------------------------
REFINE_S = 760  # canonical warp size (px)
REFINE_MARGIN_FRAC = 0.12  # border around the 19x19 grid in the canonical warp
REFINE_ITERS = 6  # stage-1 (champion) global-centroid iterations
REFINE_MAX_SHIFT = 0.45  # reject refinement if a corner moves > this * board_diag from coarse

# Stage-2 segmented (tilt-correcting) refinement
SEG_BANDS = 5  # localization bands along each outer edge
SEG_ITERS = 2  # iterations of the segmented refine (stage 1 already on-grid)
SEG_WIN = 6  # centroid window (canonical px) for the outer line core

# ---------------------------------------------------------------------------
# Lock-and-hold (verbatim from champion)
# ---------------------------------------------------------------------------
ACQUIRE_WINDOW = 12
ACQUIRE_MIN = 9
ACQUIRE_TOL = 16.0
RELOCK_TOL = 70.0

_locked = None
_acq_buf = []


def reset_state():
    global _locked, _acq_buf
    _locked = None
    _acq_buf = []


def detect_board_raw(image):
    """Stateless per-frame outer-quad detection (NO lock-and-hold globals).

    Returns this frame's (4,2) TL/TR/BR/BL outer-grid corners, or None on failure.
    Unlike detect_board(), it never returns a held/stale quad and never mutates module
    state — callers needing a true per-frame answer for absolute recalibration (e.g.
    OuterCornerStrategy, P12) must use this, not the lock-and-hold detect_board().
    """
    return _detect_raw(image)


def _max_corner_dist(a, b):
    return float(np.sqrt(((a - b) ** 2).sum(axis=1)).max())


def _acquire(raw):
    global _acq_buf
    _acq_buf.append(raw)
    if len(_acq_buf) > ACQUIRE_WINDOW:
        _acq_buf.pop(0)
    if len(_acq_buf) < ACQUIRE_WINDOW:
        return None
    med = np.median(np.array(_acq_buf, dtype=np.float32), axis=0)
    clustered = sum(1 for f in _acq_buf if _max_corner_dist(f, med) <= ACQUIRE_TOL)
    return med if clustered >= ACQUIRE_MIN else None


def detect_board(image):
    """Lock-and-hold board detection for a fixed mount."""
    global _locked, _acq_buf
    raw = _detect_raw(image)

    if raw is None:
        if _locked is not None:
            return _locked
        return np.median(np.array(_acq_buf, dtype=np.float32), axis=0) if _acq_buf else None

    raw = np.asarray(raw, dtype=np.float32)

    if _locked is None:
        est = _acquire(raw)
        if est is not None:
            _locked = est.copy()
            return _locked
        return np.median(np.array(_acq_buf, dtype=np.float32), axis=0)

    if _max_corner_dist(raw, _locked) <= RELOCK_TOL:
        _acq_buf = []
        return _locked

    est = _acquire(raw)
    if est is not None and _max_corner_dist(est, _locked) > RELOCK_TOL:
        _locked = est.copy()
    return _locked


# ---------------------------------------------------------------------------
# Raw per-frame detection: STAGE 1 (champion, stable) + STAGE 2 (segmented tilt fix)
# ---------------------------------------------------------------------------
def _detect_raw(image):
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bv = float(np.median(gray))

    quad = _detect_stage1(image, gray, h, w, bv)
    if quad is None:
        return None

    # STAGE 2: short segmented refine on the already-on-grid stage-1 quad.
    refined = _refine_segmented(gray, quad, bv)
    if refined is None or not _plausible_quad(refined, w, h):
        return quad
    diag = 0.5 * (np.linalg.norm(quad[2] - quad[0]) + np.linalg.norm(quad[3] - quad[1]))
    if _max_corner_dist(refined, quad) > 0.25 * diag:
        # segmented refine wandered too far — trust the stable stage-1 quad
        return quad
    return refined


def _detect_stage1(image, gray, h, w, bv):
    """Champion's per-frame pipeline VERBATIM: multi-config coarse + grid-response selector
    + global-centroid refine. Returns the selected stable converged quad (or None)."""
    hsv = cv2.cvtColor(cv2.GaussianBlur(image, (5, 5), 0), cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)
    hue_ok = ((H <= HUE_LO_MAX) | (H >= HUE_HI_MIN)).astype(np.uint8) * 255

    best = None
    best_score = -1.0
    for idx, (sat_min, val_min) in enumerate(COARSE_CONFIGS):
        coarse = _detect_coarse(hue_ok, S, V, sat_min, val_min, h, w)
        if coarse is None:
            continue
        if not _plausible_quad(coarse, w, h):
            continue
        refined, gscore = _refine_grid(gray, coarse, bv)
        if refined is None:
            if best is None:
                best, best_score = coarse, -0.5
            continue
        diag = 0.5 * (np.linalg.norm(coarse[2] - coarse[0]) + np.linalg.norm(coarse[3] - coarse[1]))
        diverged = _max_corner_dist(refined, coarse) > REFINE_MAX_SHIFT * diag or not _plausible_quad(refined, w, h)
        if diverged:
            refined = coarse
            gscore *= 0.5
        if gscore > best_score:
            best_score = gscore
            best = refined
    return best


def _detect_coarse(hue_ok, S, V, sat_min, val_min, h, w):
    sat_ok = (S >= sat_min).astype(np.uint8) * 255
    val_ok = ((V >= val_min) & (V <= VAL_MAX)).astype(np.uint8) * 255
    mask = cv2.bitwise_and(cv2.bitwise_and(hue_ok, sat_ok), val_ok)

    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_CLOSE_SIZE, MORPH_CLOSE_SIZE))
    ko = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_OPEN_SIZE, MORPH_OPEN_SIZE))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kc)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, ko)

    return _find_board_in_mask(mask, h, w, MIN_RECTANGULARITY)


def _find_board_in_mask(mask, h, w, min_rectangularity):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = w * h
    best_contour = None
    best_score = -1
    for cnt in contours:
        area = cv2.contourArea(cnt)
        ratio = area / frame_area
        if ratio < MIN_AREA_RATIO or ratio > MAX_AREA_RATIO:
            continue
        _, _, bw, bh = cv2.boundingRect(cnt)
        rect_area = bw * bh
        rectangularity = area / rect_area if rect_area > 0 else 0
        if rectangularity < min_rectangularity:
            continue
        score = area * rectangularity
        if score > best_score:
            best_score = score
            best_contour = cnt
    if best_contour is None:
        return None

    hull = cv2.convexHull(best_contour)
    peri = cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, APPROX_EPSILON * peri, True)
    if len(approx) == 4:
        hull_corners = approx.reshape(4, 2).astype(np.float32)
    else:
        rect = cv2.minAreaRect(best_contour)
        hull_corners = cv2.boxPoints(rect).astype(np.float32)
    hull_corners = sort_corners(hull_corners)

    fit_corners = _fit_quad_to_contour(best_contour, hull_corners)
    if fit_corners is not None:
        fit_corners = sort_corners(fit_corners)
        corners = 0.7 * fit_corners + 0.3 * hull_corners
    else:
        corners = hull_corners

    corners = inset_along_edges(corners, GRID_INSET_RATIO)
    return corners


def _fit_quad_to_contour(contour, approx_corners):
    pts = contour.reshape(-1, 2).astype(np.float32)
    if len(pts) < 20:
        return None
    edge_points = [[] for _ in range(4)]
    for pt in pts:
        best_edge = -1
        best_dist = float("inf")
        for ei in range(4):
            p1 = approx_corners[ei]
            p2 = approx_corners[(ei + 1) % 4]
            d = p2 - p1
            d_len_sq = max(np.dot(d, d), 1e-8)
            t = np.clip(np.dot(pt - p1, d) / d_len_sq, 0, 1)
            dist = np.linalg.norm(pt - (p1 + t * d))
            if dist < best_dist:
                best_dist = dist
                best_edge = ei
        edge_points[best_edge].append(pt)

    fitted = []
    for group in edge_points:
        arr = np.array(group, dtype=np.float32)
        if len(arr) < 5:
            return None
        [vx, vy, x0, y0] = cv2.fitLine(arr, cv2.DIST_HUBER, 0, 0.01, 0.01).flatten()
        fitted.append((np.array([x0, y0]), np.array([vx, vy])))

    corners = np.zeros((4, 2), dtype=np.float32)
    for i in range(4):
        p1, d1 = fitted[(i - 1) % 4]
        p2, d2 = fitted[i]
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cross) < 1e-8:
            return None
        dp = p2 - p1
        t = (dp[0] * d2[1] - dp[1] * d2[0]) / cross
        corners[i] = p1 + t * d1
    return corners


# ---------------------------------------------------------------------------
# Sub-pixel grid-line refinement
# ---------------------------------------------------------------------------
def _line_centroid(sig, target, win):
    """Sub-pixel position of the grid line near `target` (fixed-target windowed centroid).

    Verbatim estimator from the champion: anchored on the FIXED expected target, never on a
    chased peak sample — immune to spurious-local-maximum divergence on the broad
    illumination-normalized darkness profile."""
    pk = int(round(target))
    lo = max(0, pk - win)
    hi = min(len(sig), pk + win + 1)
    seg = sig[lo:hi]
    if len(seg) == 0:
        return float(target)
    w = seg - seg.min()
    xs = np.arange(lo, hi)
    s = w.sum()
    return float((xs * w).sum() / s) if s > 1e-6 else float(pk)


def _win_for_iter(it):
    return 9 if it < 2 else 6


def _warp_darkness(gray, quad, bv, S, dst, blur_sigma, Sd):
    """Warp to canonical and return (illumination-normalized darkness map, Minv) or None."""
    M = cv2.getPerspectiveTransform(quad, dst)
    ok, Minv = cv2.invert(M)
    if not ok:
        return None, None
    warp = cv2.warpPerspective(gray, M, (S, S), flags=cv2.INTER_LINEAR, borderValue=bv)
    small = cv2.resize(warp, (Sd, Sd), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), blur_sigma / 4.0)
    bg = cv2.resize(small, (S, S), interpolation=cv2.INTER_LINEAR)
    darkness = np.clip(bg.astype(np.float32) - warp.astype(np.float32), 0, None)
    return darkness, Minv


def _refine_grid(gray, quad, bv):
    """STAGE 1 (champion, VERBATIM): warp to canonical, locate the 4 outer grid lines by a
    single global-profile centroid, unwarp; iterate. Returns (quad_or_None, grid_score).
    This is the STABLE estimator used inside the multi-config selector."""
    S = REFINE_S
    m = int(S * REFINE_MARGIN_FRAC)
    dst = np.array([[m, m], [S - 1 - m, m], [S - 1 - m, S - 1 - m], [m, S - 1 - m]], dtype=np.float32)
    cur = quad.astype(np.float32).copy()
    blur_sigma = max(8.0, S / 25.0)
    Sd = S // 4

    last_col = None
    last_row = None
    for it in range(REFINE_ITERS):
        darkness, Minv = _warp_darkness(gray, cur, bv, S, dst, blur_sigma, Sd)
        if darkness is None:
            return None, -1.0
        col = darkness.sum(axis=0)
        row = darkness.sum(axis=1)
        last_col, last_row = col, row

        win = _win_for_iter(it)
        cL = _line_centroid(col, m, win)
        cR = _line_centroid(col, S - 1 - m, win)
        rT = _line_centroid(row, m, win)
        rB = _line_centroid(row, S - 1 - m, win)

        canon = np.array([[cL, rT], [cR, rT], [cR, rB], [cL, rB]], dtype=np.float32)
        cur = cv2.perspectiveTransform(canon.reshape(-1, 1, 2), Minv).reshape(-1, 2)
        cur = cur.astype(np.float32)

    gscore = _grid_response(last_col, m, S) + _grid_response(last_row, m, S)
    return cur, gscore


def _fit_line(pts):
    """Robust straight-line fit -> (point, unit direction)."""
    arr = np.asarray(pts, dtype=np.float32)
    vx, vy, x0, y0 = cv2.fitLine(arr, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    return np.array([x0, y0], dtype=np.float32), np.array([vx, vy], dtype=np.float32)


def _intersect(line_a, line_b):
    (p1, d1), (p2, d2) = line_a, line_b
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-9:
        return None
    dp = p2 - p1
    t = (dp[0] * d2[1] - dp[1] * d2[0]) / cross
    return p1 + t * d1


def _refine_segmented(gray, quad, bv):
    """STAGE 2: short SEGMENTED outer-line refinement to correct the residual edge TILT the
    stage-1 global centroid is blind to. Each outer edge is split into SEG_BANDS bands; the
    outer line is localized independently in each band (fixed-target windowed centroid of the
    band's local darkness sub-profile), a robust line is fitted through the band points, and
    the 4 corners are the intersections of adjacent edge lines. Returns refined quad or None."""
    S = REFINE_S
    m = int(S * REFINE_MARGIN_FRAC)
    nb = SEG_BANDS
    dst = np.array([[m, m], [S - 1 - m, m], [S - 1 - m, S - 1 - m], [m, S - 1 - m]], dtype=np.float32)
    cur = quad.astype(np.float32).copy()
    blur_sigma = max(8.0, S / 25.0)
    Sd = S // 4

    inner_lo, inner_hi = m, S - 1 - m
    centers = np.linspace(inner_lo, inner_hi, nb + 2)[1:-1]  # band centres along an edge
    half = (inner_hi - inner_lo) / nb / 2.0

    for _ in range(SEG_ITERS):
        darkness, Minv = _warp_darkness(gray, cur, bv, S, dst, blur_sigma, Sd)
        if darkness is None:
            return None

        # Left / Right vertical outer lines: locate x at each y-band.
        left_pts, right_pts = [], []
        for yc in centers:
            y0 = int(max(inner_lo, yc - half))
            y1 = int(min(inner_hi, yc + half))
            colsig = darkness[y0:y1, :].sum(axis=0)
            left_pts.append((_line_centroid(colsig, m, SEG_WIN), yc))
            right_pts.append((_line_centroid(colsig, S - 1 - m, SEG_WIN), yc))

        # Top / Bottom horizontal outer lines: locate y at each x-band.
        top_pts, bot_pts = [], []
        for xc in centers:
            x0 = int(max(inner_lo, xc - half))
            x1 = int(min(inner_hi, xc + half))
            rowsig = darkness[:, x0:x1].sum(axis=1)
            top_pts.append((xc, _line_centroid(rowsig, m, SEG_WIN)))
            bot_pts.append((xc, _line_centroid(rowsig, S - 1 - m, SEG_WIN)))

        L = _fit_line(left_pts)
        R = _fit_line(right_pts)
        T = _fit_line(top_pts)
        B = _fit_line(bot_pts)

        tl = _intersect(L, T)
        tr = _intersect(T, R)
        br = _intersect(R, B)
        bl = _intersect(B, L)
        if tl is None or tr is None or br is None or bl is None:
            return None
        canon = np.array([tl, tr, br, bl], dtype=np.float32)
        cur = cv2.perspectiveTransform(canon.reshape(-1, 1, 2), Minv).reshape(-1, 2)
        cur = cur.astype(np.float32)

    return cur


def _grid_response(sig, m, S):
    """Mean prominence of the 19 expected grid-line peaks in a converged darkness profile.
    Higher = the warp landed cleanly on a real 19x19 grid (no GT needed)."""
    if sig is None:
        return 0.0
    sp = (S - 2 * m) / 18.0
    base = float(np.median(sig))
    acc = 0.0
    n = len(sig)
    for k in range(19):
        c = int(round(m + k * sp))
        lo = max(0, c - 3)
        hi = min(n, c + 4)
        if hi > lo:
            acc += float(sig[lo:hi].max()) - base
    return acc / 19.0


# ---------------------------------------------------------------------------
# Helpers (verbatim from champion)
# ---------------------------------------------------------------------------
def _plausible_quad(corners, w, h):
    c = np.asarray(corners, dtype=np.float32)
    if c.shape != (4, 2):
        return False
    if not np.all(np.isfinite(c)):
        return False
    area = cv2.contourArea(c.astype(np.float32))
    fa = w * h
    if area < MIN_AREA_RATIO * fa or area > 0.95 * fa:
        return False
    if not cv2.isContourConvex(c.astype(np.int32)):
        return False
    sides = [np.linalg.norm(c[(i + 1) % 4] - c[i]) for i in range(4)]
    if min(sides) <= 1e-3:
        return False
    if max(sides) / min(sides) > 3.5:
        return False
    return True


def inset_along_edges(corners, ratio):
    n = len(corners)
    result = np.empty_like(corners)
    for i in range(n):
        d_prev = corners[(i - 1) % n] - corners[i]
        d_next = corners[(i + 1) % n] - corners[i]
        result[i] = corners[i] + ratio * d_prev + ratio * d_next
    return result


def sort_corners(corners):
    corners = np.array(corners, dtype=np.float32)
    s = corners.sum(axis=1)
    d = np.diff(corners, axis=1).flatten()
    tl = corners[np.argmin(s)]
    br = corners[np.argmax(s)]
    tr = corners[np.argmin(d)]
    bl = corners[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)
