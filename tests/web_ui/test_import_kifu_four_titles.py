from scripts.import_kifu_four_titles import GROUPS, classify_core, parsed_edition, reviewed_edition


def test_series_boundaries_exclude_adjacent_titles_and_exhibitions():
    assert "首相杯" not in GROUPS["prime-minister"][1]
    assert "Prime Minister's Cup" not in GROUPS["prime-minister"][1]
    assert classify_core("Prime Minister's Cup", "prime-minister")
    assert not classify_core("Prime Minister's Cup Winner vs the Honinbo", "prime-minister")
    assert not classify_core("首相杯争奪戦優勝記念対局", "prime-minister")
    assert classify_core("Kansai Ki-in 1st Place", "kansai-first")
    assert not classify_core("Kansai Ki-in Championship", "kansai-first")
    assert not classify_core("第2期日本关西棋院第一位获得纪念对局", "kansai-first")
    assert not classify_core("中国龙星战冠军对抗赛特别对局", "china-ryusei")


def test_sponsor_internal_edition_and_year_gate():
    assert parsed_edition({"original_raw_value": "春茧杯第26届中国名人战本选", "series_core": "春茧杯第26届中国名人战本选", "structure": {"components": []}}) == ("edition_number", 26)
    assert reviewed_edition("prime-minister", ("edition_number", 1), "1957-01-01") == ["edition_number", 1]
    assert reviewed_edition("kansai-first", ("edition_number", 70), "2025-09-01") == ["edition_number", 70]
    assert reviewed_edition("china-ryusei", ("edition_number", 3), "1998-01-01") is None
    assert reviewed_edition("china-meijin", ("edition_number", 33), "2023-11-01") == ["edition_number", 33]
