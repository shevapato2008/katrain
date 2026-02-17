"""
Board detection and perspective correction.

Ported from Fe-Fool/code/robot/image_find_focus.py (FocusFinder class).
Enhanced with:
- CLAHE preprocessing for low-contrast wood boards
- cv2.undistort when camera calibration is available
- Fallback to last known transform matrix on detection failure
"""

import cv2
import numpy as np

from katrain.vision.config import CameraConfig


class BoardFinder:
    def __init__(
        self,
        scale: float = 1.0,
        allowed_moving_girth: int = 300,
        allowed_moving_length: int = 10,
        min_perimeter: int = 600,
        camera_config: CameraConfig | None = None,
    ):
        self.scale = scale
        self.allowed_moving_girth = allowed_moving_girth
        self.allowed_moving_length = allowed_moving_length
        self.min_perimeter = min_perimeter
        self.camera_config = camera_config
        self.pre_corner_point = [(0, 0), (0, 0), (0, 0), (0, 0)]
        self.pre_max_length = 0
        self.is_first = True
        self.last_transform_matrix: np.ndarray | None = None
        self.last_warp_size: tuple[int, int] | None = None

    def find_focus(
        self, img: np.ndarray, min_threshold: int = 30, max_threshold: int = 250, use_clahe: bool = False
    ) -> tuple[np.ndarray | None, bool]:
        """
        Detect board outline and apply perspective transform.

        Returns:
            (warped_image, success) — warped_image is None if detection failed
        """
        source_img = img.copy()

        # Undistort if calibration available
        if self.camera_config and self.camera_config.is_calibrated:
            source_img = cv2.undistort(source_img, self.camera_config.camera_matrix, self.camera_config.dist_coeffs)

        processed = source_img.copy()

        if use_clahe:
            lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_ch = clahe.apply(l_ch)
            lab = cv2.merge([l_ch, a_ch, b_ch])
            processed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        processed = cv2.GaussianBlur(processed, (3, 3), 0, 0)
        canny = cv2.Canny(processed, min_threshold, max_threshold)
        k = np.ones((3, 3), np.uint8)
        canny = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, k)

        contours, _ = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:1]
        if len(contours) == 0:
            return None, False

        max_length = abs(cv2.arcLength(contours[0], True))
        if max_length < self.min_perimeter:
            return None, False

        temp = np.ones(canny.shape, np.uint8) * 255
        approx = cv2.approxPolyDP(contours[0], 10, True)
        cv2.drawContours(temp, approx, -1, (0, 255, 0), 1)

        corners = cv2.goodFeaturesToTrack(temp, 25, 0.1, 10)
        if corners is None:
            return None, False

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        cv2.cornerSubPix(temp, corners, (11, 11), (-1, -1), criteria)
        corners = corners.astype(np.intp)
        point_list = [(x, y) for [[x, y]] in corners]

        if len(point_list) < 4:
            return None, False

        corner_point = self._find_corner(point_list)
        sort_corner = self._sort_corner(corner_point)

        if self.is_first:
            self.pre_corner_point = sort_corner
            self.pre_max_length = max_length
            self.is_first = False

        if abs(self.pre_max_length - max_length) > self.allowed_moving_girth:
            self.pre_max_length = max_length
            return None, False

        if np.max(abs(np.array(sort_corner) - np.array(self.pre_corner_point))) > self.allowed_moving_length:
            self.pre_corner_point = sort_corner
            return None, False

        self.pre_corner_point = sort_corner
        self.pre_max_length = max_length

        h, w = self._calc_size(sort_corner)
        dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        src = np.float32(sort_corner)
        M = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(source_img, M, (int(w), int(h)))
        warped = cv2.flip(warped, 1)

        # Save transform for fallback
        self.last_transform_matrix = M
        self.last_warp_size = (int(w), int(h))

        return warped, True

    def _calc_size(self, corners):
        h = max(corners[2][1] - corners[1][1], corners[3][1] - corners[0][1]) * self.scale
        w = max(corners[0][0] - corners[1][0], corners[3][0] - corners[2][0]) * self.scale
        return h, w

    def _sort_corner(self, pts):
        pts = sorted(pts, key=lambda p: p[1])
        top = sorted(pts[:2], key=lambda p: p[0], reverse=True)
        bot = sorted(pts[2:], key=lambda p: p[0])
        return [top[0], top[1], bot[0], bot[1]]

    def _find_corner(self, point_list):
        """Find the 4 points forming the largest quadrilateral. O(n^3)."""
        n = len(point_list)
        best = 0
        best_idx = [0, 0, 0, 0]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                m1, m2, m1p, m2p = 0, 0, 0, 0
                for kk in range(n):
                    if kk in (i, j):
                        continue
                    a = point_list[i][1] - point_list[j][1]
                    b = point_list[j][0] - point_list[i][0]
                    c = point_list[i][0] * point_list[j][1] - point_list[j][0] * point_list[i][1]
                    t = a * point_list[kk][0] + b * point_list[kk][1] + c
                    area = (
                        abs(
                            (point_list[i][0] - point_list[kk][0]) * (point_list[j][1] - point_list[kk][1])
                            - (point_list[j][0] - point_list[kk][0]) * (point_list[i][1] - point_list[kk][1])
                        )
                        / 2
                    )
                    if t > 0 and area > m1:
                        m1, m1p = area, kk
                    elif t < 0 and area > m2:
                        m2, m2p = area, kk
                if m1 and m2 and m1 + m2 > best:
                    best_idx = [i, j, m1p, m2p]
                    best = m1 + m2
        return [point_list[i] for i in best_idx]
