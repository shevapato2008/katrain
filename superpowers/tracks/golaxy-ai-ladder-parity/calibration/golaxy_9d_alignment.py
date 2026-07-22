"""Protocol and durable evidence ledger for the Golaxy 9D HumanSL alignment experiment."""

import fcntl
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, Optional, Union
from zoneinfo import ZoneInfo

PROTOCOL_VERSION = "golaxy-9d-humansl-alignment-v1"
CANDIDATES = ("rank_9d@1s", "rank_9d@4", "rank_9d@8", "rank_9d@16", "rank_9d@32")
START_PLAYER = "rank_9d@8"
GOLAXY_API_LEVEL = 3000
LOCAL_BASE_URL = "http://127.0.0.1:8000"
DAILY_CHARGED_CAP = 20
LEDGER_SCHEMA_VERSION = 1
SOURCE_REVISION = "bb37920ba859f21684cb2d2e1a845120d9c13676"


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


@dataclass(frozen=True)
class QuotaState:
    quota_id: str
    created_at: str
    operator_date: str
    charged_attempts: int


@dataclass(frozen=True)
class AttemptReservation:
    attempt_id: int
    candidate: str
    scheduled_color: str
    quota_id: str
    selection_fingerprint: str


_SESSION_TOKEN = object()


class _ExperimentSession:
    def __init__(self, path: Path, lock_file):
        self.path = path
        self._lock_file = lock_file
        self._token = _SESSION_TOKEN
        self._pid = os.getpid()
        self._thread_id = threading.get_ident()
        self._open = True


def _fsync_file(handle) -> None:
    os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _open_created_file(path: Path, mode: str):
    existed = path.exists()
    handle = path.open(mode, encoding="utf-8")
    if not existed:
        _fsync_file(handle)
        _fsync_directory(path.parent)
    return handle


@contextmanager
def experiment_session(session_path):
    """Hold the experiment-wide, crash-released OS lock for the caller's lifetime."""

    path = Path(session_path)
    if path.exists() and not path.is_dir():
        raise ValueError("session path must be a directory")
    if not path.exists():
        path.mkdir(parents=True)
        _fsync_directory(path.parent)
    lock_path = path / ".experiment.lock"
    lock_file = _open_created_file(lock_path, "a+")
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("experiment session lock is already held") from exc
        session = _ExperimentSession(path.resolve(), lock_file)
        try:
            yield session
        finally:
            session._open = False
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


def _require_session(session) -> _ExperimentSession:
    if (
        not isinstance(session, _ExperimentSession)
        or session._token is not _SESSION_TOKEN
        or not session._open
        or session._pid != os.getpid()
        or session._thread_id != threading.get_ident()
        or session._lock_file.closed
    ):
        raise ValueError("a live owned experiment session is required")
    return session


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    raise ValueError(f"malformed JSON record at {path.name}:{line_number}")
                record = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
                if type(record) is not dict:
                    raise ValueError(f"JSON record must be an object at {path.name}:{line_number}")
                records.append(record)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in {path.name}: {exc}") from exc
    return records


def _require_exact(record: dict, expected: set[str], record_type: str) -> None:
    if set(record) != expected or record.get("type") != record_type:
        raise ValueError(f"invalid {record_type} fields")


def _plain_string(value, field: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"invalid {field}")
    return value


def _validate_operator_date(value) -> str:
    value = _plain_string(value, "operator_date")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError("invalid Asia/Shanghai operator_date") from exc
    return value


def _append_record(path: Path, record: dict) -> None:
    handle = _open_created_file(path, "a")
    try:
        handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        handle.flush()
        _fsync_file(handle)
    finally:
        handle.close()


