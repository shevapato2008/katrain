"""Vision service configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VisionServiceConfig:
    """Configuration for the vision service."""

    enabled: bool = False
    backend: str = "onnx"  # "onnx" | "rknn" | "ultralytics"
    model_path: str = ""
    camera_device: int | str = 0
    camera_width: int = 1280
    camera_height: int = 720
    board_size: int = 19
    confidence_threshold: float = 0.5
    # Hysteresis "keep" threshold: a cell already holding a same-color stone in the last
    # stable board keeps it at this lower confidence; empty cells need the full
    # confidence_threshold to gain a stone. None derives max(0.25, threshold - 0.15).
    confidence_keep: float | None = None
    # Pre-inference enhancement of the warped frame: "clahe" (validated weak-light win) | "off"
    enhance: str = "clahe"
    imgsz: int = 960
    use_clahe: bool = False
    intrinsics_file: str | None = None  # persistent camera calibration .npz
    process_mode: str = "worker"  # "worker" (subprocess) | "inprocess" (dev)
    capture_fps: int = 15

    @property
    def effective_confidence_keep(self) -> float:
        if self.confidence_keep is not None:
            return self.confidence_keep
        return max(0.25, self.confidence_threshold - 0.15)

    def to_worker_config(self) -> dict:
        """Convert to dict for passing to worker process."""
        return {
            "backend": self.backend,
            "model_path": self.model_path,
            "camera_device": self.camera_device,
            "camera_width": self.camera_width,
            "camera_height": self.camera_height,
            "confidence_threshold": self.confidence_threshold,
            "confidence_keep": self.effective_confidence_keep,
            "enhance": self.enhance,
            "use_clahe": self.use_clahe,
            "capture_fps": self.capture_fps,
        }
