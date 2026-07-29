import dataclasses
import sys
import typing
from pathlib import Path

import pytest


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

import golaxy_alignment_campaign as campaign


def results(stage, player, outcomes):
    return [
        {
            "type": "result",
            "stage": stage,
            "player": player,
            "outcome": outcome,
            "conclusive": outcome != "inconclusive",
        }
        for outcome in outcomes
    ]


def wins(count, total):
    return ["win"] * count + ["loss"] * (total - count)


def b18_history(screen_wins, ten_wins=None):
    outcomes = wins(screen_wins, 4)
    if ten_wins is not None:
        added_wins = ten_wins - screen_wins
        assert 0 <= added_wins <= 6
        outcomes += wins(added_wins, 6)
    return outcomes


def completed_prefix():
    return results("seven_d", "rank_7d@1s", wins(5, 10)) + results("one_star_b18_1", "b18@1", wins(2, 4))


def test_public_records_are_frozen_and_stage_and_grid_order_are_fixed():
    request = campaign.GameRequest("seven_d", "rank_7d@1s", "B", 10, "confirm")
    decision = campaign.StageDecision("seven_d", "completed_at_10", "rank_7d@1s", None, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.color = "W"
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.status = "changed"

    assert campaign.STAGE_ORDER == (
        "seven_d",
        "one_star_b18_1",
        "quasi_5d",
        "quasi_6d",
        "quasi_7d",
        "quasi_8d",
        "quasi_9d",
    )
    assert campaign.GRID == ("1s", "4", "8", "16", "32", "64")


@pytest.mark.parametrize("candidate_index", [-1, True, False, 6, 99])
def test_candidate_index_must_be_a_plain_in_range_integer(candidate_index):
    with pytest.raises(ValueError, match="candidate_index"):
        campaign.summarize_candidate([], "quasi_5d", candidate_index)


@pytest.mark.parametrize(
    ("stage", "player", "candidate_index"),
    [
        ("seven_d", "rank_7d@1s", None),
        ("one_star_b18_1", "b18@1", None),
        ("quasi_5d", "rank_4d@8", 2),
    ],
)
def test_candidate_rejects_more_than_ten_valid_results(stage, player, candidate_index):
    with pytest.raises(ValueError, match="more than 10 valid"):
        campaign.summarize_candidate(results(stage, player, wins(6, 11)), stage, candidate_index)


def test_next_action_return_annotation_matches_runtime_variants():
    assert typing.get_type_hints(campaign.next_action)["return"] == campaign.GameRequest | campaign.CampaignDecision


def test_seven_d_reuses_seven_valid_results_and_completes_at_ten():
    records = results("seven_d", "rank_7d@1s", wins(4, 7))
    assert campaign.next_action(records) == campaign.GameRequest("seven_d", "rank_7d@1s", "W", 10, "confirm")

    decision = campaign.stage_decision(records + results("seven_d", "rank_7d@1s", wins(2, 3)), "seven_d")
    assert (decision.status, decision.selected_player) == ("completed_at_10", "rank_7d@1s")


@pytest.mark.parametrize(
    ("screen_wins", "ten_wins", "status"),
    [
        (0, None, "weak_screen"),
        (2, None, "weak_screen"),
        (3, 3, "weak_at_10"),
        (3, 4, "aligned_at_10"),
        (4, 6, "aligned_at_10"),
        (4, 7, "overstrong_at_10"),
        (4, 10, "overstrong_at_10"),
    ],
)
def test_b18_fixed_point_terminal_statuses(screen_wins, ten_wins, status):
    records = results("seven_d", "rank_7d@1s", wins(5, 10))
    records += results("one_star_b18_1", "b18@1", b18_history(screen_wins, ten_wins))
    decision = campaign.stage_decision(records, "one_star_b18_1")
    assert (decision.status, decision.selected_player) == (status, "b18@1")


def test_b18_weak_first_four_remains_weak_screen_when_trailing_evidence_exists():
    records = results("one_star_b18_1", "b18@1", b18_history(2, 8))
    decision = campaign.stage_decision(records, "one_star_b18_1")
    assert (decision.status, decision.selected_player) == ("weak_screen", "b18@1")


def test_b18_strong_screen_is_extended_to_ten():
    records = results("seven_d", "rank_7d@1s", wins(5, 10))
    records += results("one_star_b18_1", "b18@1", wins(3, 4))
    assert campaign.next_action(records) == campaign.GameRequest("one_star_b18_1", "b18@1", "B", 10, "confirm")


def test_quasi_starts_at_exact_virtual_boundary_midpoint_eight():
    assert campaign.next_action(completed_prefix()) == campaign.GameRequest("quasi_5d", "rank_4d@8", "B", 4, "screen")


@pytest.mark.parametrize(
    ("screens", "expected_tier"),
    [
        ({"8": 3}, "1s"),
        ({"8": 2}, "32"),
        ({"8": 3, "1s": 2}, "4"),
        ({"8": 2, "32": 3}, "16"),
        ({"8": 2, "32": 2}, "64"),
    ],
)
def test_binary_search_uses_exact_floor_midpoints_and_both_endpoints(screens, expected_tier):
    records = completed_prefix()
    for tier, win_count in screens.items():
        records += results("quasi_5d", f"rank_4d@{tier}", wins(win_count, 4))
    assert campaign.next_action(records).player == f"rank_4d@{expected_tier}"


@pytest.mark.parametrize("win_count", [0, 1, 2])
def test_four_game_weak_classification(win_count):
    candidate = campaign.summarize_candidate(results("quasi_5d", "rank_4d@8", wins(win_count, 4)), "quasi_5d", 2)
    assert candidate.classification == "weak"


@pytest.mark.parametrize("win_count", [3, 4])
def test_four_game_strong_classification(win_count):
    candidate = campaign.summarize_candidate(results("quasi_5d", "rank_4d@8", wins(win_count, 4)), "quasi_5d", 2)
    assert candidate.classification == "strong"


def test_colors_alternate_independently_per_candidate():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", ["win", "loss", "win", "win"])
    first_at_one_second = campaign.next_action(records)
    assert first_at_one_second.color == "B"

    records += results("quasi_5d", "rank_4d@1s", ["loss"])
    assert campaign.next_action(records).color == "W"


def test_inconclusive_repeats_color_and_does_not_advance_valid_denominator():
    records = completed_prefix() + results("quasi_5d", "rank_4d@8", ["win", "inconclusive"])
    request = campaign.next_action(records)
    assert request == campaign.GameRequest("quasi_5d", "rank_4d@8", "W", 4, "screen")
    candidate = campaign.summarize_candidate(records, "quasi_5d", 2)
    assert (candidate.valid, candidate.inconclusive) == (1, 1)


def test_no_strong_candidate_at_upper_endpoint_has_best_observed():
    records = completed_prefix()
    for tier in ("8", "32", "64"):
        records += results("quasi_5d", f"rank_4d@{tier}", wins(2, 4))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "no_strong_candidate_in_grid"
    assert decision.selected_player is None
    assert decision.best_observed is not None


@pytest.mark.parametrize("win_count", [4, 5, 6])
def test_lowest_strong_confirmed_near_five_is_aligned(win_count):
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(win_count, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("aligned_at_10", "rank_4d@4")


def test_overstrong_at_grid_floor_terminates_without_lower_neighbor():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(8, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("overstrong_at_grid_floor", "rank_4d@1s")


def test_overstrong_confirmation_requests_lower_neighbor_then_selects_closest_with_lower_tie_break():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(8, 10))
    assert campaign.next_action(records) == campaign.GameRequest("quasi_5d", "rank_4d@1s", "B", 10, "compare_lower")

    records += results("quasi_5d", "rank_4d@1s", wins(2, 6))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "selected_closest_confirmed"
    assert decision.selected_player == "rank_4d@1s"
    assert decision.best_observed.player == "rank_4d@1s"


def test_weak_confirmation_walks_upward_until_first_qualified_candidate():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(3, 10))
    assert campaign.next_action(records).player == "rank_4d@8"
    assert campaign.next_action(records).phase == "confirm_upward"

    records += results("quasi_5d", "rank_4d@8", ["loss"] * 6)
    assert campaign.next_action(records).player == "rank_4d@16"
    records += results("quasi_5d", "rank_4d@16", wins(4, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert (decision.status, decision.selected_player) == ("selected_closest_confirmed", "rank_4d@16")


def test_upward_grid_exhaustion_reports_best_confirmed_observation():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@8", wins(3, 4))
    records += results("quasi_5d", "rank_4d@1s", wins(2, 4))
    records += results("quasi_5d", "rank_4d@4", wins(3, 10))
    records += results("quasi_5d", "rank_4d@8", ["loss"] * 6)
    for tier, win_count in (("16", 2), ("32", 3), ("64", 3)):
        records += results("quasi_5d", f"rank_4d@{tier}", wins(win_count, 10))
    decision = campaign.stage_decision(records, "quasi_5d")
    assert decision.status == "no_qualified_candidate_in_grid"
    assert decision.selected_player is None
    assert decision.best_observed.player == "rank_4d@4"


def test_final_ranking_uses_distance_then_index_and_excludes_four_game_screens():
    records = completed_prefix()
    records += results("quasi_5d", "rank_4d@1s", wins(4, 4))
    records += results("quasi_5d", "rank_4d@4", wins(7, 10))
    records += results("quasi_5d", "rank_4d@8", wins(3, 10))
    records += results("quasi_5d", "rank_4d@16", wins(5, 10))
    ranked = campaign.rank_confirmed(records, "quasi_5d")
    assert [item.player for item in ranked] == ["rank_4d@16", "rank_4d@4", "rank_4d@8"]


def test_all_quasi_stages_use_the_supplied_lower_rank_profile_and_campaign_terminates():
    records = completed_prefix()
    for stage in campaign.STAGE_ORDER[2:]:
        profile = campaign.QUASI_PROFILES[stage]
        assert campaign.next_action(records).player == f"{profile}@8"
        records += results(stage, f"{profile}@8", wins(3, 4))
        records += results(stage, f"{profile}@1s", wins(2, 4))
        records += results(stage, f"{profile}@4", wins(5, 10))

    terminal = campaign.next_action(records)
    assert terminal.status == "completed"
    assert tuple(item.stage for item in terminal.stages) == campaign.STAGE_ORDER
