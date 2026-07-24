import importlib
import inspect
import sys
from pathlib import Path

import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE
from katrain.core.ladder_calibration import GameOutcome

CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
fixed = importlib.import_module("run_golaxy_fixed_screen")


def test_fixed_players_are_only_five_and_six_visits():
    assert fixed.PLAYERS == ("rank_9d@5", "rank_9d@6")
    for player in fixed.PLAYERS:
        label, rung, selection = fixed.make_fixed_player(player)
        assert label == player
        assert rung.net == "b18"
        assert rung.max_visits == int(player.rsplit("@", 1)[1])
        assert rung.human_sl_profile == "rank_9d"
        assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
        assert selection == "search"

    with pytest.raises(ValueError, match="fixed-screen player"):
        fixed.make_fixed_player("rank_9d@8")


def test_eight_d_preset_is_exact_and_builds_rank_eight_player():
    spec = fixed.GOLAXY_8D_PRESET
    assert spec.name == "golaxy8d-rank8d4-20260724"
    assert spec.players == ("rank_8d@4",)
    assert spec.starting_colors == (("rank_8d@4", "B"),)
    assert spec.valid_per_player == 5
    assert spec.charged_cap == 9
    assert (spec.golaxy_rung, spec.golaxy_level_name, spec.golaxy_api_level) == (31, "8段", 2800)
    assert spec.expected_out_dir.name == "golaxy_8d_rank_8d_4_20260724"

    label, rung, selection = fixed.make_fixed_player("rank_8d@4", spec)
    assert label == "rank_8d@4"
    assert rung.net == "b18"
    assert rung.max_visits == 4
    assert rung.human_sl_profile == "rank_8d"
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_eight_d_preset_schedules_five_valid_games_and_repeats_inconclusive_color():
    spec = fixed.GOLAXY_8D_PRESET
    records = []
    for color in ("B", "W", "B", "W", "B"):
        game = fixed.next_game(records, spec)
        assert game == fixed.FixedGame("rank_8d@4", color)
        records.append({"type": "result", "player": game.player, "color": game.color, "outcome": "win"})
    assert fixed.next_game(records, spec) is None

    inconclusive = [{"type": "result", "player": "rank_8d@4", "color": "B", "outcome": "inconclusive"}]
    assert fixed.next_game(inconclusive, spec) == fixed.FixedGame("rank_8d@4", "B")


def test_seven_d_preset_is_exact_and_builds_rank_seven_player():
    spec = fixed.GOLAXY_7D_PRESET
    assert spec.name == "golaxy7d-rank7d4-20260724"
    assert spec.players == ("rank_7d@4",)
    assert spec.starting_colors == (("rank_7d@4", "B"),)
    assert spec.valid_per_player == 5
    assert spec.charged_cap == 9
    assert (spec.golaxy_rung, spec.golaxy_level_name, spec.golaxy_api_level) == (29, "7段", 2500)
    assert spec.expected_out_dir.name == "golaxy_7d_rank_7d_4_20260724"

    label, rung, selection = fixed.make_fixed_player("rank_7d@4", spec)
    assert label == "rank_7d@4"
    assert rung.net == "b18"
    assert rung.max_visits == 4
    assert rung.human_sl_profile == "rank_7d"
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert selection == "search"
    assert fixed.fixed_opponent(spec).golaxy_api_level == 2500


def test_seven_d_preset_schedules_five_games_and_freezes_header_cap_and_output(tmp_path):
    spec = fixed.GOLAXY_7D_PRESET
    records = []
    for color in ("B", "W", "B", "W", "B"):
        game = fixed.next_game(records, spec)
        assert game == fixed.FixedGame("rank_7d@4", color)
        records.append({"type": "result", "player": game.player, "color": game.color, "outcome": "win"})
    assert fixed.next_game(records, spec) is None
    assert fixed.validate_output_path(str(spec.expected_out_dir), spec) == spec.expected_out_dir

    ledger = fixed.FixedLedger.create(tmp_path, "golaxy7d-20260724", "f" * 40, spec)
    assert ledger.records()[0]["golaxy"] == {"rung": 29, "level_name": "7段", "api_level": 2500}
    for _ in range(9):
        ledger.reserve(fixed.FixedGame("rank_7d@4", "B"), "fingerprint")
    with pytest.raises(ValueError, match="9 charged"):
        ledger.reserve(fixed.FixedGame("rank_7d@4", "B"), "fingerprint")


