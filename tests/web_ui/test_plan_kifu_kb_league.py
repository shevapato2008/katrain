from scripts.plan_kifu_kb_league import candidate, edition_key, excluded


def test_kb_league_boundary_and_independent_selection_hold():
    assert candidate("2015韩国围甲联赛Kixx-tbroad")
    assert candidate("2024-2025年度韩国围甲联赛第8轮")
    assert excluded("KB国民银行杯2013韩国联赛预选决赛")
    assert excluded("2019~2020韩国KB国民银行杯围甲联赛全明星赛第6局")
    assert excluded("2020~2021第17届韩国KB国民银行杯围甲联赛赛季前超快棋探索赛8强战")
    for raw in ("韩国女子围棋联赛", "韩国围乙联赛", "KB Future 韩国联赛", "韩国新秀联赛", "韩国挑战联赛"):
        assert not candidate(raw) or excluded(raw)
    assert excluded("韩国联赛")


def test_edition_is_held_without_a_consistent_verified_key():
    assert edition_key("201714届韩国围甲3轮", "2017-06-08") == ["edition_number", 14]
    assert edition_key("2021~2022第19届韩国KB围甲联赛", "2022-01-20") is None
    assert edition_key("2021~2020第19届韩国KB围甲联赛", "2021-11-20") is None
    assert edition_key("2024-2025年度韩国围甲联赛第8轮", "2025-02-13") is None
    assert edition_key("2011韩国围棋联赛", "1900-01-01") is None
