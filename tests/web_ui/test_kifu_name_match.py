"""Identity matching produces review proposals, never unreviewed links."""

from datetime import datetime, timezone
import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    Base,
    KifuEvent,
    KifuEventName,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerName,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
)
from katrain.web.kifu.identity import strict_matching_names
from katrain.web.kifu.name_inventory import SELECTION_COLUMNS, _hash_row
from katrain.web.kifu.name_match import propose_album_matches


COLUMNS = [
    "id", "duplicate_of_id", "player_black", "player_white", "event",
    "round_name", "black_rank", "white_rank", "date_played",
    "black_player_id", "white_player_id", "event_id", "sources",
]


def _inventory(*rows):
    return {
        "inventory_format": 2, "sha256": "a" * 64,
        "association_columns": COLUMNS, "album_associations": list(rows),
    }


def _v3_inventory(*rows, selections=()):
    inventory = _inventory(*rows)
    digest = hashlib.sha256()
    _hash_row(digest, b"E", (1, SELECTION_COLUMNS))
    for row in selections:
        _hash_row(digest, b"E", row)
    inventory.update(
        inventory_format=3,
        base_sha256="b" * 64,
        sha256="c" * 64,
        event_selection={
            "selection_format": 1,
            "columns": list(SELECTION_COLUMNS),
            "rows": [list(row) for row in selections],
            "sha256": digest.hexdigest(),
        },
    )
    return inventory


def test_v3_player_proposals_and_reviewed_second_gn_event_use_exact_selected_spelling():
    selected = [20, "Selected Cup", "d" * 64, "independent-reviewer", "2026-10-02T10:00:00+00:00", 3, "e" * 64]
    inventory = _v3_inventory(
        [20, None, "吴清源九段", "木谷实", "GNUGo3.8", None, None, None,
         "1934-10-01", None, None, None, []],
        selections=[selected],
    )
    proposals = list(propose_album_matches(
        inventory,
        player_aliases={"吴清源": {7}},
        event_aliases={"Selected Cup": {9}, "GNUGo3.8": {99}},
    ))
    assert [item["side"] for item in proposals] == ["black", "white", "event"]
    assert proposals[0]["candidate_ids"] == [7]
    assert proposals[0]["status"] == "review_candidate"
    assert proposals[0]["inventory_format"] == 3
    assert proposals[0]["inventory_sha256"] == "c" * 64
    assert proposals[2]["raw_value"] == "Selected Cup"
    assert proposals[2]["lookup_name"] == "Selected Cup"
    assert proposals[2]["candidate_ids"] == [9]
    assert proposals[2]["status"] == "review_candidate"
    assert proposals[2]["confidence_boundary"] == "candidate_only"


def test_v3_without_valid_selection_keeps_program_label_out_of_event_identity():
    inventory = _v3_inventory(
        [20, None, "甲", "乙", "GNUGo3.8", None, None, None,
         None, None, None, None, []],
    )
    proposals = list(propose_album_matches(
        inventory, player_aliases={}, event_aliases={"GNUGo3.8": {99}},
    ))
    assert proposals[2]["raw_value"] == "GNUGo3.8"
    assert proposals[2]["status"] == "non_identity"
    assert proposals[2]["candidate_ids"] == []


@pytest.mark.parametrize("damage", ["missing_supplement", "bad_base_hash", "bad_selection_hash",
                                    "unknown_album", "wrong_original_event", "linked_original_event"])
