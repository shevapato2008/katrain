import math
from dataclasses import replace

import pytest
from katrain.core.ladder import (
    HUMAN_ARGMAX,
    HUMANSL_PIKL_BASELINE,
    HUMAN_TEMPERATURE,
    HUMAN_WEIGHTED,
    LADDER_SELECTIONS,
    LADDER_RUNGS,
    LadderMoveError,
    LadderRung,
    NATIVE_POLICY_ARGMAX,
    SEARCH,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    get_rung,
    rung_engine_params,
    ladder_override_settings,
    pick_ladder_move,
    pick_ladder_rung_move,
    pick_temperature_policy,
    policy_index_to_gtp,
    temperature_policy_distribution,
    gtp_to_colrow,
    colrow_to_golaxy,
    golaxy_to_colrow,
    config_sanity_key,
    MECHANISMS,
    rung_endpoint_digest,
    rung_strength_spec,
)

U64_MAX = 2**64 - 1


def test_temperature_distribution_t1_normalizes_without_mutating_input():
    policy = [7.0, 2.0, 1.0]
    original = policy.copy()

    transformed = temperature_policy_distribution(policy, 1.0)

    assert transformed == pytest.approx([0.7, 0.2, 0.1])
    assert policy == original
    assert transformed is not policy


def test_temperature_distribution_flattens_and_sharpens():
    policy = [0.7, 0.2, 0.1]
    cold = temperature_policy_distribution(policy, 0.5)
    native = temperature_policy_distribution(policy, 1.0)
    hot = temperature_policy_distribution(policy, 2.0)

    assert native == pytest.approx(policy)
    assert cold[0] > native[0] > hot[0]
    assert cold[2] < native[2] < hot[2]
    assert sum(cold) == pytest.approx(1.0)
    assert sum(hot) == pytest.approx(1.0)

    def entropy(distribution):
        return -sum(probability * math.log(probability) for probability in distribution if probability)

    assert entropy(cold) < entropy(native) < entropy(hot)


def test_temperature_distribution_excludes_nonpositive_entries():
    assert temperature_policy_distribution([-3.0, 0.0, 2.0, 8.0], 2.0) == pytest.approx([0.0, 0.0, 1 / 3, 2 / 3])


