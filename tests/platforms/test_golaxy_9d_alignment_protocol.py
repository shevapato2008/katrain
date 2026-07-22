import importlib
import json
import os
import subprocess
import sys
import threading
from collections import UserDict
from pathlib import Path
from types import MappingProxyType

import pytest

CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
protocol = importlib.import_module("golaxy_9d_alignment")
REVISION_ONE = "1" * 40
REVISION_TWO = "a" * 40


def _session(path, revision=REVISION_ONE):
    return protocol.experiment_session(path, revision)


def test_grid_and_initial_batch_are_frozen():
    assert protocol.PROTOCOL_VERSION == "golaxy-9d-humansl-alignment-v1"
    assert protocol.CANDIDATES == (
        "rank_9d@1s",
        "rank_9d@4",
        "rank_9d@8",
        "rank_9d@16",
        "rank_9d@32",
    )
    assert protocol.START_PLAYER == "rank_9d@8"
    assert protocol.GOLAXY_API_LEVEL == 3000
    assert protocol.LOCAL_BASE_URL == "http://127.0.0.1:8000"
    assert protocol.DAILY_CHARGED_CAP == 20
    assert protocol.next_batch({}) == protocol.Batch("rank_9d@8", 5)


@pytest.mark.parametrize(
    "player",
    [
        "rank_9d@1",
        "rank_8d@8",
        "rank_10d@8",
        "b28@8",
        "rank_9d@7",
        "rank_9d@64",
        "rank_9d",
        "rank_9d@",
        "rank_9d@8x",
        " rank_9d@8",
        "",
        None,
    ],
)
def test_player_spec_rejects_everything_outside_the_frozen_grid(player):
    with pytest.raises(ValueError, match="candidate"):
        protocol.validate_player_spec(player)


@pytest.mark.parametrize("player", ["rank_9d@1s", "rank_9d@4", "rank_9d@8", "rank_9d@16", "rank_9d@32"])
def test_player_spec_accepts_exact_frozen_candidates(player):
    assert protocol.validate_player_spec(player) == player


def evidence(*batches):
    return protocol.Evidence(tuple(protocol.EvidenceBatch(*batch) for batch in batches))


@pytest.mark.parametrize(
    ("player", "wins", "expected"),
    [
        ("rank_9d@4", 0, protocol.Batch("rank_9d@8", 10)),
        ("rank_9d@4", 1, protocol.Batch("rank_9d@8", 10)),
        ("rank_9d@4", 2, protocol.Batch("rank_9d@4", 10)),
        ("rank_9d@4", 3, protocol.Batch("rank_9d@4", 10)),
        ("rank_9d@4", 4, protocol.Batch("rank_9d@1s", 5)),
        ("rank_9d@4", 5, protocol.Batch("rank_9d@1s", 5)),
        ("rank_9d@8", 0, protocol.Batch("rank_9d@16", 5)),
        ("rank_9d@8", 2, protocol.Batch("rank_9d@8", 10)),
        ("rank_9d@8", 5, protocol.Batch("rank_9d@4", 5)),
        ("rank_9d@16", 1, protocol.Batch("rank_9d@32", 5)),
        ("rank_9d@16", 3, protocol.Batch("rank_9d@16", 10)),
        ("rank_9d@16", 4, protocol.Batch("rank_9d@8", 10)),
    ],
)
def test_first_five_route_every_interior_candidate(player, wins, expected):
    # Prefixes establish a reachable route to the tier under test.
    prefixes = {
        "rank_9d@4": (("rank_9d@8", 5, 4, 1),),
        "rank_9d@8": (),
        "rank_9d@16": (("rank_9d@8", 5, 1, 4),),
    }
    state = evidence(*prefixes[player], (player, 5, wins, 5 - wins))
    assert protocol.next_batch(state) == expected


