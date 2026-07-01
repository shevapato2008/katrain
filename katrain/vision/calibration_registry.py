"""P12 — default calibration selector registry + scenario priority policy.

Priority by scenario (see plan.md "P12 修订说明"):
  * INITIAL_SETUP (user, empty board)   → LED-anchor golden ref, then no-LED autocal.
  * RUNTIME_RECALIBRATION (auto, in-game)→ no-LED OuterCorner ONLY (LED forbidden by scenario).
  * MANUAL_FALLBACK (user recovery)      → try no-LED OuterCorner first, then LED fiducial.
"""
from __future__ import annotations

from katrain.vision.calibration_strategies import (
    EmptyBoardAutocalStrategy,
    LedAnchorStrategy,
    LedFiducialStrategy,
    OuterCornerStrategy,
)
from katrain.vision.calibration_strategy import CalibrationSelector, Scenario


def build_default_selector() -> CalibrationSelector:
    strategies = [
        OuterCornerStrategy(),
        EmptyBoardAutocalStrategy(),
        LedAnchorStrategy(),
        LedFiducialStrategy(),
    ]
    policy = {
        Scenario.INITIAL_SETUP: ["led_anchor", "empty_board_autocal"],
        Scenario.RUNTIME_RECALIBRATION: ["outer_corner"],
        Scenario.MANUAL_FALLBACK: ["outer_corner", "led_fiducial"],
    }
    return CalibrationSelector(strategies, policy)
