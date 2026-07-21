import pytest
from katrain.core.ladder import (
    LADDER_RUNGS,
    get_rung,
    rung_engine_params,
    ladder_override_settings,
    pick_ladder_move,
    gtp_to_colrow,
    colrow_to_golaxy,
    golaxy_to_colrow,
    config_sanity_key,
    MECHANISMS,
)

def test_thirty_seven_rungs():
    assert len(LADDER_RUNGS) == 37 and [r.rung for r in LADDER_RUNGS] == list(range(1, 38))


def test_band_a_native_humansl_ranks():
    # rungs 1..25 = KataGo humanSL native ranks (NOT Golaxy-aligned), human net @ 1 visit
    expected = [f"rank_{n}k" for n in range(20, 0, -1)] + [f"rank_{n}d" for n in range(1, 6)]
    band_a = LADDER_RUNGS[:25]
    assert [r.human_sl_profile for r in band_a] == expected
    for r in band_a:
        assert r.mechanism == "humansl" and r.net == "humanv0" and r.max_visits == 1
        assert r.golaxy_level_name is None and r.golaxy_api_level is None and r.display_elo is None


def test_band_b_golaxy_aligned_strong_tiers():
    # rungs 26..36 = net_search @ default b28, mapped 1:1 to Golaxy 准6段..星阵3星
    band_b = LADDER_RUNGS[25:36]
    assert [r.rank_name for r in band_b] == [
        "准6D", "6D", "准7D", "7D", "准8D", "8D", "准9D", "9D", "职业", "职业顶尖", "超职业",
    ]
    for r in band_b:
        assert r.mechanism == "net_search" and r.net == "b28" and r.human_sl_profile is None
        assert r.golaxy_api_level is not None  # a Golaxy counterpart to calibrate against
    visits = [r.max_visits for r in band_b]  # provisional visits strictly increase
    assert visits == sorted(visits) and len(set(visits)) == len(visits)


def test_ceiling_rung_37_b28():
    r = LADDER_RUNGS[36]
    assert r.rung == 37 and r.rank_name == "KataGo中等"
    assert r.mechanism == "net_search" and r.net == "b28" and r.max_visits == 500
    assert r.golaxy_level_name is None and r.golaxy_api_level is None


def test_rung_engine_params_shape():
    for r in LADDER_RUNGS:
        p = rung_engine_params(r)
        assert p["visits"] == r.max_visits and "maxVisits" not in p["extra_settings"]
    r1 = get_rung(1)
    assert rung_engine_params(r1)["extra_settings"]["humanSLProfile"] == r1.human_sl_profile


def test_override_settings_forces_black_winrate_perspective():
    ov = ladder_override_settings(get_rung(1))
    assert ov["reportAnalysisWinratesAs"] == "BLACK"


# --- Golaxy wire coordinate converters: gold standard (golaxy-protocol.md §3) ---
@pytest.mark.parametrize(
    "gtp,coord",
    [
        ("Q16", 72),
        ("Q4", 300),
        ("D4", 288),
        ("D16", 60),
        ("Q10", 186),
        ("R6", 263),
        ("D10", 174),
        ("C6", 249),
        ("K4", 294),
        ("B4", 286),
        ("A1", 342),
        ("T19", 18),
    ],
)
def test_golaxy_wire_gold_standard(gtp, coord):
    col, row0 = gtp_to_colrow(gtp, (19, 19))
    assert colrow_to_golaxy(col, row0, 19) == coord
    assert golaxy_to_colrow(coord, 19) == (col, row0)  # exact inverse, no mirror


def test_golaxy_not_mirrored():
    # D4 and D16 must be DISTINCT wire ints (mirror bug would collide their handling)
    assert colrow_to_golaxy(*gtp_to_colrow("D4", (19, 19)), 19) != colrow_to_golaxy(*gtp_to_colrow("D16", (19, 19)), 19)


def test_pick_humansl_and_search():
    bs = (19, 19)
    hp = [0.0] * (19 * 19 + 1)
    hp[(19 - 3 - 1) * 19 + 3] = 1.0  # (x=3,y=3)=D4
    assert pick_ladder_move({"humanPolicy": hp}, bs, "humansl") == (3, 3)
    assert pick_ladder_move({"moveInfos": [{"move": "Q16", "order": 0}]}, bs, "net_search") == gtp_to_colrow("Q16", bs)
    assert pick_ladder_move({"moveInfos": [{"move": "pass", "order": 0}]}, bs, "net_search") == "pass"


