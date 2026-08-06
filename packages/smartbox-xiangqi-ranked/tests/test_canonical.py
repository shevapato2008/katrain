import math

import pytest

from smartbox_xiangqi_ranked.canonical import (
    canonical_event,
    canonical_hash,
    canonical_json,
    canonical_preview,
    float_hex,
    hash_event,
)


LEGACY_V1 = {
    "base_profile_version": 12,
    "base_rated_games": 5,
    "base_rating_hex": "0x1.f400000000000p+9",
    "catalog_version": "pikafish-r1",
    "device_id": "box-01",
    "event_kind": "settle",
    "game_id": "550e8400-e29b-41d4-a716-446655440000",
    "grant_slot_id": "slot-01",
    "local_seq": 7,
    "opponent_anchor": 1510,
    "opponent_level": 3,
    "opponent_profile_hash": "2" * 64,
    "payload_schema": "xiangqi-ranked-event-v1",
    "pgn_sha256": "0" * 64,
    "player_color": "white",
    "projection_fingerprint": "1" * 64,
    "reservation_id": None,
    "result": "win",
    "scoring_contract_version": 4,
    "time_control": "standard10",
    "user_uuid": "0123456789abcdef0123456789abcdef",
}

INCOMPLETE_EVENT_V2_COMPAT = {
    "catalog_version": "pikafish-r1",
    "clock_revision": 18,
    "device_id": "box-01",
    "event_kind": "settle",
    "final_fen": "4k4/9/9/9/9/9/9/9/4R4/4K4 b - - 18 9",
    "game_id": "550e8400-e29b-41d4-a716-446655440000",
    "local_seq": 7,
    "moves": ["e2e3", "e9e8"],
    "opponent_profile_hash": "2" * 64,
    "payload_schema": "xiangqi-ranked-event-v2",
    "pgn_sha256": "0" * 64,
    "player_clock_ms": 420000,
    "projection_fingerprint": "1" * 64,
    "reservation_id": "660e8400-e29b-41d4-a716-446655440000",
    "result": "win",
    "scoring_contract_version": 4,
    "terminal_kind": "rules",
    "time_control": "standard10",
    "user_uuid": "0123456789abcdef0123456789abcdef",
}
EVENT_V2 = dict(INCOMPLETE_EVENT_V2_COMPAT, player_color="red", final_position_hash="3" * 64)

PREVIEW = {
    "schema": "xiangqi-ranked-preview-v1",
    "user_uuid": "0123456789abcdef0123456789abcdef",
    "profile_version": 2,
    "rating_hex": float_hex(1000.0),
    "rated_games": 5,
    "scoring_contract_version": 4,
    "catalog_version": "pikafish-r1",
    "opponent_profile_hash": "2" * 64,
    "outcome_win_hex": float_hex(1038.0),
    "outcome_draw_hex": float_hex(1018.0),
    "outcome_loss_hex": float_hex(998.0),
    "delta_win": 38,
    "delta_draw": 18,
    "delta_loss": -2,
    "tier_win": "十二级棋士",
    "tier_draw": "十二级棋士",
    "tier_loss": "十二级棋士",
}


def test_canonical_json_normalizes_nfc_sorts_unicode_code_points_and_is_compact_utf8():
    payload = {"é": "e\u0301", "z": ["二", "一"], "a": True}
    assert canonical_json(payload) == b'{"a":true,"z":["\xe4\xba\x8c","\xe4\xb8\x80"],"\xc3\xa9":"\xc3\xa9"}'


def test_canonical_json_preserves_array_order():
    assert canonical_json({"moves": ["e2e3", "e9e8"]}) != canonical_json({"moves": ["e9e8", "e2e3"]})


@pytest.mark.parametrize("value", [0.0, 1.25, math.nan, math.inf, -math.inf])
def test_json_float_is_always_rejected_even_when_finite(value):
    with pytest.raises((TypeError, ValueError)):
        canonical_json({"rating": value})


def test_binary64_crosses_protocol_boundaries_only_as_lowercase_float_hex():
    assert float_hex(1000.0) == "0x1.f400000000000p+9"
    assert float_hex(-0.0) == "-0x0.0p+0"
    with pytest.raises(ValueError):
        float_hex(math.nan)


def test_preview_has_an_explicit_allowlist_and_excludes_operational_metadata():
    expected = canonical_preview(PREVIEW)
    polluted = dict(PREVIEW, terminal_capability="bearer", retry_count=9, lease_until="later", receipt={"ok": True})
    assert canonical_preview(polluted) == expected


