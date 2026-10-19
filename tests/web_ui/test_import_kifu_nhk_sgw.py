from scripts.import_kifu_nhk_sgw import build_plan, classify_raw, edition_number, reviewed_edition


def test_nhk_cup_names_exclude_broadcast_exhibitions_and_source_files():
    assert classify_raw("第63期日本NHK杯快棋赛第1轮", "nhk")
    assert classify_raw("63rdNHKCup", "nhk")
    assert not classify_raw("NHK Women's New Year Tournament", "nhk")
    assert not classify_raw("NHK exhibition relay game", "nhk")
    assert not classify_raw("55jp-nhk-1-wangqingsgf", "nhk")
    assert not classify_raw("第31回NHK杯争奪囲碁昭和59年5月号", "nhk")


def test_official_calendar_windows_hold_misnumbered_editions():
    assert edition_number("第7期日本SGW杯中庸战本赛") == 7
    assert reviewed_edition("sgw", 7, "2024-11-02") == ["edition_number", 7]
    assert reviewed_edition("sgw", 7, "2023-11-02") is None
    assert edition_number("63rdNHKCup") == 63
    assert reviewed_edition("nhk", 63, "2015-04-01") == ["edition_number", 63]
    assert reviewed_edition("nhk", 50, "2004-01-25") is None


def test_nhk_special_round_holds_entire_raw_group_and_uncertain_edition():
    columns = ["id", "event", "round_name", "date_played", "sources"]
    inventory = {
        "association_columns": columns,
        "counts": {"all": 5},
        "album_associations": [
            [1, "8th NHK Cup", None, "1961-03-01", []],
            [2, "8th NHK Cup", "Goodwill Match", "1961-04-29", []],
            [3, "25th NHK Cup", None, "1978", []],
            [4, "25th NHK Cup", "New Year special", "1978-01-01", []],
            [136144, "第15期日本NHK杯快棋赛", None, "1968-09-20", []],
        ],
    }
    plan, report = build_plan(inventory, "inventory-sha", "nhk")
    assert plan["albums"] == [[136144, "第15期日本NHK杯快棋赛", "日本NHK杯电视围棋锦标赛", None, "1968-09-20"]]
    assert report["excluded"]["special_game_raw_group"] == 4
    assert report["held"]["type_only_unverified_edition"] == 1
