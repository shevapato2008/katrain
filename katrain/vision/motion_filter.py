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

    def __init__(
        self,
        change_ratio_threshold: float = 0.05,
        pixel_diff_threshold: int = 30,
        illumination_invariant: bool = False,
    ):
        """
        Args:
            change_ratio_threshold: Max fraction of pixels that can change significantly (default 5%)
            pixel_diff_threshold: Per-pixel intensity difference to count as "changed" (default 30)
        """
        self.change_ratio_threshold = change_ratio_threshold
        self.pixel_diff_threshold = pixel_diff_threshold
        self.illumination_invariant = illumination_invariant
        self.prev_frame: np.ndarray | None = None
        self._prev_features: np.ndarray | None = None
        self._prev_gray: np.ndarray | None = None

    @staticmethod
    def _illumination_features(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Remove broad light changes while retaining grid, hand and stone edges."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        if gray.shape[1] > 640:
            gray = cv2.resize(gray, (640, round(gray.shape[0] * 640 / gray.shape[1])),
                              interpolation=cv2.INTER_AREA)
        local_light = cv2.boxFilter(gray, -1, (19, 19))
        features = cv2.divide(gray, cv2.add(local_light, 10), scale=128)
        return gray, features

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
        self._prev_features = None
        self._prev_gray = None

    def is_stable_with_regions(
        self,
        frame: np.ndarray,
        roi_mask: np.ndarray | None = None,
        global_change_ratio_threshold: float = 0.30,
    ) -> tuple[bool, float | None, float]:
        """Check stability using an optional ROI and a full-frame motion guard."""
        frame_shape = frame.shape
        gray = features = None
        if self.illumination_invariant:
            gray, features = self._illumination_features(frame)
        if self.prev_frame is None:
            self.prev_frame = frame.copy()
            self._prev_gray, self._prev_features = gray, features
            gray_shape = frame.shape[:2]
            valid_mask = roi_mask is not None and roi_mask.shape == gray_shape and bool(np.any(roi_mask))
            return True, 0.0 if valid_mask else None, 0.0

        if self.prev_frame.shape != frame_shape:
            self.prev_frame = frame.copy()
            self._prev_gray, self._prev_features = gray, features
            return True, None, 0.0

        if self.illumination_invariant:
            # A dark frame contains too little structure to normalize reliably.
            # Keep the original brightness guard when the light disappears.
            if min(cv2.mean(gray)[0], cv2.mean(self._prev_gray)[0]) < 35:
                changed = cv2.absdiff(gray, self._prev_gray) > 30
            else:
                changed = cv2.absdiff(features, self._prev_features) > self.pixel_diff_threshold
            if roi_mask is not None and roi_mask.shape == frame.shape[:2] and roi_mask.shape != changed.shape:
                roi_mask = cv2.resize(roi_mask.astype(np.uint8),
                                      (changed.shape[1], changed.shape[0]),
                                      interpolation=cv2.INTER_NEAREST).astype(bool)
            gray_diff = changed
        else:
            diff = cv2.absdiff(frame, self.prev_frame)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
            changed = gray_diff > self.pixel_diff_threshold
        full_ratio = float(np.mean(changed))

        valid_mask = roi_mask is not None and roi_mask.shape == gray_diff.shape and bool(np.any(roi_mask))
        self.prev_frame = frame.copy()
        self._prev_gray, self._prev_features = gray, features
        if not valid_mask:
            return bool(full_ratio < self.change_ratio_threshold), None, full_ratio

        roi_ratio = float(np.mean(changed[roi_mask]))
        stable = roi_ratio < self.change_ratio_threshold and full_ratio < global_change_ratio_threshold
        return bool(stable), roi_ratio, full_ratio
