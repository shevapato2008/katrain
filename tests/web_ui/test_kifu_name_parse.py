"""Conservative, provisional parsing of raw SGF names and events."""

from katrain.web.kifu.name_parse import parse_event, parse_player


def test_embedded_dan_is_separated_without_changing_raw_name():
    parsed = parse_player("吴清源九段", None)
    assert parsed.raw_name == "吴清源九段"
    assert parsed.name == "吴清源"
    assert parsed.embedded_rank == parsed.display_rank == "九段"
    assert parsed.category == "readable_unlinked"
    assert parsed.confidence == "high"
    assert parsed.exceptions == ()


def test_sgf_property_fragment_is_corrupt_not_a_player_and_rank_suffix():
    parsed = parse_player("崔珪昞]BR[九段", None)
    assert parsed.raw_name == "崔珪昞]BR[九段"
    assert parsed.name == ""
    assert parsed.embedded_rank is None
    assert parsed.category == "corrupt_pending"
    assert parsed.confidence == "low"
    assert parsed.exceptions == ("sgf_property_fragment",)


def test_result_in_explicit_rank_falls_back_to_embedded_suffix():
    parsed = parse_player("吴清源九段", "白九目半胜")
    assert parsed.raw_rank == "白九目半胜"
    assert parsed.display_rank == "九段"
    assert parsed.exceptions == ("invalid_explicit_rank",)


def test_result_in_explicit_rank_without_embedded_suffix_displays_empty():
    parsed = parse_player("吴清源", "白九目半胜")
    assert parsed.display_rank == ""
    assert parsed.exceptions == ("invalid_explicit_rank",)


def test_valid_explicit_rank_takes_priority_and_records_suffix_conflict():
    parsed = parse_player("吴清源九段", "八段")
    assert parsed.display_rank == "八段"
    assert parsed.embedded_rank == "九段"
    assert parsed.exceptions == ("rank_conflict",)
    assert parsed.confidence == "low"


def test_equivalent_chinese_and_arabic_dan_ranks_do_not_conflict():
    for rank in ("9d", "9D", "9段"):
        parsed = parse_player("吴清源九段", rank)
        assert parsed.display_rank == rank
        assert parsed.embedded_rank == "九段"
        assert parsed.exceptions == ()
    assert parse_player("吴清源一段", "1d").exceptions == ()


def test_kyu_or_professional_rank_is_not_assumed_equal_to_embedded_dan():
    for rank in ("8d", "9k", "9p"):
        assert parse_player("吴清源九段", rank).exceptions == ("rank_conflict",)


def test_normal_explicit_rank_and_placeholder_are_classified():
    assert parse_player("Go Seigen", "5p").display_rank == "5p"
    assert parse_player("Unknown", None).category == "placeholder"


def test_gnugo_is_a_program_label_not_a_tournament_identity():
    parsed = parse_event("GNUGo3.8", None)
    assert parsed.raw_event == "GNUGo3.8"
    assert parsed.category == "program_source_label"
    assert parsed.event_candidate is None
    assert parsed.confidence == "high"


def test_cwi_oteai_pattern_is_only_a_provisional_event_candidate():
    parsed = parse_event("JapanPromotionTournament,1934,Fall", "Final")
    assert parsed.raw_round == "Final"
    assert parsed.category == "formal_event_candidate"
    assert parsed.event_candidate == "JapanPromotionTournament"
    assert parsed.year == "1934"
    assert parsed.season == "Fall"
    assert parsed.exceptions == ("identity_unverified",)


def test_unknown_event_is_not_declared_a_proven_tournament():
    assert parse_event("Unknown,1934,Fall", None).category == "unclassified_pending"
    assert parse_event("段位赛", None).category == "generic_event_description"
    description = parse_event("冠华弈手杯职业棋手训练赛赵兴华执白中盘胜李莹", None)
    assert description.category == "game_description"
    assert parse_event(None, None).category == "empty"
