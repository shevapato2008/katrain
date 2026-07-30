"""Pure scheduler for the fixed Golaxy HumanSL sampling campaign."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


STAGES = (
    ("sampling_quasi_5d", "rank_5d@1", 25),
    ("sampling_quasi_6d", "rank_6d@1", 27),
    ("sampling_quasi_7d", "rank_7d@1", 29),
    ("sampling_quasi_8d", "rank_8d@1", 31),
    ("sampling_quasi_9d", "rank_9d@1", 32),
)
STAGE_ORDER = tuple(stage for stage, _player, _api_level in STAGES)


@dataclass(frozen=True)
class GameRequest:
    stage: str
    player: str
    golaxy_api_level: int
    slot: int
    color: str


@dataclass(frozen=True)
class CandidateSummary:
    stage: str
    player: str
    golaxy_api_level: int
    valid: int
    wins: int
    losses: int
    inconclusive: int


@dataclass(frozen=True)
class StageDecision:
    stage: str
    status: str
    summary: CandidateSummary


@dataclass(frozen=True)
class CampaignDecision:
    status: str
    stages: tuple[StageDecision, ...]


def _stage_spec(stage: object) -> tuple[str, str, int]:
    for spec in STAGES:
        if stage == spec[0]:
            return spec
    raise ValueError(f"unknown campaign stage: {stage!r}")


def _validate_records(records: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    validated: list[Mapping[str, object]] = []
    origin_ids: set[str] = set()
    valid_by_stage = {stage: 0 for stage in STAGE_ORDER}

    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("campaign records must be mappings")
        row_type = row.get("type")
        if row_type not in {"result", "stopped"}:
            raise ValueError(f"unknown campaign record type: {row_type!r}")

        origin_id = row.get("origin_id")
        if row_type == "result" or origin_id is not None:
            if type(origin_id) is not str or not origin_id or origin_id != origin_id.strip():
                raise ValueError("origin_id must be a nonempty plain string without whitespace padding")
            if origin_id in origin_ids:
                raise ValueError(f"duplicate origin_id: {origin_id!r}")
            origin_ids.add(origin_id)

        if row_type == "result":
            stage, expected_player, _api_level = _stage_spec(row.get("stage"))
            player = row.get("player")
            if player != expected_player:
                raise ValueError(f"unknown player {player!r} for stage {stage!r}")

            slot = row.get("slot")
            if type(slot) is not int or not 0 <= slot < 10:
                raise ValueError("slot must be a plain integer from 0 through 9")
            color = row.get("color")
            if color not in {"B", "W"}:
                raise ValueError("color must be 'B' or 'W'")
            expected_color = "B" if slot % 2 == 0 else "W"
            if color != expected_color:
                raise ValueError(f"slot {slot} must use HumanSL color {expected_color}")

            outcome = row.get("outcome")
            if outcome not in {"win", "loss", "inconclusive"}:
                raise ValueError(f"unknown result outcome: {outcome!r}")
            if outcome in {"win", "loss"}:
                valid_by_stage[stage] += 1
                if valid_by_stage[stage] > 10:
                    raise ValueError(f"stage {stage!r} has more than 10 valid results")

        validated.append(row)

    return tuple(validated)


def summarize_candidate(records: Sequence[Mapping[str, object]], stage: str) -> CandidateSummary:
    stage, player, api_level = _stage_spec(stage)
    validated = _validate_records(records)
    outcomes = [row["outcome"] for row in validated if row["type"] == "result" and row["stage"] == stage]
    wins = outcomes.count("win")
    losses = outcomes.count("loss")
    return CandidateSummary(
        stage=stage,
        player=player,
        golaxy_api_level=api_level,
        valid=wins + losses,
        wins=wins,
        losses=losses,
        inconclusive=outcomes.count("inconclusive"),
    )


def stage_decision(records: Sequence[Mapping[str, object]], stage: str) -> StageDecision | None:
    summary = summarize_candidate(records, stage)
    if summary.valid < 10:
        return None
    return StageDecision(stage=stage, status="completed", summary=summary)


def _completed_stages(records: Sequence[Mapping[str, object]]) -> tuple[StageDecision, ...]:
    decisions: list[StageDecision] = []
    for stage in STAGE_ORDER:
        decision = stage_decision(records, stage)
        if decision is None:
            break
        decisions.append(decision)
    return tuple(decisions)


def _validate_sequence(records: Sequence[Mapping[str, object]]) -> None:
    active_stage_index = 0
    valid_in_stage = 0
    for row in records:
        if row["type"] != "result":
            continue
        if active_stage_index == len(STAGES):
            raise ValueError("result recorded after all campaign stages completed")

        expected_stage = STAGES[active_stage_index][0]
        if row["stage"] != expected_stage:
            raise ValueError(f"result stage {row['stage']!r} is not active stage {expected_stage!r}")
        if row["slot"] != valid_in_stage:
            raise ValueError(f"result slot {row['slot']} does not match active slot {valid_in_stage}")

        if row["outcome"] in {"win", "loss"}:
            valid_in_stage += 1
            if valid_in_stage == 10:
                active_stage_index += 1
                valid_in_stage = 0


def next_action(records: Sequence[Mapping[str, object]]) -> GameRequest | CampaignDecision:
    validated = _validate_records(records)
    _validate_sequence(validated)
    completed = _completed_stages(validated)

    if any(row["type"] == "stopped" for row in validated):
        return CampaignDecision(status="stopped", stages=completed)
    if len(completed) == len(STAGES):
        return CampaignDecision(status="completed", stages=completed)

    stage, player, api_level = STAGES[len(completed)]
    summary = summarize_candidate(validated, stage)
    slot = summary.valid
    return GameRequest(
        stage=stage,
        player=player,
        golaxy_api_level=api_level,
        slot=slot,
        color="B" if slot % 2 == 0 else "W",
    )