def _load_ledgers(session: _ExperimentSession):
    quotas: dict[str, QuotaState] = {}
    for record in _read_jsonl(session.path / "quotas.jsonl"):
        _require_exact(record, {"type", "quota_id", "created_at", "operator_date"}, "quota_created")
        quota_id = _plain_string(record["quota_id"], "quota_id")
        created_at = _plain_string(record["created_at"], "created_at")
        try:
            parsed_created_at = datetime.fromisoformat(created_at)
            if parsed_created_at.utcoffset() is None:
                raise ValueError
        except ValueError as exc:
            raise ValueError("invalid quota creation timestamp") from exc
        operator_date = _validate_operator_date(record["operator_date"])
        if quota_id in quotas:
            raise ValueError(f"duplicate quota: {quota_id}")
        quotas[quota_id] = QuotaState(quota_id, created_at, operator_date, 0)

    headers = {}
    for record in _read_jsonl(session.path / "checkpoints.jsonl"):
        _require_exact(
            record,
            {"type", "schema_version", "protocol_version", "source_revision", "candidate", "selection_fingerprint"},
            "checkpoint_header",
        )
        if type(record["schema_version"]) is not int or record["schema_version"] != LEDGER_SCHEMA_VERSION:
            raise ValueError("invalid checkpoint schema_version")
        if record["protocol_version"] != PROTOCOL_VERSION or record["source_revision"] != SOURCE_REVISION:
            raise ValueError("invalid checkpoint protocol/source revision")
        candidate = validate_player_spec(record["candidate"])
        _plain_string(record["selection_fingerprint"], "selection_fingerprint")
        if candidate in headers:
            raise ValueError(f"duplicate checkpoint header: {candidate}")
        headers[candidate] = record

    reservations: dict[int, AttemptReservation] = {}
    results = {}
    next_attempt_id = 1
    charged = {quota_id: 0 for quota_id in quotas}
    result_records = []
    conclusive_by_candidate = {candidate: 0 for candidate in CANDIDATES}
    for record in _read_jsonl(session.path / "attempts.jsonl"):
        if record.get("type") == "attempt_reserved":
            _require_exact(
                record,
                {"type", "attempt_id", "candidate", "scheduled_color", "quota_id", "selection_fingerprint"},
                "attempt_reserved",
            )
            attempt_id = record["attempt_id"]
            if type(attempt_id) is not int or attempt_id != next_attempt_id:
                raise ValueError("attempt IDs must be unique and contiguous")
            next_attempt_id += 1
            candidate = validate_player_spec(record["candidate"])
            if record["scheduled_color"] not in ("B", "W"):
                raise ValueError("invalid scheduled_color")
            expected_color = "B" if conclusive_by_candidate[candidate] % 2 == 0 else "W"
            if record["scheduled_color"] != expected_color:
                raise ValueError("reservation color does not match the next conclusive color")
            quota_id = _plain_string(record["quota_id"], "quota_id")
            fingerprint = _plain_string(record["selection_fingerprint"], "selection_fingerprint")
            if quota_id not in quotas:
                raise ValueError(f"unknown quota reference: {quota_id}")
            header = headers.get(candidate)
            if header is None or header["selection_fingerprint"] != fingerprint:
                raise ValueError("reservation does not match immutable checkpoint header")
            reservation = AttemptReservation(attempt_id, candidate, record["scheduled_color"], quota_id, fingerprint)
            reservations[attempt_id] = reservation
            charged[quota_id] += 1
            if charged[quota_id] > DAILY_CHARGED_CAP:
                raise ValueError("quota exceeds 20 charged reservations")
        elif record.get("type") == "attempt_result":
            _require_exact(
                record,
                {"type", "attempt_id", "candidate", "scheduled_color", "quota_id", "selection_fingerprint", "outcome"},
                "attempt_result",
            )
            attempt_id = record["attempt_id"]
            if type(attempt_id) is not int or attempt_id not in reservations:
                raise ValueError("result references unknown attempt reservation")
            if attempt_id in results:
                raise ValueError("duplicate attempt result")
            if record["outcome"] not in ("win", "loss", "inconclusive"):
                raise ValueError("invalid attempt outcome")
            reservation = reservations[attempt_id]
            if any(
                record[field] != getattr(reservation, attribute)
                for field, attribute in (
                    ("candidate", "candidate"),
                    ("scheduled_color", "scheduled_color"),
                    ("quota_id", "quota_id"),
                    ("selection_fingerprint", "selection_fingerprint"),
                )
            ):
                raise ValueError("result does not match exact reservation")
            results[attempt_id] = record
            result_records.append(record)
            if record["outcome"] in ("win", "loss"):
                expected_color = "B" if conclusive_by_candidate[reservation.candidate] % 2 == 0 else "W"
                if reservation.scheduled_color != expected_color:
                    raise ValueError("conclusive result uses a stale reservation color")
                conclusive_by_candidate[reservation.candidate] += 1
        else:
            raise ValueError("invalid attempts ledger record type")

    quotas = {
        quota_id: QuotaState(state.quota_id, state.created_at, state.operator_date, charged[quota_id])
        for quota_id, state in quotas.items()
    }
    return quotas, headers, reservations, results, result_records


