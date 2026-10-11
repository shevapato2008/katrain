from scripts.import_kifu_lg_chunlan import classify_core, reviewed_edition


def test_lg_world_is_distinct_from_domestic_refined_oils_and_anniversary_cups():
    assert classify_core("LG杯世界棋王战韩国预选赛", "lg-world")
    assert classify_core("朝鲜日报LG杯世界棋王战", "lg-world")
    assert not classify_core("LGRefinedOilsCup", "lg-world")
    assert not classify_core("LG杯30周年纪念邀请赛", "lg-world")
    assert not classify_core("LG杯世界棋王战特别对局", "lg-world")


def test_official_edition_windows():
    assert reviewed_edition("lg-world", ("edition_number", 30), "2026-01-01", "LG杯决赛") == ["edition_number", 30]
    assert reviewed_edition("lg-world", ("edition_number", 30), "2023-01-01", "LG杯决赛") is None
    assert reviewed_edition("chunlan", ("edition_number", 13), "2019-06-01", "春兰杯台湾选拔赛") == ["edition_number", 13]
    assert reviewed_edition("chunlan", ("edition_number", 14), "2023-07-01", "春兰杯决赛") == ["edition_number", 14]
    assert reviewed_edition("chunlan", ("edition_number", 14), "2019-01-01", "春兰杯决赛") is None