@pytest.mark.parametrize(
    ("prefix", "player", "wins", "expected"),
    [
        (
            (("rank_9d@8", 5, 5, 0), ("rank_9d@4", 5, 5, 0)),
            "rank_9d@1s",
            4,
            protocol.Batch("rank_9d@1s", 10),
        ),
        (
            (("rank_9d@8", 5, 5, 0), ("rank_9d@4", 5, 5, 0)),
            "rank_9d@1s",
            5,
            protocol.Batch("rank_9d@1s", 10),
        ),
        (
            (("rank_9d@8", 5, 5, 0), ("rank_9d@4", 5, 5, 0)),
            "rank_9d@1s",
            1,
            protocol.Batch("rank_9d@4", 10),
        ),
        (
            (("rank_9d@8", 5, 0, 5), ("rank_9d@16", 5, 0, 5)),
            "rank_9d@32",
            0,
            protocol.Batch("rank_9d@32", 10),
        ),
        (
            (("rank_9d@8", 5, 0, 5), ("rank_9d@16", 5, 0, 5)),
            "rank_9d@32",
            3,
            protocol.Batch("rank_9d@32", 10),
        ),
        (
            (("rank_9d@8", 5, 0, 5), ("rank_9d@16", 5, 0, 5)),
            "rank_9d@32",
            4,
            protocol.Batch("rank_9d@16", 10),
        ),
    ],
)
def test_first_five_obey_endpoint_rules(prefix, player, wins, expected):
    assert protocol.next_batch(evidence(*prefix, (player, 5, wins, 5 - wins))) == expected


@pytest.mark.parametrize(
    ("wins", "expected"),
    [
        (4, protocol.Batch("rank_9d@16", 5)),
        (5, protocol.Batch("rank_9d@16", 10)),
        (6, protocol.Batch("rank_9d@4", 5)),
        (8, protocol.Batch("rank_9d@4", 5)),
    ],
)
def test_ten_game_outcomes_route_failure_alignment_and_qualification(wins, expected):
    assert protocol.next_batch(evidence(("rank_9d@8", 5, 3, 2), ("rank_9d@8", 10, wins, 10 - wins))) == expected


def test_qualified_lowest_tier_is_selected_from_direct_ten_game_evidence():
    result = protocol.next_batch(
        evidence(
            ("rank_9d@8", 5, 3, 2),
            ("rank_9d@8", 10, 7, 3),
            ("rank_9d@4", 5, 1, 4),
        )
    )
    assert result == protocol.ProductDecision(
        measured_tier="rank_9d@8",
        product_tier="rank_9d@8",
        basis="direct_10_game_evidence",
        reason="lowest_qualified_tier",
    )


def test_five_five_requires_direct_safety_tier_evidence_before_decision():
    state = evidence(
        ("rank_9d@8", 5, 3, 2),
        ("rank_9d@8", 10, 5, 5),
        ("rank_9d@16", 10, 6, 4),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        measured_tier="rank_9d@8",
        product_tier="rank_9d@16",
        basis="monotonic_safety_inference",
        reason="aligned_tier_safety_margin",
    )


def test_five_five_with_failed_safety_tier_is_inconclusive_non_monotonic():
    assert protocol.next_batch(
        evidence(
            ("rank_9d@8", 5, 3, 2),
            ("rank_9d@8", 10, 5, 5),
            ("rank_9d@16", 10, 4, 6),
        )
    ) == protocol.ProtocolStop("inconclusive_non_monotonic")


def test_top_endpoint_alignment_has_no_in_grid_safety_tier():
    state = evidence(
        ("rank_9d@8", 5, 0, 5),
        ("rank_9d@16", 5, 0, 5),
        ("rank_9d@32", 5, 3, 2),
        ("rank_9d@32", 10, 5, 5),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        measured_tier="rank_9d@32",
        product_tier=None,
        basis="monotonic_safety_inference",
        reason="aligned_no_in_grid_safety_tier",
    )


def test_top_endpoint_failure_exhausts_grid():
    state = evidence(
        ("rank_9d@8", 5, 0, 5),
        ("rank_9d@16", 5, 0, 5),
        ("rank_9d@32", 5, 3, 2),
        ("rank_9d@32", 10, 4, 6),
    )
    assert protocol.next_batch(state) == protocol.ProtocolStop("grid_exhausted")