def create_or_resume_quota(session, quota_id, *, confirm_new, operator_date) -> QuotaState:
    session = _require_session(session)
    quota_id = _plain_string(quota_id, "quota_id")
    if type(confirm_new) is not bool:
        raise ValueError("confirm_new must be a boolean")
    operator_date = _validate_operator_date(operator_date)
    quotas, _, _, _, _ = _load_ledgers(session)
    existing = quotas.get(quota_id)
    if existing is not None:
        if confirm_new and existing.operator_date != operator_date:
            raise ValueError("existing quota metadata is immutable")
        return existing
    if not confirm_new:
        raise ValueError("unknown quota requires explicit confirm_new=True")
    created_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    _append_record(
        session.path / "quotas.jsonl",
        {"type": "quota_created", "quota_id": quota_id, "created_at": created_at, "operator_date": operator_date},
    )
    return QuotaState(quota_id, created_at, operator_date, 0)


def _evidence_from_results(result_records: list[dict]) -> Evidence:
    completed = []
    totals: dict[str, list[int]] = {}
    expected = Batch(START_PLAYER, 5)
    baseline_total = 0
    progressed = False
    for result in result_records:
        if result["outcome"] == "inconclusive":
            continue
        if not isinstance(expected, Batch) or result["candidate"] != expected.player:
            raise ValueError("result history is unreachable for expected batch")
        wins_losses = totals.setdefault(expected.player, [0, 0])
        wins_losses[0 if result["outcome"] == "win" else 1] += 1
        progressed = True
        if sum(wins_losses) == expected.target_conclusive:
            completed.append(EvidenceBatch(expected.player, expected.target_conclusive, *wins_losses))
            state = Evidence(tuple(completed))
            expected = next_batch(state)
            baseline_total = (
                sum(wins_losses) if isinstance(expected, Batch) and expected.player == result["candidate"] else 0
            )
            progressed = False
        elif sum(wins_losses) > expected.target_conclusive:
            raise ValueError("result history exceeds expected batch")
    if progressed:
        if not isinstance(expected, Batch):
            raise ValueError("result history continues after terminal action")
        wins_losses = totals[expected.player]
        if sum(wins_losses) <= baseline_total:
            raise ValueError("invalid partial evidence reconstruction")
        completed.append(EvidenceBatch(expected.player, expected.target_conclusive, *wins_losses))
    return Evidence(tuple(completed))


def load_evidence(session, expected_fingerprints) -> Evidence:
    session = _require_session(session)
    if not isinstance(expected_fingerprints, Mapping):
        raise ValueError("expected_fingerprints must be a mapping")
    _, headers, _, _, result_records = _load_ledgers(session)
    for candidate, fingerprint in expected_fingerprints.items():
        validate_player_spec(candidate)
        _plain_string(fingerprint, "selection_fingerprint")
        header = headers.get(candidate)
        if header is not None and header["selection_fingerprint"] != fingerprint:
            raise ValueError(f"selection fingerprint drift for {candidate}")
    return _evidence_from_results(result_records)


