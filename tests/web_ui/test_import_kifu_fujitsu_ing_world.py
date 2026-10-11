from scripts.import_kifu_fujitsu_ing_world import classify_core, reviewed_edition


def test_world_cups_exclude_unrelated_youth_and_exhibition_events():
    assert classify_core("富士通杯日本选拔赛", "fujitsu")
    assert not classify_core("富士通杯U15少年职业围棋赛", "fujitsu")
    assert not classify_core("应氏杯中国大学生赛", "ing")
    assert not classify_core("应氏杯30周年纪念对局", "ing")


def test_edition_dates_allow_qualifiers_and_delayed_ninth_ing_final():
    assert reviewed_edition("fujitsu", ("edition_number", 24), "2010-10-01", "富士通杯日本选拔赛") == ["edition_number", 24]
    assert reviewed_edition("fujitsu", ("edition_number", 24), "2009-10-01", "富士通杯日本选拔赛") is None
    assert reviewed_edition("ing", ("edition_number", 9), "2023-08-21", "应氏杯世界决赛3番棋") == ["edition_number", 9]
    assert reviewed_edition("ing", ("edition_number", 9), "2023-08-21", "应氏杯世界锦标赛") is None
