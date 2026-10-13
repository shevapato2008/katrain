"""Event component extraction is a review aid, not an identity decision."""

from katrain.web.kifu.name_structure import structure_event


def test_explicit_year_edition_and_round_preserve_every_character():
    raw = "1934年第十二届日本大手合第3轮"
    item = structure_event(raw)
    assert item["status"] == "pending_review"
    assert item["rule_version"] == "event-components-v5"
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


def test_english_ordinal_edition_keeps_full_series_name_and_raw_spans():
    for raw, edition, core in (
        ("28th Honinbo", "28th", "Honinbo"),
        ("14th Old Meijin", "14th", "Old Meijin"),
        ("1st Meijin", "1st", "Meijin"),
    ):
        item = structure_event(raw)
        assert item["grammar"] == "english_ordinal_edition"
        assert item["core"] == core
        assert item["status"] == "pending_review"
        assert [(part["kind"], part["value"]) for part in item["components"]] == [("edition", edition)]
        assert "".join(part["text"] for part in item["parts"]) == raw
        assert all(raw[part["start"]:part["end"]] == part["text"] for part in item["parts"])


def test_malformed_ordinal_and_non_event_do_not_merge_with_series():
    for raw in (
        "11st Honinbo", "0th Honinbo", "28th", "28th 中盘胜",
        "Judan,11st", "0thTengen", "27th", "10th日本天元戦",
    ):
        item = structure_event(raw)
        assert item["grammar"] == "unparsed"
        assert item["core"] == raw


def test_ordinal_suffix_and_joined_prefix_keep_qualifiers_and_exact_spans():
    examples = (
        ("Judan,32nd", "english_ordinal_suffix", "Judan", "32nd"),
        ("Meijin(Yomiuri),14th", "english_ordinal_suffix", "Meijin(Yomiuri)", "14th"),
        ("27thTengen", "english_ordinal_joined", "Tengen", "27th"),
        ("14thOldMeijinLeague", "english_ordinal_joined", "OldMeijinLeague", "14th"),
    )
    for raw, grammar, core, edition in examples:
        item = structure_event(raw)
        assert item["rule_version"] == "event-components-v5"
        assert item["grammar"] == grammar
        assert item["core"] == core
        assert item["status"] == "pending_review"
        assert [(part["kind"], part["value"]) for part in item["components"]] == [("edition", edition)]
        assert "".join(part["text"] for part in item["parts"]) == raw
        assert all(raw[part["start"]:part["end"]] == part["text"] for part in item["parts"])


def test_single_infix_edition_preserves_discontiguous_core_spans():
    for raw, core, value in (
        ("日本第11期龙星战", "日本龙星战", "11期"),
        ("同里杯第31届中国天元战新浪网选", "同里杯中国天元战新浪网选", "31届"),
        ("日本第１２期棋圣战", "日本棋圣战", "１２期"),
        ("日本第十二期十段战", "日本十段战", "十二期"),
    ):
        item = structure_event(raw)
        assert item["grammar"] == "single_edition_fragment"
        assert item["core"] == core
        assert item["status"] == "pending_review"
        assert [(p["kind"], p["value"]) for p in item["components"]] == [("edition", value)]
        assert "".join(p["text"] for p in item["parts"]) == raw
        assert all(raw[p["start"]:p["end"]] == p["text"] for p in item["parts"])


def test_ambiguous_or_unsupported_infix_edition_stays_raw():
    for raw in (
        "日本第11期龙星战第2轮", "日本第11期第12届龙星战", "日本第11期龙星战第1场",
        "日本第廿五期本因坊战", "日本第11期", "日本第11.5期龙星战",
        "日本11期龙星战", "日本第11回NHK杯", "日本第壹期龙星战",
    ):
        item = structure_event(raw)
        if raw == "日本第11期龙星战第2轮":
            assert item["core"] == "日本第11期龙星战"
        else:
            assert item["core"] == raw
            assert item["components"] == []


def test_single_round_fragment_preserves_roles_qualifiers_and_exact_spans():
    for raw, core, number in (
        ("2010金立手机杯围甲联赛第11轮主将", "2010金立手机杯围甲联赛主将", "11"),
        ("2010金立手机杯围甲联赛第九十九轮快棋", "2010金立手机杯围甲联赛快棋", "九十九"),
        ("友情杯第１轮", "友情杯", "１"),
        (" 友情杯 第９９９轮主将", " 友情杯 主将", "９９９"),
    ):
        item = structure_event(raw)
        assert item["grammar"] == "single_round_fragment"
        assert item["core"] == core
        assert item["status"] == "pending_review"
        assert item["exceptions"] == []
        assert [(p["kind"], p["value"]) for p in item["components"]] == [("round", number + "轮")]
        assert item["components"][0]["text"] == "第" + number + "轮"
        assert "".join(p["text"] for p in item["parts"]) == raw
        assert all(raw[p["start"]:p["end"]] == p["text"] for p in item["parts"])


def test_single_round_fragment_rejects_unsupported_boundaries_and_numbers():
    for raw in (
        "2013韩国围棋联赛总决赛第3回合", "第42回NHK杯テレビ囲碁トーナメント",
        "第1回おかげ杯1回戦", "《受》第1局：三子局", "2008韩国围棋联赛第6轮第1场",
        "2013金立智能手机杯围甲第19轮主将(三劫循环无胜负）", "第三轮",
        "友情杯第0轮主将", "友情杯第01轮主将", "友情杯第０１轮", "友情杯第1１轮主将",
        "友情杯第一百轮主将", "友情杯第廿轮主将", "友情杯第壹轮主将", "友情杯第1000轮主将",
        "友情杯第１轮主将 ", "友情杯第１轮其他", "友情杯第轮主将", " 第１轮", "第友情杯第１轮",
    ):
        item = structure_event(raw)
        assert item["grammar"] != "single_round_fragment"
        assert "".join(p["text"] for p in item["parts"]) == raw


def test_existing_grammars_take_precedence_over_round_fallback():
    for raw, grammar in (
        ("友情杯第1轮", "explicit_components"),
        ("2026年友情杯第１轮主将", "explicit_components"),
        ("日本第11期龙星战第１轮主将", "unparsed"),
    ):
        assert structure_event(raw)["grammar"] == grammar
