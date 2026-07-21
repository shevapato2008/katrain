import sys, importlib
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
adapters = importlib.import_module("adapters")
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode
from katrain.core.ladder import get_rung, rung_engine_params


class _MockKaTrain(KaTrainBase):
    pass


class _MockEngine:
    def request_analysis(self, *a, **k):
        pass


class _NoStartHttpEngine(KataGoHttpEngine):
    """REAL KataGoHttpEngine __init__ (so override_settings/config are the genuine values), but
    start() is stubbed so no worker thread / network is created. This is the drift-sensitive
    runtime double."""

    def start(self):
        pass


def _runtime_engine(wide_root_noise):
    kt = _MockKaTrain(force_package_config=True)
    cfg = dict(kt.config("engine"))  # the REAL engine config block from config.json
    cfg["wide_root_noise"] = wide_root_noise
    return _NoStartHttpEngine(kt, cfg)


def _real_current_node(moves):  # moves: list[(player, gtp)]
    # RU=chinese so node.ruleset == "chinese" -> runtime rules == get_rules("chinese") == harness rules
    game = Game(
        _MockKaTrain(force_package_config=True),
        _MockEngine(),
        move_tree=GameNode(properties={"SZ": 19, "RU": "chinese", "KM": 7.5}),
    )
    for player, gtp in moves:
        game.play(Move.from_gtp(gtp, player=player))
    return game.current_node


def _runtime_query(engine, rung, node):
    params = rung_engine_params(rung)
    query, _visits = engine.build_analysis_query(  # real builder on a real engine; real (query, visits)
        node,
        visits=params["visits"],
        extra_settings=params["extra_settings"],
        time_limit=False,
    )
    return query


def _strength_subset_matches(rung, engine, wrn):
    node = _real_current_node([("B", "D4"), ("W", "Q4")])
    runtime = _runtime_query(engine, rung, node)
    harness = adapters.build_ladder_analysis_query([288, 300], rung, 19, 7.5, "chinese", wide_root_noise=wrn)
    return (
        harness["maxVisits"] == runtime["maxVisits"] == rung_engine_params(rung)["visits"]
        and harness["overrideSettings"] == runtime["overrideSettings"]  # EXACT dict equality
        and harness["moves"] == runtime["moves"]
        and (harness["komi"], harness["boardXSize"], harness["boardYSize"], harness["rules"])
        == (runtime["komi"], runtime["boardXSize"], runtime["boardYSize"], runtime["rules"])
        and "maxTime" not in runtime["overrideSettings"]
        and "maxTime" not in harness["overrideSettings"]
    )


@pytest.mark.parametrize("rung_n", [20, 1, 32])  # 20=1K humansl; 1=20K humansl+temp(1.1); 32=准9D net_search
def test_harness_query_equals_runtime_strength_subset(rung_n):
    """Exact-equality parity vs a REAL KataGoHttpEngine's build_analysis_query, across the three
    mechanism/knob classes. wideRootNoise from ONE source (the real engine config)."""
    eng = _runtime_engine(0.04)
    wrn = adapters.load_engine_wide_root_noise(eng.config)  # single shared source (the real config)
    rung = get_rung(rung_n)
    assert _strength_subset_matches(rung, eng, wrn)
    # sanity: humanSL rungs carry the profile; net_search does not
    q = _runtime_query(eng, rung, _real_current_node([("B", "D4"), ("W", "Q4")]))
    if rung.human_sl_profile:
        assert q["overrideSettings"]["humanSLProfile"] == rung.human_sl_profile
    else:
        assert "humanSLProfile" not in q["overrideSettings"]


def test_contract_fails_on_runtime_override_drift():
    """If a future engine adds an override the harness doesn't replicate, the contract MUST break.
    Proves the test actually guards drift (not just passes against a duplicated double)."""
    eng = _runtime_engine(0.04)
    eng.override_settings = {**eng.override_settings, "someFutureKnob": 1}  # simulate runtime drift
    assert not _strength_subset_matches(get_rung(20), eng, 0.04)  # harness lacks the knob -> mismatch
