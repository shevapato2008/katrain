from scripts.import_kifu_historical_event_aliases import _edition_status, _myeongin_year


def test_historical_series_keep_distinct_edition_calendars():
    assert _edition_status("japan-championship", 22, "1975-01-01") == "edition"
    assert _edition_status("all-japan-first", 1, "1968-01-01") == "edition"
    assert _edition_status("japan-championship", 2, "1961-01-01") == "hold"
    assert _edition_status("korean-kuksu", 30, "1987-01-01") == "edition"
    assert _edition_status("korean-wangwi", 20, "1986-01-01") == "edition"


def test_korean_meijin_calendar_accounts_for_restart():
    assert _myeongin_year(34) == 2004
    assert _myeongin_year(35) == 2007
    assert _myeongin_year(43) == 2015
    assert _myeongin_year(44) == 2021
    assert _edition_status("korean-myeongin", 46, "2023-01-01") == "edition"
    assert _edition_status("korean-myeongin", 5, "1960-01-01") == "hold"
