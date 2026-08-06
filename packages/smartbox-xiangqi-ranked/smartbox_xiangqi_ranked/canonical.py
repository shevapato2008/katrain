"""Deterministic canonical JSON and schema allowlists for ranked contracts."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
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
    actual = frozenset(payload)
    missing = required - actual
    unknown = actual - required - OPERATIONAL_FIELDS
    if missing:
        raise ValueError(f"missing canonical fields: {sorted(missing)!r}")
    if unknown:
        raise ValueError(f"unknown canonical fields: {sorted(unknown)!r}")
    return {key: payload[key] for key in required}


def canonical_preview(payload: Mapping[str, object]) -> bytes:
    clean = _allowlisted(payload, PREVIEW_FIELDS)
    if clean["schema"] != "xiangqi-ranked-preview-v1":
        raise ValueError("unsupported preview schema")
    for field in ("rating_hex", "outcome_win_hex", "outcome_draw_hex", "outcome_loss_hex"):
        _validate_float_hex(clean[field], field)
    return canonical_json(clean)


def hash_preview(payload: Mapping[str, object]) -> str:
    return canonical_hash(canonical_preview(payload))


def _event_fields(payload: Mapping[str, object]) -> frozenset[str]:
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


def canonical_event(payload: Mapping[str, object]) -> bytes:
    clean = _allowlisted(payload, _event_fields(payload))
    kind = clean["event_kind"]
    if clean["payload_schema"] == "xiangqi-ranked-event-v1":
        _validate_float_hex(clean["base_rating_hex"], "base_rating_hex")
    if (
        clean["payload_schema"] == "xiangqi-ranked-event-v2"
        and "player_color" in clean
        and clean["player_color"] not in {"red", "black"}
    ):
        raise ValueError("v2 player_color must be red or black")
    if kind == "resign" and (clean.get("terminal_kind") != "resign" or clean.get("result") != "loss"):
        raise ValueError("resign events require terminal_kind=resign and result=loss")
    if kind == "settle" and clean.get("terminal_kind") not in {None, "rules", "timeout"}:
        raise ValueError("settle events require a rules or timeout terminal")
    if kind == "system_abort":
        _validate_fault_evidence(clean["fault_evidence"])
    return canonical_json(clean)


def hash_event(payload: Mapping[str, object]) -> str:
    return canonical_hash(canonical_event(payload))
