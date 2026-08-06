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

EVENT_V2 = {
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
    preview = {
        "schema": "xiangqi-ranked-preview-v1",
        "user_uuid": "u",
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
    expected = canonical_preview(preview)
    polluted = dict(preview, terminal_capability="bearer", retry_count=9, lease_until="later", receipt={"ok": True})
    assert canonical_preview(polluted) == expected


@pytest.mark.parametrize("bad_hex", ["1000.0", "0X1.F4P+9", "0x1.f4p+9", "nan", "inf"])
def test_preview_rejects_values_that_are_not_exact_lowercase_python_float_hex(bad_hex):
    preview = {
        "schema": "xiangqi-ranked-preview-v1",
        "user_uuid": "u",
        "profile_version": 2,
        "rating_hex": bad_hex,
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
    with pytest.raises(ValueError):
        canonical_preview(preview)


def test_legacy_settlement_v1_vector_remains_verifiable():
    assert (
        canonical_hash(canonical_event(LEGACY_V1)) == "8280e6ce6b18ea0914b6a67167390e30174f0c718d3d4717cf2f08f38b7c402b"
    )


def test_current_event_v2_vector_matches_the_frozen_design():
    assert hash_event(EVENT_V2) == "4e7fe318a405c70a2efa2e18bfdc8d24a4ebf94fb4a922fb6b06467074064857"


def test_event_v2_can_bind_color_and_final_position_hash_without_changing_the_frozen_base_vector():
    enriched = dict(EVENT_V2, player_color="red", final_position_hash="3" * 64)
    assert hash_event(enriched) != hash_event(EVENT_V2)


def test_event_hash_is_insertion_order_independent_and_excludes_operational_metadata():
    reversed_event = dict(reversed(list(EVENT_V2.items())))
    reversed_event.update(capability="secret", retry_count=3, lease="held", receipt="accepted")
    assert hash_event(reversed_event) == hash_event(EVENT_V2)


def test_resign_and_system_fault_have_strict_distinct_shapes():
    resigned = dict(EVENT_V2, event_kind="resign", terminal_kind="resign", result="loss")
    assert canonical_event(resigned)

    with pytest.raises(ValueError):
        canonical_event(dict(resigned, result="win"))

    fault = {
        key: value
        for key, value in EVENT_V2.items()
        if key
        not in {"result", "terminal_kind", "moves", "final_fen", "clock_revision", "player_clock_ms", "pgn_sha256"}
    }
    fault.update(event_kind="system_abort", fault_evidence={"kind": "engine_exit", "retry_count": 2})
    without_retry_metadata = dict(fault, fault_evidence={"kind": "engine_exit"})
    assert canonical_event(fault) == canonical_event(without_retry_metadata)

    with pytest.raises(ValueError):
        canonical_event(dict(fault, result="loss"))


def test_unknown_non_operational_fields_are_rejected_instead_of_silently_hashed_or_dropped():
    with pytest.raises(ValueError):
        canonical_event(dict(EVENT_V2, typo_result="win"))
