"""Asynchronous lifecycle for LED-anchor geometry calibration."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from katrain.vision.geometry_lock import save_geometry_lock
from katrain.vision.led_geometry_calibrator import LedGeometryCalibrator


class CalibrationBusy(RuntimeError):
    pass


class GeometryCalibrationService:
    ACTIVE_PHASES = {"waiting_empty", "dark_reference", "flashing_corners", "verifying", "building_baseline"}

    def __init__(
        self,
        *,
        led,
        capture,
        save_path,
        initial_lock=None,
        on_success=None,
        calibrator_factory=LedGeometryCalibrator,
    ):
        self.led = led
        self.capture = capture
        self.save_path = Path(save_path).expanduser()
        self.current_lock = initial_lock
        self.on_success = on_success or (lambda _lock: None)
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

    def _run(self) -> None:
        try:
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
            try:
                self.led.clear(strict=True)
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
                drift = monitor.update(frame)
                if drift.degraded:
                    with self._lock:
                        self._status["phase"] = "degraded"
                        self._status["error"] = "board_moved"
                        self._status["metrics"].update(
                            shift_cells=drift.shift_cells,
                            drift_response=drift.response,
                        )
            except Exception:
                time.sleep(0.1)
