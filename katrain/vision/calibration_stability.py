"""Small, color-independent grid gate for the RK3562 calibration camera."""

from __future__ import annotations

import cv2
import numpy as np

from katrain.vision.motion_filter import MotionFilter

GRID_SIZE = 380
_DST = np.array([[0, 0], [379, 0], [379, 379], [0, 379]], np.float32)
_PATCH_CENTERS = tuple((x, y) for y in (38, 139, 240, 341) for x in (38, 139, 240, 341))


def _ordered_quad(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, np.float32).reshape(4, 2)
    sums = points.sum(axis=1)
    differences = points[:, 0] - points[:, 1]
    return np.array(
        [points[np.argmin(sums)], points[np.argmax(differences)],
         points[np.argmax(sums)], points[np.argmin(differences)]], np.float32
    )


def _grid_scores(gray: np.ndarray, quad: np.ndarray) -> tuple[float, ...]:
    warped = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(quad, _DST), (GRID_SIZE, GRID_SIZE))
    scores = []
    for cx, cy in _PATCH_CENTERS:
        patch = warped[cy - 30:cy + 31, cx - 30:cx + 31]
        yy, xx = np.mgrid[cy - 30:cy + 31, cx - 30:cx + 31]
        dx = np.abs(xx - np.rint(xx * 18 / 379) * 379 / 18)
        dy = np.abs(yy - np.rint(yy * 18 / 379) * 379 / 18)
        on_line = (dx < 2) | (dy < 2)
        off_line = (dx > 5) & (dy > 5)
        scores.append(float(np.median(patch[off_line]) - np.median(patch[on_line])))
    return tuple(scores)


def find_visible_grid(frame: np.ndarray, previous: np.ndarray | None = None) -> np.ndarray | None:
    """Return TL,TR,BR,BL grid corners only when all five regions show grid lines.

    The printed board on the device is white. Warm-wood HSV detection cannot be used
    as a required gate. Adaptive thresholding locates the large grid quadrilateral;
    the line-versus-cell contrast rejects a still hand even with zero frame motion.
    """
    height, width = frame.shape[:2]
    scale = min(1.0, 640.0 / max(height, width))
    small = cv2.resize(frame, (round(width * scale), round(height * scale)),
                       interpolation=cv2.INTER_AREA) if scale < 1 else frame
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    candidates: list[np.ndarray] = []
    if previous is not None:
        candidates.append(np.asarray(previous, np.float32) * scale)
    frame_area = gray.shape[0] * gray.shape[1]
    # The dark printed grid can merge into the white board in the normal
    # threshold after AE changes. Its inverse still gives a closed grid border.
    for threshold_mode in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       threshold_mode, 51, 2)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:25]:
            area = cv2.contourArea(contour)
            if area < frame_area * 0.12:
                break
            if area > frame_area * 0.90:
                continue
            polygon = cv2.approxPolyDP(contour, 0.035 * cv2.arcLength(contour, True), True)
            if len(polygon) == 4 and cv2.isContourConvex(polygon):
                candidates.append(_ordered_quad(polygon))
    best: tuple[float, np.ndarray] | None = None
    for quad in candidates:
        if cv2.contourArea(quad) < frame_area * 0.12:
            continue
        scores = _grid_scores(gray, quad)
        if min(scores) < 3.5:
            continue
        quality = min(scores) * 2 + sum(scores) / len(scores)
        if best is None or quality > best[0]:
            best = (quality, quad)
    return None if best is None else best[1] / scale


