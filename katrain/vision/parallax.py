"""Stone-parallax correction parameters and calibration fit -- pure math, no I/O.

Derivation and measured inputs: superpowers/tracks/vision-optimizations/stone-parallax/geometry.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ParallaxParams:
    """What BoardStateExtractor needs: the camera nadir in the geometry-lock warp's continuous grid
    coordinates (fx = column, fy = row) and the contraction factor k = (H - h) / H."""

    nadir_fx: float
    nadir_fy: float
    k: float

    @property
    def nadir(self) -> tuple[float, float]:
        return (self.nadir_fx, self.nadir_fy)

    def to_dict(self) -> dict:
        return {"nadir_fx": self.nadir_fx, "nadir_fy": self.nadir_fy, "k": self.k}


@dataclass(frozen=True)
class FitResult:
    k: float
    nadir_fx: float
    nadir_fy: float
    m: float
    rms_cells: float
    max_resid_cells: float
    worst_index: int
    h_implied_mm: float
    n: int

    @property
    def params(self) -> ParallaxParams:
        return ParallaxParams(self.nadir_fx, self.nadir_fy, self.k)


def fit_parallax(points, detected, camera_height_mm: float) -> FitResult:
    """Least-squares fit of the forward model D = m*P + (1 - m)*C, linear in (m, b = (1 - m)*C).

    ``points``: (n, 2) true intersections as (col, row) -- the geometry-lock grid's (fx, fy).
    ``detected``: (n, 2) matching RAW (uncorrected) detected positions in the same coordinates.
    ``camera_height_mm`` (H) only feeds ``h_implied_mm = H * (1 - k)``, a diagnostic telling which
    stone height the detector reports (3.5 = mid-plane, 7.0 = top face); the correction never uses H.

    Raises ValueError rather than return an ill-posed fit: fewer than 3 samples; samples that do not
    span both board axes (collinear or coincident -- the model is not degenerate on a line, but a
    calibration that never varied one axis is a misuse, prd P1-2 acceptance 3); or m == 1 (no
    measurable parallax, so the nadir b / (1 - m) is undefined).

    Never sanity-check the fitted nadir: b's error is amplified by 1 / (1 - m) (~100x; 0.3 mm of
    noise gives ~29 mm p95), yet the nadir enters the correction multiplied by (1 - k) ~ 0.01, so the
    corrected positions stay accurate (~0.4 mm p95).
    """
    P = np.asarray(points, dtype=float)
    D = np.asarray(detected, dtype=float)
    if P.ndim != 2 or P.shape[1:] != (2,) or P.shape != D.shape:
        raise ValueError(f"points and detected must both be (n, 2); got {P.shape} and {D.shape}")
    n = len(P)
    if n < 3:
        raise ValueError(f"need at least 3 samples, got {n}")
    if np.linalg.matrix_rank(P - P.mean(axis=0)) < 2:
        raise ValueError("samples are collinear: calibration stones must span both board axes")
    A = np.zeros((2 * n, 3))
    b = np.zeros(2 * n)
    A[0::2, 0] = P[:, 0]
    A[0::2, 1] = 1.0
    b[0::2] = D[:, 0]
    A[1::2, 0] = P[:, 1]
    A[1::2, 2] = 1.0
    b[1::2] = D[:, 1]
    m, bx, by = (float(v) for v in np.linalg.lstsq(A, b, rcond=None)[0])
    if abs(1.0 - m) < 1e-9:
        raise ValueError("fitted m == 1: no measurable parallax, the nadir is undefined")
    resid = np.hypot(*(A @ np.array([m, bx, by]) - b).reshape(n, 2).T)
    k = 1.0 / m
    return FitResult(
        k=k,
        nadir_fx=bx / (1.0 - m),
        nadir_fy=by / (1.0 - m),
        m=m,
        rms_cells=float(np.sqrt(np.mean(resid**2))),
        max_resid_cells=float(resid.max()),
        worst_index=int(resid.argmax()),
        h_implied_mm=float(camera_height_mm) * (1.0 - k),
        n=n,
    )


# ver9 camera mount, from the CAD (geometry.md §3-4): lens height above the board face, and how far the
# lens foot point sits beyond the grid line nearest the camera, centred on that edge: 19.6116 cells from
# the far line (geometry.md §4), i.e. (-70.5453 - (-106.0)) / 22.0 = 1.6116 beyond the near one.
MOUNT_CAMERA_HEIGHT_MM = 339.4424
MOUNT_NADIR_OUTSIDE_CELLS = 1.6116
# A detected stone centre is the stone's mid-plane: the 7 mm stone is a symmetric lens (geometry.md §3).
STONE_CENTRE_HEIGHT_MM = 3.5
MOUNT_K = (MOUNT_CAMERA_HEIGHT_MM - STONE_CENTRE_HEIGHT_MM) / MOUNT_CAMERA_HEIGHT_MM


def mount_parallax_for_lock(lock, grid_size: int = 19) -> ParallaxParams:
    """The ver9 mount's parallax in ``lock``'s own (col, row) grid, with no stones placed (owner decision
    2026-09-22: the correction follows the geometry calibration, no separate calibration step).

    Which board edge faces the camera depends on the lock's corner order, so it is read off the lock:
    the edge nearest the lens is drawn largest in the camera image. The nadir goes
    MOUNT_NADIR_OUTSIDE_CELLS beyond the middle of that edge. An error in the nadir enters the
    correction multiplied by 1 - k (~0.01), so the CAD value is ample. On the RK3562 (2026-09-22, 38
    cells of real play) this took the median detected-to-intersection error from 0.225 to 0.093 cells.
    """
    Minv = np.linalg.inv(np.asarray(lock.M, dtype=float))
    xs = np.asarray(lock.xs, dtype=float)
    ys = np.asarray(lock.ys, dtype=float)
    last, mid, out = grid_size - 1, (grid_size - 1) // 2, MOUNT_NADIR_OUTSIDE_CELLS

    def image_length(p, q) -> float:
        a = Minv @ np.array([p[0], p[1], 1.0])
        b = Minv @ np.array([q[0], q[1], 1.0])
        return float(np.hypot(*(a[:2] / a[2] - b[:2] / b[2])))

    # nadir (fx, fy) -> image length of the two middle cells along that edge
    edges = {
        (-out, float(mid)): image_length((xs[0], ys[mid - 1]), (xs[0], ys[mid + 1])),
        (last + out, float(mid)): image_length((xs[last], ys[mid - 1]), (xs[last], ys[mid + 1])),
        (float(mid), -out): image_length((xs[mid - 1], ys[0]), (xs[mid + 1], ys[0])),
        (float(mid), last + out): image_length((xs[mid - 1], ys[last]), (xs[mid + 1], ys[last])),
    }
    nadir_fx, nadir_fy = max(edges, key=edges.get)
    return ParallaxParams(float(nadir_fx), float(nadir_fy), MOUNT_K)
