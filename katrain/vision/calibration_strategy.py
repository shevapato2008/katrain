"""P12 — unified board-calibration Strategy interface + scenario-driven selector.

This module organizes the repo's several board-calibration algorithms behind ONE
interface (Strategy pattern) and a priority Selector that picks among them per
*scenario*. It encodes the product rule "no automatic LED for geometry" structurally:

  * ``allow_led`` is DERIVED from the ``Scenario`` (``Scenario.allows_led()``), never a
    free-standing field a caller can set to a contradictory value. ``RUNTIME_RECALIBRATION``
    always forbids LED; only the user-initiated ``INITIAL_SETUP`` / ``MANUAL_FALLBACK`` allow it.
  * The selector HARD-SKIPS any ``requires_led`` strategy when the scenario forbids LED —
    its ``calibrate()`` is never even called.
  * Each LED strategy ALSO self-guards inside ``calibrate()`` (defense in depth).

See plan.md "P12 修订说明（对抗评审采纳）" — that block is authoritative.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np


class Scenario(enum.Enum):
    """When a calibration is requested — determines whether LED is permitted."""

    INITIAL_SETUP = "initial_setup"  # user-initiated, empty board → LED allowed
    RUNTIME_RECALIBRATION = "runtime_recalibration"  # automatic, mid-game → LED forbidden
    MANUAL_FALLBACK = "manual_fallback"  # user-initiated recovery → LED allowed

    def allows_led(self) -> bool:
        return self is not Scenario.RUNTIME_RECALIBRATION


@dataclass(frozen=True)
class CalibrationContext:
    """Inputs a strategy may consume. Strategy-specific slots are optional; a strategy
    whose required slot is missing must veto via ``is_applicable`` rather than crash."""

    frames: List[np.ndarray]
    board: Optional[object] = None  # 19x19 state, or None when empty/unknown
    geometry: Optional[object] = None  # current GeometryLock (M_0 / grid), if any
    led: Optional[object] = None
    capture: Optional[object] = None
    out_size: int = 950
    # strategy-specific optional inputs (only some strategies use these)
    next_point: Optional[dict] = None  # guidance move to exclude from fiducials
    last_good_M: Optional[np.ndarray] = None


@dataclass(frozen=True)
class CalibrationOutcome:
    """Result of a calibration attempt.

    Contract (修订说明 #3): ``M`` / ``Minv`` are non-None **iff** ``ok`` is True. The
    optional full-lock fields (``points`` / ``xs`` / ``ys`` / ``baseline``) are produced
    ONLY by full-board strategies (EmptyBoardAutocal, LedAnchor); frame-homography
    strategies (OuterCorner, LedFiducial) leave them None.
    """

    ok: bool
    M: Optional[np.ndarray] = None
    Minv: Optional[np.ndarray] = None
    corners: Optional[np.ndarray] = None
    confidence: float = 0.0
    strategy: str = ""
    reason: str = ""
    # optional full-lock extras
    points: Optional[np.ndarray] = None
    xs: Optional[np.ndarray] = None
    ys: Optional[np.ndarray] = None
    baseline: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.ok and (self.M is None or self.Minv is None):
            raise ValueError("CalibrationOutcome.ok=True requires non-None M and Minv")
        if not self.ok and not (self.M is None and self.Minv is None):
            raise ValueError("CalibrationOutcome.ok=False requires M and Minv to be None")


@runtime_checkable
class CalibrationStrategy(Protocol):
    """One calibration algorithm behind a uniform interface."""

    name: str
    requires_led: bool
    works_on_crowded_board: bool

    def is_applicable(self, ctx: CalibrationContext) -> bool:
        """Cheap pre-check: can this strategy even run on this context? (early veto)"""
        ...

    def calibrate(self, ctx: CalibrationContext, *, allow_led: bool) -> CalibrationOutcome:
        ...


class CalibrationSelector:
    """Tries the strategies named in ``policy[scenario]`` in order, returning the first
    success. ``allow_led`` is derived from the scenario; ``requires_led`` strategies are
    hard-skipped (never called) when the scenario forbids LED."""

    def __init__(self, strategies: List[CalibrationStrategy], policy: Dict[Scenario, List[str]]):
        self._by_name: Dict[str, CalibrationStrategy] = {s.name: s for s in strategies}
        self._policy = policy

    def calibrate(self, scenario: Scenario, ctx: CalibrationContext) -> CalibrationOutcome:
        allow_led = scenario.allows_led()
        reasons: List[str] = []
        for name in self._policy.get(scenario, []):
            strat = self._by_name.get(name)
            if strat is None:
                reasons.append(f"{name}:unregistered")
                continue
            if strat.requires_led and not allow_led:
                reasons.append(f"{name}:led-gated")
                continue
            if not strat.is_applicable(ctx):
                reasons.append(f"{name}:not-applicable")
                continue
            out = strat.calibrate(ctx, allow_led=allow_led)
            if out.ok:
                return out
            reasons.append(f"{name}:{out.reason}")
        return CalibrationOutcome(ok=False, strategy="", reason="; ".join(reasons) or "no_strategy")