@pytest.mark.parametrize("policy", [[0.0, -1.0], [-1.0, -2.0]])
def test_temperature_distribution_rejects_all_nonpositive(policy):
    with pytest.raises(ValueError):
        temperature_policy_distribution(policy, 1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_temperature_distribution_rejects_nonfinite_entries(bad):
    with pytest.raises(ValueError):
        temperature_policy_distribution([1.0, bad], 1.0)


@pytest.mark.parametrize(
    "temperature",
    [False, True, 0, -1, float("nan"), float("inf"), TEMPERATURE_MIN - 0.001, TEMPERATURE_MAX + 0.001],
)
def test_temperature_distribution_rejects_invalid_temperature(temperature):
    with pytest.raises(ValueError):
        temperature_policy_distribution([1.0], temperature)


def test_temperature_distribution_accepts_temperature_boundaries():
    assert temperature_policy_distribution([1.0], TEMPERATURE_MIN) == [1.0]
    assert temperature_policy_distribution([1.0], TEMPERATURE_MAX) == [1.0]


def test_temperature_distribution_is_stable_across_extreme_finite_weights():
    transformed = temperature_policy_distribution([1e-300, 1e300], TEMPERATURE_MIN)
    assert transformed == [0.0, 1.0]


def test_temperature_picker_rejects_wrong_policy_length():
    with pytest.raises(LadderMoveError):
        pick_temperature_policy([1.0] * 361, (19, 19), 1.0, 0)


@pytest.mark.parametrize(
    "policy",
    [None, [0.0] * 362, [float("nan")] + [0.0] * 361, [float("inf")] + [0.0] * 361],
)
def test_temperature_picker_exposes_invalid_policy_as_ladder_move_error(policy):
    with pytest.raises(LadderMoveError):
        pick_temperature_policy(policy, (19, 19), 1.0, 0)


@pytest.mark.parametrize(
    "temperature",
    [False, 0, float("nan"), float("inf"), "1.0", TEMPERATURE_MIN - 0.001, TEMPERATURE_MAX + 0.001],
)
def test_temperature_picker_exposes_invalid_temperature_as_ladder_move_error(temperature):
    policy = [0.0] * 362
    policy[0] = 1.0
    with pytest.raises(LadderMoveError):
        pick_temperature_policy(policy, (19, 19), temperature, 0)


def test_temperature_picker_can_select_pass_and_returns_policy_index():
    policy = [0.0] * 362
    policy[361] = 1.0
    assert pick_temperature_policy(policy, (19, 19), 1.0, 0) == ("pass", 361)


def test_temperature_picker_exact_inverse_cdf_edge_draws():
    policy = [0.0] * 362
    policy[342] = policy[0] = 1.0  # canonical order is A1, then A19

    assert pick_temperature_policy(policy, (19, 19), 1.0, 0) == ((0, 0), 342)
    assert pick_temperature_policy(policy, (19, 19), 1.0, 2**63 - 1) == ((0, 0), 342)
    assert pick_temperature_policy(policy, (19, 19), 1.0, 2**63) == ((0, 18), 0)
    assert pick_temperature_policy(policy, (19, 19), 1.0, U64_MAX) == ((0, 18), 0)


def test_temperature_picker_known_answer_uses_transformed_not_original_weights():
    policy = [0.0] * 362
    policy[342], policy[0] = 0.9, 0.1  # canonical candidates A1, then A19
    draw = 17_524_406_870_024_074_035  # u ~= 0.95

    assert pick_temperature_policy(policy, (19, 19), 1.0, draw) == ((0, 18), 0)
    assert pick_temperature_policy(policy, (19, 19), 0.5, draw) == ((0, 0), 342)


@pytest.mark.parametrize("draw", [False, True, -1, 1.0, U64_MAX + 1])
def test_temperature_picker_rejects_invalid_u64_draw(draw):
    policy = [0.0] * 362
    policy[0] = 1.0
    with pytest.raises(LadderMoveError):
        pick_temperature_policy(policy, (19, 19), 1.0, draw)


@pytest.mark.parametrize(
    "board_size",
    [None, [19, 19], "19x19", (19,), (19, 19, 19), (True, 19), (19, False), (0, 19), (-1, 19), (19.0, 19)],
)
def test_temperature_picker_exposes_invalid_board_size_as_ladder_move_error(board_size):
    policy = [0.0] * 362
    policy[0] = 1.0
    with pytest.raises(LadderMoveError):
        pick_temperature_policy(policy, board_size, 1.0, 0)


def test_temperature_picker_handles_arbitrarily_large_integer_values_without_overflow():
    policy = [0] * 362
    policy[0] = 10**400
    assert pick_temperature_policy(policy, (19, 19), 1.0, 0) == ((0, 18), 0)

    with pytest.raises(LadderMoveError):
        pick_temperature_policy(policy, (19, 19), 10**400, 0)


@pytest.mark.parametrize(
    "index,gtp",
    [(0, "A19"), (18, "T19"), (342, "A1"), (360, "T1"), (361, "pass")],
)
def test_policy_index_to_gtp_frozen_19x19_mapping(index, gtp):
    assert policy_index_to_gtp(index) == gtp


def test_production_rungs_and_local_temperature_default_are_unchanged():
    assert [
        (r.rung, r.rank_name, r.mechanism, r.net, r.human_sl_profile, r.max_visits, r.root_policy_temperature)
        for r in LADDER_RUNGS
    ] == [
        *[(n, f"{21 - n}K", "humansl", "humanv0", f"rank_{21 - n}k", 1, 1.1 if n <= 5 else 1.0) for n in range(1, 21)],
        *[(n, f"{n - 20}D", "humansl", "humanv0", f"rank_{n - 20}d", 1, 1.0) for n in range(21, 26)],
        (26, "准6D", "net_search", "b28", None, 4, 1.0),
        (27, "6D", "net_search", "b28", None, 8, 1.0),
        (28, "准7D", "net_search", "b28", None, 16, 1.0),
        (29, "7D", "net_search", "b28", None, 24, 1.0),
        (30, "准8D", "net_search", "b28", None, 40, 1.0),
        (31, "8D", "net_search", "b28", None, 64, 1.0),
        (32, "准9D", "net_search", "b28", None, 100, 1.0),
        (33, "9D", "net_search", "b28", None, 160, 1.0),
        (34, "职业", "net_search", "b28", None, 250, 1.0),
        (35, "职业顶尖", "net_search", "b28", None, 350, 1.0),
        (36, "超职业", "net_search", "b28", None, 450, 1.0),
        (37, "KataGo中等", "net_search", "b28", None, 500, 1.0),
    ]
    assert all(r.human_policy_temperature is None for r in LADDER_RUNGS)
    assert all(r.selection == HUMAN_WEIGHTED for r in LADDER_RUNGS[:25])
    assert all(r.selection == SEARCH for r in LADDER_RUNGS[25:])


def test_legacy_weighted_picker_behavior_is_unchanged(monkeypatch):
    import katrain.core.ai as ai

    policy = [0.0] * 362
    policy[342], policy[0], policy[361] = 1.0, 2.0, 3.0
    seen = []

    def fake_weighted_picker(moves, count):
        seen.extend(moves)
        assert count == 1
        return [moves[1]]

    monkeypatch.setattr(ai, "weighted_selection_without_replacement", fake_weighted_picker)
    assert pick_ladder_move({"humanPolicy": policy}, (19, 19), "humansl") == (0, 18)
    assert seen == [((0, 0), 1.0), ((0, 18), 2.0), ("pass", 3.0)]


def test_legacy_weighted_picker_retains_bool_weight_compatibility():
    policy = [False] * 362
    policy[342] = True
    assert pick_ladder_move({"humanPolicy": policy}, (19, 19), "humansl") == (0, 0)


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
        "准6D",
        "6D",
        "准7D",
        "7D",
        "准8D",
        "8D",
        "准9D",
        "9D",
        "职业",
        "职业顶尖",
        "超职业",
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
        selection="search",
        human_sl_profile="rank_9d",
        max_visits=40,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE),
        backend_hint="server",
        root_policy_temperature=1.0,
    )
    values.update(overrides)
    return LadderRung(**values)


