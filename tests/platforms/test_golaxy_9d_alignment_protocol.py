import importlib
import sys
from collections import UserDict
from pathlib import Path
from types import MappingProxyType

import pytest

CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
protocol = importlib.import_module("golaxy_9d_alignment")


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
