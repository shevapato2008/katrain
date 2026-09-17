"""Asynchronous lifecycle for LED-anchor geometry calibration."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from katrain.vision.camera import (
    CAMERA_AUTO_EXPOSURE_MANUAL,
    CAMERA_AUTO_EXPOSURE_ON,
    _auto_exposure_readback_matches,
    _exposure_readback_matches,
)
from katrain.vision.geometry_lock import save_geometry_lock
from katrain.vision.led_geometry_calibrator import LedGeometryCalibrator, check_frame_exposure

logger = logging.getLogger(__name__)

# 保留旧名供现有调用者；值由 camera.py 单点定义。板上实测：3.0 是硬件
# AE，1.0 是手动；常见的 OpenCV 0.25 别名在这个 V4L2 后端会被拒绝。
CAMERA_AUTO_EXPOSURE_OFF = CAMERA_AUTO_EXPOSURE_MANUAL


class CalibrationBusy(RuntimeError):
    pass


class CalibrationCancelled(RuntimeError):
    """Cancellation accepted before the durable publication boundary."""


class LegacyPublishRollbackError(RuntimeError):
    """Legacy geometry publication failed and its previous files could not be restored."""


class GeometryCalibrationService:
    ACTIVE_PHASES = {"waiting_empty", "dark_reference", "flashing_corners", "verifying", "building_baseline"}

    # 标定入口那次曝光收敛的边界。用户正站在标定屏前等,不能无限等:超了就带着当前
    # 曝光继续往下走 —— 真收不回来,后面的曝光闸会诚实拒绝,不会伪装成功。
    # 步数预算 = 20 x 1s = **20 秒**,依据是板上实测,不是拍的:rk3562 2026-09-02 夜间,
    # 把曝光钉到极暗(exposure_absolute=50 ⇒ bright=1)再开硬件 AE 计时,
    # +5s 仍是 1、+10s 仍是 1、+15s 已回到 141 ⇒ **从极端值回到带内要 10-15 秒**
    # (journal 采样粒度 5s,真值在这个区间内)。原来的 6 秒会直接撞上限。
    # ⚠️ 这条实测只量了「暗 → 亮」一个方向,而生产上真正的场景是「过曝 → 带内」,
    # 方向相反。缩短积分时间通常比拉长快(拉长要防振荡所以走缓坡),所以生产方向
    # 很可能更快 —— 但那是推断不是测量,所以上限按**测到的那个方向**定。
    EXPOSURE_CONVERGE_MAX_STEPS = 20
    EXPOSURE_CONVERGE_POLL_S = 1.0
    # 墙钟只是**兜底**,防的是单次取帧阻塞(camera.grab_fresh 自己的 timeout 是 2.0s,
    # 20 步全卡满就是 60 秒)。它**必须大于步数预算**,否则会悄悄变成真正的那道闸,
    # 而 outcome 会报 timeout 而不是 max_steps —— 两个上限并存时小的那个说了算,
    # 这正是上一版 12s < 20s 会踩的坑。
    EXPOSURE_CONVERGE_TIMEOUT_S = 30.0
    # 目标带与 auto_exposure.ExposureController 的默认带同源(spec:中位落在 [120,170])。
    EXPOSURE_TARGET_LO = 120.0
    EXPOSURE_TARGET_HI = 170.0
    # request_controls is consumed by the camera reader between reads. If the request
    # lands while a read is already in flight, the first fresh frame can legitimately
    # arrive before its readback; allow the next two frames before declaring failure.
    EXPOSURE_CONTROL_VERIFY_MAX_FRAMES = 3

    def __init__(
        self,
        *,
        led,
        capture,
        save_path=None,
        persist_state=None,
        initial_lock=None,
        on_success=None,
        on_degraded=None,
        on_suspend=None,
        on_resume=None,
        calibrator_factory=LedGeometryCalibrator,
    ):
        self.led = led
        self.capture = capture
        if save_path is None and persist_state is None:
            raise ValueError("save_path or persist_state is required")
        self.save_path = Path(save_path).expanduser() if save_path is not None else None
        self.persist_state = persist_state
        self.current_lock = initial_lock
        # Geometry-only runtime/UI notification. Durable geometry + exposure publication
        # belongs to persist_state and is already committed before this callback runs.
        self.on_success = on_success or (lambda _lock: None)
        # Called once when drift flips a ready lock to degraded — used to invalidate the
        # downstream vision worker so it stops recognizing on a stale (shifted) warp.
        self.on_degraded = on_degraded or (lambda: None)
        # Suspend/resume the downstream vision worker around a calibration run. The RKNN
        # worker otherwise keeps warping+CLAHE+detecting (~1 core) on a board that is being
        # re-locked — pointless work that starves the calibration compute, the status poll,
        # and the kiosk UI (the "卡在 N/13" freeze). on_resume re-pushes the live lock so a
        # failed/cancelled run keeps recognising on the previous geometry.
        self.on_suspend = on_suspend or (lambda: None)
        self.on_resume = on_resume or (lambda: None)
        self.calibrator_factory = calibrator_factory
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._publish_started = False
        self._thread = None
        self._geometry_revision = 0
        self._detected_anchors = []
        self._drift_monitor = None
        self._drift_stop = threading.Event()
        self._drift_thread = threading.Thread(target=self._drift_loop, daemon=True, name="geometry-drift")
        self._drift_thread.start()
        self._status = {
            "phase": "required",
            "progress": {"current": 0, "total": 13},
            "session_calibrated": False,
            "last_valid": initial_lock is not None,
            "trigger": None,
            "error": None,
            "metrics": {},
        }

    def start(self, *, trigger: str, empty_confirmed: bool) -> None:
        if self.led is None:
            raise ValueError("LED is required for geometry calibration")
        if not empty_confirmed:
            raise ValueError("empty board confirmation is required")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise CalibrationBusy("geometry calibration already running")
            self._cancel_event = threading.Event()
            self._publish_started = False
            self._drift_monitor = None
            self._detected_anchors = []
            self._status.update(
                phase="waiting_empty",
                progress={"current": 0, "total": 13},
                trigger=trigger,
                error=None,
                metrics={},
            )
            self._thread = threading.Thread(target=self._run, daemon=True, name="geometry-calibration")
            self._thread.start()

    def cancel(self) -> None:
        with self._lock:
            if not self._publish_started:
                self._cancel_event.set()
        if self.led is not None:
            try:
                self.led.clear(strict=True)
            except Exception:
                pass

    def stop(self) -> None:
        self.cancel()
        self.wait(timeout=5)
        self._drift_stop.set()
        self._drift_thread.join(timeout=2)

    def wait(self, timeout=None) -> bool:
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            return not thread.is_alive()
        return True

    def status(self) -> dict:
        with self._lock:
            status = {
                **self._status,
                "progress": dict(self._status["progress"]),
                "metrics": dict(self._status["metrics"]),
                "detected_anchors": [dict(anchor) for anchor in self._detected_anchors],
                "geometry_revision": self._geometry_revision,
            }
        status["ok"] = status["phase"] == "ready"
        status["locked"] = self.current_lock is not None
        status["confidence"] = getattr(self.current_lock, "confidence", None)
        status["out_size"] = getattr(self.current_lock, "out_size", None)
        status["capabilities"] = {
            "camera_ready": self._is_ready(self.capture),
            "led_ready": self._is_ready(self.led),
            "geometry_ready": self.current_lock is not None and status["session_calibrated"],
        }
        return status

    def confirm_existing(self) -> dict:
        """Promote a persisted lock for this process after operator inspection."""
        with self._lock:
            if self._status["phase"] not in {"required", "failed"}:
                raise ValueError("existing geometry can only be confirmed after restart or failed recalibration")
            if self.current_lock is None:
                raise ValueError("no existing geometry to confirm")
            if not self._is_ready(self.capture):
                raise ValueError("camera is not ready")
            lock = self.current_lock
            self._init_drift_monitor(lock)
            self._geometry_revision += 1
            self._status.update(
                phase="ready",
                session_calibrated=True,
                last_valid=True,
                trigger="operator_reuse",
                error=None,
                metrics={},
            )
        self.on_success(lock)
        return self.status()

    @staticmethod
    def _is_ready(service) -> bool:
        value = getattr(service, "is_connected", False)
        return bool(value() if callable(value) else value)

    def _progress(self, phase: str, current: int, total: int) -> None:
        with self._lock:
            self._status["phase"] = phase
            self._status["progress"] = {"current": current, "total": total}

    def _anchor_observed(self, row: int, col: int, point: tuple[float, float], color: str) -> None:
        with self._lock:
            self._detected_anchors.append(
                {
                    "row": int(row),
                    "col": int(col),
                    "x": float(point[0]),
                    "y": float(point[1]),
                    "color": color,
                }
            )

    def _converge_exposure(self) -> None:
        """标定开始前把曝光收敛一次。无几何锁时,这是**唯一**会去动曝光的地方。

        根因(spec §2.1 + 终审 F1):CameraHub 在 open() 时关掉硬件 AE,而软件 AE 只在
        有几何锁的时候才跑 —— 无锁时 worker 的 `_warp_frame` 返回 `(None, False)`,
        `_run_ae` 那条线一次都进不去。「棋盘被挪了、请重新标定」之后正好是无锁态,
        于是曝光停在开机那一刻:白天标定必然停在曝光闸上,而产品内没有出路。

        只驱动硬件 AE,不去加大 exposure_absolute —— 后者实测无效(见上方常量注释)。

        **收敛完必须退回手动**,三条理由,第一条最硬:
        1. 锚点定位是一个**差分测量**(lit - dark),它必须在固定曝光下跑。硬件 AE 是连续
           作动的:整个锚点循环开着 AE,同一颗锚点的 dark 帧和 lit 帧就可能是在两个不同
           曝光下拍的,差分本身被污染 —— 而这是整条链上唯一的信号来源。这不是迁就系统
           别处的假定,是这个测量方法自己的要求。
        2. 标定末尾要拍空盘基线,而 GeometryLock.baseline 是曝光相关的,AE 一直开着会让它
           随光线漂,落子分类静默退化。
        3. camera.py 的 lock_exposure 与 worker `_run_ae` 都使用同一个原生手动模式值。

        2026-09-16 板上实测已确认交接会保留亮度：原生自动模式 3 收敛到 median=124，
        切原生手动模式 1 后连续三秒保持 median=125，且模式读回为 1。
        exposure_absolute 没有可靠实时回读，但 exposure_auto 模式本身必须通过
        CameraManager.controls_effective 校验；否则不能继续做 lit-dark 差分。

        有界:轮询不超过 EXPOSURE_CONVERGE_MAX_STEPS 次、总时长不超过
        EXPOSURE_CONVERGE_TIMEOUT_S 秒。超了就带着当前曝光往下走,不卡死也不失败 ——
        但**不静默**:那条路上日志是 warning,并带 `steps=N/MAX` 与 `outcome`,
        既说清「走了几步」也说清「从哪条路出去的」。
        """
        grab = getattr(self.capture, "grab_fresh", None)
        request = getattr(self.capture, "request_controls", None)
        if grab is None or request is None or self._cancel_event.is_set():
            return  # 没有运行时控制的相机(macOS 上 UVC 写入被静默拒绝):没什么可收敛的
        stats = self._measure_exposure(grab)
        if stats is None or self._in_target_band(stats):
            # 亮度合格不代表曝光已经锁住。标定的 lit-dark 差分要求两帧使用同一曝光，
            # 所以这条短路也必须切到手动并验证驱动读回，而不是直接进入锚点循环。
            request(auto_exposure=CAMERA_AUTO_EXPOSURE_OFF)
            settled = self._wait_for_manual_exposure_readback(grab)
            logger.info(
                "geometry exposure lock: median %s -> manual verified, median now %s",
                None if stats is None else round(stats["median"]),
                None if settled is None else round(settled["median"]),
            )
            return
        logger.info(
            "geometry exposure converge: start median=%.0f clip=%.3f -> hardware AE",
            stats["median"], stats["clip_frac"],
        )
        request(auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        deadline = time.monotonic() + self.EXPOSURE_CONVERGE_TIMEOUT_S
        # 初值 = 「一路没 break,把步数用完了」。每条退出路径各自改写它,
        # 这样日志里那个 outcome 说的就是**真的从哪条路出去的**,不是推出来的。
        outcome = "max_steps"
        steps = 0
        try:
            for _step in range(self.EXPOSURE_CONVERGE_MAX_STEPS):
                if self._cancel_event.wait(self.EXPOSURE_CONVERGE_POLL_S):
                    outcome = "cancelled"
                    break
                if time.monotonic() >= deadline:
                    outcome = "timeout"
                    break
                steps += 1
                stats = self._measure_exposure(grab)
                if stats is None:
                    outcome = "no_frame"
                    break
                if self._in_target_band(stats):
                    outcome = "converged"
                    break
        finally:
            # 关回手动必须**无条件**发生。cancelled/timeout/no_frame/max_steps 四条都是
            # break,本来就走得到这里;唯一漏掉的是**抛异常**那条 —— 而它的代价最贵:
            # AE 被留在开着的状态会跨到**下一次**标定,让每一颗锚点的 dark 帧和 lit 帧
            # 落在两个不同曝光上,污染差分这个唯一的信号来源。本次失败是响的
            # (phase=failed),下一次测错是哑的。
            # 只把关闭动作放进来,**不吞异常**:异常照旧往上抛,由 _run 的 except 变成
            # phase=failed。日志那几行故意留在 finally 外面 —— 它们要再取一帧,在异常
            # 传播途中取帧再抛就会用新异常盖掉真正的那个。
            request(auto_exposure=CAMERA_AUTO_EXPOSURE_OFF)
        settled = self._wait_for_manual_exposure_readback(grab)
        # 一行里四件事,每件都在回答一个自己回答不了的问题:
        #  - 交接前后两个 median:两个数接近 ⇒ 驱动保留了 AE 收敛值;后一个跳回高位
        #    ⇒ 「驱动把曝光弹回 default」的指纹。否则 journal 里只有一个
        #    frame_overexposed,分不清是屋里太亮还是这次收敛白做了。
        #  - steps=N/MAX 与 outcome:上限现在是板上实测的 20 秒(见常量注释),但那条实测
        #    只量了「暗→亮」方向,生产是「过曝→带内」。这两个数一打出来,跑一次白天的
        #    标定就知道 20 秒对不对 —— 生产方向的收敛时间只能这么拿到。
        # 撞上限/超时退出时,标定是**带着没收敛完的曝光继续往下跑**的 —— 这条路不该
        # 静默,所以它是 warning 而不是 info。收敛/取消/没帧都不算(前者成功,后两者
        # 上游自己会报)。
        capped = outcome in {"max_steps", "timeout"}
        emit = logger.warning if capped else logger.info
        emit(
            "geometry exposure converge: median %s -> manual, median now %s "
            "(in_band=%s steps=%d/%d outcome=%s capped=%s)",
            None if stats is None else round(stats["median"]),
            None if settled is None else round(settled["median"]),
            None if settled is None else self._in_target_band(settled),
            steps,
            self.EXPOSURE_CONVERGE_MAX_STEPS,
            outcome,
            capped,
        )

    def _verify_manual_exposure_lock(self) -> None:
        if getattr(self.capture, "controls_effective", None) is not True:
            raise RuntimeError("manual exposure lock readback failed")

    def _wait_for_manual_exposure_readback(self, grab) -> dict | None:
        settled = None
        for _attempt in range(self.EXPOSURE_CONTROL_VERIFY_MAX_FRAMES):
            settled = self._measure_exposure(grab)
            if getattr(self.capture, "controls_effective", None) is not None:
                break
        self._verify_manual_exposure_lock()
        return settled

    @staticmethod
    def _measure_exposure(grab) -> dict | None:
        """整帧统计复用曝光闸那一套(check_frame_exposure),不另起炉灶。"""
        frame, _seq, _ts = grab(settle_ms=0.0)
        if frame is None:
            return None
        return check_frame_exposure(frame)[2]

    def _in_target_band(self, stats: dict) -> bool:
        return self.EXPOSURE_TARGET_LO <= stats["median"] <= self.EXPOSURE_TARGET_HI

    @staticmethod
    def _finite_control_readback(value) -> float | None:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if np.isfinite(value) else None

    def _snapshot_exposure_controls(self) -> tuple[float | None, float | None]:
        return (
            self._finite_control_readback(getattr(self.capture, "current_auto_exposure", None)),
            self._finite_control_readback(getattr(self.capture, "current_exposure", None)),
        )

    def _restore_exposure_controls(self, snapshot: tuple[float | None, float | None]) -> None:
        request = getattr(self.capture, "request_controls", None)
        if request is None:
            return
        auto_exposure, exposure = snapshot
        if auto_exposure is not None and _auto_exposure_readback_matches(CAMERA_AUTO_EXPOSURE_MANUAL, auto_exposure):
            if exposure is None:
                return
            target_auto_exposure = CAMERA_AUTO_EXPOSURE_MANUAL
            target_exposure = exposure
            request(auto_exposure=target_auto_exposure, exposure=target_exposure)
        elif auto_exposure is not None and _auto_exposure_readback_matches(CAMERA_AUTO_EXPOSURE_ON, auto_exposure):
            target_auto_exposure = CAMERA_AUTO_EXPOSURE_ON
            target_exposure = None
            request(auto_exposure=target_auto_exposure)
        else:
            return

        grab = getattr(self.capture, "grab_fresh", None)
        for _attempt in range(self.EXPOSURE_CONTROL_VERIFY_MAX_FRAMES):
            effective = getattr(self.capture, "controls_effective", None)
            if effective is not None or grab is None:
                break
            grab(settle_ms=0.0)
        effective = getattr(self.capture, "controls_effective", None)
        current_auto_exposure = self._finite_control_readback(
            getattr(self.capture, "current_auto_exposure", None)
        )
        current_exposure = self._finite_control_readback(getattr(self.capture, "current_exposure", None))
        restored = (
            effective is True
            and current_auto_exposure is not None
            and _auto_exposure_readback_matches(target_auto_exposure, current_auto_exposure)
            and (
                target_exposure is None
                or (
                    current_exposure is not None
                    and _exposure_readback_matches(target_exposure, current_exposure)
                )
            )
        )
        if not restored:
            logger.warning(
                "geometry exposure restore readback failed: controls_effective=%r "
                "target_auto=%r current_auto=%r target_exposure=%r current_exposure=%r",
                effective,
                target_auto_exposure,
                current_auto_exposure,
                target_exposure,
                current_exposure,
            )

    def _cancel_if_requested(self) -> bool:
        if not self._cancel_event.is_set():
            return False
        with self._lock:
            self._status["phase"] = "cancelled"
        return True

    def _before_publish(self) -> None:
        """Linearize cancellation immediately before the durable pointer/file swap."""
        with self._lock:
            if self._cancel_event.is_set():
                raise CalibrationCancelled("calibration cancelled before publication")
            self._publish_started = True

    def _persist_legacy(self, lock) -> None:
        """Stage both legacy files before crossing the publication boundary."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{self.save_path.name}.", dir=self.save_path.parent) as staging:
            staging_path = Path(staging)
            staged_path = staging_path / self.save_path.name
            staged_sidecar = staged_path.with_suffix(".json")
            final_sidecar = self.save_path.with_suffix(".json")
            backup_path = staging_path / "previous.npz"
            backup_sidecar = staging_path / "previous.json"
            save_geometry_lock(lock, staged_path)
            previous_files = (
                (self.save_path, backup_path, self.save_path.exists()),
                (final_sidecar, backup_sidecar, final_sidecar.exists()),
            )
            for final_path, backup, existed in previous_files:
                if existed:
                    shutil.copyfile(final_path, backup)
            self._before_publish()
            try:
                os.replace(staged_path, self.save_path)
                os.replace(staged_sidecar, final_sidecar)
            except Exception as publish_exc:
                rollback_errors = []
                for final_path, backup, existed in previous_files:
                    try:
                        if existed:
                            os.replace(backup, final_path)
                        else:
                            final_path.unlink(missing_ok=True)
                    except Exception as rollback_exc:
                        rollback_errors.append(f"{final_path.name}: {rollback_exc}")
                if rollback_errors:
                    detail = "; ".join(rollback_errors)
                    raise LegacyPublishRollbackError(
                        f"legacy geometry publish failed ({publish_exc}); rollback failed ({detail}); "
                        "persisted geometry state is unknown"
                    ) from publish_exc
                raise

    def _run(self) -> None:
        exposure_snapshot = self._snapshot_exposure_controls()
        committed = False
        try:
            # Free the CPU the vision worker hogs for the whole run; on_resume (finally)
            # re-arms it on the new lock (success) or the previous one (failure/cancel).
            self.on_suspend()
            # 挂起 worker 之后、跑锚点循环之前:把曝光收敛一次(见 _converge_exposure)。
            # 顺序是判据的一部分 —— 标定自己的曝光闸必须量在收敛之后的那一帧上。
            self._converge_exposure()
            calibrator = self.calibrator_factory(
                led=self.led,
                capture=self.capture,
                cancel_event=self._cancel_event,
                progress=self._progress,
                anchor_observer=self._anchor_observed,
            )
            result = calibrator.calibrate()
            if self._cancel_if_requested() or result.reason == "cancelled":
                with self._lock:
                    self._status["phase"] = "cancelled"
                return
            if not result.ok or result.lock is None:
                with self._lock:
                    self._status["phase"] = "failed"
                    self._status["error"] = result.reason or "calibration_failed"
                    # 失败诊断是这一层唯一的可观测出口 —— 丢掉它,任何人都分不清
                    # low_signal / ambiguous_blobs / show_failed(见 spec §2.3)。
                    metrics = {"attempts": [dict(a) for a in result.attempts]}
                    # 曝光闸的统计走自己的键:它不是一次闪灯尝试,混进 attempts 会让
                    # 界面把「闸在门口拒绝了」讲成「找了 13 个位置一个都没找到」。
                    if result.exposure_stats is not None:
                        metrics["exposure"] = dict(result.exposure_stats)
                    self._status["metrics"] = metrics
                return

            drift_monitor = self._prepare_drift_monitor(result.lock)
            fit = result.fit
            metrics = {
                "inlier_count": getattr(fit, "inlier_count", None),
                "rms_residual": getattr(fit, "rms_residual", None),
                "max_residual": getattr(fit, "max_residual", None),
            }
            if self._cancel_if_requested():
                return
            if self.persist_state is None:
                self._persist_legacy(result.lock)
            else:
                auto_exposure = getattr(self.capture, "current_auto_exposure", None)
                exposure = getattr(self.capture, "current_exposure", None)
                try:
                    auto_exposure = float(auto_exposure)
                    exposure = float(exposure)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("camera controls unavailable after calibration") from exc
                if not _auto_exposure_readback_matches(CAMERA_AUTO_EXPOSURE_MANUAL, auto_exposure):
                    raise RuntimeError("camera is not in verified manual exposure mode after calibration")
                if not np.isfinite(exposure):
                    raise RuntimeError("camera exposure is not finite after calibration")
                self.persist_state(result.lock, CAMERA_AUTO_EXPOSURE_MANUAL, exposure, self._before_publish)
            committed = True
            with self._lock:
                self.current_lock = result.lock
                self._drift_monitor = drift_monitor
                self._geometry_revision += 1
                self._status.update(
                    phase="ready",
                    progress={"current": 13, "total": 13},
                    session_calibrated=True,
                    last_valid=True,
                    error=None,
                    metrics=metrics,
                )
            try:
                self.on_success(result.lock)
            except Exception as exc:
                logger.warning("geometry calibration on_success failed after commit: %s", exc)
        except CalibrationCancelled:
            with self._lock:
                self._status["phase"] = "cancelled"
        except LegacyPublishRollbackError as exc:
            logger.error("legacy geometry rollback failed; invalidating runtime geometry: %s", exc)
            with self._lock:
                self.current_lock = None
                self._drift_monitor = None
                self._status.update(
                    phase="failed",
                    session_calibrated=False,
                    last_valid=False,
                    error=str(exc),
                )
            try:
                self.on_degraded()
            except Exception as invalidate_exc:
                logger.error("runtime geometry invalidation failed after legacy rollback error: %s", invalidate_exc)
        except Exception as exc:
            if committed:
                logger.warning("geometry calibration post-commit update failed: %s", exc)
            else:
                with self._lock:
                    self._status["phase"] = "failed"
                    self._status["error"] = str(exc)
        finally:
            if not committed:
                try:
                    self._restore_exposure_controls(exposure_snapshot)
                except Exception as exc:
                    logger.warning("geometry exposure restore failed: %s", exc)
            if self.led is not None:
                try:
                    self.led.clear(strict=True)
                except Exception:
                    pass
            try:
                self.on_resume()
            except Exception:
                pass

    def _prepare_drift_monitor(self, lock):
        if not hasattr(self.capture, "grab_fresh"):
            return None
        frame, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
        if frame is None:
            return None
        from katrain.vision.geometry_drift import GeometryDriftMonitor

        horizontal = np.linalg.norm(lock.points[:, 1:] - lock.points[:, :-1], axis=2)
        vertical = np.linalg.norm(lock.points[1:] - lock.points[:-1], axis=2)
        spacing = float(np.median(np.concatenate([horizontal.ravel(), vertical.ravel()])))
        return GeometryDriftMonitor(frame, cell_spacing_px=spacing)

    def _init_drift_monitor(self, lock) -> None:
        self._drift_monitor = self._prepare_drift_monitor(lock)

    def _drift_loop(self) -> None:
        while not self._drift_stop.wait(1.0):
            monitor = self._drift_monitor
            if monitor is None or not hasattr(self.capture, "grab_fresh"):
                continue
            with self._lock:
                if self._status["phase"] != "ready":
                    continue
            try:
                frame, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
                if frame is None:
                    continue
                self._apply_drift(monitor.update(frame))
            except Exception:
                time.sleep(0.1)

    def _apply_drift(self, drift) -> None:
        """On a ready→degraded transition, record it and invalidate downstream geometry.

        Without invalidation the vision worker keeps warping with the pre-drift matrix, so a
        bumped board yields confident-but-wrong detections (sub-cell shift → SyncStateMachine's
        confidence gate never fires) and wrong LED/voice guidance + wrong judging, with no
        recovery signal on the tsumego surface. Recovery is a fresh calibration (degraded is
        terminal for confirm_existing — see test_confirm_existing_cannot_override_degraded_state).
        """
        if not drift.degraded:
            return
        with self._lock:
            if self._status["phase"] != "ready":
                return
            self._status["phase"] = "degraded"
            self._status["error"] = "board_moved"
            self._status["metrics"].update(shift_cells=drift.shift_cells, drift_response=drift.response)
        # Outside the lock: on_degraded fans out to the vision worker (IPC).
        self.on_degraded()
