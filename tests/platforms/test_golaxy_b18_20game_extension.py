import dataclasses
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

CALIBRATION = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION))

extension = importlib.import_module("golaxy_b18_20game_extension")


PARENT = (
    Path(__file__).parents[2]
    / "superpowers/tracks/golaxy-ai-ladder-parity/calibration/results"
    / "golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(visits: int, color: str, result: str, *, conclusive: bool = True, result_id: str | None = None):
    row = {
        "type": "result",
        "visits": visits,
        "color": color,
        "outcome": result,
        "result": result,
        "conclusive": conclusive,
    }
    if result_id is not None:
        row["origin_result_id"] = result_id
    return row


def _conclusive_sequence(visits: int, count: int):
    return [
        _result(visits, "B" if index % 2 == 0 else "W", "our_win" if index % 3 else "our_loss")
        for index in range(count)
    ]


def _write_parent(tmp_path: Path, mutate) -> Path:
    rows = [json.loads(line) for line in PARENT.read_text(encoding="utf-8").splitlines()]
    mutate(rows)
    path = tmp_path / "parent.jsonl"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def test_constants_freeze_approved_campaign():
    assert extension.MODEL == "b18"
    assert extension.MODEL_SHA256 == "9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d"
    assert extension.REFEREE_MODEL == "b28"
    assert extension.REFEREE_MODEL_SHA256 == "798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0"
    assert extension.GOLAXY_LEVEL == 36
    assert extension.GOLAXY_LEVEL_NAME == "星阵3星"
    assert extension.GOLAXY_API_LEVEL == 3300
    assert extension.CANDIDATE_VISITS == (32, 64)
    assert extension.TARGET_CONCLUSIVE == 20
    assert extension.PARENT_SHA256 == "9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082"


def test_campaign_value_objects_are_immutable():
    for cls in (extension.GameRequest, extension.CandidateSummary, extension.CampaignDecision):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen


def test_load_frozen_carries_selects_only_approved_rows_in_parent_order():
    carries = extension.load_frozen_carries(PARENT, extension.PARENT_SHA256)

    assert len(carries) == 14
    assert [row["direct_parent_line"] for row in carries] == [2, 3, 4, 5, 6, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    assert [row["visits"] for row in carries] == [64] * 5 + [32] * 4 + [64] * 5
    assert all(row["type"] == "carry_result" for row in carries)
    assert all(row["direct_parent_sha256"] == extension.PARENT_SHA256 for row in carries)
    assert all(
        row["origin_result_id"] == f"legacy:{extension.PARENT_SHA256}:{row['direct_parent_line']}" for row in carries
    )
    assert all(row["outcome"] == row["result"] for row in carries)
    assert all(row["conclusive"] is True for row in carries)
    assert carries[0]["source_outcome"] == json.loads(PARENT.read_text(encoding="utf-8").splitlines()[1])["outcome"]

    at_32 = extension.summarize_candidate(carries, 32)
    at_64 = extension.summarize_candidate(carries, 64)
    assert at_32 == extension.CandidateSummary(32, 4, 1, 3, 0, 2, 2)
    assert at_64 == extension.CandidateSummary(64, 10, 7, 3, 0, 5, 5)


def test_load_frozen_carries_rejects_changed_parent_bytes(tmp_path):
    changed = tmp_path / "changed.jsonl"
    changed.write_bytes(PARENT.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="SHA256"):
        extension.load_frozen_carries(changed, extension.PARENT_SHA256)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda rows: rows[0].__setitem__("model", "b28"), "model"),
        (lambda rows: rows[1].__setitem__("level", 35), "level"),
        (lambda rows: rows[1].__setitem__("level_name", "星阵2星"), "level_name"),
        (lambda rows: rows[1].__setitem__("api_level", 3200), "api_level"),
        (lambda rows: rows[1].__setitem__("visits", 32), "visits"),
        (lambda rows: rows[1]["outcome"].__setitem__("result", "inconclusive_unsettled"), "outcome"),
        (lambda rows: rows[1]["outcome"].__setitem__("conclusive", False), "conclusive"),
        (lambda rows: rows.__setitem__(2, dict(rows[1])), "duplicate"),
    ],
)
def test_load_frozen_carries_rejects_invalid_selected_source_rows(tmp_path, mutate, message):
    changed = _write_parent(tmp_path, mutate)

    with pytest.raises(ValueError, match=message):
        extension.load_frozen_carries(changed, _sha256(changed))


def test_load_frozen_carries_rejects_wrong_inherited_color_balance(tmp_path):
    changed = _write_parent(tmp_path, lambda rows: rows[16].__setitem__("color", "W"))

    with pytest.raises(ValueError, match="color"):
        extension.load_frozen_carries(changed, _sha256(changed))


def test_scheduler_finishes_32_before_replenishing_64_and_alternates_conclusive_colors():
    inherited = extension.load_frozen_carries(PARENT, extension.PARENT_SHA256)
    assert extension.next_action(inherited) == extension.GameRequest(32, "B")

    evidence = list(inherited) + _conclusive_sequence(32, 16)
    assert extension.next_action(evidence) == extension.GameRequest(64, "B")

    evidence += _conclusive_sequence(64, 10)
    assert extension.next_action(evidence) == extension.CampaignDecision(
        "completed",
        (
            extension.CandidateSummary(32, 20, 11, 9, 0, 10, 10),
            extension.CandidateSummary(64, 20, 13, 7, 0, 10, 10),
        ),
    )


def test_inconclusive_is_replenishable_and_repeats_color():
    evidence = _conclusive_sequence(32, 4)
    evidence.append(_result(32, "B", "inconclusive_unsettled", conclusive=False))

    assert extension.summarize_candidate(evidence, 32) == extension.CandidateSummary(32, 4, 2, 2, 1, 2, 2)
    assert extension.next_action(evidence) == extension.GameRequest(32, "B")


@pytest.mark.parametrize("visits", [0, 16, 128])
def test_scheduler_rejects_unknown_candidate(visits):
    with pytest.raises(ValueError, match="visits"):
        extension.next_action([_result(visits, "B", "our_win")])


def test_scheduler_rejects_more_than_target_conclusive():
    with pytest.raises(ValueError, match="more than 20"):
        extension.next_action(_conclusive_sequence(32, 21))


@pytest.mark.parametrize(
    "row",
    [
        _result(32, "B", "unknown"),
        _result(32, "B", "our_win", conclusive=False),
        _result(32, "B", "inconclusive_score", conclusive=True),
        _result(32, "W", "our_win"),
    ],
)
def test_scheduler_rejects_invalid_outcome_or_color_sequence(row):
    with pytest.raises(ValueError):
        extension.next_action([row])
