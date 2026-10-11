from scripts.import_kifu_futures_tianyuan_changqi import reviewed_edition


def test_futures_keeps_second_division_edition_and_year_boundaries():
    assert reviewed_edition("futures", ["edition_number", 14], "2017-05-01") == ["edition_number", 14]
    assert reviewed_edition("futures", ["year", 2023], "2023-05-01") == ["edition_number", 19]
    assert reviewed_edition("futures", ["year", 2025], "2025-05-01") == ["year", 2025]
    assert reviewed_edition("futures", ["edition_number", 14], "2023-05-01") is None


def test_chinese_titles_hold_inconsistent_edition_dates():
    assert reviewed_edition("china-tianyuan", ["edition_number", 39], "2025-04-01") == ["edition_number", 39]
    assert reviewed_edition("china-tianyuan", ["edition_number", 5], "1990-04-01") is None
    assert reviewed_edition("changqi", ["edition_number", 18], "2022-10-01") == ["edition_number", 18]
    assert reviewed_edition("changqi", ["edition_number", 18], "2023-10-01") == ["edition_number", 18]
    assert reviewed_edition("changqi", ["edition_number", 18], "2018-10-01") is None
