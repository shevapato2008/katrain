"""Synthetic ver9 stone-parallax geometry for tests ONLY.

Constants are the CAD-derived values of superpowers/tracks/vision-optimizations/stone-parallax/geometry.md §3.
Production never uses them: the nadir must be calibrated on site (prd P1-2). Grid convention matches
the geometry-lock warp: fx = column, fy = row, row 0 is the far side (away from the camera), and the
nadir lies beyond row 18 on the camera side.
"""

import math

CAM_MM = (0.0, -70.545)  # lens projection centre dropped onto the board plane
H_MM = 339.4424  # lens height above the board surface
H_STONE_MM = 3.5  # detected stone centre height = half the 7 mm thickness
K_TRUE = (H_MM - H_STONE_MM) / H_MM
X0_MM, Y0_MM = -213.3, -502.0  # grid line 0 (column A / far row)
PX_MM, PY_MM = 23.7, 22.0  # column / row pitch
NADIR_GRID = ((CAM_MM[0] - X0_MM) / PX_MM, (CAM_MM[1] - Y0_MM) / PY_MM)  # (9.0, 19.6116)


def grid_to_mm(fx, fy):
    return X0_MM + fx * PX_MM, Y0_MM + fy * PY_MM


def mm_to_grid(x, y):
    return (x - X0_MM) / PX_MM, (y - Y0_MM) / PY_MM


def _forward_mm(x, y, k):
    return CAM_MM[0] + (x - CAM_MM[0]) / k, CAM_MM[1] + (y - CAM_MM[1]) / k


def detected_grid(col, row, k=K_TRUE, outward_cells=0.0):
    """Where the detector would report a stone whose contact point is (col, row), optionally displaced
    ``outward_cells`` further away from the camera (radially from the nadir, measured in grid cells).
    The forward model runs in millimetres, so the anisotropic 23.7 x 22.0 pitch is real, not assumed away."""
    fx, fy = float(col), float(row)
    if outward_cells:
        ux, uy = fx - NADIR_GRID[0], fy - NADIR_GRID[1]
        n = math.hypot(ux, uy)
        fx, fy = fx + outward_cells * ux / n, fy + outward_cells * uy / n
    return mm_to_grid(*_forward_mm(*grid_to_mm(fx, fy), k))