def test_pick_fails_loud_no_cross_mechanism_fallback():
    from katrain.core.ladder import LadderMoveError

    bs = (19, 19)
    # humansl rung with NO humanPolicy must NOT silently play a search move — it raises.
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "Q16", "order": 0}]}, bs, "humansl")
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"humanPolicy": [0.0] * (19 * 19 + 1)}, bs, "humansl")  # all-zero -> no valid dist
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"humanPolicy": [0.1] * 10}, bs, "humansl")  # wrong length
    with pytest.raises(LadderMoveError):
        pick_ladder_move({}, bs, "net_search")  # empty moveInfos


def test_pick_search_malformed_entries_raise_not_crash():
    from katrain.core.ladder import LadderMoveError

    bs = (19, 19)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": ["not-a-dict"]}, bs, "net_search")  # non-dict entry (no AttributeError)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "II9", "order": 0}]}, bs, "net_search")  # invalid column
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "Z99", "order": 0}]}, bs, "net_search")  # out-of-board
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"order": 0}]}, bs, "net_search")  # missing move field
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "Q16"}]}, bs, "net_search")  # missing order key
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "Q16", "order": True}]}, bs, "net_search")  # bool order (int subtype)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos": [{"move": "Q16", "order": -1}]}, bs, "net_search")  # negative order


def test_pick_search_any_malformed_entry_fails_closed_even_if_another_is_valid():
    # R6-H2/R7: ANY malformed entry must RAISE regardless of position — whether the malformed entry
    # is the min-order (selected) one OR a non-selected higher-order one. Covers shape, order, and
    # GTP/bounds malformations (the R7 case: valid order-0 + malformed-GTP order-1).
    from katrain.core.ladder import LadderMoveError

    bs = (19, 19)
    bads = [
        "not-a-dict",
        {"order": 0},
        {"move": "Q16"},
        {"move": "Q16", "order": True},
        {"move": "Q16", "order": -1},
        {"move": "II9", "order": 0},
        {"move": "Z99", "order": 0},
    ]
    good0 = {"move": "D4", "order": 0}
    good1 = {"move": "D4", "order": 1}
    for bad in bads:
        with pytest.raises(LadderMoveError):
            pick_ladder_move({"moveInfos": [bad, good1]}, bs, "net_search")  # malformed is min-order
    # valid order-0 selected, malformed higher-order entry must STILL raise (R7 exact case)
    for bad_gtp in [{"move": "II9", "order": 1}, {"move": "Z99", "order": 1}, {"move": "Q16", "order": True}]:
        with pytest.raises(LadderMoveError):
            pick_ladder_move({"moveInfos": [good0, bad_gtp]}, bs, "net_search")


def test_pick_non_dict_analysis_raises():
    from katrain.core.ladder import LadderMoveError

    bs = (19, 19)
    for bad in [["a", "list"], "a string", 42, None]:
        with pytest.raises(LadderMoveError):
            pick_ladder_move(bad, bs, "net_search")  # no AttributeError from .get on a non-dict
        with pytest.raises(LadderMoveError):
            pick_ladder_move(bad, bs, "humansl")


def test_ai_ladder_registered():
    from katrain.core import constants as C

    assert C.AI_LADDER == "ai:ladder"
    assert (
        C.AI_LADDER in C.AI_STRATEGIES
        and C.AI_LADDER in C.AI_STRATEGIES_RECOMMENDED_ORDER
        and C.AI_LADDER in C.AI_STRENGTH
    )


# --- config-sanity ordering guard (non-strict; ties allowed by design) ---


def test_config_key_non_decreasing():
    keys = [config_sanity_key(r) for r in LADDER_RUNGS]
    for i in range(1, len(keys)):
        assert keys[i] >= keys[i - 1] - 1e-9, f"config regressed at rung {i+1} ({LADDER_RUNGS[i].rank_name})"


def test_ceiling_has_max_config_key():
    # rung 37 (KataGo中等, b28@500) is the strongest config -> highest sanity key
    assert config_sanity_key(LADDER_RUNGS[36]) == max(config_sanity_key(r) for r in LADDER_RUNGS)


# --- rank_name (user-facing label, star阵-free) ---


def test_band_a_rank_name_is_the_humansl_rank():
    # Band A rungs are labeled by their KataGo humanSL rank; no Golaxy name involved.
    band_a = LADDER_RUNGS[:25]
    assert [r.rank_name for r in band_a] == [f"{n}K" for n in range(20, 0, -1)] + [f"{n}D" for n in range(1, 6)]
    for r in band_a:
        assert r.golaxy_level_name is None  # native, not derived from a Golaxy level


def test_pro_tiers_and_ceiling_rank_names():
    from katrain.core.ladder import get_rung
    assert get_rung(34).rank_name == "职业"
    assert get_rung(35).rank_name == "职业顶尖"
    assert get_rung(36).rank_name == "超职业"
    assert get_rung(37).rank_name == "KataGo中等"


