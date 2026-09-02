"""LED-anchor geometry calibration in seated-human board coordinates."""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from threading import Event
from typing import Callable

import cv2
import numpy as np

from katrain.vision import stone_classifier
from katrain.vision.geometry_lock import GeometryLock

logger = logging.getLogger(__name__)

# 标定入口的曝光闸。判据来自 spec §2.2 的实测:
#   01:32 暗处成功那次盘面中位 ≈150、逐锚点 peak 94-198;
#   白天 bright=254(60% 像素 ≥250)时 13 颗里 12 颗定位到噪声。
# 这两个数不是审美偏好,是「亮减暗差分还剩不剩信号」的边界。
EXPOSURE_MEDIAN_MAX = 245.0   # 高于此:盘面接近削顶,lit-dark 差分趋近 0
EXPOSURE_MEDIAN_MIN = 20.0    # 低于此:整帧欠曝,LED 之外什么都看不见
EXPOSURE_CLIP_FRAC_MAX = 0.35  # >=250 的像素占比上限

# 检测阶段容缺的下限 —— 必须与 fit_geometry_from_anchors 的 min_inliers 同源:
# 拟合阶段本来就允许 13 个锚点里有 4 个外点(RANSAC min_inliers=9),检测阶段
# 少定位到几颗不该比拟合阶段更严。两处不同值会让这份余量白留。
MIN_LOCATED_ANCHORS = 9

# lit-dark 差分的信号下限。**按搜索域取值** —— 同一个数在两个域里意思完全不同:
#   ROI 搜索(半径 47-64px ⇒ 面积 6.9k-12.9k px):域内 argmax 噪声中位实测 7.7-12.6,
#     15 是噪声的 1.2-1.9 倍,同时放得过真机 2026-09-02 实测最弱的那颗锚点
#     (18,0) 满亮度 peak=18.2 —— 它在 ROI 里跟噪声分得很开,却被原来的 20 判成 low_signal。
#   全画幅回退(1920x1080 ≈ 2.07M px):整幅 argmax 噪声中位实测 16.5-19.5,20 已经
#     贴着噪声底(只高 1.03-1.20 倍)。**这一半不动**:再往上抬会把"ROI 被投毒之后
#     靠全画幅捞回来"的锚点一起毙掉,而没有实测数据支持某个具体的更高值。
PEAK_MIN_ROI = 15.0
PEAK_MIN_FULL = 20.0

# 「本轮 ROI 预筛整个没生效」的报警线。某个**角**被眩光抢到别处时(正是本分支要修的
# 现象),那颗错的相机点照样能过 first_nondegenerate_quad 的面积判据 —— 判据只看
# canonical 坐标,看不见相机点是不是各自 canonical 点的真实像。corner_h 于是是错的,
# 九星 ROI 落到毫无关系的位置。行为上兜得住(全部 low_signal ⇒ roi_fallback 退回全画幅
# = 改动前行为),所以不改控制流,只让它别再静悄悄地发生。
# 阈值依据:正常有锁场景 roi_fallback 是 0 条;缺一个共线角(Ruling-9 已修)实测也是
# 0 条;四角真被抢会让其后**全部**九星退回,实测量级 8-9 条。7 落在这两个量级之间。
ROI_FALLBACK_WARN_MIN = 7