def test_v3_proposals_reject_unpinned_or_misapplied_event_selection(damage):
    album = [20, None, "甲", "乙", "GNUGo3.8", None, None, None,
             None, None, None, None, []]
    selected = [20, "Selected Cup", "d" * 64, "reviewer", "2026-10-02T10:00:00+00:00", 3, "e" * 64]
    inventory = _v3_inventory(album, selections=[selected])
    if damage == "missing_supplement":
        del inventory["event_selection"]
    elif damage == "bad_base_hash":
        inventory["base_sha256"] = "not-a-hash"
    elif damage == "bad_selection_hash":
        inventory["event_selection"]["sha256"] = "f" * 64
    elif damage == "unknown_album":
        inventory = _v3_inventory(album, selections=[[21, *selected[1:]]])
    elif damage == "wrong_original_event":
        inventory["album_associations"][0][COLUMNS.index("event")] = "Other Cup"
    elif damage == "linked_original_event":
        inventory["album_associations"][0][COLUMNS.index("event_id")] = 99
    with pytest.raises(ValueError):
        list(propose_album_matches(inventory, player_aliases={}, event_aliases={"Selected Cup": {9}}))


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
    assert black[0]["inventory_sha256"] == "a" * 64
    assert black[0]["inventory_format"] == 2
    assert black[0]["rule_version"] == "name-match-v1"
    assert black[0]["confidence_boundary"] == "candidate_only"


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


def test_mixed_tournament_and_result_remains_pending_for_manual_extraction():
    raw = "冠华弈手杯职业棋手训练赛赵兴华执白中盘胜李莹"
    proposals = list(propose_album_matches(
        _inventory([12, None, "甲", "乙", raw, None, None, None, None, None, None, None, []]),
        player_aliases={}, event_aliases={},
    ))
    assert proposals[2]["raw_value"] == raw
    assert proposals[2]["status"] == "manual_event_extraction"
    assert proposals[2]["candidate_ids"] == []


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


@pytest.mark.parametrize(
    "entity_kind, raw_kind",
    [("player", "raw_player"), ("event", "raw_event"), ("player", "raw_event"), ("event", "raw_player")],
)
def test_strict_translated_search_does_not_merge_entity_and_raw_owners(entity_kind, raw_kind):
    models = {
        "player": (KifuPlayer, KifuPlayerName),
        "event": (KifuEvent, KifuEventName),
        "raw_player": (KifuRawPlayerValue, KifuRawPlayerName),
        "raw_event": (KifuRawEventValue, KifuRawEventName),
    }
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            registry = KifuNameSourceRegistry(version="test", sha256="a" * 64, registry={})
            db.add(registry)
            db.flush()
            owners = []
            evidence_rows = []
            for kind in (entity_kind, raw_kind):
                owner_model, name_model = models[kind]
                owner = (
                    owner_model(raw_value="Distinct unlinked spelling", category="readable", review_status="approved")
                    if kind.startswith("raw_") else owner_model(canonical_name="Distinct linked identity")
                )
                db.add(owner)
                db.flush()
                evidence = KifuNameResearchEvidence(
                    **{f"{kind}_id": owner.id},
                    lang="ru", revision=1, source_registry_id=registry.id,
                    candidate_name="Общее имя", decision_kind="conventional", generation_rule_version="test-v1",
                    research_payload={"candidate": {"collision_decision": "distinct_people_confirmed"}},
                    producer_id="producer", producer_model="gpt-6-luna",
                    reviewer_id="reviewer", reviewer_model="gpt-6-sol",
                    reviewed_at=datetime.now(timezone.utc), review_status="approved",
                )
                db.add(evidence)
                db.flush()
                db.add(name_model(
                    **{f"{kind}_id": owner.id},
                    lang="ru", display_name="Общее имя", status="verified",
                    decision_kind="conventional", generation_rule_version="test-v1", revision=1,
                    evidence_id=evidence.id,
                ))
                owners.append(owner)
                evidence_rows.append(evidence)
            db.commit()

            assert strict_matching_names(db, "Общее имя") == (set(), set(), set(), set())

            # A pending raw display cannot make an otherwise unique entity ambiguous.
            evidence_rows[1].review_status = "pending"
            db.commit()
            expected = [set(), set(), set(), set()]
            expected[0 if entity_kind == "player" else 1] = {owners[0].id}
            assert strict_matching_names(db, "Общее имя") == tuple(expected)

            # A unique raw translation still expands only its exact original spelling.
            evidence_rows[1].review_status = "approved"
            evidence_rows[0].review_status = "pending"
            db.commit()
            expected = [set(), set(), set(), set()]
            expected[2 if raw_kind == "raw_player" else 3] = {owners[1].raw_value}
            assert strict_matching_names(db, "Общее имя") == tuple(expected)
    finally:
        engine.dispose()
