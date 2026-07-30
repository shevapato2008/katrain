import dataclasses
import importlib
import sys
from pathlib import Path

import pytest


CALIBRATION = Path(__file__).resolve().parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

campaign = importlib.import_module("golaxy_sampling_campaign")


def result(
    origin_id,
    *,
    stage="sampling_quasi_5d",
    player="rank_5d@1",
    slot=0,
    color="B",
    outcome="win",
):
    return {
        "type": "result",
        "origin_id": origin_id,
        "stage": stage,
        "player": player,
        "slot": slot,
        "color": color,
        "outcome": outcome,
    }


def completed_stage(stage_index, *, origin_prefix=None):
    stage, player, _api_level = campaign.STAGES[stage_index]
    prefix = origin_prefix or stage
    return [
        result(
            f"{prefix}-{slot}",
            stage=stage,
            player=player,
            slot=slot,
            color="B" if slot % 2 == 0 else "W",
            outcome="win" if slot < 6 else "loss",
        )
        for slot in range(10)
    ]


def test_protocol_mapping_and_frozen_value_objects_are_exact():
    assert campaign.STAGES == (
        ("sampling_quasi_5d", "rank_5d@1", 25),
        ("sampling_quasi_6d", "rank_6d@1", 27),
        ("sampling_quasi_7d", "rank_7d@1", 29),
        ("sampling_quasi_8d", "rank_8d@1", 31),
        ("sampling_quasi_9d", "rank_9d@1", 32),
    )
    assert campaign.STAGE_ORDER == tuple(stage for stage, _player, _level in campaign.STAGES)

    for value in (
        campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B"),
        campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 0, 0, 0, 0),
        campaign.StageDecision(
            "sampling_quasi_5d",
            "completed",
            campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 10, 6, 4, 0),
        ),
        campaign.CampaignDecision("completed", ()),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            value.status = "changed"


def test_empty_campaign_requests_humansl_as_black_in_first_slot():
    assert campaign.next_action([]) == campaign.GameRequest(
        stage="sampling_quasi_5d",
        player="rank_5d@1",
        golaxy_api_level=25,
        slot=0,
        color="B",
    )


@pytest.mark.parametrize("stage_index", range(len(campaign.STAGES)), ids=campaign.STAGE_ORDER)
def test_each_stage_alternates_ten_conclusive_slots_and_advances_exactly(stage_index):
    records = [row for prefix_index in range(stage_index) for row in completed_stage(prefix_index)]
    stage, player, api_level = campaign.STAGES[stage_index]
    requested_colors = []
    for slot in range(10):
        action = campaign.next_action(records)
        expected_color = "B" if slot % 2 == 0 else "W"
        assert action == campaign.GameRequest(stage, player, api_level, slot, expected_color)
        requested_colors.append(action.color)
        records.append(
            result(
                f"{stage}-game-{slot}",
                stage=stage,
                player=player,
                slot=action.slot,
                color=action.color,
                outcome="win" if slot % 3 else "loss",
            )
        )

    assert requested_colors == ["B", "W"] * 5
    assert campaign.summarize_candidate(records, stage) == campaign.CandidateSummary(
        stage=stage,
        player=player,
        golaxy_api_level=api_level,
        valid=10,
        wins=6,
        losses=4,
        inconclusive=0,
    )

    action = campaign.next_action(records)
    if stage_index + 1 < len(campaign.STAGES):
        next_stage, next_player, next_api_level = campaign.STAGES[stage_index + 1]
        assert action == campaign.GameRequest(next_stage, next_player, next_api_level, 0, "B")
    else:
        assert isinstance(action, campaign.CampaignDecision)
        assert action.status == "completed"


def test_inconclusive_does_not_enter_denominator_and_retries_same_slot_and_color():
    records = [result("attempt-1", outcome="inconclusive")]

    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 0, "B")
    assert campaign.summarize_candidate(records, "sampling_quasi_5d").inconclusive == 1

    records.append(result("attempt-2", outcome="win"))
    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_5d", "rank_5d@1", 25, 1, "W")


def test_ten_valid_results_complete_stage_and_advance_in_fixed_order():
    records = completed_stage(0)

    assert campaign.stage_decision(records, "sampling_quasi_5d") == campaign.StageDecision(
        stage="sampling_quasi_5d",
        status="completed",
        summary=campaign.CandidateSummary("sampling_quasi_5d", "rank_5d@1", 25, 10, 6, 4, 0),
    )
    assert campaign.next_action(records) == campaign.GameRequest("sampling_quasi_6d", "rank_6d@1", 27, 0, "B")


def test_all_five_stages_complete_campaign_with_stage_summaries():
    records = [row for stage_index in range(5) for row in completed_stage(stage_index)]

    decision = campaign.next_action(records)

    assert isinstance(decision, campaign.CampaignDecision)
    assert decision.status == "completed"
    assert tuple(stage.stage for stage in decision.stages) == campaign.STAGE_ORDER
    assert all(stage.status == "completed" and stage.summary.valid == 10 for stage in decision.stages)


@pytest.mark.parametrize(
    "bad_record",
    [
        result("bad", stage="sampling_quasi_10d"),
        result("bad", player="rank_5d@4"),
        result("bad", color="X"),
        result("bad", color="W"),
        result("bad", slot=-1),
        result("bad", slot=10),
        result("bad", slot=True),
        result("bad", outcome="draw"),
        {"type": "mystery", "origin_id": "bad"},
    ],
)
def test_unknown_or_illegal_result_fields_are_rejected(bad_record):
    with pytest.raises(ValueError):
        campaign.next_action([bad_record])


def test_result_must_describe_the_current_effective_slot():
    with pytest.raises(ValueError, match="slot"):
        campaign.next_action([result("future", slot=1, color="W")])


def test_duplicate_result_origin_ids_are_rejected():
    records = [result("same"), result("same", outcome="inconclusive")]

    with pytest.raises(ValueError, match="origin_id"):
        campaign.next_action(records)


def test_more_than_ten_valid_results_for_a_stage_are_rejected():
    records = completed_stage(0)
    records.append(result("eleventh", slot=9, color="W", outcome="win"))

    with pytest.raises(ValueError, match="more than 10 valid results"):
        campaign.next_action(records)


@pytest.mark.parametrize(
    "records",
    [
        [{"type": "stopped"}],
        [result("first"), {"type": "stopped", "reason": "operator stop"}],
        completed_stage(0) + [{"type": "stopped", "origin_id": "optional-stop-id"}],
    ],
)
def test_any_stopped_record_stops_campaign_without_a_game_request(records):
    decision = campaign.next_action(records)

    assert isinstance(decision, campaign.CampaignDecision)
    assert decision.status == "stopped"
