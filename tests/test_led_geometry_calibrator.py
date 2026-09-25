import logging
from threading import Event

import cv2
import numpy as np
import pytest

from katrain.vision import led_geometry_calibrator, stone_classifier
from katrain.vision.led_geometry_calibrator import (
    CALIBRATION_ANCHORS,
    LedGeometryCalibrator,
    check_frame_exposure,
    detect_led_centroid,
    first_nondegenerate_quad,
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


def test_fit_geometry_readmits_anchor_that_ransac_rejected_but_the_refined_model_accepts(monkeypatch):
    """板上 OpenCV 4.11 的 RANSAC 拒掉 (18,0),而它在精修后的 M 下在门槛内;Mac 的 OpenCV 5 不拒。
    为了在任何 OpenCV 版本上都复现,把 RANSAC 的判决钉成板上那一份:(18,0) 为外点。"""
    import json
    from pathlib import Path

    status = json.loads((Path(__file__).parent / "data" / "rk3562_calib_anchors_20260914.json").read_text())
    anchors = [((a["row"], a["col"]), (a["x"], a["y"])) for a in status["detected_anchors"]]
    board_mask = np.array([[0 if coord == (18, 0) else 1] for coord, _ in anchors], np.uint8)
    real_find = cv2.findHomography

    def board_ransac(src, dst, method=0, *args, **kwargs):
        if method == cv2.RANSAC:
            M, _ = real_find(src[board_mask[:, 0] == 1], dst[board_mask[:, 0] == 1], 0)
            return M, board_mask.copy()
        return real_find(src, dst, method, *args, **kwargs)

    monkeypatch.setattr(led_geometry_calibrator.cv2, "findHomography", board_ransac)

    fit = fit_geometry_from_anchors(anchors, out_size=950)

    assert fit.ok is True
    assert fit.inlier_count == 13
    assert fit.max_residual < 13.18 / 2  # 13 点一起拟合实测 4.2px;旧逻辑下被拒的那颗离模型 11.6px


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


def test_calibrator_retries_only_green_when_green_signal_is_missing():
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points(), green_missing_for=(3, 15))

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    attempts = [rgb for coord, rgb in led.attempts if coord == (3, 15)]
    # 绿色完全缺失也不会换成别的颜色重试(软件契约只允许绿),而亮度只有满亮度一档
    # ⇒ 这颗锚点总共只闪一次。单点缺失由标定容缺(MIN_LOCATED_ANCHORS)吸收。
    assert attempts == [(0, 255, 0)]
    assert all(red == 0 and green > 0 and blue == 0 for _coord, (red, green, blue) in led.attempts)


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
    expected_anchors = (
        (0, 0),
        (0, 18),
        (18, 18),
        (18, 0),
        (3, 3),
        (3, 9),
        (3, 15),
        (9, 3),
        (9, 9),
        (9, 15),
        (15, 3),
        (15, 9),
        (15, 15),
    )
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    observed = []

    result = LedGeometryCalibrator(
        led=led,
        capture=capture,
        anchor_observer=lambda row, col, point, color: observed.append((row, col, point, color)),
    ).calibrate()

    assert result.ok is True
    assert CALIBRATION_ANCHORS == expected_anchors
    assert [(row, col) for row, col, _point, _color in observed] == list(expected_anchors)
    assert all(color == "green" for _row, _col, _point, color in observed)
    for row, col, point, _color in observed:
        assert point == pytest.approx(_synthetic_camera_points()[(row, col)], abs=1.0)


