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
    # Consecutive stable-board frames a single new stone must persist before MoveDetector
    # confirms it as a move (on top of the 2-frame per-cell voting). Raised from the
    # MoveDetector default of 3 after a warp-margin object briefly crossing the add
    # threshold was injected as a phantom corner move.
    move_confirm_frames: int = 5
    # Rolling average of the last N warped frames before inference (static scene only —
    # reset on motion). Measured 4.7x temporal-noise reduction at 8 in weak light, which
    # stabilizes confidence and box centers. 0/1 disables.
    frame_average: int = 8
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
            "move_confirm_frames": self.move_confirm_frames,
            "frame_average": self.frame_average,
            "use_clahe": self.use_clahe,
            "capture_fps": self.capture_fps,
        }
