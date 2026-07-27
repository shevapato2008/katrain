import sys
from pathlib import Path

CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

import run_golaxy_humansl_rank_alignment as runner


def rows(rank, tier, outcomes):
    return [{"type": "result", "rank": rank, "tier": tier, "outcome": outcome} for outcome in outcomes]


def test_new_rank_starts_at_eight_visits():
    assert runner.next_action([], 5) == runner.Action("rank_5d@8", "screen")


def test_binary_search_moves_up_after_weak_screen():
    evidence = rows(5, "8", ["loss", "win", "loss", "loss"])
    assert runner.next_action(evidence, 5) == runner.Action("rank_5d@16", "screen")


def test_binary_search_moves_down_after_strong_screen():
    evidence = rows(5, "8", ["win", "win", "loss", "win"])
    assert runner.next_action(evidence, 5) == runner.Action("rank_5d@4", "screen")


def test_lower_boundary_selects_four_and_reuses_existing_games():
    evidence = rows(7, "4", ["win"] * 5) + rows(7, "1s", ["loss", "win", "loss", "loss"])
    assert runner.next_action(evidence, 7) == runner.Action("rank_7d@4", "confirm")


def test_existing_nine_dan_evidence_needs_only_one_more_at_eight():
    evidence = rows(9, "4", ["loss", "loss", "win", "win", "loss", "win", "loss", "win", "loss", "win"]) + rows(
        9, "8", ["win"] * 9
    )
    assert runner.next_action(evidence, 9) == runner.Action("rank_9d@8", "confirm")


def test_candidate_is_complete_at_ten_valid_games():
    evidence = rows(8, "4", ["win"] * 10) + rows(8, "1s", ["loss", "loss", "win", "loss"])
    assert runner.next_action(evidence, 8) == runner.Decision("rank_8d@4", 10, 10, 0)


def test_seed_results_reuse_completed_rank_seven_through_nine_games():
    evidence = runner.seed_results()
    counts = {}
    for row in evidence:
        counts[(row["rank"], row["tier"], row["outcome"])] = (
            counts.get((row["rank"], row["tier"], row["outcome"]), 0) + 1
        )
    assert counts[(7, "4", "win")] == 5
    assert counts[(8, "4", "win")] == 5
    assert counts[(9, "4", "win")] == 5
    assert counts[(9, "4", "loss")] == 5
    assert counts[(9, "8", "win")] == 9


def test_rank_five_opponent_uses_real_wire_level_2100():
    opponent = runner.opponent(5)
    assert (opponent.golaxy_level_name, opponent.golaxy_api_level) == ("5段", 2100)


def test_one_second_and_search_players_keep_humansl_semantics():
    label, rung, selection = runner.make_player(6, "1s")
    assert (label, selection, rung.net, rung.human_sl_profile, rung.max_visits) == (
        "rank_6d@1s",
        "argmax_human",
        "humanv0",
        "rank_6d",
        1,
    )
    label, rung, selection = runner.make_player(6, "4")
    assert (label, selection, rung.net, rung.human_sl_profile, rung.max_visits) == (
        "rank_6d@4",
        "search",
        "b18",
        "rank_6d",
        4,
    )


def test_initialize_carries_old_results_once(tmp_path):
    ledger = tmp_path / "alignment.jsonl"
    runner.initialize(ledger)
    first = runner.read_jsonl(ledger)
    runner.initialize(ledger)
    second = runner.read_jsonl(ledger)
    assert first == second
    assert first[0]["type"] == "header"
    assert sum(row["type"] == "carry_result" for row in first) == 29


def test_next_color_alternates_only_after_valid_results():
    evidence = rows(5, "8", ["win", "loss"])
    evidence.append({"type": "result", "rank": 5, "tier": "8", "outcome": "inconclusive", "color": "B"})
    assert runner.next_color(evidence, 5, "8") == "B"
