"""Pure protocol for the frozen Golaxy 9D HumanSL alignment experiment."""

from dataclasses import dataclass
from typing import Mapping, Optional, Union

PROTOCOL_VERSION = "golaxy-9d-humansl-alignment-v1"
CANDIDATES = ("rank_9d@1s", "rank_9d@4", "rank_9d@8", "rank_9d@16", "rank_9d@32")
START_PLAYER = "rank_9d@8"
GOLAXY_API_LEVEL = 3000
LOCAL_BASE_URL = "http://127.0.0.1:8000"
DAILY_CHARGED_CAP = 20


@dataclass(frozen=True)
class Batch:
    player: str
    target_conclusive: int


@dataclass(frozen=True)
class ProductDecision:
    measured_tier: str
    product_tier: Optional[str]
    basis: str
    reason: str


@dataclass(frozen=True)
class ProtocolStop:
    reason: str


@dataclass(frozen=True)
class EvidenceBatch:
    """Cumulative evidence at one ordered protocol milestone."""

    player: str
    target_conclusive: int
    wins: int
    losses: int


@dataclass(frozen=True)
class Evidence:
    batches: tuple[EvidenceBatch, ...] = ()


def validate_player_spec(player: object) -> str:
    if not isinstance(player, str) or player not in CANDIDATES:
        raise ValueError(f"invalid alignment candidate: {player!r}")
    return player


ProtocolAction = Union[Batch, ProductDecision, ProtocolStop]


def _direct_decision(player: str) -> ProductDecision:
    return ProductDecision(player, player, "direct_10_game_evidence", "lowest_qualified_tier")


def _totals_for(totals: Mapping[str, EvidenceBatch], player: str) -> Optional[EvidenceBatch]:
    return totals.get(player)


def _request_or_resolve(player: str, totals: Mapping[str, EvidenceBatch]) -> ProtocolAction:
    previous = _totals_for(totals, player)
    if previous is None:
        return Batch(player, 5)
    if previous.wins + previous.losses == 5:
        return Batch(player, 10)
    return _after_ten(player, totals, probe_lower=False)


def _qualified(totals: Mapping[str, EvidenceBatch]) -> list[str]:
    return [
        player
        for player in CANDIDATES
        if (record := totals.get(player)) is not None and record.wins + record.losses == 10 and record.wins >= 5
    ]


def _after_ten(last_player: str, totals: Mapping[str, EvidenceBatch], *, probe_lower: bool = True) -> ProtocolAction:
    qualified = _qualified(totals)
    if qualified:
        measured = qualified[0]
        measured_record = totals[measured]
        measured_index = CANDIDATES.index(measured)
        if measured_record.wins == 5:
            if measured_index == len(CANDIDATES) - 1:
                return ProductDecision(measured, None, "monotonic_safety_inference", "aligned_no_in_grid_safety_tier")
            safety = CANDIDATES[measured_index + 1]
            safety_record = totals.get(safety)
            if safety_record is None or safety_record.wins + safety_record.losses < 10:
                return Batch(safety, 10)
            if safety_record.wins < 5:
                return ProtocolStop("inconclusive_non_monotonic")
            return ProductDecision(measured, safety, "monotonic_safety_inference", "aligned_tier_safety_margin")

        if not probe_lower:
            return _direct_decision(measured)
        if measured_index == 0:
            return _direct_decision(measured)
        lower = CANDIDATES[measured_index - 1]
        lower_record = totals.get(lower)
        if lower_record is not None and lower_record.wins + lower_record.losses == 10:
            return _direct_decision(measured)
        return Batch(lower, 10 if lower_record is not None else 5)

    last_index = CANDIDATES.index(last_player)
    if last_index == len(CANDIDATES) - 1:
        return ProtocolStop("grid_exhausted")
    return _request_or_resolve(CANDIDATES[last_index + 1], totals)


def _after_five(record: EvidenceBatch, totals: Mapping[str, EvidenceBatch]) -> ProtocolAction:
    index = CANDIDATES.index(record.player)
    if index == 0:
        if record.wins <= 1:
            return _request_or_resolve(CANDIDATES[1], totals)
        return Batch(record.player, 10)
    if index == len(CANDIDATES) - 1:
        if record.wins <= 3:
            return Batch(record.player, 10)
        return _request_or_resolve(CANDIDATES[index - 1], totals)
    if record.wins <= 1:
        return _request_or_resolve(CANDIDATES[index + 1], totals)
    if record.wins <= 3:
        return Batch(record.player, 10)
    return _request_or_resolve(CANDIDATES[index - 1], totals)


def _after_completed(record: EvidenceBatch, totals: Mapping[str, EvidenceBatch]) -> ProtocolAction:
    if record.target_conclusive == 5:
        return _after_five(record, totals)
    return _after_ten(record.player, totals)


def _unreachable(message: str) -> ValueError:
    return ValueError(f"unreachable evidence: {message}")


def _validate_record(record: object) -> EvidenceBatch:
    if not isinstance(record, EvidenceBatch):
        raise _unreachable("batch record has the wrong type")
    try:
        validate_player_spec(record.player)
    except ValueError as exc:
        raise _unreachable(str(exc)) from exc
    if record.target_conclusive not in (5, 10):
        raise _unreachable("milestone must be 5 or 10")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (record.wins, record.losses)
    ):
        raise _unreachable("wins and losses must be non-negative integers")
    if record.wins + record.losses > record.target_conclusive:
        raise _unreachable("evidence exceeds its milestone")
    return record


def next_batch(evidence: object) -> ProtocolAction:
    """Return the unique next protocol action after strictly replaying evidence."""

    if type(evidence) is dict and not evidence:
        evidence = Evidence()
    elif isinstance(evidence, Mapping):
        raise ValueError("evidence must be an Evidence instance")
    if not isinstance(evidence, Evidence):
        raise ValueError("evidence must be an Evidence instance")
    if not isinstance(evidence.batches, tuple):
        raise ValueError("Evidence.batches must be an immutable tuple")

    expected: ProtocolAction = Batch(START_PLAYER, 5)
    totals: dict[str, EvidenceBatch] = {}
    for position, raw_record in enumerate(evidence.batches):
        record = _validate_record(raw_record)
        if not isinstance(expected, Batch):
            raise _unreachable("history continues after a terminal action")
        if (record.player, record.target_conclusive) != (expected.player, expected.target_conclusive):
            raise _unreachable(
                f"expected {expected.player} to milestone {expected.target_conclusive}, got "
                f"{record.player} to {record.target_conclusive}"
            )

        previous = totals.get(record.player)
        if previous is not None:
            if record.wins < previous.wins or record.losses < previous.losses:
                raise _unreachable("cumulative results went backwards")
            if record.wins + record.losses < previous.wins + previous.losses:
                raise _unreachable("cumulative total went backwards")
        totals[record.player] = record

        conclusive = record.wins + record.losses
        if conclusive == 0:
            raise _unreachable("a batch record must contain at least one conclusive result")
        if conclusive < record.target_conclusive:
            if position != len(evidence.batches) - 1:
                raise _unreachable("only the final batch may be partial")
            return expected
        expected = _after_completed(record, totals)
    return expected