@pytest.mark.parametrize("bad_hex", ["1000.0", "0X1.F4P+9", "0x1.f4p+9", "nan", "inf"])
def test_preview_rejects_values_that_are_not_exact_lowercase_python_float_hex(bad_hex):
    preview = dict(PREVIEW, rating_hex=bad_hex)
    with pytest.raises(ValueError):
        canonical_preview(preview)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "xiangqi-ranked-preview-v2"),
        ("user_uuid", "u"),
        ("user_uuid", "A" * 32),
        ("profile_version", -1),
        ("profile_version", True),
        ("rated_games", -1),
        ("rated_games", 1.5),
        ("scoring_contract_version", 999),
        ("scoring_contract_version", True),
        ("catalog_version", "pikafish-unknown"),
        ("opponent_profile_hash", "A" * 64),
        ("opponent_profile_hash", "2" * 63),
        ("delta_win", True),
        ("delta_draw", 1.5),
        ("tier_loss", "  "),
        ("tier_win", 7),
    ],
)
def test_preview_rejects_invalid_typed_or_unregistered_fields(field, value):
    with pytest.raises((TypeError, ValueError), match=field):
        canonical_preview(dict(PREVIEW, **{field: value}))


@pytest.mark.parametrize(
    "user_uuid",
    ["0123456789abcdef0123456789abcdef", "550e8400-e29b-41d4-a716-446655440000"],
)
def test_preview_accepts_both_authoritative_user_uuid_forms(user_uuid):
    assert canonical_preview(dict(PREVIEW, user_uuid=user_uuid))


def test_legacy_settlement_v1_vector_remains_verifiable():
    assert (
        canonical_hash(canonical_event(LEGACY_V1)) == "8280e6ce6b18ea0914b6a67167390e30174f0c718d3d4717cf2f08f38b7c402b"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_profile_version", -1),
        ("base_profile_version", True),
        ("base_rated_games", -1),
        ("base_rated_games", 1.5),
        ("catalog_version", "pikafish-r9"),
        ("device_id", "  "),
        ("game_id", "550E8400-E29B-41D4-A716-446655440000"),
        ("grant_slot_id", ""),
        ("local_seq", -1),
        ("opponent_anchor", 0),
        ("opponent_anchor", True),
        ("opponent_level", 0),
        ("opponent_level", 10),
        ("opponent_profile_hash", "g" * 64),
        ("pgn_sha256", "0" * 63),
        ("player_color", "red"),
        ("projection_fingerprint", "1" * 65),
        ("reservation_id", "not-a-uuid"),
        ("result", "1-0"),
        ("scoring_contract_version", 5),
        ("time_control", "rapid"),
        ("user_uuid", "550E8400-E29B-41D4-A716-446655440000"),
    ],
)
def test_v1_settle_rejects_invalid_fields_before_hashing(field, value):
    with pytest.raises((TypeError, ValueError), match=field):
        hash_event(dict(LEGACY_V1, **{field: value}))


@pytest.mark.parametrize(
    "event_kind,abort_reason",
    [
        ("cancel", "user_cancelled"),
        ("system_abort", "engine_unavailable"),
        ("system_abort", "system_fault"),
    ],
)
def test_v1_abort_kinds_accept_only_their_frozen_reason_enums(event_kind, abort_reason):
    event = dict(LEGACY_V1, event_kind=event_kind, abort_reason=abort_reason)
    event.pop("result")
    assert canonical_event(event)


@pytest.mark.parametrize(
    "event_kind,abort_reason",
    [("cancel", "system_fault"), ("system_abort", "user_cancelled"), ("system_abort", "network")],
)
def test_v1_abort_kinds_reject_mismatched_or_unknown_reasons(event_kind, abort_reason):
    event = dict(LEGACY_V1, event_kind=event_kind, abort_reason=abort_reason)
    event.pop("result")
    with pytest.raises(ValueError, match="abort_reason"):
        hash_event(event)


def test_incomplete_historical_v2_vector_remains_generic_canonical_hash_compatible():
    assert (
        canonical_hash(canonical_json(INCOMPLETE_EVENT_V2_COMPAT))
        == "4e7fe318a405c70a2efa2e18bfdc8d24a4ebf94fb4a922fb6b06467074064857"
    )
    with pytest.raises(ValueError, match="player_color"):
        canonical_event(INCOMPLETE_EVENT_V2_COMPAT)


@pytest.mark.parametrize("missing", ["player_color", "final_position_hash"])
def test_current_event_v2_requires_color_and_final_position_hash(missing):
    incomplete = dict(EVENT_V2)
    incomplete.pop(missing)
    with pytest.raises(ValueError, match=missing):
        canonical_event(incomplete)


def test_current_event_v2_hashes_color_and_final_position_hash():
    assert canonical_event(EVENT_V2)
    assert hash_event(dict(EVENT_V2, player_color="black")) != hash_event(EVENT_V2)
    assert hash_event(dict(EVENT_V2, final_position_hash="4" * 64)) != hash_event(EVENT_V2)


