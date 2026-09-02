"""LED-anchor geometry calibration in seated-human board coordinates."""

from __future__ import annotations

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

    ``roi`` = (cx, cy, radius_px)。给了就只在这个圆内找 —— peak>=20 这个闸是照
    73x73 的小窗口定的,用在整幅 1920x1080 上等于「找画面里最亮的噪声团」(spec §2.2)。"""
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
    if peak < 20.0:
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
    min_inliers: int = 9,
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
                return CalibrationResult(ok=False, reason=reason, attempts=({"exposure": stats},))

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
                    return CalibrationResult(ok=False, reason=f"anchor_not_found:{row},{col}", attempts=tuple(attempts))
                detected.append(((row, col), centroid))
                if index == 4:
                    # CALIBRATION_ANCHORS[:4] 是四角,顺序 (0,0)(0,18)(18,18)(18,0)。
                    src = np.array([[float(c), float(r)] for (r, c) in CALIBRATION_ANCHORS[:4]], np.float32)
                    dst = np.array([point for _anchor, point in detected[:4]], np.float32)
                    corner_h = cv2.getPerspectiveTransform(src, dst)

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
