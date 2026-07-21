import importlib
import sys
from pathlib import Path

import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE


CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
selfplay = importlib.import_module("run_selfplay")


def test_player_constructs_attested_b18_humansl_search_recipe():
    label, rung, selection = selfplay.make_player("rank_9d@40")

    assert label == "rank_9d@40"
    assert rung.net == "b18"
    assert rung.mechanism == "humansl_search"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 40
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert rung.human_sl_params is not HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_player_gives_each_humansl_search_player_a_fresh_recipe():
    _, first, _ = selfplay.make_player("rank_5d@40")
    _, second, _ = selfplay.make_player("rank_5d@80")

    assert first.human_sl_params == second.human_sl_params == HUMANSL_PIKL_BASELINE
    assert first.human_sl_params is not second.human_sl_params


@pytest.mark.parametrize(
    ("spec", "mechanism", "net", "selection"),
    [
        ("rank_9d@1", "humansl", "humanv0", "weighted"),
        ("rank_9d@1s", "humansl", "humanv0", "argmax_human"),
        ("b28@20", "net_search", "b28", "search"),
    ],
)
def test_player_preserves_native_and_pure_search_modes(spec, mechanism, net, selection):
    _, rung, actual_selection = selfplay.make_player(spec)

    assert rung.mechanism == mechanism
    assert rung.net == net
    assert rung.human_sl_params == {}
    assert actual_selection == selection


@pytest.mark.parametrize("visits", [2, 7, 16, 32, 39])
def test_player_rejects_unsupported_humansl_search_visits(visits):
    with pytest.raises(ValueError, match=r"HumanSL search.*minimum.*40"):
        selfplay.make_player(f"rank_9d@{visits}")


def test_player_rejects_search_suffix_above_one_visit():
    with pytest.raises(ValueError, match=r"1s"):
        selfplay.make_player("rank_9d@40s")
