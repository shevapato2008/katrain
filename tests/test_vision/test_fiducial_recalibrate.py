import numpy as np
import cv2
import pytest
from katrain.vision.fiducial_recalibrate import (
    select_fiducials, predict_camera_positions, detect_led_centroids,
    solve_frame_homography, drift_from_homography, CentroidResult,
)

OUT = 950
SPACING = (OUT - 1) / 18.0


def _canon(r, c):
    return (c * SPACING, r * SPACING)


def _empty_board():
    return [[None] * 19 for _ in range(19)]


def test_select_excludes_occupied_guidance_and_neighbors():
    b = _empty_board()
    b[0][1] = "B"            # 4-neighbor of corner (0,0)
    chosen = select_fiducials(b, {"row": 9, "col": 9}, target=13, min_count=8)
    assert (0, 0) not in chosen          # excluded: neighbor occupied
    assert (9, 9) not in chosen          # excluded: guidance point
    assert len(chosen) >= 8
    assert len(set(chosen)) == len(chosen)
    for (r, c) in chosen:
        assert b[r][c] is None


def test_select_prioritizes_corners_and_star():
    chosen = select_fiducials(_empty_board(), None, target=13, min_count=8)[:13]
    for p in [(0, 0), (0, 18), (18, 0), (18, 18), (9, 9), (3, 3), (15, 15)]:
        assert p in chosen


def _homography(angle_deg, tx, ty):
    th = np.radians(angle_deg)
    return np.array([[np.cos(th), -np.sin(th), tx],
                     [np.sin(th),  np.cos(th), ty],
                     [0, 0, 1]], np.float64)


def test_detect_assigns_blobs_per_roi_and_rejects_reflection():
    coords = [(0, 0), (0, 18), (18, 0), (18, 18), (9, 9)]
    expected = {p: _canon(*p) for p in coords}
    dark = np.zeros((OUT, OUT, 3), np.uint8)
    lit = dark.copy()
    for (r, c) in coords:
        x, y = int(_canon(r, c)[0]), int(_canon(r, c)[1])
        cv2.circle(lit, (x, y), 6, (0, 200, 0), -1)   # green blobs (channel 1)
    cv2.circle(lit, (470, 10), 5, (0, 180, 0), -1)     # stray reflection, far from any ROI
    res = detect_led_centroids(dark, lit, expected, channel=1, search_px=0.7 * SPACING)
    for p in coords:
        assert res[p].ok
        ex, ey = _canon(*p)
        assert abs(res[p].centroid[0] - ex) < 3 and abs(res[p].centroid[1] - ey) < 3


def test_detect_low_signal_is_rejected():
    coords = [(0, 0)]
    expected = {p: _canon(*p) for p in coords}
    dark = np.zeros((OUT, OUT, 3), np.uint8)
    lit = dark.copy()  # no blob -> low signal
    res = detect_led_centroids(dark, lit, expected, channel=1, search_px=0.7 * SPACING)
    assert not res[(0, 0)].ok
    assert res[(0, 0)].reason == "low_signal"


def test_solve_recovers_rotation_translation():
    coords = [(0, 0), (0, 9), (0, 18), (9, 0), (9, 18), (18, 0), (18, 9), (18, 18), (9, 9)]
    T = _homography(4.0, 12.0, -8.0)
    canon = np.array([_canon(*p) for p in coords], np.float64).reshape(-1, 1, 2)
    cam = cv2.perspectiveTransform(canon, np.linalg.inv(T)).reshape(-1, 2)  # camera pts
    detected = [(coords[i], (float(cam[i][0]), float(cam[i][1]))) for i in range(len(coords))]
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert fit.ok
    back = cv2.perspectiveTransform(cam.reshape(-1, 1, 2), fit.M).reshape(-1, 2)
    for i, p in enumerate(coords):
        ex, ey = _canon(*p)
        assert abs(back[i][0] - ex) < 2 and abs(back[i][1] - ey) < 2


def test_solve_four_points_one_outlier_fails():
    coords = [(0, 0), (0, 18), (18, 0), (18, 18)]
    detected = [(coords[i], _canon(*coords[i])) for i in range(4)]
    detected[0] = (coords[0], (_canon(*coords[0])[0] + 120, _canon(*coords[0])[1] - 90))  # bad
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert not fit.ok


def test_solve_nine_points_two_outliers_passes():
    coords = [(0, 0), (0, 9), (0, 18), (9, 0), (9, 18), (18, 0), (18, 9), (18, 18), (9, 9)]
    detected = [(coords[i], _canon(*coords[i])) for i in range(len(coords))]
    detected[2] = (coords[2], (_canon(*coords[2])[0] + 200, _canon(*coords[2])[1]))   # outlier
    detected[5] = (coords[5], (_canon(*coords[5])[0], _canon(*coords[5])[1] - 200))   # outlier
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert fit.ok and fit.inlier_count >= 6


def test_drift_from_homography_recovers_components():
    M0 = np.eye(3)
    Mf = _homography(3.0, 10.0, 5.0)
    d = drift_from_homography(Mf, M0, out_size=OUT)
    assert abs(d.dx - 10.0) < 1.0 and abs(d.dy - 5.0) < 1.0
    assert abs(d.deg - 3.0) < 0.5 and abs(d.scale - 1.0) < 0.02


def test_coordinate_target_is_warped_not_camera():
    """The load-bearing fix: solving against warped canonical (xs,ys) makes
    warpPerspective(current_frame, M_f) put fiducials on the canonical grid.
    Using camera-space points[row][col] as the target would NOT."""
    coords = [(0, 0), (0, 9), (0, 18), (9, 0), (9, 18), (18, 0), (18, 9), (18, 18), (9, 9)]
    M0 = _homography(0.0, 0.0, 0.0)                       # camera == canonical baseline
    # board moved: current camera frame is the canonical grid rotated+translated
    Tmove = _homography(5.0, 15.0, -10.0)
    canon = np.array([_canon(*p) for p in coords], np.float64).reshape(-1, 1, 2)
    cam_now = cv2.perspectiveTransform(canon, np.linalg.inv(Tmove)).reshape(-1, 2)
    detected = [(coords[i], (float(cam_now[i][0]), float(cam_now[i][1]))) for i in range(len(coords))]
    fit = solve_frame_homography(detected, out_size=OUT, min_inliers=6)
    assert fit.ok
    # M_f maps current camera fiducials back onto the canonical grid:
    back = cv2.perspectiveTransform(cam_now.reshape(-1, 1, 2), fit.M).reshape(-1, 2)
    for i, p in enumerate(coords):
        ex, ey = _canon(*p)
        assert abs(back[i][0] - ex) < 2 and abs(back[i][1] - ey) < 2
