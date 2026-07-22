import dataclasses
import importlib
import sys
from pathlib import Path

import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE

CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
runner = importlib.import_module("run_golaxy_9d_alignment")


def test_alignment_search_player_uses_the_frozen_b18_pikl_recipe():
    label, rung, selection = runner.make_alignment_player("rank_9d@8")

    assert label == "rank_9d@8"
    assert rung.net == "b18"
    assert rung.mechanism == "humansl_search"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 8
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert rung.human_sl_params is not HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_alignment_one_visit_player_uses_human_policy_argmax():
    label, rung, selection = runner.make_alignment_player("rank_9d@1s")

    assert label == "rank_9d@1s"
    assert rung.net == "humanv0"
    assert rung.mechanism == "humansl"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 1
    assert rung.human_sl_params == {}
    assert selection == "argmax_human"


@pytest.mark.parametrize(
    "player",
    ["rank_9d@1", "rank_8d@8", "rank_9d@2", "rank_9d@7", "rank_9d@64", "b28@8", None],
)
def test_alignment_player_rejects_plain_one_and_every_non_grid_spec(player):
    with pytest.raises(ValueError, match="candidate"):
        runner.make_alignment_player(player)


def test_alignment_player_rejects_drifted_strength_spec(monkeypatch):
    original = runner.run_selfplay.make_player

    def drifted(player, **kwargs):
        label, rung, selection = original(player, **kwargs)
        return label, dataclasses.replace(rung, net="b28"), selection

    monkeypatch.setattr(runner.run_selfplay, "make_player", drifted)

    with pytest.raises(ValueError, match="strength spec"):
        runner.make_alignment_player("rank_9d@8")


def test_alignment_player_rejects_drifted_effective_query(monkeypatch):
    original = runner.run_selfplay.adapters.build_ladder_analysis_query

    def drifted(*args, **kwargs):
        query = original(*args, **kwargs)
        query["maxVisits"] += 1
        return query

    monkeypatch.setattr(runner.run_selfplay.adapters, "build_ladder_analysis_query", drifted)

    with pytest.raises(ValueError, match="effective query"):
        runner.make_alignment_player("rank_9d@8")


def test_alignment_player_rejects_unexpected_effective_query_controls(monkeypatch):
    original = runner.run_selfplay.adapters.build_ladder_analysis_query

    def drifted(*args, **kwargs):
        query = original(*args, **kwargs)
        query["maxTime"] = 1.0
        return query

    monkeypatch.setattr(runner.run_selfplay.adapters, "build_ladder_analysis_query", drifted)

    with pytest.raises(ValueError, match="effective query"):
        runner.make_alignment_player("rank_9d@8")


def test_golaxy_9d_rung_is_only_an_immutable_opponent_descriptor():
    rung = runner.golaxy_9d_opponent()

    assert rung.rung == 33
    assert rung.golaxy_api_level == 3000
    assert rung is runner.get_rung(33)
    assert rung is not runner.make_alignment_player("rank_9d@8")[1]
