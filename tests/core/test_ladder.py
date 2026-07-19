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
    MECHANISMS,
)

WEAK_TO_STRONG = [
    "18级",
    "17级",
    "16级",
    "15级",
    "14级",
    "13级",
    "12级",
    "11级",
    "10级",
    "9级",
    "8级",
    "7级",
    "6级",
    "5级",
    "4级",
    "3级",
    "2级",
    "1级",
    "准1段",
    "1段",
    "准2段",
    "2段",
    "准3段",
    "3段",
    "准4段",
    "4段",
    "准5段",
    "5段",
    "准6段",
    "6段",
    "准7段",
    "7段",
    "准8段",
    "8段",
    "准9段",
    "9段",
    "星阵1星",
    "星阵2星",
    "星阵3星",
]


def test_forty_rungs_map_weak_to_strong():
    assert len(LADDER_RUNGS) == 40 and [r.rung for r in LADDER_RUNGS] == list(range(1, 41))
    assert [r.golaxy_level_name for r in LADDER_RUNGS[:39]] == WEAK_TO_STRONG


def test_rung_40_ceiling_net_b18():
    r = LADDER_RUNGS[39]
    assert r.golaxy_level_name is None and r.golaxy_api_level is None and r.net == "b18"


def test_all_rungs_net_b18_v1():
    # v1 ships every rung on the session's b18 engine; net must equal shipping reality.
    assert all(r.net == "b18" for r in LADDER_RUNGS)


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
