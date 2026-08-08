"""Pure scheduler for the fixed Golaxy HumanSL sampling campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import tempfile
import threading
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as SetABC
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Mapping, Sequence


SAMPLING_ALGORITHM = "golaxy-humansl-weighted-v1"
LEDGER_PROTOCOL = "golaxy-humansl-sampling-v1"
ADJUDICATION_PROTOCOL = "golaxy-sampling-adjudication-v1"
ADJUDICATION = {
    "protocol": ADJUDICATION_PROTOCOL,
    "board_size": 19,
    "rules": "Chinese",
    "komi": 7.5,
    "move_cap": 400,
    "referee_visits": 200,
    "stability_visits": 800,
    "stability_delta": 1.0,
}
VALID_SLOTS_PER_STAGE = 10
FIRST_HUMANSL_COLOR = "B"
COOLDOWN_SECONDS = 5.0
PARENT_PATH = Path(__file__).resolve().parent / "results/golaxy_alignment_campaign_20260730/campaign_v2.jsonl"
PARENT_SHA256 = "4eff5434cd864215a35171d635e4268d06f31f45ca6be27e82e4e0a1105f64d5"
_OUTPUT_LOCK_STATE = threading.local()
_SAMPLING_DOMAIN = SAMPLING_ALGORITHM.encode("ascii") + b"\0"
_UNIFORM_DENOMINATOR = 2**64

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
    u: str
    u_raw: int
    u_denominator: int
    index: int
    move: tuple[int, int] | str
    policy_sha256: str
    positive_total: float
    interval_low: float
    interval_high: float


@dataclass(frozen=True)
class LoadedSamplingCampaign:
    path: Path
    header: Mapping[str, object]
    records: tuple[Mapping[str, object], ...]
    action: GameRequest | CampaignDecision
    stopped: bool
    unknown_charged_attempts: tuple[int, ...]


def _json_line(row: Mapping[str, object]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _same_json_value(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _validate_move_audits(
    move_audits: object,
    *,
    seed: int,
    reservation_id: str,
    color: str,
) -> list[dict[str, object]]:
    fields = {
        "ply",
        "position_sha256",
        "algorithm",
        "u",
        "u_raw",
        "u_denominator",
        "index",
        "move",
        "policy_sha256",
        "positive_total",
        "interval_low",
        "interval_high",
        "final_move",
    }
    if type(move_audits) is not list:
        raise ValueError("move audits must be a list")
    validated: list[dict[str, object]] = []
    previous_ply = -1
    for audit in move_audits:
        if type(audit) is not dict or set(audit) != fields:
            raise ValueError("move audit has invalid or extra fields")
        ply = audit.get("ply")
        u_raw = audit.get("u_raw")
        denominator = audit.get("u_denominator")
        index = audit.get("index")
        positive_total = audit.get("positive_total")
        interval_low = audit.get("interval_low")
        interval_high = audit.get("interval_high")
        move = audit.get("move")
        final_move = audit.get("final_move")
        if type(ply) is not int or ply <= previous_ply:
            raise ValueError("move audit plies must be strictly increasing nonnegative integers")
        previous_ply = ply
        expected_parity = 0 if color == "B" else 1
        if ply % 2 != expected_parity:
            raise ValueError("move audit ply does not match the reserved HumanSL color")
        if (
            type(audit.get("position_sha256")) is not str
            or len(audit["position_sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in audit["position_sha256"])
            or type(audit.get("policy_sha256")) is not str
            or len(audit["policy_sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in audit["policy_sha256"])
        ):
            raise ValueError("move audit SHA-256 fields must be lowercase hex")
        if audit.get("algorithm") != SAMPLING_ALGORITHM:
            raise ValueError("move audit has the wrong sampling algorithm")
        if (
            type(u_raw) is not int
            or not 0 <= u_raw < _UNIFORM_DENOMINATOR
            or type(denominator) is not int
            or denominator != _UNIFORM_DENOMINATOR
            or audit.get("u") != f"{u_raw}/{denominator}"
        ):
            raise ValueError("move audit has an invalid exact random value")
        expected_u_raw = int(derive_uniform(seed, reservation_id, ply) * _UNIFORM_DENOMINATOR)
        if u_raw != expected_u_raw:
            raise ValueError("move audit random value does not match seed, reservation, and ply")
        if type(index) is not int or not 0 <= index <= 361:
            raise ValueError("move audit policy index is invalid")
        if index == 361:
            if move != "pass" or final_move != "pass":
                raise ValueError("move audit pass mapping is invalid")
        else:
            expected_move = [index % 19, 18 - index // 19]
            if move not in (expected_move, tuple(expected_move)) or type(final_move) is not int or final_move != index:
                raise ValueError("move audit board mapping is invalid")
        if any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in (positive_total, interval_low, interval_high)
        ):
            raise ValueError("move audit interval values must be finite")
        if not (positive_total > 0 and 0 <= interval_low < interval_high <= positive_total):
            raise ValueError("move audit interval is invalid")
        target = Fraction(u_raw, denominator) * Fraction.from_float(float(positive_total))
        if not Fraction.from_float(float(interval_low)) <= target < Fraction.from_float(float(interval_high)):
            raise ValueError("move audit random target is outside the selected interval")
        try:
            frozen = json.loads(json.dumps(audit, sort_keys=True, separators=(",", ":"), allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("move audit is not strict JSON") from exc
        validated.append(frozen)
    return validated


def _validate_campaign_id(campaign_id: object) -> str:
    if type(campaign_id) is not str or not campaign_id or campaign_id != campaign_id.strip():
        raise ValueError("campaign_id must be a nonempty plain string without whitespace padding")
    return campaign_id


def _validate_seed(seed: object) -> int:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be a plain uint64 integer")
    return seed


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_parent() -> Mapping[str, object]:
    parent_path = Path(PARENT_PATH).resolve()
    try:
        parent_bytes = parent_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read parent campaign {parent_path}: {exc}") from exc
    if hashlib.sha256(parent_bytes).hexdigest() != PARENT_SHA256:
        raise ValueError(f"parent SHA-256 mismatch for {parent_path}")
    try:
        import golaxy_alignment_campaign as alignment_campaign

        with tempfile.TemporaryDirectory(prefix="golaxy-sampling-parent-") as snapshot_directory:
            snapshot_path = Path(snapshot_directory) / parent_path.name
            snapshot_path.write_bytes(parent_bytes)
            parent = alignment_campaign.campaign_summary(snapshot_path)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid parent campaign {parent_path}: {exc}") from exc
    if parent.header.get("protocol") != "golaxy-alignment-campaign-v2":
        raise ValueError("parent campaign must use golaxy-alignment-campaign-v2")
    if (
        parent.stopped
        or not isinstance(parent.action, alignment_campaign.CampaignDecision)
        or parent.action.status != "completed"
    ):
        raise ValueError("parent campaign must be completed and not stopped")
    identity = parent.header.get("identity_snapshot")
    if not isinstance(identity, dict):
        raise ValueError("parent campaign lacks a valid identity_snapshot")
    return identity


def _read_rows(path: Path) -> list[dict[str, object]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read sampling ledger {path}: {exc}") from exc
    if not payload or not payload.endswith(b"\n"):
        raise ValueError("sampling ledger is empty or truncated")
    if b"\r" in payload:
        raise ValueError("sampling ledger is not canonical LF-delimited JSONL")
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("sampling ledger is not valid UTF-8") from exc
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on sampling ledger line {line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"sampling ledger line {line_number} must be a JSON object")
        try:
            canonical = _json_line(row).removesuffix("\n")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sampling ledger line {line_number} is not canonical JSON") from exc
        if line != canonical:
            raise ValueError(f"sampling ledger line {line_number} is not canonical JSON")
        rows.append(row)
    return rows


def _append_row(path: Path, row: Mapping[str, object]) -> None:
    try:
        line = _json_line(row)
    except (TypeError, ValueError) as exc:
        raise ValueError("sampling ledger row is not JSON serializable") from exc
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def load_campaign(path: str | Path, allow_stopped_for_summary: bool = False) -> LoadedSamplingCampaign:
    path = Path(path).resolve()
    rows = _read_rows(path)
    header, records = rows[0], rows[1:]
    expected_header_fields = {
        "type",
        "sequence",
        "protocol",
        "campaign_id",
        "sampler",
        "adjudication",
        "stages",
        "valid_slots_per_stage",
        "first_humansl_color",
        "cooldown_seconds",
        "seed",
        "parent_path",
        "parent_sha256",
        "identity_snapshot",
    }
    if set(header) != expected_header_fields:
        raise ValueError("invalid sampling campaign header fields")
    if (
        header.get("type") != "campaign_header"
        or type(header.get("sequence")) is not int
        or header.get("sequence") != 0
        or header.get("protocol") != LEDGER_PROTOCOL
        or header.get("sampler") != SAMPLING_ALGORITHM
        or not _same_json_value(header.get("adjudication"), ADJUDICATION)
        or not _same_json_value(
            header.get("stages"),
            [{"stage": stage, "player": player, "golaxy_api_level": level} for stage, player, level in STAGES],
        )
        or type(header.get("valid_slots_per_stage")) is not int
        or header.get("valid_slots_per_stage") != VALID_SLOTS_PER_STAGE
        or header.get("first_humansl_color") != FIRST_HUMANSL_COLOR
        or type(header.get("cooldown_seconds")) is not float
        or header.get("cooldown_seconds") != COOLDOWN_SECONDS
        or header.get("parent_sha256") != PARENT_SHA256
    ):
        raise ValueError("invalid frozen sampling campaign header")
    _validate_campaign_id(header.get("campaign_id"))
    _validate_seed(header.get("seed"))
    if type(header.get("parent_path")) is not str or not header["parent_path"]:
        raise ValueError("invalid parent_path in sampling campaign header")
    if not isinstance(header.get("identity_snapshot"), dict):
        raise ValueError("invalid identity_snapshot in sampling campaign header")
    if header["parent_path"] != str(Path(PARENT_PATH).resolve()):
        raise ValueError("sampling campaign header has invalid frozen parent_path")
    if not _same_json_value(header["identity_snapshot"], _read_parent()):
        raise ValueError("sampling campaign identity_snapshot does not match the frozen parent")

    evidence: list[Mapping[str, object]] = []
    reservations: dict[int, Mapping[str, object]] = {}
    completed_attempts: set[int] = set()
    origins: set[str] = set()
    open_attempt: int | None = None
    stopped = False
    request_fields = ("stage", "player", "golaxy_api_level", "slot", "color")
    reservation_fields = {"type", "sequence", "attempt_id", *request_fields}
    result_fields = reservation_fields | {"origin_id", "outcome", "conclusive", "move_audits"}
    stop_fields = {"type", "sequence", "attempt_id", "reason", "move_audits"}
    for expected_sequence, row in enumerate(records, 1):
        if type(row.get("sequence")) is not int or row["sequence"] != expected_sequence:
            raise ValueError(f"sampling ledger sequence is not continuous at line {expected_sequence + 1}")
        if stopped:
            raise ValueError(f"sampling ledger row occurs after stopped at line {expected_sequence + 1}")
        row_type = row.get("type")
        if row_type == "reservation":
            if set(row) != reservation_fields:
                raise ValueError("reservation has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id != len(reservations) + 1 or attempt_id in reservations:
                raise ValueError("reservation attempt_id order must be continuous and unique")
            if open_attempt is not None:
                raise ValueError("reservation overlaps an open reservation")
            expected = next_action(evidence)
            if not isinstance(expected, GameRequest) or any(
                not _same_json_value(row.get(key), getattr(expected, key)) for key in request_fields
            ):
                raise ValueError("reservation does not match the unique next action")
            reservations[attempt_id] = row
            open_attempt = attempt_id
        elif row_type == "result":
            if set(row) != result_fields:
                raise ValueError("result has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            if type(attempt_id) is not int or attempt_id != open_attempt or attempt_id in completed_attempts:
                raise ValueError("result has no unique open reservation")
            reservation = reservations[attempt_id]
            if any(not _same_json_value(row.get(key), reservation.get(key)) for key in request_fields):
                raise ValueError("result does not match its reservation")
            outcome = row.get("outcome")
            conclusive = row.get("conclusive")
            if outcome not in {"win", "loss", "inconclusive"} or type(conclusive) is not bool:
                raise ValueError("invalid result outcome or conclusive flag")
            if (outcome == "inconclusive") == conclusive:
                raise ValueError("result outcome and conclusive flag are inconsistent")
            origin_id = row.get("origin_id")
            expected_origin = f"{header['campaign_id']}:{attempt_id}"
            if type(origin_id) is not str or not origin_id or origin_id != expected_origin or origin_id in origins:
                raise ValueError("result has invalid or duplicate origin_id")
            origins.add(origin_id)
            _validate_move_audits(
                row["move_audits"],
                seed=header["seed"],
                reservation_id=expected_origin,
                color=reservation["color"],
            )
            evidence.append(row)
            completed_attempts.add(attempt_id)
            open_attempt = None
        elif row_type == "stopped":
            if set(row) != stop_fields:
                raise ValueError("stopped row has invalid or extra fields")
            attempt_id = row.get("attempt_id")
            reason = row.get("reason")
            if (
                type(attempt_id) is not int
                or attempt_id != open_attempt
                or attempt_id in completed_attempts
                or type(reason) is not str
                or not reason.strip()
            ):
                raise ValueError("stopped row must close the unique open reservation with a reason")
            reservation = reservations[attempt_id]
            _validate_move_audits(
                row["move_audits"],
                seed=header["seed"],
                reservation_id=f"{header['campaign_id']}:{attempt_id}",
                color=reservation["color"],
            )
            completed_attempts.add(attempt_id)
            open_attempt = None
            stopped = True
        elif row_type == "campaign_header":
            raise ValueError("campaign header must occur exactly once and first")
        else:
            raise ValueError(f"unknown sampling campaign record type: {row_type!r}")

    unmatched = () if open_attempt is None else (open_attempt,)
    if stopped:
        action: GameRequest | CampaignDecision = CampaignDecision("stopped", _completed_stages(evidence))
    else:
        action = next_action(evidence)
    loaded = LoadedSamplingCampaign(path, header, tuple(records), action, stopped, unmatched)
    if not allow_stopped_for_summary:
        if stopped:
            raise ValueError("sampling campaign ledger is stopped and has no next action")
        if unmatched:
            raise ValueError(f"sampling campaign ledger has open reservation(s) with unknown charge: {unmatched}")
    return loaded


def initialize_campaign(path: str | Path, campaign_id: str, seed: int) -> LoadedSamplingCampaign:
    path = Path(path)
    campaign_id = _validate_campaign_id(campaign_id)
    seed = _validate_seed(seed)
    identity = _read_parent()
    header = {
        "type": "campaign_header",
        "sequence": 0,
        "protocol": LEDGER_PROTOCOL,
        "campaign_id": campaign_id,
        "sampler": SAMPLING_ALGORITHM,
        "adjudication": dict(ADJUDICATION),
        "stages": [{"stage": stage, "player": player, "golaxy_api_level": level} for stage, player, level in STAGES],
        "valid_slots_per_stage": VALID_SLOTS_PER_STAGE,
        "first_humansl_color": FIRST_HUMANSL_COLOR,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "seed": seed,
        "parent_path": str(Path(PARENT_PATH).resolve()),
        "parent_sha256": PARENT_SHA256,
        "identity_snapshot": identity,
    }
    try:
        serialized = _json_line(header)
    except (TypeError, ValueError) as exc:
        raise ValueError("sampling campaign header is not JSON serializable") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise ValueError(f"sampling campaign ledger already exists: {path}") from exc
    return load_campaign(path)


@contextmanager
def _mutation_lock(path: str | Path):
    canonical = Path(path).resolve()
    active = getattr(_OUTPUT_LOCK_STATE, "paths", set())
    if canonical in active:
        yield
    else:
        with output_lock(canonical):
            yield


def _append_reservation_unlocked(path: str | Path, attempt_id: int, request: GameRequest) -> None:
    path = Path(path)
    loaded = load_campaign(path)
    if type(attempt_id) is not int or attempt_id != 1 + sum(row.get("type") == "reservation" for row in loaded.records):
        raise ValueError("attempt_id must be the next positive plain integer")
    request_fields = ("stage", "player", "golaxy_api_level", "slot", "color")
    if (
        not isinstance(request, GameRequest)
        or not isinstance(loaded.action, GameRequest)
        or any(not _same_json_value(getattr(request, key), getattr(loaded.action, key)) for key in request_fields)
    ):
        raise ValueError("reservation request must match the unique next action")
    row = {
        "type": "reservation",
        "sequence": len(loaded.records) + 1,
        "attempt_id": attempt_id,
        "stage": request.stage,
        "player": request.player,
        "golaxy_api_level": request.golaxy_api_level,
        "slot": request.slot,
        "color": request.color,
    }
    _append_row(path, row)
    campaign_summary(path)


def _append_result_unlocked(
    path: str | Path,
    attempt_id: int,
    outcome: str,
    conclusive: bool | None = None,
    *,
    move_audits: object,
) -> None:
    path = Path(path)
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive plain integer")
    loaded = campaign_summary(path)
    if loaded.stopped:
        raise ValueError("sampling campaign ledger is stopped")
    if loaded.unknown_charged_attempts != (attempt_id,):
        raise ValueError("attempt_id does not identify the unique open reservation")
    if outcome not in {"win", "loss", "inconclusive"}:
        raise ValueError("invalid result outcome")
    if conclusive is None:
        conclusive = outcome != "inconclusive"
    if type(conclusive) is not bool or (outcome == "inconclusive") == conclusive:
        raise ValueError("result outcome and conclusive flag are inconsistent")
    reservation = next(
        row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
    )
    origin_id = f"{loaded.header['campaign_id']}:{attempt_id}"
    if any(row.get("origin_id") == origin_id for row in loaded.records):
        raise ValueError(f"origin_id {origin_id!r} already exists")
    row = {
        "type": "result",
        "sequence": len(loaded.records) + 1,
        "attempt_id": attempt_id,
        "origin_id": origin_id,
        "stage": reservation["stage"],
        "player": reservation["player"],
        "golaxy_api_level": reservation["golaxy_api_level"],
        "slot": reservation["slot"],
        "color": reservation["color"],
        "outcome": outcome,
        "conclusive": conclusive,
    }
    row["move_audits"] = _validate_move_audits(
        move_audits,
        seed=loaded.header["seed"],
        reservation_id=origin_id,
        color=reservation["color"],
    )
    _append_row(path, row)
    load_campaign(path)


def _append_stop_unlocked(
    path: str | Path,
    reason: str,
    attempt_id: int | None = None,
    *,
    move_audits: object,
) -> None:
    path = Path(path)
    loaded = campaign_summary(path)
    if loaded.stopped:
        raise ValueError("sampling campaign ledger is already stopped")
    if type(reason) is not str or not reason.strip():
        raise ValueError("stop reason must be a nonempty plain string")
    if len(loaded.unknown_charged_attempts) != 1:
        raise ValueError("append_stop requires exactly one open reservation")
    open_attempt = loaded.unknown_charged_attempts[0]
    if attempt_id is None:
        attempt_id = open_attempt
    if type(attempt_id) is not int or attempt_id != open_attempt:
        raise ValueError("attempt_id does not identify the unique open reservation")
    reservation = next(
        row for row in loaded.records if row.get("type") == "reservation" and row.get("attempt_id") == attempt_id
    )
    origin_id = f"{loaded.header['campaign_id']}:{attempt_id}"
    _append_row(
        path,
        {
            "type": "stopped",
            "sequence": len(loaded.records) + 1,
            "attempt_id": attempt_id,
            "reason": reason,
            "move_audits": _validate_move_audits(
                move_audits,
                seed=loaded.header["seed"],
                reservation_id=origin_id,
                color=reservation["color"],
            ),
        },
    )
    campaign_summary(path)


def append_reservation(path: str | Path, attempt_id: int, request: GameRequest) -> None:
    with _mutation_lock(path):
        _append_reservation_unlocked(path, attempt_id, request)


def append_result(
    path: str | Path,
    attempt_id: int,
    outcome: str,
    conclusive: bool | None = None,
    *,
    move_audits: object,
) -> None:
    with _mutation_lock(path):
        _append_result_unlocked(path, attempt_id, outcome, conclusive, move_audits=move_audits)


def append_stop(path: str | Path, reason: str, attempt_id: int | None = None, *, move_audits: object) -> None:
    with _mutation_lock(path):
        _append_stop_unlocked(path, reason, attempt_id, move_audits=move_audits)


def replay_campaign(path: str | Path) -> GameRequest | CampaignDecision:
    return load_campaign(path).action


def campaign_summary(path: str | Path) -> LoadedSamplingCampaign:
    return load_campaign(path, allow_stopped_for_summary=True)


@contextmanager
def output_lock(path: str | Path):
    if os.name == "nt":
        raise RuntimeError("sampling campaign output locking is unavailable on Windows; refusing concurrent writes")
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeError("sampling campaign output locking requires fcntl") from exc

    canonical = Path(path).resolve()
    active = getattr(_OUTPUT_LOCK_STATE, "paths", None)
    if active is None:
        active = set()
        _OUTPUT_LOCK_STATE.paths = active
    if canonical in active:
        raise RuntimeError(f"sampling campaign output is already locked by this writer: {canonical}")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    lock_path = canonical.with_name(canonical.name + ".lock")
    with lock_path.open("a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError(f"sampling campaign output is already locked by another writer: {canonical}") from exc
        active.add(canonical)
        try:
            yield
        finally:
            active.remove(canonical)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
    return Fraction(raw, _UNIFORM_DENOMINATOR)


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
    unscaled_raw = u * _UNIFORM_DENOMINATOR
    if unscaled_raw.denominator != 1:
        raise ValueError("uniform value does not have the expected denominator")
    u_raw = unscaled_raw.numerator
    for position, (index, _weight) in enumerate(candidates):
        if Fraction.from_float(bounds[position + 1]) > target:
            return SamplingAudit(
                algorithm=SAMPLING_ALGORITHM,
                u=f"{u_raw}/{_UNIFORM_DENOMINATOR}",
                u_raw=u_raw,
                u_denominator=_UNIFORM_DENOMINATOR,
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


def _color_for_slot(slot: int) -> str:
    if FIRST_HUMANSL_COLOR not in {"B", "W"}:
        raise ValueError("FIRST_HUMANSL_COLOR must be 'B' or 'W'")
    if slot % 2 == 0:
        return FIRST_HUMANSL_COLOR
    return "W" if FIRST_HUMANSL_COLOR == "B" else "B"


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
            if type(slot) is not int or not 0 <= slot < VALID_SLOTS_PER_STAGE:
                raise ValueError(
                    f"slot must be a plain integer from 0 through {VALID_SLOTS_PER_STAGE - 1}"
                )
            color = row.get("color")
            if color not in {"B", "W"}:
                raise ValueError("color must be 'B' or 'W'")
            expected_color = _color_for_slot(slot)
            if color != expected_color:
                raise ValueError(f"slot {slot} must use HumanSL color {expected_color}")

            outcome = row.get("outcome")
            if outcome not in {"win", "loss", "inconclusive"}:
                raise ValueError(f"unknown result outcome: {outcome!r}")
            if outcome in {"win", "loss"}:
                valid_by_stage[stage] += 1
                if valid_by_stage[stage] > VALID_SLOTS_PER_STAGE:
                    raise ValueError(
                        f"stage {stage!r} has more than {VALID_SLOTS_PER_STAGE} valid results"
                    )

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
    if summary.valid < VALID_SLOTS_PER_STAGE:
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
            if valid_in_stage == VALID_SLOTS_PER_STAGE:
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
        color=_color_for_slot(slot),
    )
