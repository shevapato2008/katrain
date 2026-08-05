import importlib
import subprocess
import sys
from pathlib import Path


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))


def test_first_continuation_fills_the_five_missing_3d_games_white_first():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_continuation")

    assert campaign.LEDGER_PROTOCOL == "golaxy-humansl-rank1-6-sampling-continuation-v3"
    assert campaign.PARENT_SHA256 == "e40e0c4a63b5861c05d5deebb14725d3f6abda6bbb846f4a46dc938c75e34ba9"
    assert campaign.VALID_SLOTS_PER_STAGE == 5
    assert campaign.FIRST_HUMANSL_COLOR == "W"
    assert campaign.STAGES == (("sampling_3d", "rank_3d@1", 1700),)

    records = []
    for slot, color in enumerate(("W", "B", "W", "B", "W")):
        request = campaign.next_action(records)
        assert request == campaign.GameRequest("sampling_3d", "rank_3d@1", 1700, slot, color)
        records.append(
            {
                "type": "result",
                "origin_id": f"continuation:{slot}",
                "stage": request.stage,
                "player": request.player,
                "slot": request.slot,
                "color": request.color,
                "outcome": "win",
            }
        )
    assert campaign.next_action(records).status == "completed"


def test_first_continuation_inherits_identity_from_the_stopped_extension():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_continuation")
    identity = campaign._read_parent()
    assert identity["status"] == "ok"
    assert identity["models"]["b28"]["running"] is True


def test_first_continuation_runner_uses_continuation_protocol():
    campaign = importlib.import_module("golaxy_rank1_6_sampling_continuation")
    runner = importlib.import_module("run_golaxy_rank1_6_sampling_continuation")
    request = campaign.next_action([])
    assert runner.player_for_request(request).label == "rank_3d@1"
    assert runner.opponent_for_request(request).golaxy_api_level == 1700


def test_first_continuation_script_entrypoint_calls_main(tmp_path):
    campaign = importlib.import_module("golaxy_rank1_6_sampling_continuation")
    ledger = tmp_path / "continuation.jsonl"
    campaign.initialize_campaign(ledger, "continuation-entrypoint-check", seed=1)
    script = CALIBRATION / "run_golaxy_rank1_6_sampling_continuation.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--out", str(ledger), "--summary"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert '"color": "W"' in completed.stdout
    assert '"stage": "sampling_3d"' in completed.stdout
