from scripts.import_kifu_taiwan_titles import edition_status


def test_taiwan_titles_have_separate_edition_calendars():
    assert edition_status("qiwang", ["edition_number", 2], "2008-12-25") == ["edition_number", 2]
    assert edition_status("guoshou", ["edition_number", 1], "2005-04-11") == ["edition_number", 1]
    assert edition_status("tianyuan", ["edition_number", 1], "2002-01-29") == ["edition_number", 1]
    assert edition_status("zhonghuan-gosei", ["edition_number", 1], "2013-01-01") == ["edition_number", 1]
    assert edition_status("guoshou", ["edition_number", 4], "2005-04-11") is None