def test_a_daylight_anchor_is_located_because_the_flash_is_always_full_brightness():
    """白天的实测数(spec §2.2):96 档折算 peak≈7-28,闸是 20 ⇒ 半数锚点测不到;255 档过闸。

    夹具就照这个数造:96 档只抬 8 个灰阶,255 档抬 40。它同时是**取消暗档的变异靶** ——
    把 96 加回 FLASH_LEVELS,下面那条「每一次闪灯都是 255」会红。"""
    led = FakeLed()
    points = _synthetic_camera_points()

    class DimCapture(FakeCapture):
        def _frame(self):
            frame = np.full((900, 1000, 3), 150, np.uint8)
            if self.led.current is not None:
                x, y = self.camera_points[self.led.current]
                lift = 40 if max(self.led.rgb) == 255 else 8
                cv2.circle(frame, (round(x), round(y)), 8, (0, 150 + lift, 0), -1)
            return frame

    capture = DimCapture(led, points)
    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert {attempt["level"] for attempt in result.attempts} == {255}
    assert not [attempt for attempt in result.attempts if attempt.get("reason") == "low_signal"]


def test_calibration_flashes_each_anchor_once_at_full_brightness():
    """Fan 2026-09-24 的裁定:标定用固定满亮度,可调亮度只在开局之后。

    用户侧可见的那一半是**一颗锚点只闪一次** —— 「13 个点亮 2 下」正是旧的 96→255 阶梯。"""
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    assert {attempt["level"] for attempt in result.attempts} == {255}
    assert [rgb for _coord, rgb in led.attempts] == [(0, 255, 0)] * len(CALIBRATION_ANCHORS)
    assert [coord for coord, _rgb in led.attempts] == list(CALIBRATION_ANCHORS)


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
    """min_inliers=9 已经允许 13 个里有 4 个外点;检测阶段不该比拟合阶段更严。

    缺满 4 颗(不是 2 颗)才把 detected 顶到 MIN_LOCATED_ANCHORS=9 这条线上 ——
    只缺 2 颗时 detected=11,测试对 MIN_LOCATED_ANCHORS 从 9 漂到 10、11 都不敏感
    (复审变异实测:改成 10 或 11 这条测试原样全绿)。四角仍全部可见,不影响四角单应。
    """
    led = FakeLed()
    points = _synthetic_camera_points()
    invisible = {(3, 3), (9, 15), (3, 9), (15, 3)}

    class PartialCapture(FakeCapture):
        def _frame(self):
            if self.led.current in invisible:
                return np.full((900, 1000, 3), 90, np.uint8)  # 这四颗任何颜色都看不见
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


def test_first_nondegenerate_quad_rejects_the_collinear_corner_case():
    """缺 (18,0) 时最先定位到的 4 颗是 (0,0)(0,18)(18,18)(3,3) ——
    (0,0)、(3,3)、(18,18) 在主对角线上共线,这个 4 子集不能用来求单应。"""
    detected = [
        ((0, 0), (0.0, 0.0)),
        ((0, 18), (100.0, 0.0)),
        ((18, 18), (100.0, 100.0)),
        ((3, 3), (16.7, 16.7)),
    ]

    assert first_nondegenerate_quad(detected) is None

    detected.append(((3, 9), (50.0, 16.7)))
    quad = first_nondegenerate_quad(detected)
    assert quad is not None
    assert len(quad) == 4


