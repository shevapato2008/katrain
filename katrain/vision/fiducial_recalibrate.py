"""SGF-aware fiducial selection + per-frame absolute homography recovery.

Solves the CURRENT camera frame -> canonical 950x950 warp homography M_f from
LEDs lit at known EMPTY intersections. Reuses fit_geometry_from_anchors, whose
canonical target is already (col*spacing, row*spacing) == (xs[col], ys[row]).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from katrain.vision.led_geometry_calibrator import fit_geometry_from_anchors

STAR = (3, 9, 15)
CORNERS = ((0, 0), (0, 18), (18, 0), (18, 18))


@dataclass(frozen=True)
class CentroidResult:
    ok: bool
    coord: tuple[int, int]
    centroid: tuple[float, float] | None = None
    peak: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Drift:
    dx: float
    dy: float
    deg: float
    scale: float
    median_px: float


def _occupied_neighbor(board, r, c) -> bool:
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < 19 and 0 <= cc < 19 and board[rr][cc] is not None:
            return True
    return False


def select_fiducials(board, next_point, *, target: int = 13, min_count: int = 8):
    """Empty, non-collinear, well-spread intersections; corners+star first, then
    farthest-point sampling. Excludes occupied points, the guidance point, and any
    point with an occupied 4-neighbor (reflection/occlusion risk)."""
    block = set()
    if next_point is not None:
        block.add((int(next_point["row"]), int(next_point["col"])))

    def usable(r, c):
        return board[r][c] is None and (r, c) not in block and not _occupied_neighbor(board, r, c)

    chosen: list[tuple[int, int]] = [p for p in CORNERS if usable(*p)]
    for r in STAR:
        for c in STAR:
            if usable(r, c) and (r, c) not in chosen:
                chosen.append((r, c))
    seen = set(chosen)
    cand = [(r, c) for r in range(19) for c in range(19) if usable(r, c) and (r, c) not in seen]
    while len(chosen) < target and cand:
        if chosen:
            best = max(cand, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in chosen))
        else:
            best = cand[0]
        chosen.append(best)
        cand.remove(best)
    return chosen


def predict_camera_positions(coords, points: np.ndarray):
    """ROI search centers: points[row][col] is the camera-space pixel of each
    intersection under the reference geometry (M_0). Used ONLY to locate blobs,
    never as the homography target."""
    return {(int(r), int(c)): (float(points[r][c][0]), float(points[r][c][1])) for (r, c) in coords}


def detect_led_centroids(dark, lit, expected, *, channel: int, search_px: float):
    """Per-ROI weighted-centroid of the dominant lit-minus-dark blob. One dark +
    one lit frame covers ALL fiducials lit simultaneously (each searched in its
    own window, so multiple LEDs don't compete like the single-blob detector)."""
    out: dict[tuple[int, int], CentroidResult] = {}
    if dark.shape != lit.shape or dark.ndim != 3:
        return {c: CentroidResult(False, c, reason="shape_mismatch") for c in expected}
    delta = lit[..., channel].astype(np.float32) - dark[..., channel].astype(np.float32)
    delta = cv2.GaussianBlur(delta, (5, 5), 0)
    h, w = delta.shape
    rad = int(round(search_px))
    for coord, (px, py) in expected.items():
        x0, x1 = max(0, int(px) - rad), min(w, int(px) + rad + 1)
        y0, y1 = max(0, int(py) - rad), min(h, int(py) + rad + 1)
        win = delta[y0:y1, x0:x1]
        if win.size == 0:
            out[coord] = CentroidResult(False, coord, reason="out_of_frame")
            continue
        peak = float(win.max(initial=0.0))
        if peak < 20.0:
            out[coord] = CentroidResult(False, coord, peak=peak, reason="low_signal")
            continue
        thr = max(12.0, peak * 0.45)
        mask = (win >= thr).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        best = None
        for lab in range(1, count):
            if int(stats[lab, cv2.CC_STAT_AREA]) < 3:
                continue
            score = float(np.maximum(win[labels == lab], 0.0).sum())
            if best is None or score > best[0]:
                best = (score, lab)
        if best is None:
            out[coord] = CentroidResult(False, coord, peak=peak, reason="no_blob")
            continue
        ys, xs = np.where(labels == best[1])
        wts = np.maximum(win[ys, xs], 0.0)
        tot = float(wts.sum())
        cx = float(np.dot(xs, wts) / tot) + x0
        cy = float(np.dot(ys, wts) / tot) + y0
        out[coord] = CentroidResult(True, coord, centroid=(cx, cy), peak=peak)
    return out


def solve_frame_homography(detected, *, out_size: int = 950, min_inliers: int = 6):
    """detected: list[((row,col),(x,y))] camera-space centroids. Returns a
    GeometryFitResult whose .M maps camera -> canonical warp (target already
    (col*spacing,row*spacing) inside fit_geometry_from_anchors)."""
    anchors = [((int(r), int(c)), (float(x), float(y))) for (r, c), (x, y) in detected]
    return fit_geometry_from_anchors(anchors, out_size=out_size, min_inliers=min_inliers)


def drift_from_homography(M_f, M_0, *, out_size: int = 950) -> Drift:
    """Drift in canonical space between frozen M_0 and current M_f."""
    spacing = (out_size - 1) / 18.0
    grid = np.array([[c * spacing, r * spacing] for r in range(19) for c in range(19)], np.float64)
    T = np.asarray(M_f, np.float64) @ np.linalg.inv(np.asarray(M_0, np.float64))
    moved = cv2.perspectiveTransform(grid.reshape(-1, 1, 2), T).reshape(-1, 2)
    res = np.linalg.norm(moved - grid, axis=1)
    a, b, c, d = T[0, 0], T[0, 1], T[1, 0], T[1, 1]
    scale = float(np.sqrt(abs(a * d - b * c)))
    deg = float(np.degrees(np.arctan2(c, a)))
    return Drift(dx=float(T[0, 2]), dy=float(T[1, 2]), deg=deg, scale=scale, median_px=float(np.median(res)))
