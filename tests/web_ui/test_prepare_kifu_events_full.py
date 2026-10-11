from scripts.prepare_kifu_events_full import normalized_spelling, split_type_candidate


def test_type_boundary_keeps_sponsor_but_separates_year_edition_and_stage():
    assert split_type_candidate("2007金立杯围甲联赛") == {
        "type_candidate": "金立杯围甲联赛", "year": "2007", "edition": None,
        "stage": None, "round": None, "fixture": None, "reason": None,
    }
    assert split_type_candidate("201742期日本名人战循环圈赛") == {
        "type_candidate": "日本名人战", "year": "2017", "edition": "42期",
        "stage": "循环圈赛", "round": None, "fixture": None, "reason": None,
    }
    assert split_type_candidate("台湾海峰杯职业围棋赛64强战")["type_candidate"] == "台湾海峰杯职业围棋赛"
    assert split_type_candidate("日本王座战预选A组")["stage"] == "预选A组"
    assert split_type_candidate("三国赤壁古战场杯围甲15轮杭州-重庆3")["type_candidate"] == "三国赤壁古战场杯围甲"


def test_historic_game_labels_are_not_tournament_types():
    for label in ("Hoensha game", "Castle Game"):
        assert split_type_candidate(label)["reason"] == "historic_game_label"
        assert split_type_candidate(label)["type_candidate"] is None


def test_comparison_key_is_only_orthographic():
    assert normalized_spelling(" ＧＳ  Caltex ") == "gs caltex"
    assert normalized_spelling("三星杯") != normalized_spelling("LG杯")