@pytest.mark.parametrize(
    "field,value",
    [
        ("catalog_version", "pikafish-r9"),
        ("device_id", ""),
        ("game_id", "550e8400e29b41d4a716446655440000"),
        ("local_seq", True),
        ("opponent_profile_hash", "2" * 63),
        ("projection_fingerprint", "G" * 64),
        ("reservation_id", None),
        ("scoring_contract_version", 999),
        ("time_control", "standard"),
        ("user_uuid", "not-a-user"),
        ("clock_revision", -1),
        ("final_fen", " "),
        ("final_position_hash", "3" * 65),
        ("moves", "e2e3"),
        ("moves", ["e2e3", "e9e"]),
        ("moves", ["e2e2"]),
        ("pgn_sha256", "A" * 64),
        ("player_clock_ms", -1),
        ("player_color", "white"),
        ("result", "1-0"),
        ("terminal_kind", None),
        ("terminal_kind", "resign"),
    ],
)
def test_v2_settle_invalid_terminal_matrix_is_rejected_before_hashing(field, value):
    with pytest.raises((TypeError, ValueError), match=field):
        hash_event(dict(EVENT_V2, **{field: value}))


@pytest.mark.parametrize("terminal_kind", ["rules", "timeout"])
@pytest.mark.parametrize("result", ["win", "draw", "loss"])
def test_v2_settle_accepts_only_the_complete_terminal_matrix(terminal_kind, result):
    assert hash_event(dict(EVENT_V2, terminal_kind=terminal_kind, result=result))


def test_event_hash_is_insertion_order_independent_and_excludes_operational_metadata():
    reversed_event = dict(reversed(list(EVENT_V2.items())))
    reversed_event.update(capability="secret", retry_count=3, lease="held", receipt="accepted")
    assert hash_event(reversed_event) == hash_event(EVENT_V2)


def test_resign_has_the_same_complete_evidence_shape_and_forces_a_loss():
    resigned = dict(EVENT_V2, event_kind="resign", terminal_kind="resign", result="loss")
    assert canonical_event(resigned)

    with pytest.raises(ValueError):
        canonical_event(dict(resigned, result="win"))

    with pytest.raises(ValueError, match="terminal_kind"):
        canonical_event(dict(resigned, terminal_kind="rules"))


FAULT_EVIDENCE = {
    "fault_kind": "engine_unavailable",
    "retry_count": 2,
    "last_complete_revision": 17,
    "engine_exit_summary": "exit status 70",
    "health_summary": "ready probe failed",
}
SYSTEM_ABORT_V2 = {
    key: value
    for key, value in EVENT_V2.items()
    if key
    in {
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
}
SYSTEM_ABORT_V2.update(event_kind="system_abort", fault_evidence=FAULT_EVIDENCE)


def test_system_abort_fault_evidence_has_an_exact_protocol_shape_and_hashes_every_field():
    baseline = hash_event(SYSTEM_ABORT_V2)
    changes = {
        "fault_kind": "system_fault",
        "retry_count": 3,
        "last_complete_revision": 18,
        "engine_exit_summary": "exit status 71",
        "health_summary": "engine process missing",
    }
    for field, value in changes.items():
        changed = dict(SYSTEM_ABORT_V2, fault_evidence=dict(FAULT_EVIDENCE, **{field: value}))
        assert hash_event(changed) != baseline


@pytest.mark.parametrize("missing", sorted(FAULT_EVIDENCE))
def test_system_abort_rejects_missing_fault_evidence_fields(missing):
    evidence = dict(FAULT_EVIDENCE)
    evidence.pop(missing)
    with pytest.raises(ValueError, match=missing):
        canonical_event(dict(SYSTEM_ABORT_V2, fault_evidence=evidence))


@pytest.mark.parametrize(
    "field,value",
    [
        ("fault_kind", "network_error"),
        ("retry_count", -1),
        ("retry_count", True),
        ("last_complete_revision", -1),
        ("last_complete_revision", 1.5),
        ("engine_exit_summary", ""),
        ("health_summary", None),
    ],
)
def test_system_abort_rejects_invalid_fault_evidence_values(field, value):
    with pytest.raises((TypeError, ValueError), match=field):
        canonical_event(dict(SYSTEM_ABORT_V2, fault_evidence=dict(FAULT_EVIDENCE, **{field: value})))


def test_system_abort_rejects_extra_fault_evidence_and_normal_result_fields():
    with pytest.raises(ValueError, match="debug_dump"):
        canonical_event(dict(SYSTEM_ABORT_V2, fault_evidence=dict(FAULT_EVIDENCE, debug_dump="secret")))
    with pytest.raises(ValueError, match="result"):
        canonical_event(dict(SYSTEM_ABORT_V2, result="loss"))


def test_unknown_non_operational_fields_are_rejected_instead_of_silently_hashed_or_dropped():
    with pytest.raises(ValueError):
        canonical_event(dict(EVENT_V2, typo_result="win"))
