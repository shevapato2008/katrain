"""Asynchronous lifecycle for LED-anchor geometry calibration."""

from __future__ import annotations

import threading
from pathlib import Path

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

    def _run(self) -> None:
        try:
            calibrator = self.calibrator_factory(
                led=self.led,
                capture=self.capture,
                cancel_event=self._cancel_event,
                progress=self._progress,
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
            fit = result.fit
            metrics = {
                "inlier_count": getattr(fit, "inlier_count", None),
                "rms_residual": getattr(fit, "rms_residual", None),
                "max_residual": getattr(fit, "max_residual", None),
            }
            with self._lock:
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