def _policy(*weighted_indexes):
    policy = [0.0] * 362
    for index, weight in weighted_indexes:
        policy[index] = weight
    return policy


def test_ladder_selections_are_the_exact_supported_values():
    assert (
        HUMAN_WEIGHTED,
        HUMAN_TEMPERATURE,
        HUMAN_ARGMAX,
        SEARCH,
        NATIVE_POLICY_ARGMAX,
    ) == (
        "human_weighted",
        "human_temperature",
        "human_argmax",
        "search",
        "native_policy_argmax",
    )
    assert LADDER_SELECTIONS == {
        "human_weighted",
        "human_temperature",
        "human_argmax",
        "search",
        "native_policy_argmax",
    }


def test_human_argmax_uses_only_valid_human_policy_with_canonical_ties():
    rung = replace(get_rung(21), selection=HUMAN_ARGMAX)
    analysis = {
        "humanPolicy": _policy((342, 1.0), (343, 1.0), (361, 1.0)),
        "moveInfos": [{"move": "Q16", "order": 0}],
    }
    assert pick_ladder_rung_move(analysis, rung, (19, 19)) == (0, 0)

    bool_policy = [0.0] * 362
    bool_policy[342] = True
    for malformed in (None, [1.0] * 361, _policy(), _policy((0, float("nan"))), bool_policy):
        with pytest.raises(LadderMoveError):
            pick_ladder_rung_move({"humanPolicy": malformed, "moveInfos": analysis["moveInfos"]}, rung, (19, 19))


def test_native_policy_argmax_requires_exact_one_visit_root_only_response():
    rung = replace(get_rung(26), net="b18", max_visits=1, selection=NATIVE_POLICY_ARGMAX)
    analysis = {
        "rootInfo": {"visits": 1},
        "moveInfos": [],
        "policy": _policy((342, 2.0), (343, 2.0), (361, 2.0)),
    }
    assert pick_ladder_rung_move(analysis, rung, (19, 19)) == (0, 0)

    for update in (
        {"rootInfo": {"visits": True}},
        {"rootInfo": {"visits": 1.0}},
        {"rootInfo": {"visits": 2}},
        {"moveInfos": [{"move": "D4", "order": 0}]},
        {"policy": [1.0] * 361},
    ):
        with pytest.raises(LadderMoveError):
            pick_ladder_rung_move({**analysis, **update}, rung, (19, 19))


def test_search_requires_nonempty_fully_valid_move_infos():
    rung = replace(get_rung(26), selection=SEARCH)
    assert pick_ladder_rung_move(
        {"moveInfos": [{"move": "Q16", "order": 1}, {"move": "D4", "order": 0}]}, rung, (19, 19)
    ) == (3, 3)
    for infos in ([], [{"move": "D4", "order": 0}, {"move": "II9", "order": 1}]):
        with pytest.raises(LadderMoveError):
            pick_ladder_rung_move({"moveInfos": infos}, rung, (19, 19))


@pytest.mark.parametrize("selection", [HUMAN_WEIGHTED, HUMAN_TEMPERATURE])
@pytest.mark.parametrize("draw", [None, False, True, -1, 1.0, U64_MAX + 1])
def test_sampled_ladder_selections_require_explicit_plain_u64(selection, draw):
    temperature = 1.5 if selection == HUMAN_TEMPERATURE else None
    rung = replace(get_rung(21), selection=selection, human_policy_temperature=temperature)
    with pytest.raises(LadderMoveError):
        pick_ladder_rung_move({"humanPolicy": _policy((342, 1.0))}, rung, (19, 19), draw_u64=draw)