def test_golaxy_level_name_kept_internally_for_calibration():
    # Band B keeps its Golaxy counterpart internally (calibration metadata), never shown as label.
    from katrain.core.ladder import get_rung
    assert get_rung(34).golaxy_level_name == "星阵1星"  # displayed as "职业"
    assert get_rung(36).golaxy_level_name == "星阵3星"  # displayed as "超职业"
    assert get_rung(37).golaxy_level_name is None


def test_no_rank_name_leaks_xingzhen():
    # Every user-visible label must be star阵-free (rank_name feeds the UI + ai_thoughts).
    for r in LADDER_RUNGS:
        assert "星阵" not in r.rank_name


# --- canonical strength specification ---


def _humansl_search_rung(**overrides):
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, LadderRung

    values = dict(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank="rank_9d",
        rank_name="rank_9d",
        net="b18",
        mechanism="humansl_search",
        human_sl_profile="rank_9d",
        max_visits=40,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE),
        backend_hint="server",
        root_policy_temperature=1.0,
    )
    values.update(overrides)
    return LadderRung(**values)


def test_humansl_search_strength_spec_is_b18_plus_humanv0():
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    assert dict(HUMANSL_PIKL_BASELINE) == {
        "humanSLChosenMoveProp": 1.0,
        "humanSLChosenMovePiklLambda": 0.08,
        "humanSLRootExploreProbWeightless": 0.8,
        "humanSLCpuctPermanent": 2.0,
        "useUncertainty": False,
        "subtreeValueBiasFactor": 0.0,
        "useNoisePruning": False,
    }
    spec = rung_strength_spec(_humansl_search_rung())
    assert spec.main_model == "b18"
    assert spec.human_model == "humanv0"
    assert spec.visits == 40
    assert spec.override_settings["humanSLChosenMoveProp"] == 1.0
    assert "model" not in spec.override_settings
    assert "maxVisits" not in spec.override_settings


def test_humansl_search_core_spec_does_not_impose_experiment_visit_floor():
    from katrain.core.ladder import rung_strength_spec

    assert rung_strength_spec(_humansl_search_rung(max_visits=1)).visits == 1


def test_native_rungs_retain_humansl_and_net_search_semantics():
    from katrain.core.ladder import rung_strength_spec

    human = rung_strength_spec(get_rung(1))
    assert (human.visits, human.main_model, human.human_model) == (1, None, "humanv0")
    search = rung_strength_spec(get_rung(26))
    assert (search.visits, search.main_model, search.human_model) == (4, "b28", None)


def test_strength_spec_and_compatibility_projections_are_immutable_copies():
    from dataclasses import FrozenInstanceError

    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    rung = _humansl_search_rung()
    spec = rung_strength_spec(rung)
    with pytest.raises(FrozenInstanceError):
        spec.visits = 41
    with pytest.raises(TypeError):
        spec.override_settings["humanSLChosenMoveProp"] = 0.5

    overrides = ladder_override_settings(rung)
    params = rung_engine_params(rung)
    overrides["humanSLChosenMoveProp"] = 0.5
    params["extra_settings"]["humanSLChosenMovePiklLambda"] = 0.5
    assert rung.human_sl_params == dict(HUMANSL_PIKL_BASELINE)
    assert spec.override_settings["humanSLChosenMoveProp"] == 1.0
    assert params == {
        "visits": 40,
        "extra_settings": params["extra_settings"],
        "main_model": "b18",
        "human_model": "humanv0",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"mechanism": "unknown"},
        {"max_visits": 0},
        {"max_visits": -1},
        {"max_visits": 40.0},
        {"max_visits": True},
        {"net": ""},
        {"net": "humanv0"},
        {"human_sl_profile": None},
        {"human_sl_profile": ""},
        {"human_sl_params": {}},
        {"human_sl_params": {"humanSLChosenMoveProp": 0.0}},
    ],
)
def test_invalid_humansl_search_is_rejected(overrides):
    from katrain.core.ladder import rung_strength_spec

    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(**overrides))


@pytest.mark.parametrize(
    "params_update",
    [
        {"humanSLChosenMovePiklLambda": 0.0},
        {"humanSLChosenMovePiklLambda": float("nan")},
        {"humanSLChosenMoveProp": True},
        {"useUncertainty": 0},
        {"humanSLCpuctPermanent": "2.0"},
    ],
)
def test_invalid_humansl_search_recipe_is_rejected(params_update):
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params.update(params_update)
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_sl_params=params))


def test_missing_humansl_search_recipe_key_is_rejected():
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params.pop("humanSLRootExploreProbWeightless")
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_sl_params=params))