def test_missing_corner_does_not_poison_roi_prediction(monkeypatch):
    """(18,0) 是真机 2026-09-02 实测唯一没定位到的那颗。用退化 4 子集拟出的单应会把
    后面 8 颗的 ROI 预测带偏,只能靠全画幅回退救回来 —— 回退次数就是那条退化路径的指纹。
    result.ok 在这里没有判别力(回退会把它兜成 True)。

    `roi_fallback == 0` 这条断言是单边的:「ROI 被投毒 → 回退 8 次」和「压根没有
    ROI(corner_h 永远是 None,retry 从未触发)→ 回退 0 次」长得一模一样,挡得住
    退化单应、挡不住「非退化 4 子集重试路径压根没跑」。补一个 predict_anchor_roi
    的 spy:ROI 真的被算过、真的被用在了后面的锚点上,才说明 first_nondegenerate_quad
    的 `>= 4` 重试确实生效了。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    invisible = {(18, 0)}

    class PartialCapture(FakeCapture):
        def _frame(self):
            if self.led.current in invisible:
                return np.full((900, 1000, 3), 90, np.uint8)
            return super()._frame()

    calls = []
    real_predict = led_geometry_calibrator.predict_anchor_roi

    def spy(homography, row, col):
        calls.append((row, col))
        return real_predict(homography, row, col)

    monkeypatch.setattr(led_geometry_calibrator, "predict_anchor_roi", spy)

    result = LedGeometryCalibrator(led=led, capture=PartialCapture(led, points)).calibrate()

    assert result.ok is True
    assert sum(1 for a in result.attempts if a.get("roi_fallback")) == 0
    # 缺 (18,0) 时 corner_h 要等第 5 颗(3,9)补进来才能拟出非退化四边形;13 颗锚点里
    # 其后还剩 7 颗要用 ROI。用 >=7 不用 ==7,免得将来锚点顺序微调就假红。
    assert len(calls) >= 7


def test_cancel_on_last_anchor_stops_before_baseline_capture():
    """用户在第 13 颗(15,15)上按取消:_locate_anchor 读到 cancel_event 直接返回
    None(见 :346),外层循环 `continue` 之后这已经是最后一次迭代 —— 循环顶部那条
    cancel 检查再也不会执行。必须在循环结束后再补一次检查,让 cancelled 抢在收尾
    (grab_burst 8 帧 + 8 次 950x950 warpPerspective + held-out 自检)前面返回。

    判据不能只看 reason —— 把守卫挪到收尾之后一样能返回 reason='cancelled' 但仍然
    先跑了收尾。真正有判别力的是收尾**有没有跑过**,用 grab_burst 的调用次数钉住。
    """
    led = FakeLed()
    points = _synthetic_camera_points()
    cancel_event = Event()
    grab_burst_calls = []

    class TrackingCapture(FakeCapture):
        def grab_burst(self, n=8, interval=0.1):
            grab_burst_calls.append(n)
            return super().grab_burst(n=n, interval=interval)

    capture = TrackingCapture(led, points)

    def progress(phase, current, total):
        # calibrate() 调用顺序是「顶部 cancel 检查 → progress(phase, index-1, total)
        # → _locate_anchor」。current==12 就是 index==13,也就是第 13(最后一)颗
        # (15,15)。在这里置位,能精确落在「顶部检查已经放行、_locate_anchor 尚未
        # 开始」这道缝里 —— 用 anchor_observer 在第 12 颗上置位会落在缝外(那次置位
        # 发生在 _locate_anchor 返回**之前**,回到外层循环顶部时旧的顶部检查就已经
        # 先一步逮到,盖住了本该由本条测试单独钉住的收尾守卫)。
        if current == 12:
            cancel_event.set()

    result = LedGeometryCalibrator(
        led=led, capture=capture, cancel_event=cancel_event, progress=progress,
    ).calibrate()

    assert result.ok is False
    assert result.reason == "cancelled"
    assert grab_burst_calls == []


def test_check_frame_exposure_pins_median_alone():
    """clip_frac 为 0,只有 median 越线 —— 单独钉住 EXPOSURE_MEDIAN_MAX。"""
    frame = np.full((480, 640, 3), 246, np.uint8)            # 246 < 250 ⇒ 不算削顶

    ok, reason, stats = check_frame_exposure(frame)

    assert ok is False
    assert reason == "frame_overexposed"
    assert stats["median"] == pytest.approx(246, abs=1)
    assert stats["clip_frac"] == pytest.approx(0.0, abs=0.01)  # 一个像素都没到 250


def test_peak_floor_is_per_search_domain():
    """真机实测唯一掉出去的那颗锚点 (18,0) 满亮度 peak=18.2 —— 在 ROI 里它跟噪声
    (中位 7.7-12.6)分得很开,在全画幅里 20 已经贴着噪声(中位 16.5-19.5)。
    同一对帧、同一个真实 peak,两个域必须给出相反的判决。"""
    dark = np.full((900, 1000, 3), 90, np.uint8)
    lit = dark.copy()
    cv2.circle(lit, (300, 400), 8, (90, 108, 90), -1)   # 抬 18 个灰阶:落在 15 与 20 之间

    with_roi = detect_led_centroid(dark, lit, channel=1, roi=(300.0, 400.0, 60.0))
    full_frame = detect_led_centroid(dark, lit, channel=1, roi=None)

    assert 15.0 < with_roi.peak < 20.0, f"这条测试要求真实 peak 落在两条门之间,实际 {with_roi.peak}"
    assert with_roi.ok is True
    assert full_frame.ok is False
    assert full_frame.reason == "low_signal"


def test_exposure_gate_reports_stats_outside_attempts():
    """曝光闸是在门口拒绝的 —— 一颗灯都没闪过,attempts 必须是空的。

    把 stats 塞进 attempts(旧形状 `({"exposure": stats},)`)会让消费方按
    `attempts.length` 当真值判断,于是过曝失败的界面上会长出一句
    「找到 0 / 13 个定位点」—— 这句话不假,但它把「闸在门口拒绝了」讲成了
    「找了 13 个位置一个都没找到」。诊断数据改走自己的字段。"""
    led = FakeLed()
    capture = FakeCapture(led, _synthetic_camera_points())
    capture._frame = lambda: np.full((900, 1000, 3), 253, np.uint8)

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is False
    assert result.reason == "frame_overexposed"
    assert result.attempts == ()
    assert result.exposure_stats is not None
    assert result.exposure_stats["median"] == pytest.approx(253, abs=1)
    assert result.exposure_stats["clip_frac"] > 0.5


def _warnings_about_roi_prefilter(caplog):
    return [r.getMessage() for r in caplog.records if "ROI prefilter did not take effect" in r.getMessage()]


def test_warns_when_the_whole_roi_prefilter_round_evaporated(monkeypatch, caplog):
    """静默失效:某个**角**被眩光抢到别处时,那颗错的相机点照样能过
    first_nondegenerate_quad 的面积判据(判据只看 canonical 坐标,看不见相机点是不是
    真实像),corner_h 于是是错的,九星 ROI 落到毫无关系的位置。

    行为上兜得住(全部 low_signal ⇒ roi_fallback 退回全画幅 = 改动前行为),所以不改
    控制流。问题是它静悄悄:整整一轮 T5 的收益蒸发,唯一的痕迹是一堆没有消费方的
    `roi_fallback: True`。这里只补一条 warning 让它看得见。

    两个方向都要:0 条的场景必须**不**出这条 warning,否则是恒真守卫。"""
    points = _synthetic_camera_points()
    real_predict = led_geometry_calibrator.predict_anchor_roi

    def poisoned_predict(homography, row, col):
        cx, cy, radius = real_predict(homography, row, col)
        return cx + 120.0, cy, radius   # 复现「四角先验被投毒」:ROI 里找不到真 LED

    # --- 方向一:先验不可信,九星整批退回全画幅 ---
    led = FakeLed()
    monkeypatch.setattr(led_geometry_calibrator, "predict_anchor_roi", poisoned_predict)
    with caplog.at_level(logging.WARNING, logger="katrain.vision.led_geometry_calibrator"):
        poisoned = LedGeometryCalibrator(led=led, capture=FakeCapture(led, points)).calibrate()
    fallbacks = sum(1 for a in poisoned.attempts if a.get("roi_fallback"))
    assert fallbacks >= 7, f"这个场景要造出 >=7 条 roi_fallback 才有判别力,实际 {fallbacks}"
    warned = _warnings_about_roi_prefilter(caplog)
    assert len(warned) == 1, f"整轮 ROI 蒸发却一条 warning 都没有: {caplog.records}"
    assert str(fallbacks) in warned[0], f"warning 要说清是几颗退回的: {warned[0]}"

    # --- 方向二(反向对照):正常一轮,0 条退回 ⇒ 一个字都不许说 ---
    caplog.clear()
    monkeypatch.setattr(led_geometry_calibrator, "predict_anchor_roi", real_predict)
    led = FakeLed()
    with caplog.at_level(logging.WARNING, logger="katrain.vision.led_geometry_calibrator"):
        healthy = LedGeometryCalibrator(led=led, capture=FakeCapture(led, points)).calibrate()
    assert healthy.ok is True
    assert sum(1 for a in healthy.attempts if a.get("roi_fallback")) == 0
    assert _warnings_about_roi_prefilter(caplog) == [], "正常一轮不许报警(恒真守卫)"


class ProbeScriptedCapture(FakeCapture):
    """前几帧按脚本给「过曝 / 正常」,之后回到正常的合成帧。

    `blown` 的第一项是**第一帧**,所以两个用例都能分辨「取 3 帧取中位」和
    「只看第一帧」—— 两种用例的第一帧都跟多数派相反。"""

    def __init__(self, led, camera_points, *, blown):
        super().__init__(led, camera_points)
        self.blown = list(blown)

    def _frame(self):
        if self.blown:
            return np.full((900, 1000, 3), 253 if self.blown.pop(0) else 150, np.uint8)
        return super()._frame()


def test_exposure_gate_is_not_fooled_by_one_bad_frame_in_three():
    """3 帧里只有 1 帧过曝(而且正好是第一帧)⇒ 闸应当放行。

    单帧探针会被一帧噪声/AE 中间帧骗到。这里只做「取 3 帧取中位」,不加等待重试
    ——「等」是标定入口那次曝光收敛的职责,两处都做会等两遍。"""
    led = FakeLed()
    capture = ProbeScriptedCapture(led, _synthetic_camera_points(), blown=[True, False, False])

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.reason != "frame_overexposed"
    assert result.ok is True


def test_exposure_gate_still_rejects_when_two_of_three_frames_are_blown():
    """3 帧里 2 帧过曝(第一帧正常)⇒ 仍然拒绝,而且一颗灯都不许闪。

    反向对照:光「多取几帧」不够,判决必须跟着多数派走,不能变成「有一帧行就行」。"""
    led = FakeLed()
    capture = ProbeScriptedCapture(led, _synthetic_camera_points(), blown=[False, True, True])

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is False
    assert result.reason == "frame_overexposed"
    assert led.attempts == []
    assert result.exposure_stats["median"] == pytest.approx(253, abs=1)


class TransientCapture(FakeCapture):
    """棋盘外一闪而过的亮块,只出现在点亮 `transient_at` 之后的**第一帧**。

    复刻 2026-09-21 RK3562 那次:(18,0) 三轮都被认到棋盘外 (638,1058)(当次锁反算
    row 1.47 / col -3.63),人不在旁边时同一检测函数 12/12 全对 ⇒ 是暗/亮两帧之间
    画面边缘有东西变了。亮块比 LED 光斑大一个量级,单帧检测必然选它。
    """

    TRANSIENT_XY = (60, 860)

    def __init__(self, led, camera_points, transient_at):
        super().__init__(led, camera_points)
        self.transient_at = transient_at
        self._state = None
        self._frames_in_state = 0

    def grab_fresh(self, after_ts=None, settle_ms=150.0):
        frame, seq, ts = super().grab_fresh(after_ts, settle_ms)
        state = (self.led.current, self.led.rgb)
        if state != self._state:
            self._state, self._frames_in_state = state, 0
        self._frames_in_state += 1
        if self.led.current == self.transient_at and self._frames_in_state == 1:
            cv2.circle(frame, self.TRANSIENT_XY, 25, (230, 230, 230), -1)
        return frame, seq, ts


def test_a_one_frame_transient_off_board_does_not_become_the_corner():
    """灯亮着的那段时间里连拍几帧,只认每一帧都亮的地方 —— 一闪而过的东西过不了。"""
    led = FakeLed()
    points = _synthetic_camera_points()
    capture = TransientCapture(led, points, transient_at=(18, 0))

    result = LedGeometryCalibrator(led=led, capture=capture).calibrate()

    assert result.ok is True
    seen = {(a["row"], a["col"]): a["camera"] for a in result.lock.diag["anchors"]}
    true_x, true_y = points[(18, 0)]
    assert abs(seen[(18, 0)][0] - true_x) < 2 and abs(seen[(18, 0)][1] - true_y) < 2
