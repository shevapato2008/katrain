from katrain.kifu_ingest.name_reuse import build_event_lexicon, propose_event_reuse


LANGS = ("cn", "tw", "en", "jp", "ko")


def old_rows(raw, names, raw_id=1):
    return [
        {
            "raw_id": raw_id,
            "raw_value": raw,
            "lang": lang,
            "display_name": names[lang],
            "status": "verified",
            "evidence_id": raw_id * 10 + i,
        }
        for i, lang in enumerate(LANGS)
    ]


def names(cn, en):
    return {"cn": cn, "tw": cn, "en": en, "jp": cn, "ko": cn}


def propose(raw, rows):
    return propose_event_reuse(raw, build_event_lexicon(rows))


def test_exact_raw_reuses_five_names_with_source_evidence():
    source = names("第1届围棋赛", "1st Go Tournament")
    candidate = propose("第1届围棋赛", old_rows("第1届围棋赛", source))
    assert candidate["method"] == "reuse"
    assert candidate["rule"] == "exact_raw_v1"
    assert candidate["names5"] == source
    assert candidate["sources"][0]["old_raw"] == "第1届围棋赛"
    assert candidate["sources"][0]["old_names"] == source
    assert candidate["sources"][0]["evidence_ids"] == dict(zip(LANGS, range(10, 15)))


def test_digit_template_changes_year_and_english_ordinal_once():
    source = names("2025第1届华为围棋赛第2轮", "2025 Huawei Go Tournament, 1st edition, 2nd round")
    candidate = propose(
        "2026第2届华为围棋赛第3轮", old_rows("2025第1届华为围棋赛第2轮", source)
    )
    assert candidate["method"] == "translation"
    assert candidate["rule"] == "ascii_digit_template_v1"
    assert candidate["names5"]["cn"] == "2026第2届华为围棋赛第3轮"
    assert candidate["names5"]["en"] == "2026 Huawei Go Tournament, 2nd edition, 3rd round"
    assert candidate["digit_mapping"] == {"2025": "2026", "1": "2", "2": "3"}


def test_digit_replacement_is_single_pass_and_handles_teen_ordinals():
    source = names("2025第11届赛", "2025 11th tournament")
    candidate = propose("2026第12届赛", old_rows("2025第11届赛", source))
    assert candidate["names5"]["en"] == "2026 12th tournament"
    source = names("2025第1届赛", "2025 1st tournament")
    candidate = propose("2026第2届赛", old_rows("2025第1届赛", source))
    assert candidate["names5"]["en"] == "2026 2nd tournament"


def test_mismatched_skeleton_or_inconsistent_mapping_is_unresolved():
    source = names("2025第1届赛", "2025 1st tournament")
    rows = old_rows("2025第1届赛", source)
    assert propose("2026第2回赛", rows) is None
    assert propose("2026第2届赛第3轮", rows) is None
    repeated = old_rows("2025赛2025", names("2025赛2025", "2025 tournament 2025"))
    assert propose("2026赛2027", repeated) is None


def test_missing_digit_or_invalid_english_ordinal_rejects_whole_candidate():
    rows = old_rows("2025第1届赛", names("2025第1届赛", "1st tournament"))
    assert propose("2026第2届赛", rows) is None
    rows = old_rows("2025第1届赛", names("2025第1届赛", "2025 1th tournament"))
    assert propose("2026第2届赛", rows) is None


def test_conflicting_templates_are_unresolved_and_matching_outputs_merge_sources():
    first = old_rows("2024第1届赛", names("2024第1届赛", "2024 1st tournament"), 1)
    other = old_rows("2025第2届赛", names("2025第2届赛", "2025 2nd Go contest"), 2)
    assert propose("2026第3届赛", first + other) is None
    other = old_rows("2025第2届赛", names("2025第2届赛", "2025 2nd tournament"), 2)
    candidate = propose("2026第3届赛", first + other)
    assert len(candidate["sources"]) == 2


def test_incomplete_or_conflicting_five_language_source_is_unusable():
    rows = old_rows("2025第1届赛", names("2025第1届赛", "2025 1st tournament"))
    assert propose("2026第2届赛", rows[:-1]) is None
    assert propose("2025第1届赛", rows[:-1]) is None
    conflict = dict(rows[0], display_name="不同译名")
    assert propose("2025第1届赛", rows + [conflict]) is None
    assert propose("", rows) is None


def test_empty_display_name_cannot_be_reused():
    rows = old_rows("2025赛", names("2025赛", "2025 tournament"))
    rows[2]["display_name"] = ""
    assert propose("2025赛", rows) is None


def test_extra_unrelated_number_in_display_blocks_template():
    rows = old_rows("2025赛", names("2025赛", "2025 tournament, board 19"))
    assert propose("2026赛", rows) is None