CALIBRATION_ANCHORS = (
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


@dataclass(frozen=True)
class LedCentroidResult:
    ok: bool
    centroid: tuple[float, float] | None = None
    peak: float = 0.0
    area: int = 0
    margin: float = 0.0
    reason: str | None = None


@dataclass(frozen=True)
class GeometryFitResult:
    ok: bool
    M: np.ndarray | None = None
    Minv: np.ndarray | None = None
    inlier_mask: np.ndarray | None = None
    inlier_count: int = 0
    rms_residual: float | None = None
    max_residual: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CalibrationResult:
    ok: bool
    lock: GeometryLock | None = None
    reason: str | None = None
    fit: GeometryFitResult | None = None
    attempts: tuple[dict, ...] = ()
    # 曝光闸的整帧统计。**不进 attempts** —— attempts 的每一条都是一次真的闪灯尝试
    # (必带 row/col/color),消费方按它的长度当真值判断。闸是在门口拒绝的,一颗灯都
    # 没闪过,混进去会让界面把「闸拒绝了」渲染成「找了 13 个位置一个都没找到」。
    exposure_stats: dict | None = None


def check_frame_exposure(frame: np.ndarray) -> tuple[bool, str | None, dict]:
    """标定入口的曝光闸:过曝时 lit-dark 差分恒为 0,检测器只会在噪声里游走。

    量的是**原始整帧**而不是 warp 后的盘面 —— 标定阶段还没有几何可用,
    auto_exposure.meter_brightness 那条路在这里走不通。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    small = gray[::4, ::4]
    stats = {
        "median": float(np.median(small)),
        "clip_frac": float((small >= 250).mean()),
        "shadow_frac": float((small <= 10).mean()),
    }
    if stats["median"] >= EXPOSURE_MEDIAN_MAX or stats["clip_frac"] >= EXPOSURE_CLIP_FRAC_MAX:
        return False, "frame_overexposed", stats
    if stats["median"] <= EXPOSURE_MEDIAN_MIN:
        return False, "frame_underexposed", stats
    return True, None, stats


def detect_led_centroid(
    dark: np.ndarray, lit: np.ndarray, *, channel: int, roi: tuple[float, float, float] | None = None
) -> LedCentroidResult:
    """Find the dominant positive light blob in a lit-minus-dark frame.

    ``roi`` = (cx, cy, radius_px)。给了就只在这个圆内找 —— 原来那个 peak>=20 的闸是照
    73x73 的小窗口定的,用在整幅 1920x1080 上等于「找画面里最亮的噪声团」(spec §2.2)。
    信号下限随搜索域走:ROI 用 PEAK_MIN_ROI,全画幅用 PEAK_MIN_FULL(见常量注释)。"""
    if dark.shape != lit.shape or dark.ndim != 3:
        return LedCentroidResult(ok=False, reason="shape_mismatch")
    delta = lit[..., channel].astype(np.float32) - dark[..., channel].astype(np.float32)
    delta = cv2.GaussianBlur(delta, (5, 5), 0)
    if roi is not None:
        cx, cy, radius = roi
        keep = np.zeros(delta.shape, np.uint8)
        cv2.circle(keep, (int(round(cx)), int(round(cy))), max(1, int(round(radius))), 1, -1)
        delta = np.where(keep.astype(bool), delta, 0.0)
    peak = float(delta.max(initial=0.0))
    if peak < (PEAK_MIN_FULL if roi is None else PEAK_MIN_ROI):
        return LedCentroidResult(ok=False, peak=peak, reason="low_signal")

    threshold = max(12.0, peak * 0.45)
    mask = (delta >= threshold).astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    blobs = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 3:
            continue
        weights = np.maximum(delta[labels == label], 0.0)
        score = float(weights.sum())
        blobs.append((score, label, area))
    if not blobs:
        return LedCentroidResult(ok=False, peak=peak, reason="no_blob")
    blobs.sort(reverse=True)
    score, label, area = blobs[0]
    second_score = blobs[1][0] if len(blobs) > 1 else 0.0
    margin = score / max(second_score, 1.0)
    if len(blobs) > 1 and margin < 1.3:
        return LedCentroidResult(ok=False, peak=peak, area=area, margin=margin, reason="ambiguous_blobs")

    ys, xs = np.where(labels == label)
    weights = np.maximum(delta[ys, xs], 0.0)
    total = float(weights.sum())
    centroid = (float(np.dot(xs, weights) / total), float(np.dot(ys, weights) / total))
    return LedCentroidResult(ok=True, centroid=centroid, peak=peak, area=area, margin=margin)


def fit_geometry_from_anchors(
    anchors: list[tuple[tuple[int, int], np.ndarray | tuple[float, float]]],
    *,
    out_size: int = 950,
    min_inliers: int = MIN_LOCATED_ANCHORS,  # 同源:检测阶段容缺不能比这条 RANSAC 门槛更严
    max_rms_cells: float = 0.12,
    max_residual_cells: float = 0.25,
) -> GeometryFitResult:
    """Fit camera-to-canonical homography from known human-coordinate anchors."""
    if len(anchors) < 4:
        return GeometryFitResult(ok=False, reason="not_enough_points")
    spacing = (out_size - 1) / 18.0
    camera_points = np.asarray([point for _coord, point in anchors], np.float32)
    canonical_points = np.asarray([[col * spacing, row * spacing] for (row, col), _point in anchors], np.float32)
    M, mask = cv2.findHomography(
        camera_points,
        canonical_points,
        cv2.RANSAC,
        ransacReprojThreshold=max(2.0, spacing * max_residual_cells),
    )
    if M is None or mask is None:
        return GeometryFitResult(ok=False, reason="homography_failed")
    inliers = mask.reshape(-1).astype(bool)
    inlier_count = int(inliers.sum())
    if inlier_count < min_inliers:
        return GeometryFitResult(
            ok=False, M=M, inlier_mask=inliers, inlier_count=inlier_count, reason="not_enough_inliers"
        )

    projected = cv2.perspectiveTransform(camera_points.reshape(-1, 1, 2), M).reshape(-1, 2)
    residuals = np.linalg.norm(projected - canonical_points, axis=1)[inliers]
    rms = float(np.sqrt(np.mean(np.square(residuals))))
    maximum = float(residuals.max(initial=0.0))
    if rms > spacing * max_rms_cells or maximum > spacing * max_residual_cells:
        return GeometryFitResult(
            ok=False,
            M=M,
            inlier_mask=inliers,
            inlier_count=inlier_count,
            rms_residual=rms,
            max_residual=maximum,
            reason="residual_too_large",
        )
    try:
        Minv = np.linalg.inv(M)
    except np.linalg.LinAlgError:
        return GeometryFitResult(ok=False, M=M, inlier_mask=inliers, inlier_count=inlier_count, reason="singular")
    return GeometryFitResult(
        ok=True,
        M=M,
        Minv=Minv,
        inlier_mask=inliers,
        inlier_count=inlier_count,
        rms_residual=rms,
        max_residual=maximum,
    )


ROI_CELLS = 1.5  # ROI 半径 = 1.5 个格距。棋盘不会在一次标定里移动超过这个量级。
ROI_RADIUS_MIN_PX = 24.0


def predict_anchor_roi(homography: np.ndarray, row: int, col: int) -> tuple[float, float, float]:
    """用四角拟出的临时单应预测某锚点的像素位置,半径按**该处局部**格距算 ——
    透视下近端格子比远端大,用全局常数会在一端过紧、另一端过松。"""
    here = cv2.perspectiveTransform(np.array([[[float(col), float(row)]]], np.float32), homography)[0][0]
    diag = cv2.perspectiveTransform(
        np.array([[[float(col) + 1.0, float(row) + 1.0]]], np.float32), homography)[0][0]
    local_cell = float(np.hypot(diag[0] - here[0], diag[1] - here[1])) / float(np.sqrt(2.0))
    return float(here[0]), float(here[1]), max(ROI_RADIUS_MIN_PX, ROI_CELLS * local_cell)


# 四角单应只能用**非退化**的 4 点子集来拟。getPerspectiveTransform 要的是
# 任意三点不共线(不是任意四点):容缺之后 detected[:4] 可能是「3 个角 + (3,3)」,
# 而 (0,0)、(3,3)、(18,18) 正在主对角线上。这种配置下单应不唯一,函数不报错也不出
# NaN,返回一个有限但任意的解 —— 实测把后续 ROI 预测带偏中位 132px、最大 725px。
MIN_QUAD_TRI_AREA = 20.0  # canonical 格单位^2。满盘半幅三角形 = 162,取 ~12%,同时挡住共线与细长四边形


def _triangle_area(a, b, c) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2.0


def first_nondegenerate_quad(detected):
    """按定位顺序找第一个「任意三点围成的三角形面积都 >= MIN_QUAD_TRI_AREA」的 4 子集。
    找不到就返回 None —— 调用方必须继续走全画幅,而不是拿一个退化单应去预测 ROI。"""
    for quad in itertools.combinations(detected, 4):
        pts = [(float(col), float(row)) for (row, col), _point in quad]
        if all(_triangle_area(*tri) >= MIN_QUAD_TRI_AREA for tri in itertools.combinations(pts, 3)):
            return list(quad)
    return None


class LedGeometryCalibrator:
    """Orchestrate strict LED flashes and fresh-frame geometry capture."""

    # (通道, 颜色名) —— 亮度由 FLASH_LEVELS 决定,不再写死在 RGB 里。
    COLOR_CHANNELS = ((1, "green"), (2, "red"), (0, "blue"))
    # 先暗后亮:暗处 96 档 peak 94-198 已充裕且不削顶;只在 low_signal 时才拉满。
    FLASH_LEVELS = (96, 255)

    @staticmethod
    def _rgb_for(channel: int, level: int) -> tuple[int, int, int]:
        """channel 用的是 BGR 序(detect_led_centroid 的 channel 参数),set_rgb_points 要 RGB。"""
        rgb = [0, 0, 0]
        rgb[{0: 2, 1: 1, 2: 0}[channel]] = level
        return tuple(rgb)

    def __init__(
        self,
        *,
        led,
        capture,
        out_size: int = 950,
        settle_ms: float = 150.0,
        cancel_event: Event | None = None,
        progress: Callable[[str, int, int], None] | None = None,
        anchor_observer: Callable[[int, int, tuple[float, float], str], None] | None = None,
    ):
        self.led = led
        self.capture = capture
        self.out_size = out_size
        self.settle_ms = settle_ms
        self.cancel_event = cancel_event or Event()
        self.progress = progress or (lambda _phase, _current, _total: None)
        self.anchor_observer = anchor_observer or (lambda _row, _col, _point, _color: None)

    def calibrate(self) -> CalibrationResult:
        detected = []
        attempts = []
        try:
            probe, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
            if probe is None:
                return CalibrationResult(ok=False, reason="no_frames")
            ok, reason, stats = check_frame_exposure(probe)
            logger.info(
                "geometry exposure gate: ok=%s reason=%s median=%.0f clip=%.3f",
                ok, reason, stats["median"], stats["clip_frac"],
            )
            if not ok:
                return CalibrationResult(ok=False, reason=reason, exposure_stats=stats)

            total = len(CALIBRATION_ANCHORS)
            corner_h = None
            for index, (row, col) in enumerate(CALIBRATION_ANCHORS, start=1):
                if self.cancel_event.is_set():
                    return CalibrationResult(ok=False, reason="cancelled", attempts=tuple(attempts))
                phase = "flashing_corners" if index <= 4 else "verifying"
                self.progress(phase, index - 1, total)
                roi = predict_anchor_roi(corner_h, row, col) if corner_h is not None else None
                centroid = self._locate_anchor(row, col, attempts, roi=roi)
                if centroid is None:
                    continue  # 容缺:拟合阶段本来就允许 4 个外点(MIN_LOCATED_ANCHORS)
                detected.append(((row, col), centroid))
                # index==4 时 detected 未必已有 4 个(前面可能已经容缺跳过)。用
                # >=4(不是 ==4)是因为第一个满足条件的 4 子集不一定在 detected 恰好
                # 4 个时出现 —— first_nondegenerate_quad 可能在 4 个里全共线/退化,
                # 要等第 5、第 6 颗补进来才有非退化的 4 子集可挑(见下方常量注释)。
                if corner_h is None and len(detected) >= 4:
                    quad = first_nondegenerate_quad(detected)
                    if quad is not None:
                        src = np.array([[float(c), float(r)] for (r, c), _point in quad], np.float32)
                        dst = np.array([point for _anchor, point in quad], np.float32)
                        corner_h = cv2.getPerspectiveTransform(src, dst)

            if self.cancel_event.is_set():
                # 循环顶部那条检查在最后一颗锚点上按了取消时够不着(continue 直接跳出
                # 循环,不会再回到顶部)。这里补一次,让 cancelled 优先于 too_few_anchors
                # ——也优先于收尾阶段(grab_burst + 8 次 warpPerspective + held-out 自检)。
                return CalibrationResult(ok=False, reason="cancelled", attempts=tuple(attempts))

            # 只报警、不改判决:这一轮 T5 的收益静静蒸发了,唯一的痕迹是这些
            # roi_fallback,而这个键没有任何消费方(见 ROI_FALLBACK_WARN_MIN)。
            fallbacks = sum(1 for attempt in attempts if attempt.get("roi_fallback"))
            if fallbacks >= ROI_FALLBACK_WARN_MIN:
                logger.warning(
                    "geometry: corner prior may be untrustworthy — %d anchors fell back to "
                    "full-frame; this run's ROI prefilter did not take effect",
                    fallbacks,
                )

            if len(detected) < MIN_LOCATED_ANCHORS:
                return CalibrationResult(ok=False, reason="too_few_anchors", attempts=tuple(attempts))

            fit = fit_geometry_from_anchors(detected, out_size=self.out_size)
            if not fit.ok:
                return CalibrationResult(ok=False, reason=fit.reason, fit=fit, attempts=tuple(attempts))

            self.progress("building_baseline", total, total)
            cleared = self.led.clear(strict=True)
            if not cleared.get("ok"):
                return CalibrationResult(ok=False, reason="led_clear_failed", fit=fit, attempts=tuple(attempts))
            frames = self.capture.grab_burst(n=8)
            if len(frames) != 8:
                return CalibrationResult(ok=False, reason="baseline_frames_missing", fit=fit, attempts=tuple(attempts))
            lock = self._build_lock(fit, frames, detected, attempts)
            return CalibrationResult(ok=True, lock=lock, fit=fit, attempts=tuple(attempts))
        finally:
            try:
                self.led.clear(strict=True)
            except Exception:
                pass

    def _locate_anchor(
        self, row: int, col: int, attempts: list[dict], roi: tuple[float, float, float] | None = None
    ):
        # 复用最近一次成功抓到的 (dark, lit) 帧对做 ROI 回退,不必为回退再多闪一次灯(D2③)。
        last_capture: tuple[np.ndarray, np.ndarray, int, str, int] | None = None
        for channel, color_name in self.COLOR_CHANNELS:
            for level in self.FLASH_LEVELS:
                if self.cancel_event.is_set():
                    return None
                cleared = self.led.clear(strict=True)
                if not cleared.get("ok"):
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "clear_failed"})
                    logger.warning(
                        "geometry anchor (%d,%d) %s@%d: reason=clear_failed", row, col, color_name, level,
                    )
                    break
                dark, _seq, _ts = self.capture.grab_fresh(
                    after_ts=cleared.get("shown_at"), settle_ms=self.settle_ms)
                shown = self.led.set_rgb_points(
                    [{"row": row, "col": col, "rgb": self._rgb_for(channel, level)}], strict=True)
                if not shown.get("ok"):
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "show_failed"})
                    logger.warning(
                        "geometry anchor (%d,%d) %s@%d: reason=show_failed", row, col, color_name, level,
                    )
                    break
                lit, _seq, _ts = self.capture.grab_fresh(
                    after_ts=shown.get("shown_at"), settle_ms=self.settle_ms)
                if dark is None or lit is None:
                    attempts.append({"row": row, "col": col, "color": color_name,
                                     "level": level, "reason": "no_frame"})
                    logger.warning(
                        "geometry anchor (%d,%d) %s@%d: reason=no_frame", row, col, color_name, level,
                    )
                    break
                last_capture = (dark, lit, channel, color_name, level)
                result = detect_led_centroid(dark, lit, channel=channel, roi=roi)
                attempts.append({
                    "row": row, "col": col, "color": color_name, "level": level,
                    "ok": result.ok, "peak": result.peak, "area": result.area,
                    "margin": result.margin, "reason": result.reason,
                })
                logger.info(
                    "geometry anchor (%d,%d) %s@%d: ok=%s peak=%.1f area=%s margin=%s reason=%s",
                    row, col, color_name, level, result.ok, result.peak,
                    result.area, result.margin, result.reason,
                )
                if result.ok:
                    point = (float(result.centroid[0]), float(result.centroid[1]))
                    self.anchor_observer(row, col, point, color_name)
                    return result.centroid
                if result.reason != "low_signal":
                    break  # 只有信号弱才值得升亮度
        if roi is not None and last_capture is not None:
            # ROI 全画幅先验可能被投毒(某个角测偏 ⇒ 单应算偏),把可被 RANSAC 吸收的
            # 离群锚点变成整条标定 hard-fail。带 ROI 的尝试全败后,退回全画幅用最近一次
            # 已经拍到的帧再试一次 —— 不需要再多闪一次灯。
            dark, lit, channel, color_name, level = last_capture
            result = detect_led_centroid(dark, lit, channel=channel, roi=None)
            attempts.append({
                "row": row, "col": col, "color": color_name, "level": level,
                "ok": result.ok, "peak": result.peak, "area": result.area,
                "margin": result.margin, "reason": result.reason, "roi_fallback": True,
            })
            logger.info(
                "geometry anchor (%d,%d) %s@%d: roi_fallback ok=%s peak=%.1f area=%s margin=%s reason=%s",
                row, col, color_name, level, result.ok, result.peak,
                result.area, result.margin, result.reason,
            )
            if result.ok:
                point = (float(result.centroid[0]), float(result.centroid[1]))
                self.anchor_observer(row, col, point, color_name)
                return result.centroid
        return None

    def _build_lock(self, fit, frames, detected, attempts):
        M = np.asarray(fit.M, np.float64)
        Minv = np.asarray(fit.Minv, np.float64)
        size = self.out_size
        xs = np.linspace(0, size - 1, 19).astype(np.float32)
        ys = np.linspace(0, size - 1, 19).astype(np.float32)
        gx, gy = np.meshgrid(xs, ys)
        canonical_grid = np.stack([gx, gy], axis=-1).astype(np.float32)
        points = cv2.perspectiveTransform(canonical_grid.reshape(-1, 1, 2), Minv).reshape(19, 19, 2)
        canonical_corners = np.array([[[0, 0]], [[size - 1, 0]], [[size - 1, size - 1]], [[0, size - 1]]], np.float32)
        corners = cv2.perspectiveTransform(canonical_corners, Minv).reshape(4, 2)
        warps = [cv2.warpPerspective(frame, M, (size, size)) for frame in frames]
        # Sample the 361-point grid ONCE per warp and reuse it for both the held-out
        # check and the final baseline. The naive path samples 16x for 8 frames (7 +
        # 1 + 8, re-sampling the first 7 twice); sampling is the SBC finalization
        # hotspot, so halving the calls halves ~7.5s on RK3562.
        grids = [stone_classifier.sample_grid(warp, xs, ys) for warp in warps]
        held_out_baseline = stone_classifier.build_baseline_from_samples(grids[:7])
        state = stone_classifier.classify_from_sample(grids[7], held_out_baseline)
        empty_black = int((state == stone_classifier.BLACK).sum())
        empty_white = int((state == stone_classifier.WHITE).sum())
        if empty_black or empty_white:
            raise RuntimeError(f"empty baseline held-out check failed: black={empty_black}, white={empty_white}")
        baseline = stone_classifier.build_baseline_from_samples(grids)
        confidence = (fit.inlier_count / len(CALIBRATION_ANCHORS)) * max(
            0.0, 1.0 - (fit.rms_residual or 0.0) / max((size - 1) / 18.0, 1.0)
        )
        return GeometryLock(
            corners=corners.astype(np.float32),
            points=points.astype(np.float32),
            xs=xs,
            ys=ys,
            M=M,
            Minv=Minv,
            out_size=size,
            baseline=baseline.astype(np.float32),
            confidence=float(confidence),
            nmatch=int(fit.inlier_count),
            empty_black=empty_black,
            empty_white=empty_white,
            diag={
                "source": "led_anchor_ransac",
                "orientation": "seated_human",
                "anchors": [
                    {"row": row, "col": col, "camera": [float(point[0]), float(point[1])]}
                    for (row, col), point in detected
                ],
                "inlier_mask": fit.inlier_mask.astype(int).tolist(),
                "rms_residual": fit.rms_residual,
                "max_residual": fit.max_residual,
                "attempts": attempts,
            },
            source_height=int(frames[-1].shape[0]),
            source_width=int(frames[-1].shape[1]),
        )
