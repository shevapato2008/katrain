"""Pure scheduling and append-only recovery for a single-writer Golaxy campaign.

Callers must serialize all mutations to a ledger. Cross-process file locking is intentionally
left to the live-runner layer; the append API guarantees validation, flush, and fsync durability.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
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
LEDGER_PROTOCOL = "golaxy-alignment-campaign-v1"
SEED_SHA256 = "c3a782609b47f812df26c1aacf871c72c2661581687773b2059eac642b4efbc2"
SEED_PATH = (
    Path(__file__).resolve().parent / "results/golaxy_humansl_rank7_rank9_refinement_20260728/refinement_v1.jsonl"
)
SEED_LINES = (2, 3, 4, 5, 12, 14, 16)


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


@dataclass(frozen=True)
class LoadedCampaign:
    path: Path
    header: Mapping[str, object]
    records: tuple[Mapping[str, object], ...]
    evidence: tuple[Mapping[str, object], ...]
    evidence_lines: tuple[int, ...]
    stopped: bool
    unknown_charged_attempts: tuple[int, ...]
    ancestor_campaign_ids: tuple[str, ...]
    action: GameRequest | CampaignDecision


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_line(row: Mapping[str, object]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _validate_campaign_id(campaign_id: object) -> str:
    if type(campaign_id) is not str or not campaign_id or campaign_id != campaign_id.strip() or ":" in campaign_id:
        raise ValueError("campaign_id must be a nonempty plain string without whitespace padding or ':'")
    return campaign_id


def _fsync_directory(directory: Path) -> None:
    """Durably persist a new directory entry, failing closed on unsupported POSIX filesystems."""
    if os.name == "nt":  # Windows does not support opening directories for fsync.
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(directory, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _append_row(path: Path, row: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_json_line(row))
        handle.flush()
        os.fsync(handle.fileno())


def _read_rows(path: Path) -> list[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read campaign ledger {path}: {exc}") from exc
    if not lines:
        raise ValueError("campaign ledger is empty; header required")
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on ledger line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"ledger line {line_number} must be a JSON object")
        rows.append(row)
    return rows


def _validate_header(header: Mapping[str, object], records: Sequence[Mapping[str, object]]) -> None:
    required = {"type", "protocol", "campaign_id", "identity_snapshot"}
    optional = {"parent_path", "parent_sha256"}
    if not required <= set(header) or set(header) - required - optional:
        raise ValueError("invalid campaign header fields")
    if header.get("type") != "campaign_header" or header.get("protocol") != LEDGER_PROTOCOL:
        raise ValueError("invalid campaign header protocol")
    _validate_campaign_id(header.get("campaign_id"))
    if not isinstance(header.get("identity_snapshot"), dict):
        raise ValueError("invalid campaign header identity_snapshot")
    has_parent_path = "parent_path" in header
    has_parent_sha = "parent_sha256" in header
    if has_parent_path != has_parent_sha:
        raise ValueError("campaign header must contain both parent_path and parent_sha256")
    if has_parent_path and (
        not isinstance(header["parent_path"], str)
        or not header["parent_path"]
        or not isinstance(header["parent_sha256"], str)
        or len(header["parent_sha256"]) != 64
    ):
        raise ValueError("invalid campaign header parent reference")
    if any(row.get("type") == "campaign_header" for row in records):
        raise ValueError("campaign header must occur exactly once and first")


def _validate_evidence_row(row: Mapping[str, object], line_number: int) -> None:
    if not isinstance(row.get("origin_result_id"), str) or not row["origin_result_id"]:
        raise ValueError(f"evidence line {line_number} lacks origin_result_id")
    if row.get("stage") not in STAGE_ORDER:
        raise ValueError(f"evidence line {line_number} has invalid stage")
    if not isinstance(row.get("player"), str) or row.get("color") not in {"B", "W"}:
        raise ValueError(f"evidence line {line_number} has invalid player or color")
    if row.get("outcome") not in {"win", "loss", "inconclusive"} or not isinstance(row.get("conclusive"), bool):
        raise ValueError(f"evidence line {line_number} has invalid outcome")
    if (row["outcome"] == "inconclusive") == row["conclusive"]:
        raise ValueError(f"evidence line {line_number} has inconsistent conclusive flag")


def _same_evidence(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    keys = ("origin_result_id", "stage", "player", "color", "outcome", "conclusive")
    return all(left.get(key) == right.get(key) for key in keys)


def _load_campaign(path: Path, allow_stopped_for_summary: bool, ancestors: frozenset[Path]) -> LoadedCampaign:
    path = path.resolve()
    if path in ancestors:
        raise ValueError("campaign parent chain contains a cycle")
    rows = _read_rows(path)
    header, records = rows[0], rows[1:]
    _validate_header(header, records)

    parent: LoadedCampaign | None = None
    parent_sha: str | None = None
    if "parent_path" in header:
        parent_path = Path(str(header["parent_path"]))
        if not parent_path.is_absolute():
            parent_path = path.parent / parent_path
        parent_sha = _sha256(parent_path)
        if parent_sha != header["parent_sha256"]:
            raise ValueError(f"parent SHA-256 mismatch for {parent_path}")
        parent = _load_campaign(parent_path, True, ancestors | {path})
        if not parent.stopped:
            raise ValueError("parent campaign must be stopped before evidence can be imported")

    evidence: list[Mapping[str, object]] = []
    evidence_lines: list[int] = []
    origins: set[str] = set()
    reservations: dict[int, Mapping[str, object]] = {}
    completed_attempts: set[int] = set()
    seed_by_line = {row["direct_parent_line"]: row for row in _seed_evidence()} if parent is None else {}
    stopped = False
    stop_types: set[str] = set()
    for line_number, row in enumerate(records, 2):
        row_type = row.get("type")
        if stopped and not (row_type == "campaign_stopped" and stop_types == {"stopped"}):
            raise ValueError(f"ledger row on line {line_number} occurs after stop")
        if row_type in {"result", "carry_result"}:
            _validate_evidence_row(row, line_number)
            origin = str(row["origin_result_id"])
            if origin in origins:
                raise ValueError(f"duplicate origin_result_id {origin}")
            origins.add(origin)
            evidence.append(row)
            evidence_lines.append(line_number)
        if row_type == "reservation":
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id <= 0 or attempt_id in reservations:
                raise ValueError(f"invalid or duplicate reservation on line {line_number}")
            if row.get("stage") not in STAGE_ORDER or row.get("color") not in {"B", "W"}:
                raise ValueError(f"invalid reservation on line {line_number}")
            reservations[attempt_id] = row
        elif row_type == "result":
            attempt_id = row.get("attempt_id")
            reservation = reservations.get(attempt_id) if type(attempt_id) is int else None
            if reservation is None or attempt_id in completed_attempts:
                raise ValueError(f"result on line {line_number} has no unique reservation")
            expected_origin = f"{header['campaign_id']}:{attempt_id}"
            if row["origin_result_id"] != expected_origin:
                raise ValueError(f"result on line {line_number} has invalid immutable origin_result_id")
            for key in ("stage", "player", "color"):
                if row.get(key) != reservation.get(key):
                    raise ValueError(f"result on line {line_number} does not match reservation")
            completed_attempts.add(attempt_id)
        elif row_type == "carry_result":
            if parent is None:
                if row.get("direct_parent_sha256") != SEED_SHA256 or row.get("direct_parent_line") not in SEED_LINES:
                    raise ValueError(f"invalid legacy seed carry on line {line_number}")
                expected_origin = f"legacy:{SEED_SHA256}:{row['direct_parent_line']}"
                expected_seed = seed_by_line[row["direct_parent_line"]]
                if row["origin_result_id"] != expected_origin or not _same_evidence(row, expected_seed):
                    raise ValueError(f"legacy seed carry on line {line_number} does not match its SHA-validated source")
            else:
                direct_line = row.get("direct_parent_line")
                if row.get("direct_parent_sha256") != parent_sha or type(direct_line) is not int:
                    raise ValueError(f"invalid direct parent reference on line {line_number}")
                try:
                    parent_index = parent.evidence_lines.index(direct_line)
                except ValueError as exc:
                    raise ValueError(f"direct parent line {direct_line} is not completed evidence") from exc
                if not _same_evidence(row, parent.evidence[parent_index]):
                    raise ValueError(f"carry on line {line_number} does not match direct parent evidence")
        elif row_type in {"campaign_stopped", "stopped"}:
            if row_type in stop_types:
                raise ValueError(f"duplicate {row_type} row on line {line_number}")
            allowed_fields = {"type", "reason"} | ({"attempt_id"} if row_type == "stopped" else set())
            if not {"type", "reason"} <= set(row) or set(row) - allowed_fields:
                raise ValueError(f"stop row on line {line_number} has invalid fields")
            reason = row.get("reason")
            if type(reason) is not str or not reason.strip():
                raise ValueError(f"stop row on line {line_number} requires a nonempty plain-string reason")
            attempt_id = row.get("attempt_id")
            if attempt_id is not None:
                if (
                    row_type != "stopped"
                    or type(attempt_id) is not int
                    or attempt_id not in reservations
                    or attempt_id in completed_attempts
                ):
                    raise ValueError(f"stopped row on line {line_number} has no unique reservation")
                completed_attempts.add(attempt_id)
            stopped = True
            stop_types.add(str(row_type))
        elif row_type in {"stage_started", "stage_completed"}:
            if set(row) != {"type", "stage"} or type(row.get("stage")) is not str or row["stage"] not in STAGE_ORDER:
                raise ValueError(f"stage control on line {line_number} has invalid stage")
            continue
        elif row_type != "reservation":
            raise ValueError(f"unknown ledger row type {row_type!r} on line {line_number}")

    carry_origins = {str(row["origin_result_id"]) for row in evidence if row.get("type") == "carry_result"}
    expected_carry_origins = (
        {str(row["origin_result_id"]) for row in seed_by_line.values()}
        if parent is None
        else {str(row["origin_result_id"]) for row in parent.evidence}
    )
    if carry_origins != expected_carry_origins:
        raise ValueError("ledger does not contain the complete required carry evidence set")
    expected_direct_lines = list(SEED_LINES if parent is None else parent.evidence_lines)
    carry_rows = [row for row in records if row.get("type") == "carry_result"]
    if (
        any(row.get("type") != "carry_result" for row in records[: len(carry_rows)])
        or [row.get("direct_parent_line") for row in carry_rows] != expected_direct_lines
    ):
        raise ValueError("carry evidence must be a complete initial prefix in direct-parent order")

    for stage in STAGE_ORDER:
        indices = (None,) if stage in {"seven_d", "one_star_b18_1"} else range(len(GRID))
        for candidate_index in indices:
            summarize_candidate(evidence, stage, candidate_index)

    replayed: list[Mapping[str, object]] = []
    open_attempt: int | None = None
    request_keys = ("stage", "player", "color", "target_valid", "phase")
    for line_number, row in enumerate(records, 2):
        if row.get("type") == "carry_result":
            replayed.append(row)
        elif row.get("type") == "reservation":
            if open_attempt is not None:
                raise ValueError(f"reservation on line {line_number} overlaps unmatched reservation {open_attempt}")
            expected = next_action(replayed)
            if not isinstance(expected, GameRequest) or any(
                row.get(key) != getattr(expected, key) for key in request_keys
            ):
                raise ValueError(f"reservation on line {line_number} does not match the next expected request")
            open_attempt = int(row["attempt_id"])
        elif row.get("type") == "result":
            if row.get("attempt_id") != open_attempt:
                raise ValueError(f"result on line {line_number} is not for the current reservation")
            replayed.append(row)
            open_attempt = None
        elif row.get("type") == "stopped" and row.get("attempt_id") is not None:
            if row.get("attempt_id") != open_attempt:
                raise ValueError(f"stopped row on line {line_number} is not for the current reservation")
            open_attempt = None

    unmatched = tuple(sorted(set(reservations) - completed_attempts))
    action = next_action(evidence)
    loaded = LoadedCampaign(
        path,
        header,
        tuple(records),
        tuple(evidence),
        tuple(evidence_lines),
        stopped,
        unmatched,
        (() if parent is None else (str(parent.header["campaign_id"]), *parent.ancestor_campaign_ids)),
        action,
    )
    if not allow_stopped_for_summary:
        if stopped:
            raise ValueError("campaign ledger is stopped and cannot be resumed")
        if unmatched:
            raise ValueError(f"campaign ledger has unmatched reservation(s): {unmatched}")
    return loaded


def load_campaign(path: str | Path, allow_stopped_for_summary: bool = False) -> LoadedCampaign:
    return _load_campaign(Path(path), allow_stopped_for_summary, frozenset())


def _seed_evidence() -> list[dict[str, object]]:
    if _sha256(SEED_PATH) != SEED_SHA256:
        raise ValueError(f"seed SHA-256 mismatch for {SEED_PATH}")
    source_rows = _read_rows(SEED_PATH)
    seeded: list[dict[str, object]] = []
    for line_number in SEED_LINES:
        source = source_rows[line_number - 1]
        if source.get("rank") != 7 or source.get("tier") != "1s" or source.get("outcome") not in {"win", "loss"}:
            raise ValueError(f"frozen seed line {line_number} is not a valid rank_7d@1s result")
        seeded.append(
            {
                "type": "carry_result",
                "stage": "seven_d",
                "player": "rank_7d@1s",
                "color": source["color"],
                "outcome": source["outcome"],
                "conclusive": True,
                "origin_result_id": f"legacy:{SEED_SHA256}:{line_number}",
                "direct_parent_sha256": SEED_SHA256,
                "direct_parent_line": line_number,
            }
        )
    return seeded


def initialize_campaign(
    path: str | Path,
    campaign_id: str,
    identity_snapshot: Mapping[str, object],
    parent_path: str | Path | None = None,
    parent_sha256: str | None = None,
) -> LoadedCampaign:
    path = Path(path)
    campaign_id = _validate_campaign_id(campaign_id)
    if (parent_path is None) != (parent_sha256 is None):
        raise ValueError("parent_path and exact parent SHA-256 are both required")
    try:
        frozen_identity = dict(identity_snapshot)
    except (TypeError, ValueError) as exc:
        raise ValueError("identity_snapshot must be a JSON-serializable mapping") from exc
    header: dict[str, object] = {
        "type": "campaign_header",
        "protocol": LEDGER_PROTOCOL,
        "campaign_id": campaign_id,
        "identity_snapshot": frozen_identity,
    }
    carries: list[dict[str, object]]
    if parent_path is None:
        carries = _seed_evidence()
    else:
        parent_path = Path(parent_path).resolve()
        actual_sha = _sha256(parent_path)
        if actual_sha != parent_sha256:
            raise ValueError(f"parent SHA-256 mismatch for {parent_path}")
        parent = load_campaign(parent_path, allow_stopped_for_summary=True)
        if not parent.stopped:
            raise ValueError("parent campaign must be stopped before evidence can be imported")
        if campaign_id in (parent.header["campaign_id"], *parent.ancestor_campaign_ids):
            raise ValueError(f"campaign_id {campaign_id!r} duplicates an ancestor campaign_id")
        header.update(parent_path=str(parent_path), parent_sha256=parent_sha256)
        carries = []
        for evidence, line_number in zip(parent.evidence, parent.evidence_lines):
            carries.append(
                {
                    "type": "carry_result",
                    "stage": evidence["stage"],
                    "player": evidence["player"],
                    "color": evidence["color"],
                    "outcome": evidence["outcome"],
                    "conclusive": evidence["conclusive"],
                    "origin_result_id": evidence["origin_result_id"],
                    "direct_parent_sha256": parent_sha256,
                    "direct_parent_line": line_number,
                }
            )
    try:
        serialized_ledger = _json_line(header) + "".join(_json_line(carry) for carry in carries)
    except (TypeError, ValueError) as exc:
        raise ValueError("campaign header and carries must be JSON serializable") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized_ledger)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise ValueError(f"campaign ledger already exists: {path}") from exc
    return load_campaign(path)


def append_reservation(path: str | Path, attempt_id: int, request: GameRequest) -> None:
    loaded = load_campaign(path)
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive plain integer")
    if any(row.get("attempt_id") == attempt_id for row in loaded.records if row.get("type") == "reservation"):
        raise ValueError(f"attempt_id {attempt_id} is already reserved")
    if not isinstance(request, GameRequest):
        raise ValueError("reservation request must be a GameRequest")
    if request != loaded.action:
        raise ValueError("reservation request does not match the next expected Task 1 request")
    _append_row(
        Path(path),
        {
            "type": "reservation",
            "attempt_id": attempt_id,
            "stage": request.stage,
            "player": request.player,
            "color": request.color,
            "target_valid": request.target_valid,
            "phase": request.phase,
        },
    )


def append_result(path: str | Path, attempt_id: int, outcome: str, conclusive: bool | None = None) -> None:
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive plain integer")
    loaded = load_campaign(path, allow_stopped_for_summary=True)
    if loaded.stopped:
        raise ValueError("cannot append a result after campaign stopped")
    reservations = [
        row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
    ]
    completed = [row for row in loaded.records if row.get("type") == "result" and row.get("attempt_id") == attempt_id]
    if len(reservations) != 1 or completed:
        raise ValueError(f"attempt_id {attempt_id} does not have one unmatched reservation")
    if outcome not in {"win", "loss", "inconclusive"}:
        raise ValueError("invalid result outcome")
    if conclusive is None:
        conclusive = outcome != "inconclusive"
    if type(conclusive) is not bool or (outcome == "inconclusive") == conclusive:
        raise ValueError("outcome and conclusive flag are inconsistent")
    reservation = reservations[0]
    origin_result_id = f"{loaded.header['campaign_id']}:{attempt_id}"
    if any(row.get("origin_result_id") == origin_result_id for row in loaded.evidence):
        raise ValueError(f"origin_result_id {origin_result_id} already exists in campaign evidence")
    _append_row(
        Path(path),
        {
            "type": "result",
            "attempt_id": attempt_id,
            "stage": reservation["stage"],
            "player": reservation["player"],
            "color": reservation["color"],
            "outcome": outcome,
            "conclusive": conclusive,
            "origin_result_id": origin_result_id,
        },
    )


def append_stop(
    path: str | Path,
    reason: str,
    event_type: str = "campaign_stopped",
    attempt_id: int | None = None,
) -> None:
    loaded = load_campaign(path, allow_stopped_for_summary=True)
    if loaded.stopped:
        has_campaign_stop = any(row.get("type") == "campaign_stopped" for row in loaded.records)
        if event_type != "campaign_stopped" or has_campaign_stop:
            raise ValueError("campaign ledger is already stopped")
    if event_type not in {"campaign_stopped", "stopped"}:
        raise ValueError("stop event type must be campaign_stopped or stopped")
    if type(reason) is not str or not reason.strip():
        raise ValueError("stop reason must be a nonempty plain string")
    if attempt_id is not None:
        if event_type != "stopped" or type(attempt_id) is not int:
            raise ValueError("only a stopped game may reference a plain integer attempt_id")
        reservations = [
            row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
        ]
        if len(reservations) != 1 or attempt_id not in loaded.unknown_charged_attempts:
            raise ValueError(f"attempt_id {attempt_id} does not have one unmatched reservation")
    row: dict[str, object] = {"type": event_type, "reason": reason}
    if attempt_id is not None:
        row["attempt_id"] = attempt_id
    _append_row(Path(path), row)


def append_stage_event(path: str | Path, event_type: str, stage: str) -> None:
    load_campaign(path)
    if (
        type(event_type) is not str
        or event_type not in {"stage_started", "stage_completed"}
        or type(stage) is not str
        or stage not in STAGE_ORDER
    ):
        raise ValueError("invalid stage event")
    _append_row(Path(path), {"type": event_type, "stage": stage})


def replay_campaign(path: str | Path) -> GameRequest | CampaignDecision:
    return load_campaign(path).action


def campaign_summary(path: str | Path) -> LoadedCampaign:
    return load_campaign(path, allow_stopped_for_summary=True)