def check_grid_lighting(frame: np.ndarray, quad: np.ndarray) -> tuple[str | None, dict]:
    """Conservative board-only exposure check; a hand shadow is gated separately."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    warped = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(quad.astype(np.float32), _DST),
                                 (GRID_SIZE, GRID_SIZE))
    inner = warped[12:-12, 12:-12]
    stats = {"board_median": float(np.median(inner)),
             "board_clip_frac": float(np.mean(inner >= 250)),
             "board_shadow_frac": float(np.mean(inner <= 20))}
    if stats["board_median"] >= 230 or stats["board_clip_frac"] >= 0.10:
        return "frame_overexposed", stats
    if stats["board_median"] <= 50:
        return "frame_underexposed", stats
    return None, stats


class CalibrationStabilityGate:
    def __init__(self, *, required_frames: int = 4):
        self.required_frames = required_frames
        self.motion = MotionFilter(change_ratio_threshold=0.035, pixel_diff_threshold=13,
                                   illumination_invariant=True)
        self.capture_motion = MotionFilter(change_ratio_threshold=0.05, pixel_diff_threshold=13,
                                           illumination_invariant=True)
        self.stable_frames = 0
        self.quad: np.ndarray | None = None
        self.anchor_quad: np.ndarray | None = None
        self.grid_visible = False
        self._frame_scale = 1.0
        self._anchor_frame: np.ndarray | None = None
        self._led_corners = []
        self._led_drift = None
        self._led_bounds = None
        self.last_motion_ratios: tuple[float | None, float] = (None, 0.0)

    @staticmethod
    def _small(frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        return cv2.resize(frame, (round(w * min(1, 640 / w)), round(h * min(1, 640 / w))),
                          interpolation=cv2.INTER_AREA) if w > 640 else frame

    def reset(self) -> None:
        self.motion.reset()
        self.capture_motion.reset()
        self.stable_frames = 0

    def confirm_anchor(self, row=None, col=None, point=None) -> None:
        """Keep the board position of the first confirmed LED point across transient resets."""
        if self.anchor_quad is None and self.quad is not None:
            self.anchor_quad = self.quad.copy()
        if self._anchor_frame is None and self.capture_motion.prev_frame is not None:
            self._anchor_frame = self.capture_motion.prev_frame.copy()
        if point is not None and (row, col) in ((0, 0), (0, 18), (18, 18), (18, 0)):
            self._led_corners.append(np.asarray(point, np.float32) * self._frame_scale)
            if len(self._led_corners) == 4 and self._anchor_frame is not None:
                from katrain.vision.geometry_drift import GeometryDriftMonitor

                corners = np.asarray(self._led_corners, np.float32)
                spacing = float(np.median(np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1))) / 18
                height, width = self._anchor_frame.shape[:2]
                x0, y0 = np.maximum(np.floor(corners.min(axis=0)).astype(int), 0)
                x1, y1 = np.minimum(np.ceil(corners.max(axis=0)).astype(int) + 1, (width, height))
                if x1 <= x0 or y1 <= y0:
                    return  # final corner geometry validation will reject invalid points
                self._led_bounds = (x0, y0, x1, y1)
                self._led_drift = GeometryDriftMonitor(
                    self._anchor_frame[y0:y1, x0:x1], cell_spacing_px=spacing,
                    threshold_cells=0.25, consecutive_frames=1,
                )

    def _led_displaced(self, small: np.ndarray) -> bool:
        if self._led_drift is None:
            return False
        x0, y0, x1, y1 = self._led_bounds
        return self._led_drift.update(small[y0:y1, x0:x1]).degraded

    def anchors_displaced(self) -> bool:
        """A newly stable board must still align with the already confirmed LED points."""
        if self.motion.prev_frame is not None and self._led_displaced(self.motion.prev_frame):
            return True
        if self.anchor_quad is None or self.quad is None:
            return False
        edges = np.linalg.norm(np.roll(self.anchor_quad, -1, axis=0) - self.anchor_quad, axis=1)
        cell_px = float(np.median(edges)) / 18.0
        # One corner can jump a few pixels when an LED or passing shadow changes
        # the contour; a moved board shifts multiple corners together.
        return bool(np.median(np.linalg.norm(self.quad - self.anchor_quad, axis=1)) > 0.25 * cell_px)

    @staticmethod
    def _board_mask(small: np.ndarray, frame: np.ndarray, quad: np.ndarray | None) -> np.ndarray | None:
        if quad is None:
            return None
        ratio = small.shape[1] / frame.shape[1]
        mask = np.zeros(small.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, np.rint(quad * ratio).astype(np.int32), 1)
        return mask.astype(bool)

    def observe(self, frame: np.ndarray) -> tuple[bool, str | None]:
        quad = find_visible_grid(frame, self.quad)
        small = self._small(frame)
        self._frame_scale = small.shape[1] / frame.shape[1]
        self.grid_visible = quad is not None
        if quad is not None:
            self.quad = quad
        mask = self._board_mask(small, frame, self.quad)
        first = self.motion.prev_frame is None
        stable, roi_ratio, full_ratio = self.motion.is_stable_with_regions(small, mask)
        self.last_motion_ratios = (roi_ratio, full_ratio)
        if first or not stable:
            self.stable_frames = 0
            return False, "board_motion"
        self.stable_frames += 1
        ready = self.stable_frames >= self.required_frames
        if ready:
            # Capture starts by comparing against this release frame, including
            # the very first dark/lit sample. Reuse its small image and grid ROI.
            self.capture_motion.is_stable_with_regions(small, mask)
        return ready, None

    def capture_reason(self, frame: np.ndarray) -> str | None:
        quad = find_visible_grid(frame, self.quad)
        self.grid_visible = quad is not None
        if quad is not None:
            self.quad = quad
        small = self._small(frame)
        if self._led_displaced(small):
            return "board_moved"
        stable, _roi_ratio, _full_ratio = self.capture_motion.is_stable_with_regions(
            small, self._board_mask(small, frame, self.quad)
        )
        return None if stable else "board_motion"

    def anchor_roi(self, row: int, col: int) -> tuple[float, float, float] | None:
        if self.quad is None or not self.grid_visible:
            return None
        # Human coordinates: (0,0)=bottom-left in the camera, (0,18)=top-left.
        src = np.array([[0, 0], [18, 0], [18, 18], [0, 18]], np.float32)
        dst = self.quad[[3, 0, 1, 2]].astype(np.float32)
        H = cv2.getPerspectiveTransform(src, dst)
        point = cv2.perspectiveTransform(np.array([[[float(col), float(row)]]], np.float32), H)[0, 0]
        edge = min(np.linalg.norm(dst[0] - dst[1]), np.linalg.norm(dst[0] - dst[3]))
        radius = max(40.0, float(edge) / 18 * 2.5)
        return float(point[0]), float(point[1]), radius
