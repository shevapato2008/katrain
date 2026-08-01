"""Pure evidence importer and scheduler for the Golaxy b18 20-game extension."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MODEL = "b18"
MODEL_SHA256 = "9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d"
REFEREE_MODEL = "b28"
REFEREE_MODEL_SHA256 = "798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0"
GOLAXY_LEVEL = 36
GOLAXY_LEVEL_NAME = "星阵3星"
GOLAXY_API_LEVEL = 3300
CANDIDATE_VISITS = (32, 64)
TARGET_CONCLUSIVE = 20
PARENT_PATH = Path(__file__).resolve().parent / "results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl"
PARENT_SHA256 = "9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082"

_CARRY_LINES = (2, 3, 4, 5, 6, 17, 18, 19, 20, 21, 22, 23, 24, 25)
_CONCLUSIVE_OUTCOMES = frozenset(("our_win", "our_loss"))
_INCONCLUSIVE_OUTCOMES = frozenset(("inconclusive_score", "inconclusive_unsettled", "inconclusive_unstable"))
_ACCEPTED_OUTCOMES = _CONCLUSIVE_OUTCOMES | _INCONCLUSIVE_OUTCOMES
V6_PROTOCOL = "golaxy-b18-three-star-20game-extension-v6"
V7_PROTOCOL = "golaxy-b18-three-star-20game-extension-v7"
CONTINUATION_AUTHORIZATION = "explicit_user_continue"

GAME_CONTRACT = {
    "golaxy_level": GOLAXY_LEVEL,
    "golaxy_level_name": GOLAXY_LEVEL_NAME,
    "golaxy_api_level": GOLAXY_API_LEVEL,
    "player_model": MODEL,
    "player_model_sha256": MODEL_SHA256,
    "referee_model": REFEREE_MODEL,
    "referee_model_sha256": REFEREE_MODEL_SHA256,
    "candidate_visits": list(CANDIDATE_VISITS),
    "board_size": 19,
    "rules": "Chinese",
    "komi": 7.5,
    "handicap": 0,
    "wide_root_noise": 0.04,
    "score_perspective": "BLACK",
    "move_cap": 400,
    "referee_visits": 200,
    "stability_visits": 800,
    "stability_delta": 1.0,
    "execution": "strict_serial",
    "cooldown_seconds": 5,
    "target_valid": TARGET_CONCLUSIVE,
    "candidate_order": list(CANDIDATE_VISITS),
}


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


@dataclass(frozen=True)
class GameRequest:
    visits: int
    color: str


@dataclass(frozen=True)
class CandidateSummary:
    visits: int
    conclusive: int
    wins: int
    losses: int
    inconclusive: int
    black: int
    white: int


@dataclass(frozen=True)
class CampaignDecision:
    status: str
    candidates: tuple[CandidateSummary, ...]


@dataclass(frozen=True)
class LoadedCampaign:
    path: Path
    header: Mapping[str, object]
    records: tuple[Mapping[str, object], ...]
    evidence: tuple[Mapping[str, object], ...]
    action: GameRequest | CampaignDecision
    stopped: bool
    open_attempt: int | None


def _validate_source_row(row: Mapping[str, object], line_number: int) -> None:
    expected_fields = {
        "type": "carry_result",
        "level_name": GOLAXY_LEVEL_NAME,
    }
    for field, expected in expected_fields.items():
        if row.get(field) != expected:
            raise ValueError(f"parent line {line_number} has wrong {field}")
    for field, expected in (("level", GOLAXY_LEVEL), ("api_level", GOLAXY_API_LEVEL)):
        if type(row.get(field)) is not int or row[field] != expected:
            raise ValueError(f"parent line {line_number} has wrong {field}")
    if "rung" in row and (type(row["rung"]) is not int or row["rung"] != GOLAXY_LEVEL):
        raise ValueError(f"parent line {line_number} has wrong rung")
    if type(row.get("visits")) is not int or row["visits"] not in CANDIDATE_VISITS:
        raise ValueError(f"parent line {line_number} has wrong visits")
    if row.get("color") not in {"B", "W"}:
        raise ValueError(f"parent line {line_number} has wrong color")

    outcome = row.get("outcome")
    if not isinstance(outcome, Mapping):
        raise ValueError(f"parent line {line_number} has invalid outcome")
    result = outcome.get("result")
    if result not in _CONCLUSIVE_OUTCOMES:
        raise ValueError(f"parent line {line_number} has invalid outcome")
    if outcome.get("conclusive") is not True:
        raise ValueError(f"parent line {line_number} has invalid conclusive status")
    if outcome.get("our_color") != row["color"]:
        raise ValueError(f"parent line {line_number} has inconsistent outcome color")
    if outcome.get("our_win") is not (result == "our_win"):
        raise ValueError(f"parent line {line_number} has inconsistent outcome result")


def load_frozen_carries(parent_path: Path, expected_sha256: str) -> tuple[dict, ...]:
    """Load only the approved b18 rows after verifying the direct parent's bytes."""

    parent_path = Path(parent_path)
    raw = parent_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(f"parent SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")

    try:
        rows = [json.loads(line, parse_constant=_reject_json_constant) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("parent is not valid UTF-8 JSONL") from exc
    if not rows or not isinstance(rows[0], Mapping) or rows[0].get("model") != MODEL:
        raise ValueError("parent header has wrong model")
    if len(rows) < _CARRY_LINES[-1]:
        raise ValueError("parent is missing approved source rows")

    selected = [(line_number, rows[line_number - 1]) for line_number in _CARRY_LINES]
    fingerprints: set[str] = set()
    for line_number, row in selected:
        if not isinstance(row, Mapping):
            raise ValueError(f"parent line {line_number} is not an object")
        fingerprint = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if fingerprint in fingerprints:
            raise ValueError(f"duplicate selected source row at parent line {line_number}")
        fingerprints.add(fingerprint)
        _validate_source_row(row, line_number)

    for visits, expected_count, expected_colors, expected_outcomes in (
        (32, 4, {"B": 2, "W": 2}, {"our_win": 1, "our_loss": 3}),
        (64, 10, {"B": 5, "W": 5}, {"our_win": 7, "our_loss": 3}),
    ):
        candidate = [(line_number, row) for line_number, row in selected if row["visits"] == visits]
        colors = {color: sum(row["color"] == color for _line, row in candidate) for color in ("B", "W")}
        outcomes = {
            outcome: sum(row["outcome"]["result"] == outcome for _line, row in candidate)
            for outcome in _CONCLUSIVE_OUTCOMES
        }
        if len(candidate) != expected_count or outcomes != expected_outcomes:
            raise ValueError(f"wrong inherited counts for visits {visits}")
        if colors != expected_colors or [row["color"] for _line, row in candidate] != [
            "B" if index % 2 == 0 else "W" for index in range(expected_count)
        ]:
            raise ValueError(f"wrong inherited color balance for visits {visits}")

    carries = []
    for line_number, row in selected:
        source_outcome = dict(row["outcome"])
        result = source_outcome["result"]
        carries.append(
            {
                "type": "carry_result",
                "visits": row["visits"],
                "color": row["color"],
                "outcome": result,
                "result": result,
                "conclusive": True,
                "origin_result_id": f"legacy:{actual_sha256}:{line_number}",
                "direct_parent_sha256": actual_sha256,
                "direct_parent_line": line_number,
                "source_outcome": source_outcome,
            }
        )
    return tuple(carries)


def _same_json_value(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _validate_carry_prefix(evidence: Sequence[Mapping[str, object]]) -> None:
    if not any(isinstance(row, Mapping) and row.get("type") == "carry_result" for row in evidence):
        return

    frozen = load_frozen_carries(PARENT_PATH, PARENT_SHA256)
    if len(evidence) < len(frozen):
        raise ValueError("evidence does not contain the exact frozen carry prefix")
    for index, expected in enumerate(frozen):
        if not isinstance(evidence[index], Mapping) or not _same_json_value(evidence[index], expected):
            raise ValueError(f"evidence row {index + 1} does not match the exact frozen carry prefix")
    seen_live = False
    for index, row in enumerate(evidence[len(frozen) :], len(frozen) + 1):
        if isinstance(row, Mapping) and row.get("type") == "carry_result":
            detail = "carry_result after live evidence" if seen_live else "extra carry_result"
            raise ValueError(f"invalid frozen carry prefix: {detail} at row {index}")
        seen_live = True


def _validate_evidence(evidence: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    _validate_carry_prefix(evidence)
    validated: list[Mapping[str, object]] = []
    conclusive_counts = {visits: 0 for visits in CANDIDATE_VISITS}
    seen_result_ids: set[str] = set()
    for index, row in enumerate(evidence, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"evidence row {index} is not an object")
        visits = row.get("visits")
        if type(visits) is not int or visits not in CANDIDATE_VISITS:
            raise ValueError(f"evidence row {index} has invalid visits")
        result = row.get("result", row.get("outcome"))
        if result not in _ACCEPTED_OUTCOMES or (
            "result" in row and "outcome" in row and row["result"] != row["outcome"]
        ):
            raise ValueError(f"evidence row {index} has invalid outcome")
        conclusive = row.get("conclusive")
        if conclusive is not (result in _CONCLUSIVE_OUTCOMES):
            raise ValueError(f"evidence row {index} has inconsistent conclusive status")
        if conclusive and conclusive_counts[visits] >= TARGET_CONCLUSIVE:
            raise ValueError(f"candidate {visits} has more than {TARGET_CONCLUSIVE} conclusive results")

        if row.get("type") != "carry_result":
            active_visits = next(
                (candidate for candidate in CANDIDATE_VISITS if conclusive_counts[candidate] < TARGET_CONCLUSIVE),
                None,
            )
            if visits != active_visits:
                raise ValueError(f"evidence row {index} does not match active candidate {active_visits}")

        expected_color = "B" if conclusive_counts[visits] % 2 == 0 else "W"
        if row.get("color") != expected_color:
            raise ValueError(f"evidence row {index} has invalid color sequence")
        if conclusive:
            conclusive_counts[visits] += 1
            if conclusive_counts[visits] > TARGET_CONCLUSIVE:
                raise ValueError(f"candidate {visits} has more than {TARGET_CONCLUSIVE} conclusive results")

        result_id = row.get("origin_result_id")
        if result_id is not None:
            if not isinstance(result_id, str) or not result_id:
                raise ValueError(f"evidence row {index} has invalid origin_result_id")
            if result_id in seen_result_ids:
                raise ValueError(f"duplicate evidence origin_result_id: {result_id}")
            seen_result_ids.add(result_id)
        validated.append(row)
    return tuple(validated)


def summarize_candidate(evidence: Sequence[Mapping[str, object]], visits: int) -> CandidateSummary:
    if type(visits) is not int or visits not in CANDIDATE_VISITS:
        raise ValueError(f"invalid candidate visits: {visits}")
    validated = _validate_evidence(evidence)
    rows = [row for row in validated if row["visits"] == visits]
    conclusive_rows = [row for row in rows if row["conclusive"]]
    outcomes = [row.get("result", row.get("outcome")) for row in rows]
    return CandidateSummary(
        visits=visits,
        conclusive=len(conclusive_rows),
        wins=outcomes.count("our_win"),
        losses=outcomes.count("our_loss"),
        inconclusive=len(rows) - len(conclusive_rows),
        black=sum(row["color"] == "B" for row in conclusive_rows),
        white=sum(row["color"] == "W" for row in conclusive_rows),
    )


def next_action(evidence: Sequence[Mapping[str, object]]) -> GameRequest | CampaignDecision:
    validated = _validate_evidence(evidence)
    summaries = tuple(summarize_candidate(validated, visits) for visits in CANDIDATE_VISITS)
    for summary in summaries:
        if summary.conclusive < TARGET_CONCLUSIVE:
            return GameRequest(summary.visits, "B" if summary.conclusive % 2 == 0 else "W")
    return CampaignDecision("completed", summaries)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_line(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"


def _json_copy(value: object, name: str) -> object:
    try:
        return json.loads(_json_line(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    serialized = "".join(_json_line(row) for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise ValueError(f"campaign ledger already exists: {path}") from exc


def _append_row(path: Path, row: Mapping[str, object]) -> None:
    line = _json_line(row)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _validate_campaign_id(value: object) -> str:
    if type(value) is not str or not value.strip() or ":" in value:
        raise ValueError("campaign_id must be a nonempty plain string without ':'")
    return value


def _read_rows(path: Path) -> list[dict[str, object]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        lines = text.splitlines()
        if not lines:
            raise ValueError("campaign ledger is empty")
        rows = [json.loads(line, parse_constant=_reject_json_constant) for line in lines]
    except ValueError as exc:
        if "non-standard JSON constant" in str(exc):
            raise ValueError(str(exc)) from exc
        raise ValueError("campaign ledger is not valid UTF-8 JSONL") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("campaign ledger is not valid UTF-8 JSONL") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("campaign ledger rows must be JSON objects")
    return rows


def _base_header(campaign_id: str, health: object, protocol: str) -> dict[str, object]:
    if not isinstance(health, Mapping):
        raise ValueError("complete_health_response must be a JSON-serializable mapping")
    return {
        "type": "campaign_header",
        "protocol": protocol,
        "campaign_id": _validate_campaign_id(campaign_id),
        "created_at": _now(),
        "source_v5_path": str(PARENT_PATH.resolve()),
        "source_v5_sha256": PARENT_SHA256,
        "target_valid": TARGET_CONCLUSIVE,
        "candidate_order": list(CANDIDATE_VISITS),
        "game_contract": dict(GAME_CONTRACT),
        "complete_health_response": _json_copy(health, "complete_health_response"),
    }


def _validate_base_header(header: Mapping[str, object], protocol: str) -> None:
    common = {
        "type",
        "protocol",
        "campaign_id",
        "created_at",
        "source_v5_path",
        "source_v5_sha256",
        "target_valid",
        "candidate_order",
        "game_contract",
        "complete_health_response",
    }
    extra = set() if protocol == V6_PROTOCOL else {"authorization", "parent_path", "parent_sha256"}
    if protocol == V7_PROTOCOL and "excluded_uncertain_reservation" in header:
        extra.add("excluded_uncertain_reservation")
    if set(header) != common | extra:
        raise ValueError("campaign header has invalid or extra fields")
    if (
        header.get("type") != "campaign_header"
        or header.get("protocol") != protocol
        or type(header.get("created_at")) is not str
        or not header["created_at"]
        or header.get("source_v5_path") != str(PARENT_PATH.resolve())
        or header.get("source_v5_sha256") != PARENT_SHA256
        or type(header.get("target_valid")) is not int
        or header["target_valid"] != TARGET_CONCLUSIVE
        or not _same_json_value(header.get("candidate_order"), list(CANDIDATE_VISITS))
        or not _same_json_value(header.get("game_contract"), GAME_CONTRACT)
        or not isinstance(header.get("complete_health_response"), dict)
    ):
        raise ValueError("campaign header does not match the frozen contract")
    _validate_campaign_id(header.get("campaign_id"))


_CARRY_FIELDS = {
    "type",
    "visits",
    "color",
    "outcome",
    "result",
    "conclusive",
    "origin_result_id",
    "direct_parent_sha256",
    "direct_parent_line",
    "source_outcome",
}
_V7_CARRY_REQUIRED = _CARRY_FIELDS - {"source_outcome"}
_RESERVATION_FIELDS = {"type", "attempt_id", "request_id", "visits", "color", "target_valid", "created_at"}
_OUTCOME_FIELDS = {"our_color", "result", "our_win", "num_moves", "black_score", "conclusive", "end_reason"}
_RESULT_FIELDS = (_RESERVATION_FIELDS | _OUTCOME_FIELDS | {"origin_result_id", "elapsed_seconds", "completed_at"}) - {
    "created_at"
}
_STOP_FIELDS = {"type", "attempt_id", "request_id", "reason", "stopped_at"}


def _normalized_evidence(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "type": row["type"],
        "visits": row["visits"],
        "color": row["color"],
        "outcome": row["result"],
        "result": row["result"],
        "conclusive": row["conclusive"],
        "origin_result_id": row["origin_result_id"],
    }


def _carry_from_parent(row: Mapping[str, object], parent_sha: str, line_number: int) -> dict[str, object]:
    carried = _normalized_evidence(row)
    carried["type"] = "carry_result"
    carried["direct_parent_sha256"] = parent_sha
    carried["direct_parent_line"] = line_number
    if "source_outcome" in row:
        carried["source_outcome"] = row["source_outcome"]
    return carried


def _scheduler_evidence(evidence: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    """Remove continuation-hop provenance before applying Task 1 scheduling rules."""

    frozen = {row["origin_result_id"]: row for row in load_frozen_carries(PARENT_PATH, PARENT_SHA256)}
    normalized: list[Mapping[str, object]] = []
    for row in evidence:
        origin = row.get("origin_result_id")
        if origin in frozen:
            normalized.append(frozen[str(origin)])
        elif row.get("type") == "carry_result":
            live = _normalized_evidence(row)
            live["type"] = "result"
            normalized.append(live)
        else:
            normalized.append(row)
    return tuple(normalized)


def _validate_outcome_values(row: Mapping[str, object], color: str) -> None:
    result = row.get("result")
    if result not in _ACCEPTED_OUTCOMES or row.get("our_color") != color:
        raise ValueError("invalid GameOutcome result or color")
    conclusive = row.get("conclusive")
    our_win = row.get("our_win")
    if type(conclusive) is not bool or type(our_win) is not bool:
        raise ValueError("GameOutcome flags must be booleans")
    if conclusive is not (result in _CONCLUSIVE_OUTCOMES):
        raise ValueError("GameOutcome conclusive flag is incoherent")
    if our_win is not (result == "our_win"):
        raise ValueError("GameOutcome our_win flag is incoherent")
    moves = row.get("num_moves")
    if type(moves) is not int or not 0 <= moves <= GAME_CONTRACT["move_cap"]:
        raise ValueError("GameOutcome num_moves is invalid")
    score = row.get("black_score")
    if score is not None and (type(score) not in (int, float) or not (-float("inf") < score < float("inf"))):
        raise ValueError("GameOutcome black_score is invalid")
    if result == "inconclusive_score" and score is not None:
        raise ValueError("inconclusive_score requires black_score=None")
    if result in {"inconclusive_unsettled", "inconclusive_unstable"} and score is None:
        raise ValueError(f"{result} requires a finite numeric black_score")
    if type(row.get("end_reason")) is not str or not row["end_reason"]:
        raise ValueError("GameOutcome end_reason is invalid")


def _expected_v7_carries(header: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    parent_path = Path(str(header["parent_path"])).resolve()
    parent_sha = str(header["parent_sha256"])
    if _sha256(parent_path) != parent_sha:
        raise ValueError("v7 parent SHA256 mismatch")
    parent = load_campaign(parent_path, summary=True)
    ancestor_ids = {str(parent.header["campaign_id"])}
    ancestor = parent
    while ancestor.header["protocol"] == V7_PROTOCOL:
        ancestor = load_campaign(str(ancestor.header["parent_path"]), summary=True)
        ancestor_ids.add(str(ancestor.header["campaign_id"]))
    if header.get("campaign_id") in ancestor_ids:
        raise ValueError("v7 campaign_id duplicates an ancestor campaign_id")
    if not parent.stopped and parent.open_attempt is None:
        raise ValueError("v7 parent must be stopped or have one unmatched reservation")
    if not _same_json_value(header["complete_health_response"], parent.header["complete_health_response"]):
        raise ValueError("v7 complete health response does not equal its parent")
    expected_uncertain: dict[str, object] | None = None
    if parent.open_attempt is not None:
        line_number, reservation = next(
            (number, row)
            for number, row in enumerate(parent.records, 2)
            if row.get("type") == "reservation" and row.get("attempt_id") == parent.open_attempt
        )
        expected_uncertain = {"direct_parent_line": line_number, "reservation": dict(reservation)}
    actual_uncertain = header.get("excluded_uncertain_reservation")
    if expected_uncertain is None:
        if "excluded_uncertain_reservation" in header:
            raise ValueError("closed stopped parent must not have an uncertain reservation descriptor")
    elif not _same_json_value(actual_uncertain, expected_uncertain):
        raise ValueError("excluded uncertain reservation does not exactly match the parent")
    return tuple(
        _carry_from_parent(row, parent_sha, line_number)
        for line_number, row in enumerate(parent.records, 2)
        if row.get("type") in {"carry_result", "result"}
    )


def load_campaign(path: str | Path, *, summary: bool = False) -> LoadedCampaign:
    path = Path(path).resolve()
    rows = _read_rows(path)
    header, records = rows[0], rows[1:]
    protocol = header.get("protocol")
    if protocol not in {V6_PROTOCOL, V7_PROTOCOL}:
        raise ValueError("unsupported campaign protocol")
    _validate_base_header(header, protocol)
    if any(row.get("type") == "campaign_header" for row in records):
        raise ValueError("campaign header must occur exactly once and first")

    if protocol == V6_PROTOCOL:
        expected_carries = load_frozen_carries(PARENT_PATH, PARENT_SHA256)
    else:
        if (
            header.get("authorization") != CONTINUATION_AUTHORIZATION
            or type(header.get("parent_path")) is not str
            or type(header.get("parent_sha256")) is not str
        ):
            raise ValueError("invalid v7 continuation identity")
        expected_carries = _expected_v7_carries(header)
    if len(records) < len(expected_carries):
        raise ValueError("campaign is missing its complete carry prefix")
    for index, expected in enumerate(expected_carries):
        if not _same_json_value(records[index], expected):
            raise ValueError(f"carry provenance mismatch at line {index + 2}")

    evidence: list[Mapping[str, object]] = list(records[: len(expected_carries)])
    origins = {str(row["origin_result_id"]) for row in evidence}
    reservations: dict[int, Mapping[str, object]] = {}
    completed: set[int] = set()
    open_attempt: int | None = None
    stopped = False
    for line_number, row in enumerate(records[len(expected_carries) :], len(expected_carries) + 2):
        if stopped:
            raise ValueError(f"row occurs after stopped at line {line_number}")
        row_type = row.get("type")
        if row_type == "carry_result":
            raise ValueError("carry_result may occur only in the complete prefix")
        if row_type == "reservation":
            if set(row) != _RESERVATION_FIELDS:
                raise ValueError("reservation has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id <= 0 or attempt_id in reservations:
                raise ValueError("reservation attempt_id must be a unique positive plain integer")
            if attempt_id != len(reservations) + 1 or open_attempt is not None:
                raise ValueError("reservation order is invalid or overlaps an open reservation")
            action = next_action(_scheduler_evidence(evidence))
            if not isinstance(action, GameRequest) or any(
                row.get(field) != expected
                for field, expected in (
                    ("visits", action.visits),
                    ("color", action.color),
                    ("target_valid", TARGET_CONCLUSIVE),
                )
            ):
                raise ValueError("reservation does not match the unique next action")
            if (
                row.get("request_id") != f"{header['campaign_id']}:{attempt_id}"
                or type(row.get("created_at")) is not str
            ):
                raise ValueError("reservation identity is invalid")
            reservations[attempt_id] = row
            open_attempt = attempt_id
        elif row_type == "result":
            if set(row) != _RESULT_FIELDS:
                raise ValueError("result has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id != open_attempt or attempt_id in completed:
                raise ValueError("result does not close the unique open reservation")
            reservation = reservations[attempt_id]
            for field in ("request_id", "visits", "color", "target_valid"):
                if row.get(field) != reservation.get(field):
                    raise ValueError("result does not match its reservation")
            origin = row.get("origin_result_id")
            if origin != f"{header['campaign_id']}:{attempt_id}" or origin in origins:
                raise ValueError("result origin_result_id is invalid or duplicate")
            _validate_outcome_values(row, str(reservation["color"]))
            elapsed = row.get("elapsed_seconds")
            if (
                type(elapsed) not in (int, float)
                or not math.isfinite(elapsed)
                or elapsed < 0
                or type(row.get("completed_at")) is not str
            ):
                raise ValueError("result timing is invalid")
            origins.add(str(origin))
            evidence.append(row)
            completed.add(attempt_id)
            open_attempt = None
        elif row_type == "stopped":
            if set(row) != _STOP_FIELDS:
                raise ValueError("stopped has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id != open_attempt or attempt_id in completed:
                raise ValueError("stopped does not close the unique open reservation")
            if row.get("request_id") != reservations[attempt_id]["request_id"]:
                raise ValueError("stopped request_id does not match its reservation")
            if (
                type(row.get("reason")) is not str
                or not row["reason"].strip()
                or type(row.get("stopped_at")) is not str
            ):
                raise ValueError("stopped reason or timestamp is invalid")
            completed.add(attempt_id)
            open_attempt = None
            stopped = True
        else:
            raise ValueError(f"unknown campaign record type: {row_type!r}")

    scheduler_evidence = _scheduler_evidence(evidence)
    action = (
        CampaignDecision("stopped", tuple(summarize_candidate(scheduler_evidence, v) for v in CANDIDATE_VISITS))
        if stopped
        else next_action(scheduler_evidence)
    )
    loaded = LoadedCampaign(path, header, tuple(records), tuple(evidence), action, stopped, open_attempt)
    if not summary and stopped:
        raise ValueError("campaign ledger is stopped")
    if not summary and open_attempt is not None:
        raise ValueError("campaign ledger has an open reservation with uncertain execution")
    return loaded


def initialize_v6_campaign(
    path: str | Path, campaign_id: str, complete_health_response: Mapping[str, object]
) -> LoadedCampaign:
    path = Path(path)
    header = _base_header(campaign_id, complete_health_response, V6_PROTOCOL)
    carries = load_frozen_carries(PARENT_PATH, PARENT_SHA256)
    _write_new(path, [header, *carries])
    return load_campaign(path)


def initialize_v7_continuation(
    path: str | Path,
    campaign_id: str,
    complete_health_response: Mapping[str, object],
    *,
    parent_path: str | Path,
    parent_sha256: str,
    authorization: str,
) -> LoadedCampaign:
    path = Path(path)
    parent_path = Path(parent_path).resolve()
    if path.resolve() == parent_path:
        raise ValueError("v7 output must be distinct from its parent")
    if path.exists():
        raise ValueError(f"campaign ledger already exists: {path}")
    if authorization != CONTINUATION_AUTHORIZATION:
        raise ValueError("v7 continuation requires explicit_user_continue authorization")
    if type(parent_sha256) is not str or _sha256(parent_path) != parent_sha256:
        raise ValueError("parent SHA256 mismatch")
    parent = load_campaign(parent_path, summary=True)
    if parent.header["protocol"] not in {V6_PROTOCOL, V7_PROTOCOL}:
        raise ValueError("v7 parent has unsupported protocol")
    if not parent.stopped and parent.open_attempt is None:
        raise ValueError("v7 parent must be stopped or have one unmatched reservation")
    frozen_health = _json_copy(complete_health_response, "complete_health_response")
    if not _same_json_value(frozen_health, parent.header["complete_health_response"]):
        raise ValueError("complete health response drifted from parent")
    ancestor_ids = {str(parent.header["campaign_id"])}
    ancestor = parent
    while ancestor.header["protocol"] == V7_PROTOCOL:
        ancestor = load_campaign(str(ancestor.header["parent_path"]), summary=True)
        ancestor_ids.add(str(ancestor.header["campaign_id"]))
    if campaign_id in ancestor_ids:
        raise ValueError("campaign_id duplicates an ancestor")
    header = _base_header(campaign_id, frozen_health, V7_PROTOCOL)
    header.update(
        authorization=CONTINUATION_AUTHORIZATION,
        parent_path=str(parent_path),
        parent_sha256=parent_sha256,
    )
    if parent.open_attempt is not None:
        line_number, reservation = next(
            (number, row)
            for number, row in enumerate(parent.records, 2)
            if row.get("type") == "reservation" and row.get("attempt_id") == parent.open_attempt
        )
        header["excluded_uncertain_reservation"] = {
            "direct_parent_line": line_number,
            "reservation": dict(reservation),
        }
    carries = [
        _carry_from_parent(row, parent_sha256, line_number)
        for line_number, row in enumerate(parent.records, 2)
        if row.get("type") in {"carry_result", "result"}
    ]
    _write_new(path, [header, *carries])
    return load_campaign(path)


def append_reservation(path: str | Path, attempt_id: int, request: GameRequest) -> None:
    path = Path(path)
    loaded = load_campaign(path)
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive plain integer")
    if attempt_id != 1 + sum(row.get("type") == "reservation" for row in loaded.records):
        raise ValueError("attempt_id must be the next unique reservation id")
    if not isinstance(request, GameRequest) or request != loaded.action:
        raise ValueError("reservation must equal the unique next_action")
    _append_row(
        path,
        {
            "type": "reservation",
            "attempt_id": attempt_id,
            "request_id": f"{loaded.header['campaign_id']}:{attempt_id}",
            "visits": request.visits,
            "color": request.color,
            "target_valid": TARGET_CONCLUSIVE,
            "created_at": _now(),
        },
    )
    load_campaign(path, summary=True)


def _outcome_mapping(outcome: object) -> dict[str, object]:
    if isinstance(outcome, Mapping):
        source = outcome
        return {field: source.get(field) for field in _OUTCOME_FIELDS}
    try:
        return {field: getattr(outcome, field) for field in _OUTCOME_FIELDS}
    except AttributeError as exc:
        raise ValueError("outcome must expose the complete serialized GameOutcome fields") from exc


def append_result(path: str | Path, attempt_id: int, outcome: object, elapsed_seconds: float) -> None:
    path = Path(path)
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive plain integer")
    loaded = load_campaign(path, summary=True)
    if loaded.stopped:
        raise ValueError("campaign ledger is stopped")
    if loaded.open_attempt != attempt_id:
        raise ValueError("attempt_id does not identify the unique open reservation")
    if type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be a finite nonnegative plain int or float")
    reservation = next(
        row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
    )
    fields = _outcome_mapping(outcome)
    _validate_outcome_values(fields, str(reservation["color"]))
    row = {
        "type": "result",
        "attempt_id": attempt_id,
        "request_id": reservation["request_id"],
        "visits": reservation["visits"],
        "color": reservation["color"],
        "target_valid": reservation["target_valid"],
        "origin_result_id": f"{loaded.header['campaign_id']}:{attempt_id}",
        **fields,
        "elapsed_seconds": elapsed_seconds,
        "completed_at": _now(),
    }
    _append_row(path, row)
    load_campaign(path, summary=True)


def append_stop(path: str | Path, attempt_id: int | str, reason: str | None = None) -> None:
    path = Path(path)
    loaded = load_campaign(path, summary=True)
    if loaded.stopped:
        raise ValueError("campaign ledger is already stopped")
    if isinstance(attempt_id, str) and reason is None:
        reason, attempt_id = attempt_id, loaded.open_attempt
    if type(attempt_id) is not int or attempt_id != loaded.open_attempt:
        raise ValueError("attempt_id does not identify the unique open reservation")
    if type(reason) is not str or not reason.strip():
        raise ValueError("stop reason must be a nonempty plain string")
    reservation = next(
        row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
    )
    _append_row(
        path,
        {
            "type": "stopped",
            "attempt_id": attempt_id,
            "request_id": reservation["request_id"],
            "reason": reason,
            "stopped_at": _now(),
        },
    )
    load_campaign(path, summary=True)


def campaign_summary(path: str | Path) -> dict[str, object]:
    loaded = load_campaign(path, summary=True)
    candidates: dict[str, object] = {}
    for visits in CANDIDATE_VISITS:
        rows = [row for row in loaded.evidence if row["visits"] == visits]
        inherited = [row for row in rows if str(row["origin_result_id"]).startswith("legacy:")]
        new = [row for row in rows if row not in inherited]

        def counts(items: Sequence[Mapping[str, object]]) -> dict[str, int]:
            return {
                "wins": sum(row["result"] == "our_win" for row in items),
                "losses": sum(row["result"] == "our_loss" for row in items),
                "black": sum(row["conclusive"] and row["color"] == "B" for row in items),
                "white": sum(row["conclusive"] and row["color"] == "W" for row in items),
            }

        candidates[str(visits)] = {"inherited": counts(inherited), "new": counts(new), "combined": counts(rows)}
    attempts: dict[str, Mapping[str, object]] = {}
    cursor: LoadedCampaign | None = loaded
    seen_paths: set[Path] = set()
    while cursor is not None and cursor.path not in seen_paths:
        seen_paths.add(cursor.path)
        for row in cursor.records:
            if row.get("type") == "reservation":
                attempts[str(row["request_id"])] = row
        descriptor = cursor.header.get("excluded_uncertain_reservation")
        if isinstance(descriptor, Mapping):
            reservation = descriptor.get("reservation")
            if isinstance(reservation, Mapping):
                attempts[str(reservation.get("request_id"))] = reservation
        if cursor.header["protocol"] == V7_PROTOCOL:
            cursor = load_campaign(str(cursor.header["parent_path"]), summary=True)
        else:
            cursor = None
    inconclusive = {
        outcome: sum(row["result"] == outcome for row in loaded.evidence) for outcome in sorted(_INCONCLUSIVE_OUTCOMES)
    }
    action: object
    if isinstance(loaded.action, GameRequest):
        action = {"visits": loaded.action.visits, "color": loaded.action.color}
    else:
        action = loaded.action.status
    return {
        "path": str(loaded.path),
        "sha256": _sha256(loaded.path),
        "protocol": loaded.header["protocol"],
        "stopped": loaded.stopped,
        "open_attempt": loaded.open_attempt,
        "completion_status": loaded.action.status if isinstance(loaded.action, CampaignDecision) else "in_progress",
        "next_action": action,
        "candidates": candidates,
        "total_attempts": len(attempts),
        "inconclusive": inconclusive,
        "warning": "Descriptive extension evidence only; not a rerun of the original ladder.",
    }
