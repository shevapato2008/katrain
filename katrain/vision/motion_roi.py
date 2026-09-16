"""Board-region masks used to restrict motion detection."""

from __future__ import annotations

import cv2
import numpy as np


def _normalise_corners(corners) -> np.ndarray | None:
    try:
        points = np.asarray(corners, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    return np.ascontiguousarray(points)


def _normalise_source_size(source_size) -> tuple[float | None, float | None] | None:
    try:
        width, height = source_size
    except (TypeError, ValueError):
        return None
    if width is None and height is None:
        return (None, None)
    if width is None or height is None:
        return None
    try:
        width, height = float(width), float(height)
    except (TypeError, ValueError):
        return None
    if not np.isfinite((width, height)).all() or width <= 0 or height <= 0:
        return None
    return (width, height)


def build_motion_roi_mask(
    frame_shape: tuple[int, ...],
    corners,
    source_size: tuple[int | None, int | None] = (None, None),
) -> np.ndarray | None:
    """Return an expanded boolean board mask in frame coordinates, or ``None``."""
    try:
        height, width = int(frame_shape[0]), int(frame_shape[1])
    except (IndexError, TypeError, ValueError):
        return None
    if height <= 0 or width <= 0:
        return None

    points = _normalise_corners(corners)
    dimensions = _normalise_source_size(source_size)
    if points is None or dimensions is None:
        return None
    geometry = points.astype(np.float64, copy=True)
    if dimensions != (None, None):
        source_width, source_height = dimensions
        geometry *= np.array([width / source_width, height / source_height], dtype=np.float64)

    edge_lengths = np.linalg.norm(np.roll(geometry, -1, axis=0) - geometry, axis=1)
    mean_edge_length = float(edge_lengths.mean())
    if not np.isfinite(mean_edge_length) or mean_edge_length > 18 * max(height, width):
        return None
    radius = max(1, round(mean_edge_length / 18))
    points = np.ascontiguousarray(geometry, dtype=np.float32)

    if cv2.contourArea(points.reshape(-1, 1, 2)) <= 0:
        return None
    image_rect = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    intersection_area, _ = cv2.intersectConvexConvex(points, image_rect)
    if intersection_area <= 0:
        return None

    board = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(board, np.rint(points).astype(np.int32), 1)
    if not np.any(board):
        return None

    kernel_size = 2 * radius + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.dilate(board, kernel, iterations=1).astype(bool)


class MotionRoiMaskCache:
    def __init__(self) -> None:
        self._masks: dict[tuple, np.ndarray | None] = {}

    def get(self, frame_shape, corners, source_size=(None, None)) -> np.ndarray | None:
        points = _normalise_corners(corners)
        dimensions = _normalise_source_size(source_size)
        corner_key = points.tobytes() if points is not None else repr(corners)
        key = (tuple(frame_shape) if hasattr(frame_shape, "__iter__") else frame_shape, corner_key, dimensions)
        if key not in self._masks:
            self._masks[key] = build_motion_roi_mask(frame_shape, corners, source_size)
        return self._masks[key]

    def invalidate(self) -> None:
        self._masks.clear()
