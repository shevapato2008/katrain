"""Vision service configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Half the default 120-170 band width, so a bare midpoint reproduces a sensible band
# (e.g. "145" -> 120.0-170.0, matching the historical default).
AE_SCALAR_HALF_WIDTH = 25.0

# Sustain tier for stones already on the board (owner decision 2026-09-22; see
# VisionServiceConfig.confidence_sustain). Far-side white stones in a dense cluster were measured
# dropping below the 0.30 keep threshold for up to 45 s in a static scene on the RK3562.
DEFAULT_CONFIDENCE_SUSTAIN = 0.20

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
    # Presence "sustain" tier (2026-09-22): a stone already on the stable board is kept alive by
    # detections down to this confidence. Only board assignment ever sees these sub-keep detections
    # (where they cannot add a stone); new stones, confirmation cards and the confidence statistics
    # still see only detections >= confidence_keep. None -> min(DEFAULT_CONFIDENCE_SUSTAIN, keep).
    confidence_sustain: float | None = None
    # Pre-inference enhancement of the warped frame: "clahe" (validated weak-light win) | "off"
    enhance: str = "clahe"
    # Consecutive stable-board frames a single new stone must persist before MoveDetector
    # confirms it as a move (on top of the 2-frame per-cell voting). Raised from the
    # MoveDetector default of 3 after a warp-margin object briefly crossing the add
    # threshold was injected as a phantom corner move.
    move_confirm_frames: int = 5
    # Fast path: a pending move whose peak confidence has already reached
    # `move_confirm_fast_confidence` confirms after this many frames instead of
    # `move_confirm_frames`. Confirmation is the whole recognition latency — nothing is
    # computed during the wait, the detector is just counting — so at ~2.3 fps the full
    # 5 frames cost 1.73s between the stone landing and the board reacting.
    move_confirm_fast_frames: int = 3
    # Measured on the box from a real 117-move game (peak_conf per confirmed move):
    # min 0.55, p25 0.72, median 0.75, p75 0.81, max 0.88. At 0.70, 80% of real moves
    # take the fast path; the remaining 20% are the genuinely marginal ones that the
    # extra frames exist for. Set above the observed max to disable the fast path.
    move_confirm_fast_confidence: float = 0.70
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
    # Reference-frame check ("off" | "shadow" | "on", 2026-09-23): compare each cell against the last
    # frame whose raw board matched the game record and keep the occupancy of cells that look
    # unchanged, bounded per cell. "shadow" computes and logs it without touching recognition — the
    # default until board data in daylight sets the threshold and the two hold limits.
    # See superpowers/tracks/vision-optimizations/reference-frame/design.md.
    reference_check: str = "shadow"
    imgsz: int = 960
    use_clahe: bool = False
    intrinsics_file: str | None = None  # persistent camera calibration .npz
    process_mode: str = "worker"  # "worker" (subprocess) | "inprocess" (dev)
    capture_fps: int = 15
    # Stone-parallax correction {"nadir_fx", "nadir_fy", "k"} for the geometry-lock extractor, or None.
    # Never set by hand: server.py fills it at startup from <hardware-vision-dir>/parallax/
    # go-19x19.json, written by the optional katrain.vision.tools.calibrate_parallax. Wins over the
    # lock-derived correction below.
    parallax: dict | None = None
    # Without a calibration file, derive the ver9 mount's parallax from every geometry lock the worker
    # receives (parallax.mount_parallax_for_lock; owner decision 2026-09-22). False = no correction at all.
    parallax_enabled: bool = True

    @property
    def effective_confidence_keep(self) -> float:
        if self.confidence_keep is not None:
            return self.confidence_keep
        return max(0.25, self.confidence_threshold - 0.15)

    @property
    def effective_confidence_sustain(self) -> float:
        value = DEFAULT_CONFIDENCE_SUSTAIN if self.confidence_sustain is None else self.confidence_sustain
        return min(value, self.effective_confidence_keep)

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
            "confidence_sustain": self.effective_confidence_sustain,
            "enhance": self.enhance,
            "move_confirm_frames": self.move_confirm_frames,
            "move_confirm_fast_frames": self.move_confirm_fast_frames,
            "move_confirm_fast_confidence": self.move_confirm_fast_confidence,
            "move_miss_grace": self.move_miss_grace,
            "ambiguous_confidence": self.ambiguous_confidence,
            "frame_average": self.frame_average,
            "ambiguous_promote_frames": self.ambiguous_promote_frames,
            "auto_exposure": self.auto_exposure,
            "ae_target_lo": ae_lo,
            "ae_target_hi": ae_hi,
            "use_clahe": self.use_clahe,
            "capture_fps": self.capture_fps,
            "parallax": self.parallax,
            "parallax_auto": self.parallax_enabled,
            "reference_check": self.reference_check,
        }