@pytest.mark.parametrize(
    ("target", "wins", "losses"),
    [(5, 1, 0), (5, 2, 2), (10, 4, 2), (10, 5, 4)],
)
def test_partial_active_batch_resumes_same_milestone(target, wins, losses):
    prefix = () if target == 5 else (("rank_9d@8", 5, 3, 2),)
    assert protocol.next_batch(evidence(*prefix, ("rank_9d@8", target, wins, losses))) == protocol.Batch(
        "rank_9d@8", target
    )


@pytest.mark.parametrize(
    "state",
    [
        evidence(("rank_9d@8", 5, 6, 0)),
        evidence(("rank_9d@8", 10, 11, 0)),
        evidence(("rank_9d@8", 5, 3, 1), ("rank_9d@8", 5, 3, 2)),
        evidence(("rank_9d@16", 5, 1, 4)),
        evidence(("rank_9d@8", 5, 3, 2), ("rank_9d@8", 10, 2, 8)),
    ],
)
def test_unreachable_histories_are_rejected(state):
    with pytest.raises(ValueError, match="unreachable evidence"):
        protocol.next_batch(state)


def test_non_empty_mapping_is_not_a_second_evidence_schema():
    with pytest.raises(ValueError, match="Evidence"):
        protocol.next_batch({"rank_9d@8": {"wins": 3, "losses": 2}})


@pytest.mark.parametrize(
    "mapping",
    [
        UserDict(),
        MappingProxyType({}),
        UserDict({"rank_9d@8": None}),
        MappingProxyType({"rank_9d@8": None}),
    ],
)
def test_only_exact_empty_builtin_dict_is_allowed_as_empty_shorthand(mapping):
    with pytest.raises(ValueError, match="Evidence"):
        protocol.next_batch(mapping)


class EmptyCustomMapping(dict):
    pass


def test_empty_custom_mapping_is_rejected():
    with pytest.raises(ValueError, match="Evidence"):
        protocol.next_batch(EmptyCustomMapping())


@pytest.mark.parametrize(
    ("player", "prefix", "wins", "expected"),
    [
        *[
            (
                "rank_9d@1s",
                (("rank_9d@8", 5, 4, 1), ("rank_9d@4", 5, 4, 1)),
                wins,
                protocol.Batch("rank_9d@4", 10) if wins <= 1 else protocol.Batch("rank_9d@1s", 10),
            )
            for wins in range(6)
        ],
        *[
            (
                "rank_9d@4",
                (("rank_9d@8", 5, 4, 1),),
                wins,
                (
                    protocol.Batch("rank_9d@8", 10)
                    if wins <= 1
                    else protocol.Batch("rank_9d@4", 10) if wins <= 3 else protocol.Batch("rank_9d@1s", 5)
                ),
            )
            for wins in range(6)
        ],
        *[
            (
                "rank_9d@8",
                (),
                wins,
                (
                    protocol.Batch("rank_9d@16", 5)
                    if wins <= 1
                    else protocol.Batch("rank_9d@8", 10) if wins <= 3 else protocol.Batch("rank_9d@4", 5)
                ),
            )
            for wins in range(6)
        ],
        *[
            (
                "rank_9d@16",
                (("rank_9d@8", 5, 1, 4),),
                wins,
                (
                    protocol.Batch("rank_9d@32", 5)
                    if wins <= 1
                    else protocol.Batch("rank_9d@16", 10) if wins <= 3 else protocol.Batch("rank_9d@8", 10)
                ),
            )
            for wins in range(6)
        ],
        *[
            (
                "rank_9d@32",
                (("rank_9d@8", 5, 1, 4), ("rank_9d@16", 5, 1, 4)),
                wins,
                protocol.Batch("rank_9d@32", 10) if wins <= 3 else protocol.Batch("rank_9d@16", 10),
            )
            for wins in range(6)
        ],
    ],
)
def test_every_five_game_outcome_for_every_candidate(player, prefix, wins, expected):
    assert protocol.next_batch(evidence(*prefix, (player, 5, wins, 5 - wins))) == expected


