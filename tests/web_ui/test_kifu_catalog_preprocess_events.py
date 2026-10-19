"""Raw EV inventory ingestion preserves review boundaries and exact spellings."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuRawEventValue
from katrain.web.kifu.catalog_preprocess_events import (
    NULL_EVENT_SENTINEL,
    event_series_review_queue,
    prepare_event_raw_values,
    upsert_event_raw_values,
)


def _inventory(events):
    counts = {}
    for raw in events:
        counts[raw] = counts.get(raw, 0) + 1
    return {
        "inventory_format": 4,
        "counts": {"all": len(events)},
        "distinct_values": {"all": {"event": len(counts)}},
        "association_columns": ["id", "event"],
        "album_associations": [[index, raw] for index, raw in enumerate(events, 1)],
        "scopes": {"all": {"values": {"event": [
            {"value": raw, "occurrences": count, "affected_games": count}
            for raw, count in counts.items()
        ]}}},
    }


def test_prepares_all_slots_with_lossless_components_and_frequency_queue():
    events = [
        "28th Honinbo", "29th Honinbo", "28th Honinbo",
        "2026年世界围棋团体赛第2局", "2026年世界围棋团体赛第2轮",
        "段位赛", "GNUGo3.8", "甲]EV[乙", "冠华弈手杯赵兴华执白中盘胜李莹", None, "",
    ]
    rows = prepare_event_raw_values(_inventory(events), expected_games=len(events))
    by_original = {row["parsed_data"]["original_raw_value"]: row for row in rows}
    assert len(rows) == len(set(events))
    assert sum(row["parsed_data"]["occurrences"] for row in rows) == len(events)
    assert by_original[None]["raw_value"] == NULL_EVENT_SENTINEL
    assert by_original[""]["raw_value"] == ""
    assert by_original[None]["category"] == by_original[""]["category"] == "empty"
    assert all(row["review_status"] == "pending" for row in rows)
    assert all(row["parsed_data"]["series_core"] is None for row in rows
               if row["category"] in {"empty", "generic_event_description", "program_source_label",
                                      "corrupt_data", "game_description"})

    honinbo = by_original["28th Honinbo"]["parsed_data"]
    assert honinbo["series_core"] == "Honinbo"
    assert honinbo["structure"]["components"][0]["kind"] == "edition"
    for row in rows:
        original = row["parsed_data"]["original_raw_value"]
        parts = row["parsed_data"]["structure"]["parts"]
        assert "".join(part["text"] for part in parts) == (original or "")
        assert all((original or "")[part["start"]:part["end"]] == part["text"] for part in parts)

    queue = event_series_review_queue(rows)
    assert queue[0]["series_core"] == "Honinbo"
    assert queue[0]["occurrences"] == 3
    assert queue[0]["raw_value_count"] == 2
    assert next(item for item in queue if item["series_core"] == "世界围棋团体赛")["occurrences"] == 2
    assert all(item["series_core"] not in {"段位赛", "GNUGo3.8", "甲]EV[乙"} for item in queue)


def test_upsert_is_idempotent_and_preserves_review_decision(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    events = [None, "", "28th Honinbo", "28th Honinbo", "GNUGo3.8"]
    rows = prepare_event_raw_values(_inventory(events), expected_games=5)
    with Session(engine) as db:
        assert upsert_event_raw_values(db, rows) == {"inserted": 4, "updated": 0, "unchanged": 0, "protected": 0}
        db.commit()
        first = {row.raw_value: row.id for row in db.scalars(select(KifuRawEventValue))}
        honinbo = db.scalar(select(KifuRawEventValue).where(KifuRawEventValue.raw_value == "28th Honinbo"))
        honinbo.review_status = "approved"
        honinbo.review_metadata = {"reviewer": "human"}
        db.commit()
        assert upsert_event_raw_values(db, rows) == {"inserted": 0, "updated": 0, "unchanged": 3, "protected": 1}
        db.commit()
        second = {row.raw_value: row.id for row in db.scalars(select(KifuRawEventValue))}
        assert second == first
        honinbo = db.scalar(select(KifuRawEventValue).where(KifuRawEventValue.raw_value == "28th Honinbo"))
        assert honinbo.review_status == "approved"
        assert honinbo.review_metadata == {"reviewer": "human"}
        assert honinbo.parsed_data["occurrences"] == 2
        assert db.scalar(select(KifuRawEventValue).where(
            KifuRawEventValue.raw_value == NULL_EVENT_SENTINEL)).parsed_data["original_raw_value"] is None


def test_reviewed_and_old_parser_rows_are_protected_while_current_pending_rows_refresh(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    first = prepare_event_raw_values(_inventory(["28th Honinbo", "GNUGo3.8", "段位赛"]))
    second = prepare_event_raw_values(_inventory(["28th Honinbo", "28th Honinbo", "GNUGo3.8", "段位赛", "段位赛"]))
    with Session(engine) as db:
        upsert_event_raw_values(db, first)
        db.commit()
        reviewed = db.scalar(select(KifuRawEventValue).where(KifuRawEventValue.raw_value == "28th Honinbo"))
        reviewed.review_status = "rejected"
        reviewed.review_metadata = {"reason": "reviewed"}
        older = db.scalar(select(KifuRawEventValue).where(KifuRawEventValue.raw_value == "GNUGo3.8"))
        older.parser_version = "old-parser"
        db.commit()
        assert upsert_event_raw_values(db, second) == {
            "inserted": 0, "updated": 1, "unchanged": 0, "protected": 2,
        }
        db.commit()
        assert reviewed.parsed_data["occurrences"] == 1
        assert reviewed.review_metadata == {"reason": "reviewed"}
        assert older.parser_version == "old-parser"
        assert db.scalar(select(KifuRawEventValue).where(
            KifuRawEventValue.raw_value == "段位赛")).parsed_data["occurrences"] == 2


def test_format_two_inventory_remains_eligible_for_raw_slot_reconciliation():
    inventory = _inventory(["28th Honinbo", None])
    inventory["inventory_format"] = 2
    assert sum(row["parsed_data"]["occurrences"] for row in prepare_event_raw_values(inventory)) == 2


@pytest.mark.parametrize("change", ["missing_association", "duplicate_association", "bad_count", "bad_distinct",
                                         "duplicate_raw_row", "wrong_expected_total"])
def test_rejects_incomplete_or_inconsistent_event_inventory(change):
    inventory = _inventory(["28th Honinbo", None])
    expected = 2
    if change == "missing_association":
        inventory["album_associations"].pop()
    elif change == "duplicate_association":
        inventory["album_associations"][1][0] = 1
    elif change == "bad_count":
        inventory["scopes"]["all"]["values"]["event"][0]["occurrences"] = 3
    elif change == "bad_distinct":
        inventory["distinct_values"]["all"]["event"] = 3
    elif change == "duplicate_raw_row":
        inventory["scopes"]["all"]["values"]["event"].append(
            {"value": "28th Honinbo", "occurrences": 1, "affected_games": 1})
        inventory["distinct_values"]["all"]["event"] = 3
    else:
        expected = 3
    with pytest.raises(ValueError):
        prepare_event_raw_values(inventory, expected_games=expected)


def test_null_sentinel_collision_is_rejected():
    with pytest.raises(ValueError, match="sentinel"):
        prepare_event_raw_values(_inventory([None, NULL_EVENT_SENTINEL]))
