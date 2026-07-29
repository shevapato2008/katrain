"""Pure scheduling protocol for the serial Golaxy alignment campaign."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


STAGE_ORDER = (
    "seven_d",
    "one_star_b18_1",
    "quasi_5d",
    "quasi_6d",
    "quasi_7d",
    "quasi_8d",
    "quasi_9d",
)
GRID = ("1s", "4", "8", "16", "32", "64")
QUASI_PROFILES = {
    "quasi_5d": "rank_4d",
    "quasi_6d": "rank_5d",
    "quasi_7d": "rank_6d",
    "quasi_8d": "rank_7d",
    "quasi_9d": "rank_8d",
}


@dataclass(frozen=True)
class Candidate:
    player: str
    candidate_index: int | None
    valid: int
    wins: int
    losses: int
    inconclusive: int
    classification: str | None


@dataclass(frozen=True)
class GameRequest:
    stage: str
    player: str
    color: str
    target_valid: int
    phase: str


@dataclass(frozen=True)
class StageDecision:
    stage: str
    status: str
    selected_player: str | None
    best_observed: Candidate | None
    evidence: tuple[Candidate, ...]


@dataclass(frozen=True)
class CampaignDecision:
    status: str
    stages: tuple[StageDecision, ...]


def _player(stage: str, candidate_index: int | None = None) -> str:
    if stage == "seven_d":
        return "rank_7d@1s"
    if stage == "one_star_b18_1":
        return "b18@1"
    if stage not in QUASI_PROFILES:
        raise ValueError(f"unknown campaign stage: {stage}")
    if type(candidate_index) is not int or not 0 <= candidate_index < len(GRID):
        raise ValueError(f"candidate_index must be a plain integer from 0 through {len(GRID) - 1}")
    return f"{QUASI_PROFILES[stage]}@{GRID[candidate_index]}"


def _outcomes(records: Sequence[Mapping[str, object]], stage: str, player: str) -> tuple[list[str], int]:
    conclusive: list[str] = []
    inconclusive = 0
    for row in records:
        if row.get("type") not in {"result", "carry_result"}:
            continue
        if row.get("stage") != stage or row.get("player") != player:
            continue
        outcome = row.get("outcome")
        if row.get("conclusive") is False or outcome == "inconclusive":
            inconclusive += 1
        elif outcome in {"win", "loss"}:
            conclusive.append(str(outcome))
    return conclusive, inconclusive


def summarize_candidate(
    records: Sequence[Mapping[str, object]], stage: str, candidate_index: int | None = None
) -> Candidate:
    player = _player(stage, candidate_index)
    outcomes, inconclusive = _outcomes(records, stage, player)
    if len(outcomes) > 10:
        raise ValueError(f"candidate {player} has more than 10 valid results")
    first_four = outcomes[:4]
    classification = None
    if len(first_four) == 4:
        classification = "strong" if first_four.count("win") >= 3 else "weak"
    return Candidate(
        player=player,
        candidate_index=candidate_index,
        valid=len(outcomes),
        wins=outcomes.count("win"),
        losses=outcomes.count("loss"),
        inconclusive=inconclusive,
        classification=classification,
    )


def _stage_evidence(records: Sequence[Mapping[str, object]], stage: str) -> tuple[Candidate, ...]:
    indices = (None,) if stage in {"seven_d", "one_star_b18_1"} else range(len(GRID))
    return tuple(
        candidate
        for index in indices
        if (candidate := summarize_candidate(records, stage, index)).valid or candidate.inconclusive
    )


def rank_confirmed(records: Sequence[Mapping[str, object]], stage: str) -> tuple[Candidate, ...]:
    if stage not in QUASI_PROFILES:
        raise ValueError("confirmed-candidate ranking is only defined for quasi-dan stages")
    confirmed = [summarize_candidate(records, stage, index) for index in range(len(GRID))]
    confirmed = [candidate for candidate in confirmed if candidate.valid >= 10]
    return tuple(sorted(confirmed, key=lambda item: (abs(item.wins - 5), item.candidate_index)))


def _binary_boundary(records: Sequence[Mapping[str, object]], stage: str) -> tuple[int, int, int | None]:
    lo, hi = -1, len(GRID)
    while hi - lo > 1:
        midpoint = (lo + hi) // 2
        candidate = summarize_candidate(records, stage, midpoint)
        if candidate.valid < 4:
            return lo, hi, midpoint
        if candidate.classification == "strong":
            hi = midpoint
        else:
            lo = midpoint
    return lo, hi, None


def stage_decision(records: Sequence[Mapping[str, object]], stage: str) -> StageDecision | None:
    evidence = _stage_evidence(records, stage)
    if stage == "seven_d":
        candidate = summarize_candidate(records, stage)
        if candidate.valid < 10:
            return None
        return StageDecision(stage, "completed_at_10", candidate.player, candidate, evidence)

    if stage == "one_star_b18_1":
        candidate = summarize_candidate(records, stage)
        if candidate.classification == "weak":
            return StageDecision(stage, "weak_screen", candidate.player, candidate, evidence)
        if candidate.valid >= 10:
            status = (
                "weak_at_10" if candidate.wins <= 3 else "aligned_at_10" if candidate.wins <= 6 else "overstrong_at_10"
            )
            return StageDecision(stage, status, candidate.player, candidate, evidence)
        return None

    if stage not in QUASI_PROFILES:
        raise ValueError(f"unknown campaign stage: {stage}")

    _lo, hi, pending = _binary_boundary(records, stage)
    if pending is not None:
        return None
    if hi == len(GRID):
        observed = [candidate for candidate in evidence if candidate.valid >= 4]
        best_observed = max(observed, key=lambda item: (item.wins, -(item.candidate_index or 0)))
        return StageDecision(stage, "no_strong_candidate_in_grid", None, best_observed, evidence)

    lowest_strong = summarize_candidate(records, stage, hi)
    if lowest_strong.valid < 10:
        return None
    if 4 <= lowest_strong.wins <= 6:
        return StageDecision(stage, "aligned_at_10", lowest_strong.player, lowest_strong, evidence)
    if lowest_strong.wins >= 7:
        if hi == 0:
            return StageDecision(stage, "overstrong_at_grid_floor", lowest_strong.player, lowest_strong, evidence)
        lower = summarize_candidate(records, stage, hi - 1)
        if lower.valid < 10:
            return None
        best_observed = rank_confirmed(records, stage)[0]
        return StageDecision(stage, "selected_closest_confirmed", best_observed.player, best_observed, evidence)

    for index in range(hi + 1, len(GRID)):
        candidate = summarize_candidate(records, stage, index)
        if candidate.valid < 10:
            return None
        if candidate.wins >= 4:
            best_observed = rank_confirmed(records, stage)[0]
            return StageDecision(stage, "selected_closest_confirmed", best_observed.player, best_observed, evidence)

    best_observed = rank_confirmed(records, stage)[0]
    return StageDecision(stage, "no_qualified_candidate_in_grid", None, best_observed, evidence)


def _request(records: Sequence[Mapping[str, object]], stage: str) -> GameRequest:
    if stage == "seven_d":
        candidate = summarize_candidate(records, stage)
        return GameRequest(stage, candidate.player, "B" if candidate.valid % 2 == 0 else "W", 10, "confirm")
    if stage == "one_star_b18_1":
        candidate = summarize_candidate(records, stage)
        target = 4 if candidate.valid < 4 else 10
        phase = "screen" if target == 4 else "confirm"
        return GameRequest(stage, candidate.player, "B" if candidate.valid % 2 == 0 else "W", target, phase)

    _lo, hi, pending = _binary_boundary(records, stage)
    if pending is not None:
        candidate = summarize_candidate(records, stage, pending)
        return GameRequest(stage, candidate.player, "B" if candidate.valid % 2 == 0 else "W", 4, "screen")

    lowest = summarize_candidate(records, stage, hi)
    if lowest.valid < 10:
        candidate, phase = lowest, "confirm"
    elif lowest.wins >= 7:
        candidate, phase = summarize_candidate(records, stage, hi - 1), "compare_lower"
    else:
        next_index = next(
            index for index in range(hi + 1, len(GRID)) if summarize_candidate(records, stage, index).valid < 10
        )
        candidate, phase = summarize_candidate(records, stage, next_index), "confirm_upward"
    return GameRequest(stage, candidate.player, "B" if candidate.valid % 2 == 0 else "W", 10, phase)


def next_action(records: Sequence[Mapping[str, object]]) -> GameRequest | CampaignDecision:
    decisions: list[StageDecision] = []
    for stage in STAGE_ORDER:
        decision = stage_decision(records, stage)
        if decision is None:
            return _request(records, stage)
        decisions.append(decision)
    return CampaignDecision("completed", tuple(decisions))
