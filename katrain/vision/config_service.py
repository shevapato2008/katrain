"""Vision service configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Half the default 120-170 band width, so a bare midpoint reproduces a sensible band
# (e.g. "145" -> 120.0-170.0, matching the historical default).
AE_SCALAR_HALF_WIDTH = 25.0

# Single source of truth for the accepted-forms wording, shared by every malformed-input
# ValueError raised below.
_AE_TARGET_ACCEPTED_FORMS = "expected 'LO-HI' or a single midpoint value (e.g. '120-170' or '145')"


def _invalid_ae_target_error(value: str) -> ValueError:
    return ValueError(f"Invalid ae_target {value!r}: {_AE_TARGET_ACCEPTED_FORMS}")


def parse_ae_target(value: str) -> tuple[float, float]:
    """Parse a software-AE target brightness spec into a (lo, hi) gray-level band.

    Accepts either band form "LO-HI" (e.g. "120-170") or a single midpoint scalar
    (e.g. "145"), which is expanded into a band of width 2 * AE_SCALAR_HALF_WIDTH
    centered on the value and clamped to the valid gray range [0, 255].
    """
    # Splitting on "-" means any negative input (a bare "-5" or a band bound like
    # "10--5") produces an empty/extra token that the part-count or float() parse
    # below rejects, and a negative bound can't be expressed in "LO-HI" form at all
    # (the "-" is the delimiter) — so no explicit < 0 guard is reachable here.
    parts = value.split("-") if value else []
    if len(parts) == 1:
        try:
            midpoint = float(parts[0])
        except ValueError:
            raise _invalid_ae_target_error(value) from None
        if not math.isfinite(midpoint):
            raise _invalid_ae_target_error(value) from None
        lo = max(0.0, midpoint - AE_SCALAR_HALF_WIDTH)
        hi = min(255.0, midpoint + AE_SCALAR_HALF_WIDTH)
        if lo >= hi:
            raise ValueError(f"Invalid ae_target {value!r}: clamped band [{lo}, {hi}] is not a valid range")
        return lo, hi
    if len(parts) == 2:
        try:
            lo, hi = float(parts[0]), float(parts[1])
        except ValueError:
            raise _invalid_ae_target_error(value) from None
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise _invalid_ae_target_error(value) from None
        if lo >= hi:
            raise ValueError(f"Invalid ae_target {value!r}: lo must be less than hi")
        return lo, hi
    raise _invalid_ae_target_error(value)


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
    # Consecutive ABSENT frames a pending move survives with its count frozen (marginal
    # stones blink; zero tolerance made them permanently unconfirmable).
    move_miss_grace: int = 2
    # Rolling average of the last N warped frames before inference (static scene only —
    # reset on motion). Measured 4.7x temporal-noise reduction at 8 in weak light, which
    # stabilizes confidence and box centers. 0/1 disables.
    frame_average: int = 8
    # A confirmed move below this confidence is routed to the on-screen confirmation
    # card instead of auto-playing. Far-side stones on the Mac rig meter ~0.36-0.45,
    # so a strict gate turns every far move into a manual confirmation — tune per rig.
    ambiguous_confidence: float = 0.55
    # Consecutive frames a sub-add-confidence detection must persist on an empty cell
    # before it is promoted to an ambiguous_stone confirmation prompt (a real stone
    # stuck below the add threshold otherwise has NO path onto the board).
    ambiguous_promote_frames: int = 12
    # Software AE ("software" | "off"): drive the board-region median brightness into
    # ae_target by adjusting exposure at runtime. Advisory-only where exposure controls
    # are inert (macOS); actuates on SBC/V4L2 where lock_exposure disables the camera's
    # own AE.
    auto_exposure: str = "software"
    # Target brightness as either a "LO-HI" gray-level band or a single midpoint scalar
    # (e.g. "120-170" or "145"; a bare midpoint expands to a +/-AE_SCALAR_HALF_WIDTH band,
    # clamped to [0, 255] — see parse_ae_target). Calibrated: known-good scenes meter 146-160.
    ae_target: str = "120-170"
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
        ae_lo, ae_hi = parse_ae_target(self.ae_target)
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
            "move_miss_grace": self.move_miss_grace,
            "ambiguous_confidence": self.ambiguous_confidence,
            "frame_average": self.frame_average,
            "ambiguous_promote_frames": self.ambiguous_promote_frames,
            "auto_exposure": self.auto_exposure,
            "ae_target_lo": ae_lo,
            "ae_target_hi": ae_hi,
            "use_clahe": self.use_clahe,
            "capture_fps": self.capture_fps,
        }