@pytest.mark.parametrize("total", [1, 2, 3, 4])
def test_every_partial_total_before_first_milestone_resumes_to_five(total):
    assert protocol.next_batch(evidence(("rank_9d@8", 5, total, 0))) == protocol.Batch("rank_9d@8", 5)


@pytest.mark.parametrize("total", [6, 7, 8, 9])
def test_every_partial_total_before_second_milestone_resumes_to_ten(total):
    wins = total - 2
    state = evidence(("rank_9d@8", 5, 3, 2), ("rank_9d@8", 10, wins, 2))
    assert protocol.next_batch(state) == protocol.Batch("rank_9d@8", 10)


def test_zero_conclusive_record_is_rejected():
    with pytest.raises(ValueError, match="unreachable evidence"):
        protocol.next_batch(evidence(("rank_9d@8", 5, 0, 0)))


def test_revisits_a_previously_screened_tier_then_selects_qualified_higher_tier():
    screened = evidence(
        ("rank_9d@8", 5, 0, 5),
        ("rank_9d@16", 5, 2, 3),
        ("rank_9d@16", 10, 6, 4),
    )
    assert protocol.next_batch(screened) == protocol.Batch("rank_9d@8", 10)

    revisited = evidence(
        *[tuple(vars(batch).values()) for batch in screened.batches],
        ("rank_9d@8", 10, 4, 6),
    )
    assert protocol.next_batch(revisited) == protocol.ProductDecision(
        "rank_9d@16", "rank_9d@16", "direct_10_game_evidence", "lowest_qualified_tier"
    )


def test_multiple_qualified_tiers_select_the_lowest_tested_tier():
    state = evidence(
        ("rank_9d@8", 5, 3, 2),
        ("rank_9d@8", 10, 7, 3),
        ("rank_9d@4", 5, 3, 2),
        ("rank_9d@4", 10, 6, 4),
        ("rank_9d@1s", 5, 2, 3),
        ("rank_9d@1s", 10, 6, 4),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        "rank_9d@1s", "rank_9d@1s", "direct_10_game_evidence", "lowest_qualified_tier"
    )


def test_lowest_five_five_uses_safety_rule_even_when_multiple_tiers_pass():
    state = evidence(
        ("rank_9d@8", 5, 0, 5),
        ("rank_9d@16", 5, 3, 2),
        ("rank_9d@16", 10, 7, 3),
        ("rank_9d@8", 10, 5, 5),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        "rank_9d@8", "rank_9d@16", "monotonic_safety_inference", "aligned_tier_safety_margin"
    )


@pytest.mark.parametrize("wins", [6, 7])
def test_lowest_endpoint_six_or_more_wins_selects_directly(wins):
    state = evidence(
        ("rank_9d@8", 5, 5, 0),
        ("rank_9d@4", 5, 5, 0),
        ("rank_9d@1s", 5, 2, 3),
        ("rank_9d@1s", 10, wins, 10 - wins),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        "rank_9d@1s", "rank_9d@1s", "direct_10_game_evidence", "lowest_qualified_tier"
    )


def test_lowest_endpoint_five_five_uses_rank_9d_at_4_as_safety_tier():
    state = evidence(
        ("rank_9d@8", 5, 5, 0),
        ("rank_9d@4", 5, 5, 0),
        ("rank_9d@1s", 5, 2, 3),
        ("rank_9d@1s", 10, 5, 5),
        ("rank_9d@4", 10, 6, 4),
    )
    assert protocol.next_batch(state) == protocol.ProductDecision(
        "rank_9d@1s", "rank_9d@4", "monotonic_safety_inference", "aligned_tier_safety_margin"
    )


def test_public_protocol_records_are_frozen():
    record = protocol.EvidenceBatch("rank_9d@8", 5, 1, 0)
    with pytest.raises((AttributeError, TypeError)):
        record.wins = 2
    with pytest.raises((AttributeError, TypeError)):
        protocol.Batch("rank_9d@8", 5).target_conclusive = 10


