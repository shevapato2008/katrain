import cv2
import numpy as np
import pytest

from katrain.vision import led_geometry_calibrator, stone_classifier
from katrain.vision.led_geometry_calibrator import (
    CALIBRATION_ANCHORS,
    LedGeometryCalibrator,
    check_frame_exposure,
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
            is_green = self.led.rgb[0] == 0 and self.led.rgb[2] == 0 and self.led.rgb[1] > 0
            if self.green_missing_for == self.led.current and is_green:
                # 缺失是彻底的(两档亮度都拍不到),不是「暗处偏弱」——所以不受
                # FLASH_LEVELS 影响,模拟绿色通道在这颗锚点上真的坏了。
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
    # green 在两档亮度上都拍不到信号(彻底缺失,不是可以靠拉满亮度救回的弱信号)
    # 才换色到 red —— 换色本身就是本测试要钉住的行为。
    assert attempts[:3] == [(0, 96, 0), (0, 255, 0), (96, 0, 0)]


def test_build_lock_samples_each_baseline_frame_once(monkeypatch):
    # `_build_lock` grabs an 8-frame burst. Sampling the 361-point grid is the SBC
    # hotspot (~0.5s/call on RK3562), so it must sample each warp EXACTLY once — not
    # 16x (build_baseline(7) + classify(1) + build_baseline(8), re-sampling 7 twice).
    calls = {"n": 0}
    real_sample_grid = stone_classifier.sample_grid

    def counting_sample_grid(*args, **kwargs):
        calls["n"] += 1
        return real_sample_grid(*args, **kwargs)

    monkeypatch.setattr(stone_classifier, "sample_grid", counting_sample_grid)

    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert calls["n"] == 8


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


def test_locate_anchor_retries_at_full_brightness_when_signal_is_weak():
    """白天 96 档折算 peak≈7-28、闸是 20(spec §2.2)。弱信号必须换满亮度再试一次,
    而不是直接判 anchor_not_found。"""
    led = FakeLed()
    points = _synthetic_camera_points()

    class DimCapture(FakeCapture):
        def _frame(self):
            frame = np.full((900, 1000, 3), 150, np.uint8)
            if self.led.current is not None:
                x, y = self.camera_points[self.led.current]
                # 96 档在这个场景下只抬 8 个灰阶(低于 peak>=20 的闸);255 档抬 40。
                lift = 40 if max(self.led.rgb) == 255 else 8
                cv2.circle(frame, (round(x), round(y)), 8, (0, 150 + lift, 0), -1)
            return frame

    capture = DimCapture(led, points)
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    levels = [a.get("level") for a in result.attempts if a.get("ok")]
    assert levels and all(level == 255 for level in levels)
    assert any(a["reason"] == "low_signal" and a["level"] == 96 for a in result.attempts)


def test_dark_room_still_succeeds_at_the_dim_level_only():
    """暗处 96 档就够(peak 94-198),不许无谓地把灯拉满 —— 削顶会把质心拉偏。"""
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert all(a["level"] == 96 for a in result.attempts if a.get("ok"))


def test_check_frame_exposure_rejects_blown_out_frame():
    frame = np.full((480, 640, 3), 253, np.uint8)

    ok, reason, stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_overexposed"
    assert stats["median"] == pytest.approx(253, abs=1)
    assert stats["clip_frac"] > 0.5


def test_check_frame_exposure_rejects_black_frame():
    frame = np.full((480, 640, 3), 2, np.uint8)

    ok, reason, _stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_underexposed"


def test_check_frame_exposure_accepts_the_band_that_worked_in_the_dark():
    # 01:32 那次成功标定时盘面中位 ≈150(spec §2.1 表)。
    frame = np.full((480, 640, 3), 150, np.uint8)

    ok, reason, _stats = check_frame_exposure(frame)

    assert ok is True
    assert reason is None


def test_calibrate_fails_fast_on_overexposed_frame_without_flashing_any_led():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    capture._frame = lambda: np.full((900, 1000, 3), 253, np.uint8)

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is False
    assert result.reason == "frame_overexposed"
    # D2③ + 用户体验:环境不行的时候不要先闪 13 颗灯再说不行。
    assert led.attempts == []


def test_check_frame_exposure_pins_clip_frac_alone():
    """median 远低于 245,只有 clip_frac 越线 —— 单独钉住 EXPOSURE_CLIP_FRAC_MAX。"""
    frame = np.full((480, 640, 3), 100, np.uint8)
    frame[:192] = 255                      # 192/480 = 40% 的行削顶

    ok, reason, stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_overexposed"
    assert stats["median"] == pytest.approx(100, abs=1)      # 远在 245 之下
    assert stats["clip_frac"] == pytest.approx(0.40, abs=0.02)


def test_detect_led_centroid_ignores_a_brighter_blob_outside_the_roi():
    """白天实测:(15,9) 被画面右上角眩光抢走,报到 (1807,142) 而真值在 (1286,629)。
    ROI 内没有更亮的东西时,ROI 外再亮也不许赢。"""
    dark = np.full((900, 1000, 3), 120, np.uint8)
    lit = dark.copy()
    cv2.circle(lit, (300, 400), 8, (120, 170, 120), -1)   # 真 LED:抬 50
    cv2.circle(lit, (900, 80), 20, (120, 240, 120), -1)   # 眩光:抬 120,更亮更大

    without_roi = detect_led_centroid(dark, lit, channel=1)
    with_roi = detect_led_centroid(dark, lit, channel=1, roi=(300.0, 400.0, 60.0))

    assert without_roi.centroid == pytest.approx((900, 80), abs=3.0)   # 现状:被抢走
    assert with_roi.ok is True
    assert with_roi.centroid == pytest.approx((300, 400), abs=2.0)


def test_calibrate_uses_corner_homography_to_roi_the_star_points():
    """四角先全画幅定位;随后 9 颗星位改用四角单应预测的 ROI 搜索,不再被
    画面别处更亮的假货抢走 —— 只在非四角阶段出现的眩光复现 spec §2.2 的长相
    (被抢走的是九星,四角当时是对的)。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    corners = set(CALIBRATION_ANCHORS[:4])

    class GlareCapture(FakeCapture):
        def _frame(self):
            frame = super()._frame()
            if self.led.current is not None and self.led.current not in corners:
                cv2.circle(frame, (970, 20), 18, (255, 255, 255), -1)   # 只在九星阶段出现
            return frame

    capture = GlareCapture(led, points)
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert result.lock is not None
    # 九星必须落回它们真正的位置,而不是那块假货。
    for (row, col), got in zip(CALIBRATION_ANCHORS[4:], result.lock.diag["anchors"][4:]):
        want = points[(row, col)]
        assert (got["camera"][0], got["camera"][1]) == pytest.approx(tuple(want), abs=3.0)


def test_roi_hit_costs_one_attempt_and_a_poisoned_roi_falls_back(monkeypatch):
    """ROI 半径够 ⇒ 一次命中,不必回退。

    这颗合成锚点的预测中心和真实相机坐标重合(dist≈0),所以只断言"命中一次"钉不住
    ROI_CELLS —— 任何 >=1px 的半径都赢(连 ROI_RADIUS_MIN_PX=24px 那个地板都用不上就已经
    够用),把 ROI_CELLS 改多小都是绿的。补一个 40px 的偏移:LED 画的是半径 8px 的圆,
    地板半径 24px 时 ROI 边缘离真锚点只有 40-8=32px(> 24px)才能把整颗 LED 挡在圈外
    ——挡不干净(比如偏移 30px 时只挡住 22px,还差 2px 才够着地板半径,ROI 会把 LED
    的近侧那一小片圆弧漏进来,detect_led_centroid 照样命中,测试对 ROI_CELLS 的
    改动完全不敏感)。40px 比 ROI_CELLS=1.5 在这颗锚点撑出的半径(约 64px)小,
    真半径时 LED 整颗都在 ROI 内、不会被裁到只剩一角。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    capture = FakeCapture(led, points)

    real_predict = led_geometry_calibrator.predict_anchor_roi

    def offset_predict(homography, row, col):
        cx, cy, radius = real_predict(homography, row, col)
        if (row, col) == (3, 3):
            cx += 40.0  # 见上:32px(=40-8px LED 半径)> ROI_RADIUS_MIN_PX(24px) 才挡得干净;
            # 40px < ROI_CELLS(1.5)*local_cell(≈64px) 才不会连真半径都装不下整颗 LED。
        return cx, cy, radius

    monkeypatch.setattr(led_geometry_calibrator, "predict_anchor_roi", offset_predict)

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()
    assert result.ok is True
    star = [a for a in result.attempts if (a["row"], a["col"]) == (3, 3)]
    assert len(star) == 1, f"ROI 半径够时该一次命中,实际 {len(star)} 次: {star}"


def test_calibrate_recovers_when_predicted_roi_is_poisoned(monkeypatch):
    """预测中心被投毒偏移 120px(≈2.8 格,复审实测过 70px 就已经 anchor_not_found)——
    ROI 内找不到真 LED,六次带 ROI 的尝试全部 low_signal 之后必须回退到全画幅再试一次,
    而不是让整条标定 anchor_not_found(离群锚点本该被 fit_geometry_from_anchors 的
    RANSAC 吸收,不该先在 ROI 这一步就整体报废)。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    capture = FakeCapture(led, points)

    real_predict = led_geometry_calibrator.predict_anchor_roi

    def poisoned_predict(homography, row, col):
        cx, cy, radius = real_predict(homography, row, col)
        return cx + 120.0, cy, radius

    monkeypatch.setattr(led_geometry_calibrator, "predict_anchor_roi", poisoned_predict)

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    star = [a for a in result.attempts if (a["row"], a["col"]) == (3, 3)]
    assert star[-1].get("roi_fallback") is True
    assert star[-1]["ok"] is True


def test_calibrate_tolerates_up_to_four_missing_anchors():
    """min_inliers=9 已经允许 13 个里有 4 个外点;检测阶段不该比拟合阶段更严。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    invisible = {(3, 3), (9, 15)}

    class PartialCapture(FakeCapture):
        def _frame(self):
            if self.led.current in invisible:
                return np.full((900, 1000, 3), 90, np.uint8)  # 这两颗任何颜色都看不见
            return super()._frame()

    result = LedGeometryCalibrator(led=led, capture=PartialCapture(led, points)).calibrate()

    assert result.ok is True
    assert result.lock is not None


def test_calibrate_stops_when_too_few_anchors_are_located():
    led = FakeLed()
    points = _synthetic_camera_points()
    visible = {(0, 0), (0, 18), (18, 18), (18, 0)}

    class MostlyBlindCapture(FakeCapture):
        def _frame(self):
            if self.led.current not in visible:
                return np.full((900, 1000, 3), 90, np.uint8)
            return super()._frame()

    result = LedGeometryCalibrator(led=led, capture=MostlyBlindCapture(led, points)).calibrate()

    assert result.ok is False
    assert result.reason == "too_few_anchors"
    # 诊断必须活着 —— 用户要知道是哪几颗没找到。
    assert sum(1 for a in result.attempts if a.get("ok")) == 4


def test_check_frame_exposure_pins_median_alone():
    """clip_frac 为 0,只有 median 越线 —— 单独钉住 EXPOSURE_MEDIAN_MAX。"""
    frame = np.full((480, 640, 3), 246, np.uint8)            # 246 < 250 ⇒ 不算削顶

    ok, reason, stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_overexposed"
    assert stats["median"] == pytest.approx(246, abs=1)
    assert stats["clip_frac"] == pytest.approx(0.0, abs=0.01)  # 一个像素都没到 250