def test_sampled_ladder_selections_use_inverse_cdf_and_rung_temperature():
    policy = _policy((342, 0.9), (0, 0.1))
    draw = 17_524_406_870_024_074_035
    weighted = replace(get_rung(21), selection=HUMAN_WEIGHTED)
    hot = replace(get_rung(21), selection=HUMAN_TEMPERATURE, human_policy_temperature=0.5)
    assert pick_ladder_rung_move({"humanPolicy": policy}, weighted, (19, 19), draw_u64=draw) == (0, 18)
    assert pick_ladder_rung_move({"humanPolicy": policy}, hot, (19, 19), draw_u64=draw) == (0, 0)


def test_ladder_response_fields_are_not_interchangeable():
    human = replace(get_rung(21), selection=HUMAN_ARGMAX)
    native = replace(get_rung(26), net="b18", max_visits=1, selection=NATIVE_POLICY_ARGMAX)
    search = replace(get_rung(26), selection=SEARCH)
    with pytest.raises(LadderMoveError):
        pick_ladder_rung_move({"policy": _policy((342, 1.0))}, human, (19, 19))
    with pytest.raises(LadderMoveError):
        pick_ladder_rung_move(
            {"rootInfo": {"visits": 1}, "moveInfos": [], "humanPolicy": _policy((342, 1.0))}, native, (19, 19)
        )
    with pytest.raises(LadderMoveError):
        pick_ladder_rung_move({"policy": _policy((342, 1.0))}, search, (19, 19))


def test_versioned_pikl_and_pure_b18_endpoint_digests_bind_effective_strength():
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE, HUMANSL_PIKL_BASELINE_V1

    assert HUMANSL_PIKL_BASELINE is HUMANSL_PIKL_BASELINE_V1
    pikl = _humansl_search_rung(max_visits=2, selection=SEARCH)
    pure = replace(
        pikl,
        mechanism="net_search",
        human_sl_profile=None,
        human_sl_params={},
        selection=SEARCH,
    )
    pikl_spec = rung_strength_spec(pikl)
    pure_spec = rung_strength_spec(pure)
    assert (pikl_spec.main_model, pikl_spec.human_model, pikl.human_sl_profile, dict(pikl.human_sl_params)) == (
        "b18",
        "humanv0",
        "rank_9d",
        dict(HUMANSL_PIKL_BASELINE_V1),
    )
    assert pure_spec.main_model == "b18" and pure_spec.human_model is None
    assert pure.human_sl_profile is None and pure.human_sl_params == {}

    identity_a = {"model_sha256": "abc", "katago_version": "1.16.3"}
    identity_b = {"katago_version": "1.16.3", "model_sha256": "abc"}
    digest = rung_endpoint_digest(pikl, identity_a)
    assert digest == rung_endpoint_digest(pikl, identity_b)
    assert len(digest) == 64
    assert digest != rung_endpoint_digest(replace(pikl, max_visits=3), identity_a)
    assert digest != rung_endpoint_digest(pikl, {**identity_a, "model_sha256": "changed"})
    assert digest != rung_endpoint_digest(pure, identity_a)


def test_endpoint_digest_uses_effective_projected_root_temperature():
    identity = {"model_sha256": "abc"}
    exact_default = replace(get_rung(26), root_policy_temperature=1.0)
    within_projection_tolerance = replace(get_rung(26), root_policy_temperature=1.0000000005)
    assert ladder_override_settings(exact_default) == ladder_override_settings(within_projection_tolerance)
    assert rung_endpoint_digest(exact_default, identity) == rung_endpoint_digest(within_projection_tolerance, identity)


@pytest.mark.parametrize(
    "identity",
    [
        {1: "x"},
        {"nested": {1: "x"}},
        {"nested": {True: "x"}},
        {"tuple_is_not_json": (1, 2)},
        {"nonfinite": float("nan")},
        {"unsupported": {1, 2}},
    ],
)
def test_endpoint_digest_rejects_non_strict_json_identity(identity):
    with pytest.raises(ValueError):
        rung_endpoint_digest(get_rung(26), identity)


def test_endpoint_digest_rejects_non_string_effective_override_key():
    params = dict(HUMANSL_PIKL_BASELINE)
    params[1] = "x"
    with pytest.raises(ValueError):
        rung_endpoint_digest(_humansl_search_rung(human_sl_params=params), {"model_sha256": "abc"})


