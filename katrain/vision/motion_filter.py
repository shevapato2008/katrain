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
        if self.prev_frame is None:
            self.prev_frame = frame.copy()
            return True

        diff = cv2.absdiff(frame, self.prev_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
        changed_ratio = np.sum(gray_diff > self.pixel_diff_threshold) / gray_diff.size
        self.prev_frame = frame.copy()
        return bool(changed_ratio < self.change_ratio_threshold)