def test_three_star_conditional_preset_is_exact():
    spec = fixed.GOLAXY_3STAR_PRESET
    assert spec.name == "golaxy3star-rank9d-conditional-20260725"
    assert spec.players == (
        "rank_9d@8",
        "rank_9d@16",
        "rank_9d@32",
        "rank_9d@64",
        "rank_9d@4",
        "rank_9d@2",
    )
    assert spec.valid_per_player == 5
    assert spec.charged_cap == 32
    assert (spec.golaxy_rung, spec.golaxy_level_name, spec.golaxy_api_level) == (36, "星阵3星", 3300)
    assert spec.expected_out_dir.name == "golaxy_3star_rank_9d_conditional_20260725"
    assert fixed.fixed_opponent(spec).golaxy_api_level == 3300


def _five_results(player, outcomes):
    return [
        {"type": "result", "player": player, "color": color, "outcome": outcome}
        for color, outcome in zip(("B", "W", "B", "W", "B"), outcomes)
    ]


def test_three_star_five_zero_at_eight_goes_down_and_skips_upper_visits():
    spec = fixed.GOLAXY_3STAR_PRESET
    records = _five_results("rank_9d@8", ["win"] * 5)
    assert fixed.next_game(records, spec) == fixed.FixedGame("rank_9d@4", "B")

    records += _five_results("rank_9d@4", ["win"] * 5)
    assert fixed.next_game(records, spec) == fixed.FixedGame("rank_9d@2", "B")

    records += _five_results("rank_9d@2", ["win", "loss", "win", "loss", "win"])
    assert fixed.next_game(records, spec) is None


def test_three_star_non_sweep_at_eight_runs_upper_visits_in_order():
    spec = fixed.GOLAXY_3STAR_PRESET
    records = _five_results("rank_9d@8", ["win", "win", "win", "win", "loss"])
    assert fixed.next_game(records, spec) == fixed.FixedGame("rank_9d@16", "B")

    for player, next_player in (("rank_9d@16", "rank_9d@32"), ("rank_9d@32", "rank_9d@64")):
        records += _five_results(player, ["win"] * 5)
        assert fixed.next_game(records, spec) == fixed.FixedGame(next_player, "B")

    records += _five_results("rank_9d@64", ["win"] * 5)
    assert fixed.next_game(records, spec) is None


def test_three_star_inconclusive_repeats_same_player_and_color():
    spec = fixed.GOLAXY_3STAR_PRESET
    records = [{"type": "result", "player": "rank_9d@8", "color": "B", "outcome": "inconclusive"}]
    assert fixed.next_game(records, spec) == fixed.FixedGame("rank_9d@8", "B")


def test_next_game_runs_five_then_six_with_opposite_starting_colors():
    records = []
    expected = [
        ("rank_9d@5", "B"),
        ("rank_9d@5", "W"),
        ("rank_9d@5", "B"),
        ("rank_9d@5", "W"),
        ("rank_9d@5", "B"),
        ("rank_9d@6", "W"),
        ("rank_9d@6", "B"),
        ("rank_9d@6", "W"),
        ("rank_9d@6", "B"),
        ("rank_9d@6", "W"),
    ]
    for player, color in expected:
        game = fixed.next_game(records)
        assert (game.player, game.color) == (player, color)
        records.append({"type": "result", "player": player, "color": color, "outcome": "win"})
    assert fixed.next_game(records) is None


def test_inconclusive_does_not_advance_player_or_color():
    records = [{"type": "result", "player": "rank_9d@5", "color": "B", "outcome": "inconclusive"}]
    assert fixed.next_game(records) == fixed.FixedGame("rank_9d@5", "B")


def test_reservation_cap_is_twenty(tmp_path):
    ledger = fixed.FixedLedger.create(tmp_path, "quota-20260724", "f" * 40)
    for attempt_id in range(1, 21):
        reservation = ledger.reserve(fixed.FixedGame("rank_9d@5", "B"), "fingerprint")
        assert reservation.attempt_id == attempt_id
    with pytest.raises(ValueError, match="20 charged"):
        ledger.reserve(fixed.FixedGame("rank_9d@5", "B"), "fingerprint")