def test_evidence_requires_an_immutable_tuple_history():
    with pytest.raises(ValueError, match="tuple"):
        protocol.next_batch(protocol.Evidence([]))


def _reserve(session, quota_id="q1", batch=None, fingerprint="fp-1"):
    return protocol.reserve_next_attempt(session, quota_id, batch or protocol.Batch("rank_9d@8", 5), fingerprint)


def test_quota_requires_confirmation_and_resume_preserves_metadata(tmp_path):
    with _session(tmp_path) as session:
        with pytest.raises(ValueError, match="confirm"):
            protocol.create_or_resume_quota(session, "q1", confirm_new=False, operator_date="2026-07-22")
        original = protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        resumed = protocol.create_or_resume_quota(session, "q1", confirm_new=False, operator_date="2099-01-01")
        assert resumed == original
        with pytest.raises(ValueError, match="metadata"):
            protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2099-01-01")

    record = json.loads((tmp_path / "quotas.jsonl").read_text())
    assert record == {
        "type": "quota_created",
        "quota_id": "q1",
        "created_at": original.created_at,
        "operator_date": "2026-07-22",
    }


def test_quota_cap_charges_crashed_reservations_and_ids_continue_across_quotas(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        reservations = [_reserve(session) for _ in range(20)]
        assert [item.attempt_id for item in reservations] == list(range(1, 21))
        with pytest.raises(ValueError, match="20"):
            _reserve(session)
        protocol.create_or_resume_quota(session, "q2", confirm_new=True, operator_date="2026-07-22")
        assert _reserve(session, "q2").attempt_id == 21


def test_checkpoint_precedes_first_reservation_and_drift_is_detected_after_crash(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        reservation = _reserve(session)
        header = json.loads((tmp_path / "checkpoints.jsonl").read_text())
        assert header["type"] == "checkpoint_header"
        assert header["schema_version"] == 1
        assert header["protocol_version"] == protocol.PROTOCOL_VERSION
        assert header["source_revision"]
        assert header["candidate"] == reservation.candidate
        assert header["selection_fingerprint"] == "fp-1"
        with pytest.raises(ValueError, match="fingerprint"):
            _reserve(session, fingerprint="changed")


def test_inconclusive_does_not_advance_color_and_ten_conclusive_are_balanced(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        first = _reserve(session)
        assert first.scheduled_color == "B"
        protocol.append_attempt_result(session, first, "inconclusive", "fp-1")
        second = _reserve(session)
        assert second.scheduled_color == "B"
        protocol.append_attempt_result(session, second, "win", "fp-1")
        colors = [second.scheduled_color]
        outcomes = ["win", "win", "loss", "loss", "win", "win", "loss", "loss", "loss"]
        for index in range(9):
            item = _reserve(session, batch=protocol.Batch("rank_9d@8", 5 if index < 4 else 10))
            colors.append(item.scheduled_color)
            protocol.append_attempt_result(session, item, outcomes[index], "fp-1")
        assert colors.count("B") == colors.count("W") == 5
        loaded = protocol.load_evidence(session, {"rank_9d@8": "fp-1"})
        assert loaded == evidence(("rank_9d@8", 5, 3, 2), ("rank_9d@8", 10, 5, 5))


def test_results_strictly_cross_reference_reservations(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        item = _reserve(session)
        for changed in (
            protocol.AttemptReservation(
                item.attempt_id + 10,
                item.candidate,
                item.scheduled_color,
                item.quota_id,
                item.selection_fingerprint,
                REVISION_ONE,
            ),
            protocol.AttemptReservation(
                item.attempt_id,
                "rank_9d@4",
                item.scheduled_color,
                item.quota_id,
                item.selection_fingerprint,
                REVISION_ONE,
            ),
            protocol.AttemptReservation(
                item.attempt_id, item.candidate, "W", item.quota_id, item.selection_fingerprint, REVISION_ONE
            ),
            protocol.AttemptReservation(
                item.attempt_id,
                item.candidate,
                item.scheduled_color,
                "other",
                item.selection_fingerprint,
                REVISION_ONE,
            ),
        ):
            with pytest.raises(ValueError, match="reservation"):
                protocol.append_attempt_result(session, changed, "win", "fp-1")
        with pytest.raises(ValueError, match="fingerprint"):
            protocol.append_attempt_result(session, item, "win", "wrong")
        protocol.append_attempt_result(session, item, "win", "fp-1")
        with pytest.raises(ValueError, match="duplicate"):
            protocol.append_attempt_result(session, item, "loss", "fp-1")


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        (
            "quotas.jsonl",
            '{"type":"quota_created","quota_id":"q","quota_id":"x","created_at":"x","operator_date":"2026-01-01"}\n',
            "duplicate",
        ),
        ("quotas.jsonl", "not-json\n", "JSON"),
        (
            "quotas.jsonl",
            '{"type":"quota_created","quota_id":"q","created_at":"2026-01-01T00:00:00+08:00","operator_date":"2026-01-01"}\n'
            * 2,
            "duplicate quota",
        ),
        (
            "attempts.jsonl",
            '{"type":"attempt_reserved","attempt_id":2,"candidate":"rank_9d@8","scheduled_color":"B","quota_id":"q","selection_fingerprint":"fp","source_revision":"1111111111111111111111111111111111111111"}\n',
            "contiguous",
        ),
        (
            "attempts.jsonl",
            '{"type":"attempt_reserved","attempt_id":1,"candidate":"rank_9d@8","scheduled_color":"B","quota_id":"missing","selection_fingerprint":"fp","source_revision":"1111111111111111111111111111111111111111"}\n',
            "unknown quota",
        ),
    ],
)
def test_malformed_or_inconsistent_ledgers_fail_closed(tmp_path, filename, contents, message):
    (tmp_path / filename).write_text(contents)
    with _session(tmp_path) as session:
        with pytest.raises(ValueError, match=message):
            protocol.load_evidence(session, {})


def test_expected_batch_is_verified_before_reservation(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        with pytest.raises(ValueError, match="batch"):
            _reserve(session, batch=protocol.Batch("rank_9d@16", 5))
        assert not (tmp_path / "attempts.jsonl").exists()


def test_naive_quota_creation_timestamp_is_rejected(tmp_path):
    (tmp_path / "quotas.jsonl").write_text(
        '{"type":"quota_created","quota_id":"q","created_at":"2026-07-22T12:00:00",' '"operator_date":"2026-07-22"}\n'
    )
    with _session(tmp_path) as session:
        with pytest.raises(ValueError, match="timestamp"):
            protocol.load_evidence(session, {})


def test_tampered_reservation_color_is_rejected_during_replay(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        _reserve(session)
    ledger = tmp_path / "attempts.jsonl"
    ledger.write_text(ledger.read_text().replace('"scheduled_color":"B"', '"scheduled_color":"W"'))
    with _session(tmp_path) as session:
        with pytest.raises(ValueError, match="color"):
            protocol.load_evidence(session, {"rank_9d@8": "fp-1"})


def test_stale_same_color_reservation_cannot_break_conclusive_balance(tmp_path):
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        first = _reserve(session)
        presumed_crashed = _reserve(session)
        assert (first.scheduled_color, presumed_crashed.scheduled_color) == ("B", "B")
        protocol.append_attempt_result(session, first, "win", "fp-1")
        with pytest.raises(ValueError, match="color"):
            protocol.append_attempt_result(session, presumed_crashed, "win", "fp-1")


def test_session_ownership_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="session"):
        protocol.create_or_resume_quota(object(), "q", confirm_new=True, operator_date="2026-07-22")
    with _session(tmp_path) as session:
        pass
    with pytest.raises(ValueError, match="session"):
        protocol.load_evidence(session, {})


def test_internal_session_class_and_module_sentinel_cannot_forge_ownership(tmp_path):
    ordinary = (tmp_path / "ordinary").open("a+")
    try:
        with pytest.raises((TypeError, RuntimeError), match="session|construct"):
            protocol._ExperimentSession(tmp_path, ordinary)
        forged = object.__new__(protocol._ExperimentSession)
        forged.path = tmp_path
        forged._lock_file = ordinary
        forged._token = getattr(protocol, "_SESSION_TOKEN", object())
        forged._pid = os.getpid()
        forged._thread_id = threading.get_ident()
        forged._open = True
        with pytest.raises(ValueError, match="session"):
            protocol.create_or_resume_quota(forged, "q-forged", confirm_new=True, operator_date="2026-07-22")
    finally:
        ordinary.close()


@pytest.mark.parametrize("revision", ["", "a" * 39, "a" * 41, "A" * 40, "g" * 40, None, 1])
def test_source_revision_must_be_full_lowercase_sha1(tmp_path, revision):
    with pytest.raises(ValueError, match="source revision"):
        with protocol.experiment_session(tmp_path, revision):
            pass


def test_source_revision_is_caller_supplied_and_bound_to_replay(tmp_path):
    for directory, revision in ((tmp_path / "one", REVISION_ONE), (tmp_path / "two", REVISION_TWO)):
        with _session(directory, revision) as session:
            protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
            reservation = _reserve(session)
            protocol.append_attempt_result(session, reservation, "win", "fp-1")
        header = json.loads((directory / "checkpoints.jsonl").read_text())
        attempt_records = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines()]
        assert header["source_revision"] == revision
        assert reservation.source_revision == revision
        assert {record["source_revision"] for record in attempt_records} == {revision}

    with _session(tmp_path / "one", REVISION_TWO) as session:
        with pytest.raises(ValueError, match="source revision"):
            protocol.load_evidence(session, {"rank_9d@8": "fp-1"})


def test_first_creation_fsyncs_file_and_parent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(protocol, "_fsync_file", lambda handle: calls.append(("file", Path(handle.name).name)))
    monkeypatch.setattr(protocol, "_fsync_directory", lambda path: calls.append(("directory", Path(path))))
    with _session(tmp_path) as session:
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
    assert ("file", "quotas.jsonl") in calls
    assert ("directory", tmp_path) in calls


def test_durability_order_for_quota_checkpoint_reservation_and_result(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(protocol, "_fsync_file", lambda handle: calls.append(("file", Path(handle.name).name)))
    monkeypatch.setattr(protocol, "_fsync_directory", lambda path: calls.append(("directory", Path(path).name)))
    with _session(tmp_path) as session:
        calls.clear()
        protocol.create_or_resume_quota(session, "q1", confirm_new=True, operator_date="2026-07-22")
        assert calls == [("file", "quotas.jsonl"), ("directory", tmp_path.name), ("file", "quotas.jsonl")]

        calls.clear()
        protocol.create_or_resume_quota(session, "q2", confirm_new=True, operator_date="2026-07-22")
        assert calls == [("file", "quotas.jsonl")]

        calls.clear()
        first = _reserve(session)
        checkpoint_last_fsync = max(i for i, call in enumerate(calls) if call == ("file", "checkpoints.jsonl"))
        reservation_first_fsync = min(i for i, call in enumerate(calls) if call == ("file", "attempts.jsonl"))
        assert checkpoint_last_fsync < reservation_first_fsync
        assert ("directory", tmp_path.name) in calls

        calls.clear()
        _reserve(session)
        assert calls == [("file", "attempts.jsonl")]

        calls.clear()
        protocol.append_attempt_result(session, first, "win", "fp-1")
        assert calls == [("file", "attempts.jsonl")]


def test_cross_process_lock_rejects_contention_and_recovers_after_abrupt_exit(tmp_path):
    code = f"""import sys, time
sys.path.insert(0, {str(CALIBRATION_DIR)!r})
import golaxy_9d_alignment as p
with p.experiment_session({str(tmp_path)!r}, {REVISION_ONE!r}):
 print("locked", flush=True)
 time.sleep(60)
"""
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises((BlockingIOError, RuntimeError), match="lock|session"):
            with _session(tmp_path):
                pass
        child.kill()
        child.wait(timeout=10)
        with _session(tmp_path):
            pass
    finally:
        if child.poll() is None:
            child.kill()
