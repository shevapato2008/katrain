"""P12 Task 9 — crowded-board accuracy GATE for OuterCornerStrategy (no-LED).

Renders synthetic boards at varying stone fill rates + rotations, runs an outer-quad
detector, and reports the median corner-detection error in CELLS. The GATE: median error
< ``max_outer_corner_error_cells`` (default 0.12) → OuterCorner is safe as the RUNTIME
default; above → keep LED 'every-move' / require manual fallback for crowded boards.

Synthetic numbers are a LOWER BOUND (real wood/shadow/lighting are harder); the real-hardware
run is the blocking gate (plan.md P12 待硬件). The detector is injectable so the gate LOGIC
is unit-testable without the HSV pipeline.
"""
from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np

from katrain.vision.geometry_detect import detect_board_raw, sort_corners


def dense_stones(fill_pct: float, rng: np.random.Generator):
    """Return ~fill_pct of the 361 intersections as (row, col), randomly placed."""
    coords = [(r, c) for r in range(19) for c in range(19)]
    k = int(round(float(fill_pct) * len(coords)))
    idx = rng.permutation(len(coords))[:k]
    return [coords[i] for i in idx]


def _canonical_corners(out_size: int) -> np.ndarray:
    s = out_size
    return np.array([[0, 0], [s - 1, 0], [s - 1, s - 1], [0, s - 1]], np.float32)


def render_board(camera_quad, *, fill_pct=0.0, out_size=950, frame_size=(1280, 720), seed=0) -> np.ndarray:
    """Render a synthetic wood board (tan + grid + stones) seen at ``camera_quad`` (TL,TR,BR,BL)."""
    rng = np.random.default_rng(seed)
    s = out_size
    spacing = (s - 1) / 18.0
    canon = np.full((s, s, 3), (150, 180, 210), np.uint8)  # tan board (BGR)
    for i in range(19):
        p = int(round(i * spacing))
        cv2.line(canon, (p, 0), (p, s - 1), (60, 70, 90), 2)
        cv2.line(canon, (0, p), (s - 1, p), (60, 70, 90), 2)
    for (r, c) in dense_stones(fill_pct, rng):
        x, y = int(round(c * spacing)), int(round(r * spacing))
        color = (20, 20, 20) if rng.random() < 0.5 else (235, 235, 235)
        cv2.circle(canon, (x, y), int(spacing * 0.45), color, -1)
    W, H = frame_size
    H_c2cam = cv2.getPerspectiveTransform(_canonical_corners(s), np.asarray(camera_quad, np.float32))
    warped = cv2.warpPerspective(canon, H_c2cam, (W, H), borderValue=(30, 30, 30))
    mask = cv2.warpPerspective(np.full((s, s), 255, np.uint8), H_c2cam, (W, H))
    frame = np.full((H, W, 3), (30, 30, 30), np.uint8)
    frame[mask > 0] = warped[mask > 0]
    return frame


def corner_error_cells(detected_quad, true_quad) -> float:
    """Median corner-detection error, normalized by the camera-space cell spacing."""
    a = sort_corners(detected_quad).astype(np.float64)
    b = sort_corners(true_quad).astype(np.float64)
    diag = 0.5 * (np.linalg.norm(b[2] - b[0]) + np.linalg.norm(b[3] - b[1]))
    cell_px = diag / (18.0 * np.sqrt(2.0))
    return float(np.median(np.linalg.norm(a - b, axis=1)) / cell_px)


def _rotate_quad(quad, deg, center):
    R = cv2.getRotationMatrix2D(center, deg, 1.0)
    q = np.hstack([np.asarray(quad, np.float64), np.ones((4, 1))])
    return (R @ q.T).T


def measure(
    detect_fn: Optional[Callable] = None,
    *,
    fills=(0.0, 0.5, 0.8, 0.95),
    rotations=(0.0, 3.0, 6.0),
    out_size=950,
    frame_size=(1280, 720),
    base_quad=None,
    seed=0,
):
    """Return {(fill, deg): median_error_cells_or_None}. None = detector found no board."""
    detect = detect_fn or detect_board_raw
    W, H = frame_size
    base = np.array(base_quad if base_quad is not None else [[260, 150], [1010, 170], [1040, 690], [240, 660]], np.float64)
    center = (float(base[:, 0].mean()), float(base[:, 1].mean()))
    results = {}
    for fill in fills:
        for deg in rotations:
            quad = _rotate_quad(base, deg, center) if deg else base
            frame = render_board(quad, fill_pct=fill, out_size=out_size, frame_size=frame_size, seed=seed)
            det = detect(frame)
            results[(fill, deg)] = None if det is None else corner_error_cells(det, quad)
    return results


def gate(results, max_error_cells=0.12):
    """True iff every measured (non-None) error is under threshold."""
    errs = [e for e in results.values() if e is not None]
    return bool(errs) and all(e < max_error_cells for e in errs)


if __name__ == "__main__":  # manual benchmark: python -m katrain.vision.tools.outer_corner_accuracy
    res = measure()
    for (fill, deg), err in sorted(res.items()):
        print(f"fill={fill:>4.0%}  rot={deg:>3.0f}deg  err={'DETECT_FAIL' if err is None else f'{err:.3f} cells'}")
    print(f"GATE(<0.12 cells) = {gate(res)}")
