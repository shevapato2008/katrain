"""Asynchronous lifecycle for LED-anchor geometry calibration."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import numpy as np

from katrain.vision.geometry_lock import save_geometry_lock
from katrain.vision.led_geometry_calibrator import LedGeometryCalibrator, check_frame_exposure

logger = logging.getLogger(__name__)

# CAP_PROP_AUTO_EXPOSURE 的两个值。都是板上实测过的,不是按名字猜的:
#   3.0  = 硬件 AE。spec §2.2:手工 `v4l2-ctl -c exposure_auto=3` 当场把整帧中位从
#          254 拉回 128-153。这是唯一被证实能把画面调**亮**的手段 ——
#          `exposure_auto_priority=0` 把积分时间钳在帧周期(≈33ms)内,所以
#          exposure_absolute 只调得下、调不上(166→10000 实测无效)。
#   0.25 = 手动。spec §2.1:camera.py 在 open() 里写这个值,板上量到 v4l2
#          `exposure_auto` 由 3(自动)变成 1(手动);worker_inprocess._run_ae
#          用的也是同一个哨兵,两处必须同源。
CAMERA_AUTO_EXPOSURE_ON = 3.0
CAMERA_AUTO_EXPOSURE_OFF = 0.25


class CalibrationBusy(RuntimeError):
    pass


class GeometryCalibrationService:
    ACTIVE_PHASES = {"waiting_empty", "dark_reference", "flashing_corners", "verifying", "building_baseline"}

    # 标定入口那次曝光收敛的边界。用户正站在标定屏前等,不能无限等:超了就带着当前
    # 曝光继续往下走 —— 真收不回来,后面的曝光闸会诚实拒绝,不会伪装成功。
    EXPOSURE_CONVERGE_MAX_STEPS = 6
    EXPOSURE_CONVERGE_TIMEOUT_S = 12.0
    EXPOSURE_CONVERGE_POLL_S = 1.0
    # 目标带与 auto_exposure.ExposureController 的默认带同源(spec:中位落在 [120,170])。
    EXPOSURE_TARGET_LO = 120.0
    EXPOSURE_TARGET_HI = 170.0

    def __init__(
        self,
        *,
        led,
        capture,
        save_path,
        initial_lock=None,
        on_success=None,
        on_degraded=None,
        on_suspend=None,
        on_resume=None,
        calibrator_factory=LedGeometryCalibrator,
    ):
        self.led = led
        self.capture = capture
        self.save_path = Path(save_path).expanduser()
        self.current_lock = initial_lock
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
        3. camera.py 的 lock_exposure 与 worker `_run_ae` 的 auto_exposure=0.25 都假定手动。

        ⚠️ 待板上核实:退回手动时驱动应当保留 AE 刚收敛出来的 exposure_absolute(V4L2 的
        常规行为)。万一它弹回 default,这次收敛白做 —— 但**不会假绿**:紧接着的曝光闸
        会重新量整帧,该报 frame_overexposed 还是照报。核实不必专门安排一次测量:下面
        那行日志把交接前后的两个 median 并排写出来,跑一次标定读一行 journal 就知道。
        (没有实时回读曝光值的口:camera.py 的 controls_effective 是 bool「上次控制有没有
        生效」,initial_exposure 是 open() 那一刻的读数,都不是当前值。)

        有界:轮询不超过 EXPOSURE_CONVERGE_MAX_STEPS 次、总时长不超过
        EXPOSURE_CONVERGE_TIMEOUT_S 秒。超了就带着当前曝光往下走,不卡死也不失败。
        """
        grab = getattr(self.capture, "grab_fresh", None)
        request = getattr(self.capture, "request_controls", None)
        if grab is None or request is None or self._cancel_event.is_set():
            return  # 没有运行时控制的相机(macOS 上 UVC 写入被静默拒绝):没什么可收敛的
        stats = self._measure_exposure(grab)
        if stats is None or self._in_target_band(stats):
            return  # 已经在带内:不动它
        logger.info(
            "geometry exposure converge: start median=%.0f clip=%.3f -> hardware AE",
            stats["median"], stats["clip_frac"],
        )
        request(auto_exposure=CAMERA_AUTO_EXPOSURE_ON)
        deadline = time.monotonic() + self.EXPOSURE_CONVERGE_TIMEOUT_S
        for _step in range(self.EXPOSURE_CONVERGE_MAX_STEPS):
            if self._cancel_event.wait(self.EXPOSURE_CONVERGE_POLL_S) or time.monotonic() >= deadline:
                break
            stats = self._measure_exposure(grab)
            if stats is None or self._in_target_band(stats):
                break
        request(auto_exposure=CAMERA_AUTO_EXPOSURE_OFF)
        # 交接前后各一个 median,并排写进 journal:两个数接近 ⇒ 驱动保留了 AE 收敛值;
        # 后一个跳回高位 ⇒ 就是「驱动把曝光弹回 default」的指纹,一眼看得出来。
        # 归因靠这一行 —— 否则 journal 里只有一个 frame_overexposed,分不清是屋里太亮
        # 还是这次收敛白做了,而这两件事的处置完全不同。
        settled = self._measure_exposure(grab)
        logger.info(
            "geometry exposure converge: median %s -> manual, median now %s (in_band=%s)",
            None if stats is None else round(stats["median"]),
            None if settled is None else round(settled["median"]),
            None if settled is None else self._in_target_band(settled),
        )

    @staticmethod
    def _measure_exposure(grab) -> dict | None:
        """整帧统计复用曝光闸那一套(check_frame_exposure),不另起炉灶。"""
        frame, _seq, _ts = grab(settle_ms=0.0)
        if frame is None:
            return None
        return check_frame_exposure(frame)[2]

    def _in_target_band(self, stats: dict) -> bool:
        return self.EXPOSURE_TARGET_LO <= stats["median"] <= self.EXPOSURE_TARGET_HI

    def _run(self) -> None:
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
            if self._cancel_event.is_set() or result.reason == "cancelled":
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

            save_geometry_lock(result.lock, self.save_path)
            self.current_lock = result.lock
            self.on_success(result.lock)
            self._init_drift_monitor(result.lock)
            fit = result.fit
            metrics = {
                "inlier_count": getattr(fit, "inlier_count", None),
                "rms_residual": getattr(fit, "rms_residual", None),
                "max_residual": getattr(fit, "max_residual", None),
            }
            with self._lock:
                self._geometry_revision += 1
                self._status.update(
                    phase="ready",
                    progress={"current": 13, "total": 13},
                    session_calibrated=True,
                    last_valid=True,
                    error=None,
                    metrics=metrics,
                )
        except Exception as exc:
            with self._lock:
                self._status["phase"] = "failed"
                self._status["error"] = str(exc)
        finally:
            if self.led is not None:
                try:
                    self.led.clear(strict=True)
                except Exception:
                    pass
            try:
                self.on_resume()
            except Exception:
                pass

    def _init_drift_monitor(self, lock) -> None:
        if not hasattr(self.capture, "grab_fresh"):
            return
        frame, _seq, _ts = self.capture.grab_fresh(settle_ms=0.0)
        if frame is None:
            return
        from katrain.vision.geometry_drift import GeometryDriftMonitor

        horizontal = np.linalg.norm(lock.points[:, 1:] - lock.points[:, :-1], axis=2)
        vertical = np.linalg.norm(lock.points[1:] - lock.points[:-1], axis=2)
        spacing = float(np.median(np.concatenate([horizontal.ravel(), vertical.ravel()])))
        self._drift_monitor = GeometryDriftMonitor(frame, cell_spacing_px=spacing)

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
