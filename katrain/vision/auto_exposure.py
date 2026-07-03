"""Software auto-exposure: board-ROI metering + target-band exposure control.

Industry-standard structure (Basler "Exposure Auto" / FLIR "Target Brightness"): the
median luminance of a metering ROI is driven into a target band by multiplicative
exposure corrections with damping, a deadband, and a hold-off after each actuation.
Exposure only — gain stays at its fixed value (the gain ladder is SBC-stage work).

On hosts where exposure controls are inert (macOS AVFoundation rejects all UVC
exposure writes), the worker runs the controller in advisory mode: brightness and
the would-be direction are logged, nothing is actuated.

Default target band [120, 170] was calibrated on live captures: every known-good
scene (recognition working) metered 146-160 on the board region; the weak-light
failure mode on the Mac is gain noise at normalized brightness, not darkness — on
the SBC with the camera AE locked off, brightness genuinely tracks ambient light
and this band is what keeps stones near max SNR.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class BrightnessStats:
    median: float  # median gray level of the board region (0-255)
    clip_frac: float  # fraction of pixels >= 250 (blown highlights / glare)
    shadow_frac: float  # fraction of pixels <= 10 (crushed shadows)


def meter_brightness(warped: np.ndarray, margin_cells: float = 1.0, grid_size: int = 19) -> BrightnessStats:
    """Median-based metering over the grid region of a warped board frame.

    The blank warp margin is stripped (its content is off-board), the region is
    stride-downsampled 4x (statistics only), and the MEDIAN is used so small bright
    spots (glare, lit LEDs) or dark spots (stones) cannot drag the reading the way
    a mean would — the board surface dominates."""
    h, w = warped.shape[:2]
    cells = grid_size - 1 + 2 * margin_cells
    py = int(round(h * margin_cells / cells))
    px = int(round(w * margin_cells / cells))
    inner = warped[py : h - py, px : w - px] if py or px else warped
    small = inner[::4, ::4]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    return BrightnessStats(
        median=float(np.median(gray)),
        clip_frac=float((gray >= 250).mean()),
        shadow_frac=float((gray <= 10).mean()),
    )


class ExposureController:
    """Drives board-median luminance into [target_lo, target_hi] via exposure steps.

    Pure logic with an injected clock (``now`` parameters) — unit-testable without a
    camera. ``update()`` returns the new exposure value to actuate, or None.

    Behavior (matching industrial AE functions):
    - Deadband: no action while the median sits inside the band.
    - Confirmation: the median must be out of band in the SAME direction for
      ``confirm_evals`` consecutive evaluations (spaced ``eval_interval`` apart)
      before anything moves — transient shadows/hands never trigger.
    - Damped multiplicative correction: new = cur * (target_mid / median) ** damping,
      factor clamped to [0.5, 2.0] per step, exposure clamped to [min, max].
    - Highlight guard: clip_frac > max_clip_frac forces a step DOWN even when the
      median looks fine (a glare patch can blow out while the board meters mid-gray).
    - Anti-flicker: exposures >= ``flicker_step`` are quantized to multiples of it
      (V4L2 UVC exposure is in 100 microsecond units, so 100 = 10 ms = one half-cycle
      at 50 Hz mains).
    - Hold-off: after an actuation, evaluations are suppressed for ``holdoff``
      seconds so the sensor settles before the next reading counts.
    """

    def __init__(
        self,
        target_lo: float = 120.0,
        target_hi: float = 170.0,
        damping: float = 0.6,
        eval_interval: float = 2.0,
        holdoff: float = 2.0,
        confirm_evals: int = 2,
        min_exposure: float = 1.0,
        max_exposure: float = 5000.0,
        flicker_step: float = 100.0,
        max_clip_frac: float = 0.02,
        seed_exposure: float = 300.0,
    ):
        self.target_lo = target_lo
        self.target_hi = target_hi
        self.damping = damping
        self.eval_interval = eval_interval
        self.holdoff = holdoff
        self.confirm_evals = confirm_evals
        self.min_exposure = min_exposure
        self.max_exposure = max_exposure
        self.flicker_step = flicker_step
        self.max_clip_frac = max_clip_frac
        self.seed_exposure = seed_exposure

        self._exposure: float | None = None  # current actuated value (None until seeded)
        self._last_eval: float | None = None
        self._last_action: float | None = None
        self._streak = 0
        self._streak_dir = 0

    @property
    def current_exposure(self) -> float | None:
        return self._exposure

    def seed(self, exposure: float | None) -> None:
        """Set the starting exposure (camera readback at open); None keeps the default."""
        if exposure is not None and exposure > 0:
            self._exposure = float(exposure)

    def band_position(self, stats: BrightnessStats) -> str:
        """'low' / 'high' / 'ok' — advisory-mode direction hint."""
        if stats.clip_frac > self.max_clip_frac or stats.median > self.target_hi:
            return "high"
        if stats.median < self.target_lo:
            return "low"
        return "ok"

    def update(self, stats: BrightnessStats, now: float) -> float | None:
        """Feed one metering sample; returns a new exposure value to apply, or None."""
        if self._last_eval is not None and now - self._last_eval < self.eval_interval:
            return None
        self._last_eval = now
        if self._last_action is not None and now - self._last_action < self.holdoff:
            return None

        position = self.band_position(stats)
        direction = {"low": 1, "high": -1, "ok": 0}[position]
        if direction == 0:
            self._streak = 0
            self._streak_dir = 0
            return None
        if direction != self._streak_dir:
            self._streak_dir = direction
            self._streak = 1
        else:
            self._streak += 1
        if self._streak < self.confirm_evals:
            return None

        target_mid = (self.target_lo + self.target_hi) / 2.0
        factor = (target_mid / max(stats.median, 1.0)) ** self.damping
        if direction < 0 and factor >= 1.0:
            factor = 0.7  # highlight guard fired with an in-band median: fixed step down
        factor = min(2.0, max(0.5, factor))

        cur = self._exposure if self._exposure is not None else self.seed_exposure
        new = min(self.max_exposure, max(self.min_exposure, cur * factor))
        new = self._quantize(new)
        if abs(new - cur) < 1e-6:
            self._streak = 0  # clamped/quantized into place — nothing further to do
            return None

        self._exposure = new
        self._last_action = now
        self._streak = 0
        self._streak_dir = 0
        return new

    def _quantize(self, exposure: float) -> float:
        if exposure >= self.flicker_step:
            return max(self.flicker_step, round(exposure / self.flicker_step) * self.flicker_step)
        return max(self.min_exposure, round(exposure))
