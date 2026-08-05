import importlib
import subprocess
import sys
from pathlib import Path


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))


def test_extension_freezes_six_additional_games_for_each_live_matchup():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_extension")

    assert campaign.LEDGER_PROTOCOL == "golaxy-humansl-rank1-6-sampling-extension-v2"
    assert campaign.VALID_SLOTS_PER_STAGE == 6
    assert campaign.PARENT_SHA256 == "9c2fc8c55705687ff3107e3940717b5fa22de996851f1e1274a018df1ea62be7"
    assert len(campaign.STAGES) == 10

    records = []
    for stage, player, api_level in campaign.STAGES:
        for slot in range(6):
            color = "B" if slot % 2 == 0 else "W"
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
    assert len(records) == 60


def test_extension_parent_is_the_completed_four_game_campaign():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_extension")

    identity = campaign._read_parent()
    assert identity["status"] == "ok"
    assert identity["models"]["b18"]["running"] is True
    assert identity["models"]["b28"]["running"] is True


def test_extension_runner_uses_extension_protocol():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_extension")
    runner = importlib.import_module("run_golaxy_rank1_6_sampling_extension")

    request = campaign.next_action([])
    player = runner.player_for_request(request)
    opponent = runner.opponent_for_request(request)
    assert player.label == "rank_1d@1"
    assert player.selection == "weighted"
    assert opponent.golaxy_api_level == 1200


def test_extension_script_entrypoint_calls_main_after_protocol_override(tmp_path):
    campaign = importlib.import_module("golaxy_rank1_6_sampling_extension")
    ledger = tmp_path / "extension.jsonl"
    campaign.initialize_campaign(ledger, "extension-entrypoint-check", seed=1)
    script = CALIBRATION / "run_golaxy_rank1_6_sampling_extension.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--out", str(ledger), "--summary"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"stage": "sampling_quasi_1d"' in completed.stdout
