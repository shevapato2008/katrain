"""Identity matching produces review proposals, never unreviewed links."""

from katrain.web.kifu.name_match import propose_album_matches


COLUMNS = [
    "id", "duplicate_of_id", "player_black", "player_white", "event",
    "round_name", "black_rank", "white_rank", "date_played",
    "black_player_id", "white_player_id", "event_id", "sources",
]


def _inventory(*rows):
    return {"inventory_format": 2, "association_columns": COLUMNS, "album_associations": list(rows)}


def test_rank_suffix_and_cross_script_aliases_propose_the_same_identity():
    inventory = _inventory(
        [1, None, "吴清源九段", "木谷实", None, None, None, None, None, None, None, None, []],
        [2, None, "Go Seigen", "木谷实", None, None, None, None, None, None, None, None, []],
    )
    proposals = list(propose_album_matches(
        inventory,
        player_aliases={"吴清源": {7}, "Go Seigen": {7}},
        event_aliases={},
    ))
    black = [item for item in proposals if item["side"] == "black"]
    assert [(item["album_id"], item["candidate_ids"], item["status"]) for item in black] == [
        (1, [7], "review_candidate"), (2, [7], "review_candidate")
    ]
    assert all(item["existing_id"] is None for item in black)
    assert black[0]["parsed_rank"] == "九段"


def test_same_spelling_collision_stays_ambiguous_and_unlinked_name_stays_raw_scoped():
    proposals = list(propose_album_matches(
        _inventory([3, None, "同名", "无记录棋手", None, None, None, None, None, None, None, None, []]),
        player_aliases={"同名": {11, 12}},
        event_aliases={},
    ))
    assert proposals[0]["status"] == "ambiguous"
    assert proposals[0]["candidate_ids"] == [11, 12]
    assert proposals[1]["status"] == "raw_display_required"
    assert proposals[1]["raw_value"] == "无记录棋手"
    assert proposals[1]["candidate_ids"] == []


def test_bad_and_placeholder_values_never_propose_an_identity():
    proposals = list(propose_album_matches(
        _inventory([4, None, "崔珪昞]BR[九段", "Black", "GNUGo3.8", None, None, None, None, None, None, None, []]),
        player_aliases={"崔珪昞": {4}, "Black": {5}},
        event_aliases={"GNUGo3.8": {6}},
    ))
    assert [(item["side"], item["status"], item["candidate_ids"]) for item in proposals] == [
        ("black", "corrupt_pending", []),
        ("white", "non_identity", []),
        ("event", "non_identity", []),
    ]


def test_event_year_is_only_a_component_after_event_identity_review():
    proposals = list(propose_album_matches(
        _inventory(
            [
                5, None, "甲", "乙", "JapanPromotionTournament,1934,Fall",
                None, None, None, "1934-10-01", None, None, None, [],
            ],
            [6, None, "甲", "乙", "1934年春季赞助商杯", None, None, None, "1934-04-01", None, None, None, []],
        ),
        player_aliases={},
        event_aliases={"JapanPromotionTournament": {9}, "赞助商杯": {10}},
    ))
    events = [item for item in proposals if item["side"] == "event"]
    assert events[0]["status"] == "review_candidate"
    assert events[0]["candidate_ids"] == [9]
    assert events[0]["components"] == {"year": "1934", "season": "Fall"}
    assert events[1]["status"] == "raw_display_required"
    assert events[1]["candidate_ids"] == []


def test_existing_links_are_reported_without_reassignment():
    proposals = list(propose_album_matches(
        _inventory([7, None, "同名", "乙", None, None, None, None, None, 17, None, None, []]),
        player_aliases={"同名": {18}},
        event_aliases={},
    ))
    assert proposals[0]["status"] == "existing_link_conflict"
    assert proposals[0]["existing_id"] == 17
    assert proposals[0]["candidate_ids"] == [18]

    ambiguous = list(propose_album_matches(
        _inventory([8, None, "同名", "乙", None, None, None, None, None, 17, None, None, []]),
        player_aliases={"同名": {17, 18}},
        event_aliases={},
    ))
    assert ambiguous[0]["status"] == "existing_link_conflict"


def test_rank_and_event_chronology_conflicts_are_visible_in_review_proposals():
    proposals = list(propose_album_matches(
        _inventory([
            9, None, "吴清源九段", "木谷实", "JapanPromotionTournament,1934,Fall",
            "Spring event", "八段", None, "1935-02-01", None, None, None, [],
        ]),
        player_aliases={"吴清源": {7}},
        event_aliases={"JapanPromotionTournament": {9}},
    ))
    assert "rank_conflict" in proposals[0]["exceptions"]
    assert "event_year_date_mismatch" in proposals[2]["exceptions"]
    assert "event_season_round_mismatch" in proposals[2]["exceptions"]


def test_old_inventory_format_cannot_be_approved_with_missing_date_and_rank_fields():
    try:
        list(propose_album_matches({"inventory_format": 1, "association_columns": [], "album_associations": []},
                                   player_aliases={}, event_aliases={}))
    except ValueError as exc:
        assert "inventory_format" in str(exc)
    else:
        raise AssertionError("old inventory was accepted")


def test_structural_event_groups_are_distinct_review_candidates():
    proposals = list(propose_album_matches(
        _inventory(
            [10, None, "甲", "乙", "Oteai 1960", None, None, None, "1960-01-01", None, None, None, []],
            [11, None, "甲", "乙", "1934年日本大手合", None, None, None, "1934-01-01", None, None, None, []],
        ),
        player_aliases={},
        event_aliases={"Oteai": {9}, "日本大手合": {9}},
    ))
    events = [item for item in proposals if item["side"] == "event"]
    assert [item["lookup_name"] for item in events] == ["Oteai", "日本大手合"]
    assert [item["structure"]["grammar"] for item in events] == ["oteai_year", "explicit_components"]
    assert all(item["status"] == "review_candidate" for item in events)
    assert all("family_identity_review" in item["exceptions"] for item in events)
