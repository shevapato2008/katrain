from scripts.import_kifu_nongshim_mlily import classify_core, parsed_edition, reviewed_edition


def test_nongshim_series_excludes_separate_senior_and_exhibition_events():
    assert classify_core("第27届农心辛拉面杯韩国选拔赛", "nongshim")
    assert not classify_core("农心白山水杯世界围棋元老最强战", "nongshim")
    assert not classify_core("第4届农心杯高校赛", "nongshim")
    assert not classify_core("农心杯中韩经典超级对决", "nongshim")


def test_mlily_series_excludes_other_sponsored_events_and_checks_edition_year():
    assert classify_core("第五届MLILI梦百合0压床垫杯世界公开赛", "mlily")
    assert not classify_core("梦百合杯围甲联赛", "mlily")
    assert not classify_core("梦百合熬鹰杯业余赛", "mlily")
    assert not classify_core("古李十番棋梦百合赞助", "mlily")
    data = {"original_raw_value": "2017世界3届Mlily梦百合杯64强赛", "series_core": "Mlily梦百合杯"}
    assert parsed_edition(data) == ("edition_number", 3)
    assert reviewed_edition("mlily", ("edition_number", 3), "2017-06-01") == ["edition_number", 3]
    assert reviewed_edition("mlily", ("edition_number", 3), "2020-06-01") is None
    assert reviewed_edition("nongshim", ("year", 2025), "2025-06-01") == ["edition_number", 27]
