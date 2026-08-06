"""Deterministic canonical JSON and schema allowlists for ranked contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import uuid
from collections.abc import Mapping, Sequence

OPERATIONAL_FIELDS = frozenset(
    {
        "capability",
        "terminal_capability",
        "retry_count",
        "retry_at",
        "next_retry_at",
        "lease",
        "lease_until",
        "receipt",
    }
)

PREVIEW_FIELDS = frozenset(
    {
        "schema",
        "user_uuid",
        "profile_version",
        "rating_hex",
        "rated_games",
        "scoring_contract_version",
        "catalog_version",
        "opponent_profile_hash",
        "outcome_win_hex",
        "outcome_draw_hex",
        "outcome_loss_hex",
        "delta_win",
        "delta_draw",
        "delta_loss",
        "tier_win",
        "tier_draw",
        "tier_loss",
    }
)

EVENT_V1_COMMON = frozenset(
    {
        "base_profile_version",
        "base_rated_games",
        "base_rating_hex",
        "catalog_version",
        "device_id",
        "event_kind",
        "game_id",
        "grant_slot_id",
        "local_seq",
        "opponent_anchor",
        "opponent_level",
        "opponent_profile_hash",
        "payload_schema",
        "pgn_sha256",
        "player_color",
        "projection_fingerprint",
        "reservation_id",
        "scoring_contract_version",
        "time_control",
        "user_uuid",
    }
)

EVENT_V2_IDENTITY = frozenset(
    {
        "catalog_version",
        "device_id",
        "event_kind",
        "game_id",
        "local_seq",
        "opponent_profile_hash",
        "payload_schema",
        "projection_fingerprint",
        "reservation_id",
        "scoring_contract_version",
        "time_control",
        "user_uuid",
    }
)
EVENT_V2_TERMINAL = frozenset(
    {
        "clock_revision",
        "final_fen",
        "final_position_hash",
        "moves",
        "pgn_sha256",
        "player_clock_ms",
        "player_color",
        "result",
        "terminal_kind",
    }
)
FAULT_EVIDENCE_FIELDS = frozenset(
    {"fault_kind", "retry_count", "last_complete_revision", "engine_exit_summary", "health_summary"}
)
_LOWER_HEX_32 = re.compile(r"[0-9a-f]{32}")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UCI_MOVE = re.compile(r"[a-i][0-9][a-i][0-9]")
_RESULTS = frozenset({"win", "draw", "loss"})
_TIME_CONTROLS = frozenset({"unlimited", "blitz5", "standard10", "slow20"})


def float_hex(value: float) -> str:
    if isinstance(value, bool) or not isinstance(value, float):
        raise TypeError("binary64 values must be Python floats")
    if not math.isfinite(value):
        raise ValueError("binary64 values must be finite")
    return value.hex().lower()


def _validate_float_hex(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a lowercase Python float.hex string")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a lowercase Python float.hex string") from exc
    if not math.isfinite(parsed) or parsed.hex() != value:
        raise ValueError(f"{field} must be an exact lowercase Python float.hex string")


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise TypeError("JSON floats are forbidden; use a lowercase binary64 float.hex string")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("object keys collide after NFC normalization")
            normalized[normalized_key] = _normalize(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    normalized = _normalize(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def canonical_hash(value: object) -> str:
    encoded = value if isinstance(value, bytes) else canonical_json(value)
    return hashlib.sha256(encoded).hexdigest()


def _allowlisted(payload: Mapping[str, object], required: frozenset[str]) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("canonical payload must be an object")
    actual = frozenset(payload)
    missing = required - actual
    unknown = actual - required - OPERATIONAL_FIELDS
    if missing:
        raise ValueError(f"missing canonical fields: {sorted(missing)!r}")
    if unknown:
        raise ValueError(f"unknown canonical fields: {sorted(unknown)!r}")
    return {key: payload[key] for key in required}


def _validate_nonnegative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def _validate_positive_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")


def _validate_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")


def _validate_nonempty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be a non-empty trimmed string")


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a non-empty canonical identifier")


def _validate_lower_hash(value: object, field: str) -> None:
    if not isinstance(value, str) or _LOWER_HEX_64.fullmatch(value) is None:
        raise ValueError(f"{field} must be exactly 64 lowercase hexadecimal characters")


def _validate_uuid(value: object, field: str, *, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical lowercase UUID")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{field} must be a canonical lowercase UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{field} must be a canonical lowercase UUID")


def _validate_user_uuid(value: object) -> None:
    if isinstance(value, str) and _LOWER_HEX_32.fullmatch(value) is not None:
        return
    _validate_uuid(value, "user_uuid")


def _validate_registry_versions(clean: Mapping[str, object]) -> None:
    # Lazy imports avoid catalog -> canonical -> catalog initialization cycles.
    from .catalog import SUPPORTED_CATALOGS
    from .scoring import SUPPORTED_CONTRACTS

    scoring_version = clean["scoring_contract_version"]
    if isinstance(scoring_version, bool) or not isinstance(scoring_version, int):
        raise ValueError("scoring_contract_version must be a registered integer")
    if scoring_version not in SUPPORTED_CONTRACTS:
        raise ValueError("scoring_contract_version must be registered")
    catalog_version = clean["catalog_version"]
    if not isinstance(catalog_version, str) or catalog_version not in SUPPORTED_CATALOGS:
        raise ValueError("catalog_version must be registered")


def _validate_common_context(clean: Mapping[str, object]) -> None:
    _validate_user_uuid(clean["user_uuid"])
    _validate_registry_versions(clean)
    _validate_lower_hash(clean["opponent_profile_hash"], "opponent_profile_hash")


def canonical_preview(payload: Mapping[str, object]) -> bytes:
    clean = _allowlisted(payload, PREVIEW_FIELDS)
    if clean["schema"] != "xiangqi-ranked-preview-v1":
        raise ValueError("schema must be xiangqi-ranked-preview-v1")
    _validate_common_context(clean)
    for field in ("profile_version", "rated_games"):
        _validate_nonnegative_int(clean[field], field)
    for field in ("delta_win", "delta_draw", "delta_loss"):
        _validate_int(clean[field], field)
    for field in ("tier_win", "tier_draw", "tier_loss"):
        _validate_nonempty_string(clean[field], field)
    for field in ("rating_hex", "outcome_win_hex", "outcome_draw_hex", "outcome_loss_hex"):
        _validate_float_hex(clean[field], field)
    return canonical_json(clean)


def hash_preview(payload: Mapping[str, object]) -> str:
    return canonical_hash(canonical_preview(payload))


def _event_fields(payload: Mapping[str, object]) -> frozenset[str]:
    if not isinstance(payload, Mapping):
        raise ValueError("canonical payload must be an object")
    schema = payload.get("payload_schema")
    kind = payload.get("event_kind")
    if schema == "xiangqi-ranked-event-v1":
        if kind == "settle":
            return EVENT_V1_COMMON | {"result"}
        if kind in {"cancel", "system_abort"}:
            return EVENT_V1_COMMON | {"abort_reason"}
        raise ValueError("unsupported v1 event kind")
    if schema == "xiangqi-ranked-event-v2":
        if kind in {"settle", "resign"}:
            return EVENT_V2_IDENTITY | EVENT_V2_TERMINAL
        if kind == "system_abort":
            return EVENT_V2_IDENTITY | {"fault_evidence"}
        raise ValueError("unsupported v2 event kind")
    raise ValueError("unsupported event schema")


def _validate_fault_evidence(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("fault_evidence must be an object")
    actual = frozenset(value)
    missing = FAULT_EVIDENCE_FIELDS - actual
    extra = actual - FAULT_EVIDENCE_FIELDS
    if missing:
        raise ValueError(f"fault_evidence missing fields: {sorted(missing)!r}")
    if extra:
        raise ValueError(f"fault_evidence unknown fields: {sorted(extra)!r}")

    if value["fault_kind"] not in {"engine_unavailable", "system_fault"}:
        raise ValueError("fault_kind must be engine_unavailable or system_fault")
    for field in ("retry_count", "last_complete_revision"):
        field_value = value[field]
        if isinstance(field_value, bool) or not isinstance(field_value, int) or field_value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    for field in ("engine_exit_summary", "health_summary"):
        field_value = value[field]
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"{field} must be a non-empty string")


def _validate_event_identity(clean: Mapping[str, object], *, allow_null_reservation: bool) -> None:
    _validate_common_context(clean)
    if clean["time_control"] not in _TIME_CONTROLS:
        raise ValueError("time_control must be unlimited, blitz5, standard10, or slow20")
    _validate_identifier(clean["device_id"], "device_id")
    _validate_uuid(clean["game_id"], "game_id")
    _validate_nonnegative_int(clean["local_seq"], "local_seq")
    _validate_lower_hash(clean["projection_fingerprint"], "projection_fingerprint")
    _validate_uuid(clean["reservation_id"], "reservation_id", allow_none=allow_null_reservation)


def _validate_v1(clean: Mapping[str, object]) -> None:
    _validate_event_identity(clean, allow_null_reservation=True)
    _validate_nonnegative_int(clean["base_profile_version"], "base_profile_version")
    _validate_nonnegative_int(clean["base_rated_games"], "base_rated_games")
    _validate_float_hex(clean["base_rating_hex"], "base_rating_hex")
    _validate_identifier(clean["grant_slot_id"], "grant_slot_id")
    _validate_positive_int(clean["opponent_anchor"], "opponent_anchor")
    _validate_positive_int(clean["opponent_level"], "opponent_level")
    if clean["opponent_level"] > 9:
        raise ValueError("opponent_level must be between 1 and 9")
    _validate_lower_hash(clean["pgn_sha256"], "pgn_sha256")
    if clean["player_color"] not in {"white", "black"}:
        raise ValueError("player_color must be white or black for v1")

    kind = clean["event_kind"]
    if kind == "settle":
        if clean["result"] not in _RESULTS:
            raise ValueError("result must be win, draw, or loss")
    else:
        allowed_reasons = {"user_cancelled"} if kind == "cancel" else {"engine_unavailable", "system_fault"}
        if clean["abort_reason"] not in allowed_reasons:
            raise ValueError(f"abort_reason is invalid for {kind}")


def _validate_moves(value: object) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("moves must be an array or sequence")
    for move in value:
        if not isinstance(move, str) or _UCI_MOVE.fullmatch(move) is None or move[:2] == move[2:]:
            raise ValueError("moves must contain only canonical Xiangqi UCI moves")


def _validate_v2(clean: Mapping[str, object]) -> None:
    _validate_event_identity(clean, allow_null_reservation=False)
    kind = clean["event_kind"]
    if kind == "system_abort":
        _validate_fault_evidence(clean["fault_evidence"])
        return

    _validate_nonnegative_int(clean["clock_revision"], "clock_revision")
    _validate_nonempty_string(clean["final_fen"], "final_fen")
    _validate_lower_hash(clean["final_position_hash"], "final_position_hash")
    _validate_moves(clean["moves"])
    _validate_lower_hash(clean["pgn_sha256"], "pgn_sha256")
    _validate_nonnegative_int(clean["player_clock_ms"], "player_clock_ms")
    if clean["player_color"] not in {"red", "black"}:
        raise ValueError("player_color must be red or black for v2")
    if clean["result"] not in _RESULTS:
        raise ValueError("result must be win, draw, or loss")
    if kind == "resign":
        if clean["terminal_kind"] != "resign":
            raise ValueError("terminal_kind must be resign for resign events")
        if clean["result"] != "loss":
            raise ValueError("result must be loss for resign events")
    elif clean["terminal_kind"] not in {"rules", "timeout"}:
        raise ValueError("terminal_kind must be rules or timeout for settle events")


def canonical_event(payload: Mapping[str, object]) -> bytes:
    clean = _allowlisted(payload, _event_fields(payload))
    if clean["payload_schema"] == "xiangqi-ranked-event-v1":
        _validate_v1(clean)
    else:
        _validate_v2(clean)
    return canonical_json(clean)


def hash_event(payload: Mapping[str, object]) -> str:
    return canonical_hash(canonical_event(payload))
