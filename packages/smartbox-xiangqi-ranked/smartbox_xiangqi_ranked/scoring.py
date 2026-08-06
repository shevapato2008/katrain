"""Versioned, pure Xiangqi ranked scoring.

This module deliberately contains no persistence, identity, clock, or network code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

SCORING_CONTRACT_VERSION = 4
INITIAL_RATING = 1000

ANCHORS = {
    1: 1010,
    2: 1260,
    3: 1510,
    4: 1760,
    5: 1960,
    6: 2160,
    7: 2360,
    8: 2560,
    9: 2900,
}
K_PROVISIONAL = 40
K_STABLE = 20
PROVISIONAL_GAMES = 20
RATING_FLOOR = 100
FARM_MARGIN = 130
FARM_CEIL = {level: anchor + FARM_MARGIN for level, anchor in ANCHORS.items()}

TIERS = (
    (100, "十二级棋士"),
    (1150, "八级棋士"),
    (1400, "四级棋士"),
    (1650, "一级棋士"),
    (1900, "地方大师"),
    (2100, "棋协大师"),
    (2300, "国家大师"),
    (2500, "特级大师"),
    (2600, "超越职业"),
)

Outcome = Literal["win", "draw", "loss"]
TimeControl = Literal["unlimited", "blitz5", "standard10", "slow20"]
OUTCOMES: tuple[Outcome, ...] = ("win", "draw", "loss")
TIME_CONTROLS: tuple[TimeControl, ...] = ("unlimited", "blitz5", "standard10", "slow20")


@dataclass(frozen=True)
class RatingState:
    rating: float
    rated_games: int

    def __post_init__(self) -> None:
        if isinstance(self.rating, bool) or not isinstance(self.rating, (int, float)):
            raise TypeError("rating must be a finite number")
        if not math.isfinite(float(self.rating)):
            raise ValueError("rating must be finite")
        if isinstance(self.rated_games, bool) or not isinstance(self.rated_games, int):
            raise TypeError("rated_games must be an integer")
        if self.rated_games < 0:
            raise ValueError("rated_games cannot be negative")
        object.__setattr__(self, "rating", float(self.rating))


@dataclass(frozen=True)
class RatingChange:
    before: RatingState
    after: RatingState
    outcome: Outcome
    display_before: int
    display_after: int
    display_delta: int


def expected(rating: float, anchor: float) -> float:
    return 1.0 / (1.0 + 10 ** ((anchor - rating) / 400))


def k_factor(rated_games: int) -> int:
    return K_PROVISIONAL if rated_games < PROVISIONAL_GAMES else K_STABLE


def outcome_from_result(result: str, player_color: str) -> Outcome:
    if result not in {"1-0", "0-1", "1/2-1/2"}:
        raise ValueError(f"unsupported result: {result!r}")
    if player_color not in {"red", "black"}:
        raise ValueError(f"unsupported player color: {player_color!r}")
    if result == "1/2-1/2":
        return "draw"
    player_won = (result == "1-0") == (player_color == "red")
    return "win" if player_won else "loss"


def apply_one_v4(state: RatingState, *, opponent_level: int, outcome: Outcome) -> RatingChange:
    """Apply the existing continuous Elo formula exactly once."""

    if opponent_level not in ANCHORS:
        raise ValueError(f"unsupported opponent level: {opponent_level!r}")
    if outcome not in OUTCOMES:
        raise ValueError(f"unsupported outcome: {outcome!r}")

    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[outcome]
    before_rating = state.rating
    expectation = expected(before_rating, ANCHORS[opponent_level])
    raw_delta = k_factor(state.rated_games) * (score - expectation)
    if outcome == "win":
        raw_delta = min(raw_delta, max(0.0, FARM_CEIL[opponent_level] - before_rating))
    after_rating = max(before_rating + raw_delta, float(RATING_FLOOR))
    after = RatingState(after_rating, state.rated_games + 1)
    display_before = round(before_rating)
    display_after = round(after_rating)
    return RatingChange(
        before=state,
        after=after,
        outcome=outcome,
        display_before=display_before,
        display_after=display_after,
        display_delta=display_after - display_before,
    )


# Append-only compatibility registry. Never delete a version that an issued
# reservation or a durable Outbox event may still reference.
SUPPORTED_CONTRACTS = {4: apply_one_v4}


def apply_one(
    state: RatingState,
    *,
    opponent_level: int,
    outcome: Outcome,
    time_control: TimeControl,
    contract_version: int = SCORING_CONTRACT_VERSION,
) -> RatingChange:
    if time_control not in TIME_CONTROLS:
        raise ValueError(f"unsupported time control: {time_control!r}")
    try:
        implementation = SUPPORTED_CONTRACTS[contract_version]
    except KeyError as exc:
        raise ValueError(f"unsupported scoring contract: {contract_version!r}") from exc
    return implementation(state, opponent_level=opponent_level, outcome=outcome)


def project_three(
    state: RatingState,
    *,
    opponent_level: int,
    time_control: TimeControl,
    contract_version: int = SCORING_CONTRACT_VERSION,
) -> dict[Outcome, RatingChange]:
    return {
        outcome: apply_one(
            state,
            opponent_level=opponent_level,
            outcome=outcome,
            time_control=time_control,
            contract_version=contract_version,
        )
        for outcome in OUTCOMES
    }


def pick_level(rating: float) -> int:
    """Choose the nearest catalog anchor, with midpoint ties going upward."""

    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        raise TypeError("rating must be a finite number")
    if not math.isfinite(float(rating)):
        raise ValueError("rating must be finite")
    levels = tuple(ANCHORS)
    for lower, upper in zip(levels, levels[1:]):
        midpoint = (ANCHORS[lower] + ANCHORS[upper]) / 2
        if rating < midpoint:
            return lower
    return levels[-1]


def tier_of(rating: float) -> dict[str, object]:
    index = 0
    for candidate, (minimum, _name) in enumerate(TIERS):
        if minimum <= rating:
            index = candidate
        else:
            break
    minimum, name = TIERS[index]
    if index + 1 == len(TIERS):
        next_tier = None
    else:
        next_minimum, next_name = TIERS[index + 1]
        next_tier = {"name": next_name, "min": next_minimum}
    return {"name": name, "min": minimum, "next": next_tier}
