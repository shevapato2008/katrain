"""
Inter-frame motion filter to skip processing during hand movements.

Improved from Fe-Fool's max-pixel-diff approach:
- Uses percentage of significantly changed pixels instead of single max pixel value
- More robust to auto-exposure changes and localized reflections
- Applied to raw camera frame BEFORE board detection (saves compute)
"""

import cv2
import numpy as np


class MotionFilter:
    """Rejects frames where significant pixel change indicates motion."""

    def __init__(self, change_ratio_threshold: float = 0.05, pixel_diff_threshold: int = 30):
        """
        Args:
            change_ratio_threshold: Max fraction of pixels that can change significantly (default 5%)
            pixel_diff_threshold: Per-pixel intensity difference to count as "changed" (default 30)
        """
        self.change_ratio_threshold = change_ratio_threshold
        self.pixel_diff_threshold = pixel_diff_threshold
        self.prev_frame: np.ndarray | None = None

    def is_stable(self, frame: np.ndarray) -> bool:
        """Check if the frame is stable (no significant motion)."""
        return self.is_stable_with_ratio(frame)[0]

    def is_stable_with_ratio(self, frame: np.ndarray) -> tuple[bool, float]:
        """Check stability and return (stable, changed_ratio) for diagnostics."""
        stable, _, changed_ratio = self.is_stable_with_regions(frame)
        return stable, changed_ratio

    def reset(self) -> None:
        """Discard the current comparison baseline."""
        self.prev_frame = None

    def is_stable_with_regions(
        self,
        frame: np.ndarray,
        roi_mask: np.ndarray | None = None,
        global_change_ratio_threshold: float = 0.30,
    ) -> tuple[bool, float | None, float]:
        """Check stability using an optional ROI and a full-frame motion guard."""
        frame_shape = frame.shape
        if self.prev_frame is None:
            self.prev_frame = frame.copy()
            gray_shape = frame.shape[:2]
            valid_mask = roi_mask is not None and roi_mask.shape == gray_shape and bool(np.any(roi_mask))
            return True, 0.0 if valid_mask else None, 0.0

        if self.prev_frame.shape != frame_shape:
            self.prev_frame = frame.copy()
            return True, None, 0.0

        diff = cv2.absdiff(frame, self.prev_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
        changed = gray_diff > self.pixel_diff_threshold
        full_ratio = float(np.mean(changed))

        valid_mask = roi_mask is not None and roi_mask.shape == gray_diff.shape and bool(np.any(roi_mask))
        self.prev_frame = frame.copy()
        if not valid_mask:
            return bool(full_ratio < self.change_ratio_threshold), None, full_ratio

        roi_ratio = float(np.mean(changed[roi_mask]))
        stable = roi_ratio < self.change_ratio_threshold and full_ratio < global_change_ratio_threshold
        return bool(stable), roi_ratio, full_ratio