def next_conclusive_color(session, candidate: str) -> str:
    session = _require_session(session)
    _, _, _, _, result_records = _load_ledgers(session)
    conclusive = sum(
        record["candidate"] == candidate and record["outcome"] in ("win", "loss") for record in result_records
    )
    return "B" if conclusive % 2 == 0 else "W"


def reserve_next_attempt(session, quota_id, expected_batch, expected_fingerprint) -> AttemptReservation:
    session = _require_session(session)
    if not isinstance(expected_batch, Batch):
        raise ValueError("expected_batch must be a Batch")
    fingerprint = _plain_string(expected_fingerprint, "selection_fingerprint")
    quotas, headers, reservations, _, result_records = _load_ledgers(session)
    if quota_id not in quotas:
        raise ValueError("unknown quota; create or resume it first")
    reconstructed = _evidence_from_results(result_records)
    actual_batch = next_batch(reconstructed)
    if actual_batch != expected_batch:
        raise ValueError(f"expected batch mismatch: protocol requires {actual_batch!r}")
    candidate = validate_player_spec(expected_batch.player)
    header = headers.get(candidate)
    if header is not None and header["selection_fingerprint"] != fingerprint:
        raise ValueError(f"selection fingerprint drift for {candidate}")
    if header is None:
        _append_record(
            session.path / "checkpoints.jsonl",
            {
                "type": "checkpoint_header",
                "schema_version": LEDGER_SCHEMA_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "source_revision": SOURCE_REVISION,
                "candidate": candidate,
                "selection_fingerprint": fingerprint,
            },
        )
    if quotas[quota_id].charged_attempts >= DAILY_CHARGED_CAP:
        raise ValueError("quota already has 20 charged reservations")
    color = (
        "B"
        if sum(record["candidate"] == candidate and record["outcome"] in ("win", "loss") for record in result_records)
        % 2
        == 0
        else "W"
    )
    reservation = AttemptReservation(len(reservations) + 1, candidate, color, quota_id, fingerprint)
    _append_record(
        session.path / "attempts.jsonl",
        {
            "type": "attempt_reserved",
            "attempt_id": reservation.attempt_id,
            "candidate": candidate,
            "scheduled_color": color,
            "quota_id": quota_id,
            "selection_fingerprint": fingerprint,
        },
    )
    return reservation


def append_attempt_result(session, reservation, outcome, expected_fingerprint) -> None:
    session = _require_session(session)
    if not isinstance(reservation, AttemptReservation):
        raise ValueError("result requires an AttemptReservation")
    fingerprint = _plain_string(expected_fingerprint, "selection_fingerprint")
    if outcome not in ("win", "loss", "inconclusive"):
        raise ValueError("invalid attempt outcome")
    _, headers, reservations, results, result_records = _load_ledgers(session)
    stored = reservations.get(reservation.attempt_id)
    if stored is None or stored != reservation:
        raise ValueError("result reservation does not match stored reservation")
    if reservation.attempt_id in results:
        raise ValueError("duplicate attempt result")
    if outcome in ("win", "loss"):
        conclusive = sum(
            record["candidate"] == reservation.candidate and record["outcome"] in ("win", "loss")
            for record in result_records
        )
        expected_color = "B" if conclusive % 2 == 0 else "W"
        if reservation.scheduled_color != expected_color:
            raise ValueError("conclusive result uses a stale reservation color")
    header = headers.get(reservation.candidate)
    if (
        fingerprint != reservation.selection_fingerprint
        or header is None
        or header["selection_fingerprint"] != fingerprint
    ):
        raise ValueError("selection fingerprint mismatch")
    _append_record(
        session.path / "attempts.jsonl",
        {
            "type": "attempt_result",
            "attempt_id": reservation.attempt_id,
            "candidate": reservation.candidate,
            "scheduled_color": reservation.scheduled_color,
            "quota_id": reservation.quota_id,
            "selection_fingerprint": reservation.selection_fingerprint,
            "outcome": outcome,
        },
    )