def test_endpoint_digest_keeps_bool_and_number_identities_distinct():
    rung = get_rung(26)
    assert rung_endpoint_digest(rung, {"value": True}) != rung_endpoint_digest(rung, {"value": 1})
    assert rung_endpoint_digest(rung, {"value": 1}) == rung_endpoint_digest(rung, {"value": 1.0})


def test_ladder_rung_defensively_freezes_human_sl_params_and_serializes_explicitly():
    original = dict(HUMANSL_PIKL_BASELINE)
    rung = _humansl_search_rung(human_sl_params=original)
    spec = rung_strength_spec(rung)
    digest = rung_endpoint_digest(rung, {"model_sha256": "abc"})

    original["humanSLCpuctPermanent"] = 99.0
    assert rung.human_sl_params["humanSLCpuctPermanent"] == 2.0
    assert rung_strength_spec(rung) == spec
    assert rung_endpoint_digest(rung, {"model_sha256": "abc"}) == digest
    with pytest.raises(TypeError):
        rung.human_sl_params["humanSLCpuctPermanent"] = 3.0

    replaced = replace(rung, max_visits=3)
    assert replaced.max_visits == 3 and replaced.human_sl_params == rung.human_sl_params
    serialized = rung.to_dict()
    assert serialized["human_sl_params"] == dict(rung.human_sl_params)
    serialized["human_sl_params"]["humanSLCpuctPermanent"] = 4.0
    assert rung.human_sl_params["humanSLCpuctPermanent"] == 2.0


def test_versioned_pikl_baseline_and_alias_are_the_same_immutable_mapping():
    from katrain.core.ladder import HUMANSL_PIKL_BASELINE_V1

    assert HUMANSL_PIKL_BASELINE is HUMANSL_PIKL_BASELINE_V1
    key = "humanSLCpuctPermanent"
    with pytest.raises(TypeError):
        HUMANSL_PIKL_BASELINE_V1[key] = 3.0
    with pytest.raises(TypeError):
        HUMANSL_PIKL_BASELINE[key] = 4.0


def test_ladder_rung_old_positional_arguments_retain_their_bindings():
    rung = LadderRung(
        0,
        None,
        None,
        None,
        "b18",
        "b18",
        "b18",
        "net_search",
        None,
        2,
        {},
        "client",
        1.25,
        None,
    )
    assert rung.human_sl_params == {}
    assert rung.backend_hint == "client"
    assert rung.root_policy_temperature == 1.25
    assert rung.human_policy_temperature is None
    assert rung.selection is None


def test_unresolved_or_unknown_selection_fails_closed_on_executable_paths():
    legacy = replace(get_rung(21), selection=None)
    assert legacy.selection is None
    for rung in (legacy, replace(legacy, selection="weighted")):
        with pytest.raises(ValueError):
            rung_strength_spec(rung)
        with pytest.raises(ValueError):
            rung_endpoint_digest(rung, {"model": "humanv0"})
        with pytest.raises(LadderMoveError):
            pick_ladder_rung_move({"humanPolicy": _policy((342, 1.0))}, rung, (19, 19), draw_u64=0)


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


def test_human_policy_temperature_is_validated_but_not_projected_to_engine():
    from dataclasses import replace

    from katrain.core.ladder import rung_strength_spec

    rung = replace(get_rung(21), selection=HUMAN_TEMPERATURE, human_policy_temperature=1.3)
    assert "human_policy_temperature" not in rung_strength_spec(rung).override_settings
    assert "humanPolicyTemperature" not in ladder_override_settings(rung)
    assert "humanPolicyTemperature" not in rung_engine_params(rung)["extra_settings"]


@pytest.mark.parametrize(
    "temperature",
    [False, True, 0, -1, float("nan"), float("inf"), TEMPERATURE_MIN - 0.001, TEMPERATURE_MAX + 0.001],
)
def test_invalid_local_human_policy_temperature_is_rejected(temperature):
    from dataclasses import replace

    from katrain.core.ladder import rung_strength_spec

    with pytest.raises(ValueError):
        rung_strength_spec(replace(get_rung(21), human_policy_temperature=temperature))


def test_local_human_policy_temperature_is_rejected_for_non_humansl_mechanisms():
    from dataclasses import replace

    from katrain.core.ladder import rung_strength_spec

    with pytest.raises(ValueError):
        rung_strength_spec(replace(get_rung(26), human_policy_temperature=1.0))
    with pytest.raises(ValueError):
        rung_strength_spec(_humansl_search_rung(human_policy_temperature=1.0))


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
