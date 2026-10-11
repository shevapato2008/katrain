from scripts.import_kifu_korean_leagues import edition_status


def test_korean_league_edition_calendars_stay_separate():
    assert edition_status("men", ["year", 2004], "2004-06-01") == ("edition", 1)
    assert edition_status("men", ["edition_number", 19], "2023-06-01") == ("edition", 19)
    assert edition_status("women", ["edition_number", 11], "2025-06-01") == ("edition", 11)
    assert edition_status("seniors", ["edition_number", 10], "2025-06-01") == ("edition", 10)
    assert edition_status("men", None, "2007-06-01") == ("type_only", None)
    assert edition_status("men", ["year", 2011], "1900-01-01") == ("type_only", None)
