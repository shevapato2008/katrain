"""Canonical board warp with optional margin.

Single source of truth for the rectified-board warp used by BOTH the training labeler
(baipu_autolabel) and the geometry-lock inference path (worker_inprocess), so the images the
detector is trained on and the images it sees at serve time share the same geometry. The margin
(in grid cells) keeps edge/corner stones fully inside the frame; the matching mapping border lives
in BoardConfig(margin_cells=...).
"""

import cv2
import numpy as np


def margin_px_for(out_size: int, margin_cells: float, grid_size: int = 19) -> int:
    """Pixels of blank border to add on each side for ``margin_cells`` cells of margin."""
    if margin_cells <= 0:
        return 0
    return int(round(margin_cells * (out_size - 1) / (grid_size - 1)))


def adjust_M_for_resolution(M, source_wh, frame_wh):
    """Rescale a homography ``M`` (calibrated against a ``source_wh`` = (width, height) frame) so it
    applies correctly to a live ``frame_wh`` = (width, height) frame of a different resolution.

    Returns ``M`` unchanged when ``source_wh`` is unknown (None / contains None) or already equals
    ``frame_wh``. Otherwise returns ``M @ S`` where ``S`` scales frame pixels → source pixels, so a
    frame point maps through the original calibration into the same canonical location. This makes
    the geometry-lock warp robust to a camera that delivers a different resolution than the lock was
    built at (see the geometry-lock source_width/source_height fields)."""
    M = np.asarray(M, np.float64)
    if source_wh is None or source_wh[0] is None or source_wh[1] is None:
        return M
    sw, sh = float(source_wh[0]), float(source_wh[1])
    fw, fh = float(frame_wh[0]), float(frame_wh[1])
    if (sw, sh) == (fw, fh):
        return M
    S = np.array([[sw / fw, 0.0, 0.0], [0.0, sh / fh, 0.0], [0.0, 0.0, 1.0]], np.float64)
    return M @ S


def warp_with_margin(frame, M, out_size: int, margin_cells: float = 0.0, grid_size: int = 19):
    """Rectify ``frame`` with homography ``M`` to an ``out_size`` square, optionally adding a blank
    border of ``margin_cells`` cells around the grid. Returns an ``out_size + 2*pad`` square when
    ``margin_cells`` > 0, else a plain ``out_size`` square."""
    M = np.asarray(M, np.float64)
    pad = margin_px_for(out_size, margin_cells, grid_size)
    if pad:
        T = np.array([[1.0, 0.0, pad], [0.0, 1.0, pad], [0.0, 0.0, 1.0]], np.float64)
        size = out_size + 2 * pad
        return cv2.warpPerspective(frame, T @ M, (size, size))
    return cv2.warpPerspective(frame, M, (out_size, out_size))
