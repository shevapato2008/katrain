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
