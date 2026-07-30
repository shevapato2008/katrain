"""Pure scheduler for the fixed Golaxy HumanSL sampling campaign."""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as SetABC
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence


SAMPLING_ALGORITHM = "golaxy-humansl-weighted-v1"
_SAMPLING_DOMAIN = SAMPLING_ALGORITHM.encode("ascii") + b"\0"

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


@dataclass(frozen=True)
class SamplingAudit:
    algorithm: str
    u: Fraction
    index: int
    move: tuple[int, int] | str
    policy_sha256: str
    positive_total: float
    interval_low: float
    interval_high: float


def _sampling_payload(seed: object, reservation_id: object, ply: object) -> bytes:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be a plain uint64 integer")
    if type(reservation_id) is not str or not reservation_id:
        raise ValueError("reservation_id must be a nonempty plain string")
    try:
        reservation_bytes = str.encode(reservation_id, "utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("reservation_id must be valid UTF-8") from error
    if len(reservation_bytes) > 65535:
        raise ValueError("reservation_id UTF-8 encoding exceeds 65535 bytes")
    if type(ply) is not int or not 0 <= ply < 2**32:
        raise ValueError("ply must be a plain uint32 integer")
    return (
        _SAMPLING_DOMAIN
        + struct.pack(">Q", seed)
        + struct.pack(">H", len(reservation_bytes))
        + reservation_bytes
        + struct.pack(">I", ply)
    )


def derive_uniform(seed: int, reservation_id: str, ply: int) -> Fraction:
    digest = hashlib.sha256(_sampling_payload(seed, reservation_id, ply)).digest()
    raw = int.from_bytes(digest[:8], "big")
    return Fraction(raw, 2**64)


def _validated_policy(policy: object) -> tuple[list[float], str]:
    if type(policy) is not list or len(policy) != 362:
        raise ValueError("policy must be a list of exactly 362 values")

    weights: list[float] = []
    encoded = bytearray()
    for value in policy:
        if type(value) not in {int, float}:
            raise ValueError("policy values must be plain integers or floats")
        try:
            weight = float(value)
            packed = struct.pack(">d", weight)
        except (OverflowError, struct.error) as error:
            raise ValueError("policy values must be representable as binary64") from error
        if not math.isfinite(weight):
            raise ValueError("policy values must be finite")
        weights.append(weight)
        encoded.extend(packed)
    return weights, hashlib.sha256(encoded).hexdigest()


def _validated_legal_indices(legal_indices: object) -> set[int]:
    if not isinstance(legal_indices, (SequenceABC, SetABC)):
        raise ValueError("legal_indices must be a sequence or set")

    validated: set[int] = set()
    for index in legal_indices:
        if type(index) is not int or not 0 <= index < 362:
            raise ValueError("legal indices must be plain integers from 0 through 361")
        if index in validated:
            raise ValueError("legal indices must not contain duplicates")
        validated.add(index)
    return validated


def sample_human_policy(
    policy: list[int | float], legal_indices: Sequence[int] | set[int], seed: int, reservation_id: str, ply: int
) -> SamplingAudit:
    weights, policy_sha256 = _validated_policy(policy)
    legal = _validated_legal_indices(legal_indices)
    u = derive_uniform(seed, reservation_id, ply)
    candidates = [(index, weights[index]) for index in range(362) if index in legal and weights[index] > 0.0]
    candidate_weights = [weight for _index, weight in candidates]
    try:
        positive_total = math.fsum(candidate_weights)
        bounds = [math.fsum(candidate_weights[:end]) for end in range(len(candidate_weights) + 1)]
    except (OverflowError, ValueError) as error:
        raise ValueError("positive policy mass must be finite") from error
    if not math.isfinite(positive_total) or positive_total <= 0.0:
        raise ValueError("legal policy must have positive finite mass")

    target = u * Fraction.from_float(positive_total)
    for position, (index, _weight) in enumerate(candidates):
        if Fraction.from_float(bounds[position + 1]) > target:
            return SamplingAudit(
                algorithm=SAMPLING_ALGORITHM,
                u=u,
                index=index,
                move="pass" if index == 361 else (index % 19, 18 - index // 19),
                policy_sha256=policy_sha256,
                positive_total=positive_total,
                interval_low=bounds[position],
                interval_high=bounds[position + 1],
            )
    raise ValueError("no candidate interval contains the sampled target")


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
