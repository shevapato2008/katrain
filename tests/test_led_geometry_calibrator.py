import cv2
import numpy as np
import pytest

from katrain.vision.led_geometry_calibrator import (
    CALIBRATION_ANCHORS,
    LedGeometryCalibrator,
    detect_led_centroid,
    fit_geometry_from_anchors,
)


def test_detect_led_centroid_rejects_reflection_and_returns_main_blob():
    dark = np.full((200, 240, 3), 25, np.uint8)
    lit = dark.copy()
    cv2.circle(lit, (160, 70), 9, (25, 180, 25), -1)
    cv2.circle(lit, (30, 150), 3, (25, 90, 25), -1)

    result = detect_led_centroid(dark, lit, channel=1)

    assert result.ok is True
    assert result.centroid == pytest.approx((160, 70), abs=1.0)
    assert result.margin > 1.5


def test_detect_led_centroid_rejects_low_signal():
    dark = np.full((100, 100, 3), 40, np.uint8)
    lit = dark.copy()
    lit[50, 50, 1] = 44

    result = detect_led_centroid(dark, lit, channel=1)

    assert result.ok is False
    assert result.reason == "low_signal"


def test_fit_geometry_uses_human_orientation_and_ransac_outliers():
    canonical = np.array([[col * 40.0, row * 40.0] for row, col in CALIBRATION_ANCHORS], np.float32)
    canonical_corners = np.array([[0, 0], [720, 0], [720, 720], [0, 720]], np.float32)
    camera_corners = np.array([[150, 100], [900, 130], [820, 850], [210, 800]], np.float32)
    H = cv2.getPerspectiveTransform(canonical_corners, camera_corners)
    camera = cv2.perspectiveTransform(canonical.reshape(-1, 1, 2), H).reshape(-1, 2)
    camera[5] += (95, -70)
    camera[10] += (-80, 90)

    fit = fit_geometry_from_anchors(list(zip(CALIBRATION_ANCHORS, camera)), out_size=721)

    assert fit.ok is True
    assert fit.inlier_count >= 11
    for row, col in ((0, 0), (0, 18), (3, 16)):
        camera_point = cv2.perspectiveTransform(np.array([[[col * 40.0, row * 40.0]]], np.float32), H)
        recovered = cv2.perspectiveTransform(camera_point, fit.M)[0, 0]
        assert recovered == pytest.approx((col * 40.0, row * 40.0), abs=2.0)


def test_fit_geometry_rejects_large_residual():
    rng = np.random.default_rng(4)
    camera = rng.uniform(0, 900, size=(len(CALIBRATION_ANCHORS), 2))

    fit = fit_geometry_from_anchors(list(zip(CALIBRATION_ANCHORS, camera)), out_size=950)

    assert fit.ok is False
    assert fit.reason in {"not_enough_inliers", "residual_too_large"}


class FakeLed:
    def __init__(self):
        self.current = None
        self.rgb = None
        self.clear_calls = 0
        self.attempts = []

    def clear(self, *, strict=False):
        self.current = None
        self.rgb = None
        self.clear_calls += 1
        return {"ok": True, "shown_at": 1.0, "errors": []}

    def set_rgb_points(self, points, *, strict=False):
        self.current = (points[0]["row"], points[0]["col"])
        self.rgb = tuple(points[0]["rgb"])
        self.attempts.append((self.current, self.rgb))
        return {"ok": True, "shown_at": 2.0, "errors": []}


class FakeCapture:
    def __init__(self, led, camera_points, *, green_missing_for=None):
        self.led = led
        self.camera_points = camera_points
        self.green_missing_for = green_missing_for
        self.seq = 0

    def _frame(self):
        frame = np.full((900, 1000, 3), 90, np.uint8)
        if self.led.current is not None:
            if self.green_missing_for == self.led.current and self.led.rgb == (0, 96, 0):
                return frame
            x, y = self.camera_points[self.led.current]
            red, green, blue = self.led.rgb
            observed = tuple(220 if value else 90 for value in (blue, green, red))
            cv2.circle(frame, (round(x), round(y)), 8, observed, -1)
        return frame

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        self.seq += 1
        return self._frame(), self.seq, float(self.seq + 10)

    def grab_burst(self, n=8, interval=0.1):
        current = self.led.current
        self.led.current = None
        frames = [self._frame() for _ in range(n)]
        self.led.current = current
        return frames


def _synthetic_camera_points():
    spacing = 949 / 18
    canonical = np.array([[col * spacing, row * spacing] for row, col in CALIBRATION_ANCHORS], np.float32)
    source = np.array([[0, 0], [949, 0], [949, 949], [0, 949]], np.float32)
    target = np.array([[180, 100], [900, 150], [800, 820], [220, 790]], np.float32)
    H = cv2.getPerspectiveTransform(source, target)
    camera = cv2.perspectiveTransform(canonical.reshape(-1, 1, 2), H).reshape(-1, 2)
    return {anchor: point for anchor, point in zip(CALIBRATION_ANCHORS, camera)}


def test_calibrator_builds_human_geometry_and_clears_led():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert result.lock is not None
    assert result.lock.empty_self_check_ok is True
    assert result.lock.points.shape == (19, 19, 2)
    assert result.lock.diag["orientation"] == "seated_human"
    assert led.current is None
    assert led.clear_calls >= len(CALIBRATION_ANCHORS) + 1


def test_calibrator_retries_red_when_green_signal_is_missing():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points(), green_missing_for=(3, 15))

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    attempts = [rgb for coord, rgb in led.attempts if coord == (3, 15)]
    assert attempts[:2] == [(0, 96, 0), (96, 0, 0)]


def test_calibrator_reports_each_detected_anchor():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    observed = []

    result = LedGeometryCalibrator(
        led=led,
        capture=capture,
        anchor_observer=lambda row, col, point, color: observed.append((row, col, point, color)),
    ).calibrate()

    assert result.ok is True
    assert [(row, col) for row, col, _point, _color in observed] == list(CALIBRATION_ANCHORS)
    assert all(color == "green" for _row, _col, _point, color in observed)
    for row, col, point, _color in observed:
        assert point == pytest.approx(_synthetic_camera_points()[(row, col)], abs=1.0)
