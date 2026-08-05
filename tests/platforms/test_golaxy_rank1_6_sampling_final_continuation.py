import importlib
import subprocess
import sys
from pathlib import Path


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))


def test_final_continuation_fills_six_games_for_the_four_remaining_matchups():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_final_continuation")

    assert campaign.LEDGER_PROTOCOL == "golaxy-humansl-rank1-6-sampling-final-continuation-v4"
    assert campaign.PARENT_SHA256 == "b5f3878c2c162d2b6b350c1a570b1d82c71a95a0d35a43447a1302adef4dcc37"
    assert campaign.VALID_SLOTS_PER_STAGE == 6
    assert campaign.FIRST_HUMANSL_COLOR == "B"
    assert campaign.STAGES == (
        ("sampling_quasi_4d", "rank_4d@1", 1800),
        ("sampling_4d", "rank_4d@1", 1900),
        ("sampling_5d", "rank_5d@1", 2100),
        ("sampling_6d", "rank_6d@1", 2300),
    )

    records = []
    for stage, player, api_level in campaign.STAGES:
        for slot in range(6):
            color = "B" if slot % 2 == 0 else "W"
            request = campaign.next_action(records)
            assert request == campaign.GameRequest(stage, player, api_level, slot, color)
            records.append(
                {
                    "type": "result",
                    "origin_id": f"{stage}:{slot}",
                    "stage": stage,
                    "player": player,
                    "slot": slot,
                    "color": color,
                    "outcome": "win",
                }
            )
    assert campaign.next_action(records).status == "completed"
    assert len(records) == 24


def test_final_continuation_inherits_completed_first_continuation_identity():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_final_continuation")
    assert campaign._read_parent()["status"] == "ok"


def test_final_continuation_runner_and_script_use_final_protocol(tmp_path):
    campaign = importlib.import_module("golaxy_rank1_6_sampling_final_continuation")
    runner = importlib.import_module("run_golaxy_rank1_6_sampling_final_continuation")
    request = campaign.next_action([])
    assert runner.player_for_request(request).label == "rank_4d@1"
    assert runner.opponent_for_request(request).golaxy_api_level == 1800

    ledger = tmp_path / "final-continuation.jsonl"
    campaign.initialize_campaign(ledger, "final-continuation-entrypoint-check", seed=1)
    script = CALIBRATION / "run_golaxy_rank1_6_sampling_final_continuation.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--out", str(ledger), "--summary"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"stage": "sampling_quasi_4d"' in completed.stdout