def test_eight_d_ledger_header_and_reservation_cap_are_frozen(tmp_path):
    spec = fixed.GOLAXY_8D_PRESET
    ledger = fixed.FixedLedger.create(tmp_path, "golaxy8d-20260724", "f" * 40, spec)
    assert ledger.records()[0] == {
        "type": "header",
        "quota_id": "golaxy8d-20260724",
        "source_revision": "f" * 40,
        "preset": "golaxy8d-rank8d4-20260724",
        "players": ["rank_8d@4"],
        "charged_cap": 9,
        "golaxy": {"rung": 31, "level_name": "8段", "api_level": 2800},
    }
    for attempt_id in range(1, 10):
        reservation = ledger.reserve(fixed.FixedGame("rank_8d@4", "B"), "fingerprint")
        assert reservation.attempt_id == attempt_id
    with pytest.raises(ValueError, match="9 charged"):
        ledger.reserve(fixed.FixedGame("rank_8d@4", "B"), "fingerprint")

    resumed = fixed.FixedLedger.open(tmp_path, "golaxy8d-20260724", "f" * 40, spec)
    assert resumed.spec == spec


def test_result_append_is_durable_and_rejects_duplicates(tmp_path):
    ledger = fixed.FixedLedger.create(tmp_path, "quota-20260724", "f" * 40)
    reservation = ledger.reserve(fixed.FixedGame("rank_9d@5", "B"), "fingerprint")
    ledger.append_result(reservation, "win", "fingerprint")

    resumed = fixed.FixedLedger.open(tmp_path, "quota-20260724", "f" * 40)
    assert fixed.next_game(resumed.records()) == fixed.FixedGame("rank_9d@5", "W")
    with pytest.raises(ValueError, match="duplicate result"):
        resumed.append_result(reservation, "loss", "fingerprint")


def test_shared_preflight_accepts_an_explicit_player_factory():
    assert "player_factory" in inspect.signature(fixed.alignment.common_preflight).parameters


def test_summary_reports_each_fixed_candidate(tmp_path):
    ledger = fixed.FixedLedger.create(tmp_path, "quota-20260724", "f" * 40)
    for outcome in ("win", "loss"):
        game = fixed.next_game(ledger.records())
        reservation = ledger.reserve(game, "fingerprint")
        ledger.append_result(reservation, outcome, "fingerprint")

    summary = fixed.summarize(ledger)
    assert summary["charged_attempts"] == 2
    assert summary["players"]["rank_9d@5"] == {"wins": 1, "losses": 1, "inconclusive": 0, "valid": 2}
    assert summary["next_game"] == {"player": "rank_9d@5", "color": "B"}


def test_outcome_classification_is_fail_closed():
    def outcome(result, our_win, conclusive):
        return GameOutcome("B", result, our_win, 100, 1.0, conclusive)

    assert fixed.classify_outcome(outcome("our_win", True, True)) == "win"
    assert fixed.classify_outcome(outcome("our_loss", False, True)) == "loss"
    assert fixed.classify_outcome(outcome("inconclusive_unstable", False, False)) == "inconclusive"
    with pytest.raises(ValueError, match="unexpected fixed-screen outcome"):
        fixed.classify_outcome(outcome("transport_error", False, False))


def test_cli_requires_explicit_quota_for_live_mode():
    args = fixed.build_parser().parse_args(
        ["--expected-source-revision", "f" * 40, "--out", "/tmp/out", "--base-url", "http://127.0.0.1:8000"]
    )
    with pytest.raises(ValueError, match="quota-id"):
        fixed.validate_args(args)


def test_cli_selects_eight_d_preset_and_requires_its_exact_output_path(tmp_path):
    args = fixed.build_parser().parse_args(
        [
            "--preset",
            "golaxy8d-rank8d4-20260724",
            "--preflight-only",
            "--expected-source-revision",
            "f" * 40,
            "--out",
            str(fixed.GOLAXY_8D_PRESET.expected_out_dir),
            "--base-url",
            "http://127.0.0.1:8000",
        ]
    )
    spec = fixed.resolve_preset(args.preset)
    assert spec is fixed.GOLAXY_8D_PRESET
    assert fixed.validate_output_path(args.out, spec) == spec.expected_out_dir
    with pytest.raises(ValueError, match="output must be exactly"):
        fixed.validate_output_path(str(tmp_path), spec)
