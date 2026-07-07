"""Zero-touch auto-calibration for the fixed mount (route B).

Fuses the two complementary strengths found empirically:
  - champion coarse detection (detect.py, the promoted optimizer winner): lighting-robust board localization
    (multi-config HSV + hue-wrap + grid-response config selector),
  - calibrate.py comb-fit: pose-robust grid-line localization (normalized padded warp +
    19-tooth rigid comb -> cannot latch onto a single wooden frame edge).

Pipeline: median several EMPTY frames -> champion coarse rough quad -> comb-fit refine
(iterated) -> divergence guard (fall back to coarse if comb is untrustworthy) ->
self-verification confidence (matched comb teeth + corner stability) -> lock session.npz.

NO human in the loop. If confidence is low it refuses to lock (caller can retry / flag).
"""

import numpy as np, cv2
from katrain.vision import geometry_calibrate as calibrate
from katrain.vision import stone_classifier as stones
from katrain.vision import geometry_detect as detect

GRID, OUT_SIZE = 19, 950
CONF_MIN = 0.80  # lock only if confidence >= this
NMATCH_MIN = 16  # comb teeth matched per axis (of 19) to trust the comb


def _comb_refine(image, rough, size=1000, pad=180, iters=3):
    """Comb-fit refine that also returns the matched-teeth counts (confidence signal)."""
    cur = np.asarray(rough, np.float32)
    mv = mh = 0
    for _ in range(iters):
        M, Minv = calibrate._padded_warp(cur, size, pad)
        warp = cv2.warpPerspective(image, M, (size, size))
        mask = calibrate._wood_mask(warp)
        cp, rp = calibrate._profiles(warp, mask)
        xs, mv = calibrate._fit_comb(cp, size)
        ys, mh = calibrate._fit_comb(rp, size)
        if xs is None or ys is None:
            return None, 0, 0
        gx, gy = np.meshgrid(xs, ys)
        wpts = np.stack([gx, gy], -1).astype(np.float32)
        opts = cv2.perspectiveTransform(wpts.reshape(-1, 1, 2), Minv).reshape(GRID, GRID, 2)
        cur = np.array([opts[0, 0], opts[0, -1], opts[-1, -1], opts[-1, 0]], np.float32)
    return cur, int(mv), int(mh)


def auto_calibrate(frames):
    """frames: list of EMPTY-board BGR images. Returns dict with corners + confidence + diag."""
    detect.reset_state()
    rough = None
    for f in frames:
        rough = detect.detect_board(f)
    if rough is None:
        return {"ok": False, "reason": "coarse detection failed", "confidence": 0.0}
    rough = np.asarray(rough, np.float32)

    ref, mv, mh = _comb_refine(frames[-1], rough)
    diag = 0.5 * (np.linalg.norm(rough[2] - rough[0]) + np.linalg.norm(rough[3] - rough[1]))
    if ref is None:
        corners, nmatch, moved = rough, 0, 0.0
    else:
        moved = float(np.sqrt(((ref - rough) ** 2).sum(1)).max())
        nmatch = min(mv, mh)
        comb_ok = nmatch >= NMATCH_MIN and moved < 0.4 * diag
        corners = ref if comb_ok else rough  # divergence guard -> fall back to coarse

    # confidence: fraction of comb teeth matched, penalized if comb diverged / was rejected
    teeth = min(mv, mh) / float(GRID)
    penalty = 1.0 if (ref is not None and nmatch >= NMATCH_MIN and moved < 0.4 * diag) else 0.4
    conf = round(teeth * penalty, 2)
    return {
        "ok": conf >= CONF_MIN,
        "corners": corners,
        "confidence": conf,
        "nmatch_x": mv,
        "nmatch_y": mh,
        "moved_px": round(moved, 1),
        "diag_px": round(diag, 1),
    }
