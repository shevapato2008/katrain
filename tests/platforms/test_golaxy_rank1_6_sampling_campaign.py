import importlib
import subprocess
import sys
from pathlib import Path


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

campaign = importlib.import_module("golaxy_rank1_6_sampling_campaign")
runner = importlib.import_module("run_golaxy_rank1_6_sampling_campaign")


def test_all_matchups_freeze_twelve_requested_comparisons_and_two_carries():
    assert campaign.ALL_MATCHUPS == (
        ("sampling_quasi_1d", "rank_1d@1", 1200, "live"),
        ("sampling_1d", "rank_1d@1", 1300, "live"),
        ("sampling_quasi_2d", "rank_2d@1", 1400, "live"),
        ("sampling_2d", "rank_2d@1", 1500, "live"),
        ("sampling_quasi_3d", "rank_3d@1", 1600, "live"),
        ("sampling_3d", "rank_3d@1", 1700, "live"),
        ("sampling_quasi_4d", "rank_4d@1", 1800, "live"),
        ("sampling_4d", "rank_4d@1", 1900, "live"),
        ("sampling_quasi_5d", "rank_5d@1", 2000, "carry"),
        ("sampling_5d", "rank_5d@1", 2100, "live"),
        ("sampling_quasi_6d", "rank_6d@1", 2200, "carry"),
        ("sampling_6d", "rank_6d@1", 2300, "live"),
    )
    assert campaign.CARRY_STAGES == ("sampling_quasi_5d", "sampling_quasi_6d")
    assert campaign.PARENT_SHA256 == "7b8a3fa348f95fa8756824171631b5a9af30895df2f84e0310aa9d437ef8818e"


def test_live_schedule_contains_only_ten_new_matchups_and_four_alternating_games_each():
    assert len(campaign.STAGES) == 10
    assert campaign.VALID_SLOTS_PER_STAGE == 4
    assert sum(1 for _stage, _player, _level, source in campaign.ALL_MATCHUPS if source == "live") == 10

    records = []
    for stage, player, api_level in campaign.STAGES:
        for slot, color in enumerate(("B", "W", "B", "W")):
            assert campaign.next_action(records) == campaign.GameRequest(stage, player, api_level, slot, color)
            records.append(
                {
                    "type": "result",
                    "origin_id": f"{stage}:{slot}",
                    "stage": stage,
                    "player": player,
                    "slot": slot,
                    "color": color,
                    "outcome": "win" if slot % 2 == 0 else "loss",
                }
            )

    assert campaign.next_action(records).status == "completed"
    assert len(records) == 40


def test_inconclusive_repeats_the_same_slot_and_native_weighted_player_is_enforced():
    first = campaign.next_action([])
    retry = campaign.next_action(
        [
            {
                "type": "result",
                "origin_id": "inconclusive:1",
                "stage": first.stage,
                "player": first.player,
                "slot": first.slot,
                "color": first.color,
                "outcome": "inconclusive",
            }
        ]
    )
    assert retry == first

    player = runner.player_for_request(first)
    assert player.label == "rank_1d@1"
    assert player.selection == "weighted"
    assert player.rung.human_sl_profile == "rank_1d"
    assert player.rung.max_visits == 1


def test_each_live_stage_resolves_to_the_frozen_wire_level():
    expected_names = {
        1200: "准1段",
        1300: "1段",
        1400: "准2段",
        1500: "2段",
        1600: "准3段",
        1700: "3段",
        1800: "准4段",
        1900: "4段",
        2100: "5段",
        2300: "6段",
    }
    for stage, player, api_level in campaign.STAGES:
        opponent = runner.opponent_for_request(campaign.GameRequest(stage, player, api_level, 0, "B"))
        assert opponent.golaxy_api_level == api_level
        assert opponent.golaxy_level_name == expected_names[api_level]


def test_script_entrypoint_uses_rank1_6_protocol_before_calling_main(tmp_path):
    ledger = tmp_path / "campaign.jsonl"
    campaign.initialize_campaign(ledger, "entrypoint-check", seed=1)
    script = CALIBRATION / "run_golaxy_rank1_6_sampling_campaign.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--out", str(ledger), "--summary"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"stage": "sampling_quasi_1d"' in completed.stdout