@pytest.mark.parametrize(
    "rung",
    [
        _humansl_search_rung(mechanism="net_search", human_sl_profile="rank_9d", human_sl_params={}),
        _humansl_search_rung(mechanism="net_search", human_sl_profile=None),
        _humansl_search_rung(mechanism="net_search", human_sl_profile=None, human_sl_params={"model": "b18"}),
        _humansl_search_rung(mechanism="humansl", net="b18", max_visits=1, human_sl_params={}),
        _humansl_search_rung(mechanism="humansl", net="humanv0", max_visits=2, human_sl_params={}),
    ],
)
def test_invalid_mechanism_specific_strength_combinations_are_rejected(rung):
    from katrain.core.ladder import rung_strength_spec

    with pytest.raises(ValueError):
        rung_strength_spec(rung)


@pytest.mark.parametrize("temperature", [False, 0, -0.1, float("nan"), float("inf"), "1.0"])
def test_invalid_root_policy_temperature_is_rejected(temperature):
    from katrain.core.ladder import rung_strength_spec

    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(root_policy_temperature=temperature))


@pytest.mark.parametrize("nested_value", [{"nested": 1}, [1, 2]])
def test_nested_humansl_override_value_is_rejected(nested_value):
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params["unsupportedNestedSetting"] = nested_value
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_sl_params=params))


def test_strength_spec_constructor_rejects_nested_override_values():
    from katrain.core.ladder import LadderStrengthSpec

    with pytest.raises(ValueError):
        LadderStrengthSpec(visits=1, main_model=None, human_model=None, override_settings={"nested": []})


def test_humansl_requires_empty_params():
    from katrain.core.ladder import rung_strength_spec

    rung = _humansl_search_rung(
        mechanism="humansl",
        net="humanv0",
        max_visits=1,
        human_sl_params={"humanSLChosenMoveProp": 1.0},
    )
    with pytest.raises(ValueError):
        rung_strength_spec(rung)


def test_humansl_search_rejects_reserved_max_visits_override():
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params["maxVisits"] = 40
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_sl_params=params))


@pytest.mark.parametrize(
    "key,value",
    [
        ("humanSLChosenMoveProp", -0.1),
        ("humanSLChosenMoveProp", 1.1),
        ("humanSLChosenMoveProp", float("nan")),
        ("humanSLChosenMoveProp", float("inf")),
        ("humanSLChosenMovePiklLambda", -0.1),
        ("humanSLChosenMovePiklLambda", float("inf")),
        ("humanSLChosenMovePiklLambda", 1_000_000_000.000001),
        ("humanSLRootExploreProbWeightless", 0.0),
        ("humanSLRootExploreProbWeightless", -0.1),
        ("humanSLRootExploreProbWeightless", 1.1),
        ("humanSLRootExploreProbWeightless", float("nan")),
        ("humanSLRootExploreProbWeightless", float("inf")),
        ("humanSLRootExploreProbWeightless", True),
        ("humanSLCpuctPermanent", 0.0),
        ("humanSLCpuctPermanent", -0.1),
        ("humanSLCpuctPermanent", float("nan")),
        ("humanSLCpuctPermanent", float("inf")),
        ("humanSLCpuctPermanent", True),
        ("humanSLCpuctPermanent", 1000.000001),
        ("subtreeValueBiasFactor", -0.000001),
        ("subtreeValueBiasFactor", 1.000001),
        ("subtreeValueBiasFactor", float("nan")),
        ("subtreeValueBiasFactor", float("inf")),
        ("subtreeValueBiasFactor", True),
    ],
)
def test_invalid_pikl_numeric_range_is_rejected(key, value):
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params[key] = value
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_sl_params=params))


@pytest.mark.parametrize(
    "key,value",
    [
        ("humanSLChosenMoveProp", 0.000001),
        ("humanSLChosenMoveProp", 1.0),
        ("humanSLChosenMovePiklLambda", 0.000001),
        ("humanSLChosenMovePiklLambda", 1_000_000_000.0),
        ("humanSLRootExploreProbWeightless", 0.000001),
        ("humanSLRootExploreProbWeightless", 1.0),
        ("humanSLCpuctPermanent", 0.000001),
        ("humanSLCpuctPermanent", 1000.0),
        ("subtreeValueBiasFactor", 0.0),
        ("subtreeValueBiasFactor", 1.0),
    ],
)
def test_pikl_numeric_boundaries_are_accepted(key, value):
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, rung_strength_spec

    params = dict(HUMANSL_PIKL_BASELINE)
    params[key] = value
    assert rung_strength_spec(_humansl_search_rung(human_sl_params=params)).override_settings[key] == value
