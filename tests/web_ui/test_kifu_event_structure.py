"""Event component extraction is a review aid, not an identity decision."""

from katrain.web.kifu.name_structure import structure_event


def test_explicit_year_edition_and_round_preserve_every_character():
    raw = "1934年第十二届日本大手合第3轮"
    item = structure_event(raw)
    assert item["status"] == "pending_review"
    assert item["rule_version"] == "event-components-v1"
    assert item["core"] == "日本大手合"
    assert [(part["kind"], part["value"]) for part in item["components"]] == [
        ("year", "1934"), ("edition", "十二届"), ("round", "3轮")
    ]
    assert "".join(part["text"] for part in item["parts"]) == raw
    assert all(raw[part["start"]:part["end"]] == part["text"] for part in item["parts"])


def test_bare_year_or_sponsor_and_league_qualifiers_are_not_stripped_globally():
    for raw in ("2014韩国围甲联赛", "KB国民银行杯2012韩国围甲联赛", "中国女子围乙联赛"):
        item = structure_event(raw)
        assert item["core"] == raw
        assert item["components"] == []


def test_named_oteai_grammars_are_separate_pending_groups():
    examples = (
        ("Oteai 1960", "oteai_year", "Oteai", [("year", "1960")]),
        (
            "JapanPromotionTournament,1934,Fall", "cwi_japan_promotion",
            "JapanPromotionTournament", [("year", "1934"), ("season", "Fall")],
        ),
        ("1934年日本大手合", "explicit_components", "日本大手合", [("year", "1934")]),
    )
    for raw, grammar, core, components in examples:
        item = structure_event(raw)
        assert item["grammar"] == grammar
        assert item["core"] == core
        assert [(part["kind"], part["value"]) for part in item["components"]] == components
        assert "".join(part["text"] for part in item["parts"]) == raw


def test_unrecognized_numerals_and_result_sentences_remain_unmodified():
    for raw in ("第廿五届本因坊战", "冠华弈手杯赵兴华执白中盘胜李莹", "第3局"):
        item = structure_event(raw)
        assert item["core"] == raw
        assert item["components"] == []


def test_round_unit_and_year_are_kept_distinct():
    one = structure_event("2026年世界围棋团体赛第2局")
    two = structure_event("2026年世界围棋团体赛第2轮")
    assert one["core"] == two["core"] == "世界围棋团体赛"
    assert one["components"][-1]["value"] == "2局"
    assert two["components"][-1]["value"] == "2轮"
    assert one["components"][-1]["kind"] == "game"
    assert two["components"][-1]["kind"] == "round"
