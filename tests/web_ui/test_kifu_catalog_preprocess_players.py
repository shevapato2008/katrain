"""Full-scope player raw-value classification without identity decisions."""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuRawPlayerValue
from katrain.web.kifu.catalog_preprocess_players import (
    PLAYER_PARSER_VERSION,
    prepare_player_raw_values,
    upsert_player_raw_values,
)
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def _inventory():
    def album(album_id, black, white):
        fields = {key: None for key in ASSOCIATION_COLUMNS}
        fields.update(id=album_id, player_black=black, player_white=white, sources=[])
        return [fields[key] for key in ASSOCIATION_COLUMNS]

    return {
        "inventory_format": 4,
        "counts": {"all": 3},
        "detail_ids": [1, 2, 3],
        "association_columns": list(ASSOCIATION_COLUMNS),
        "album_associations": [
            album(1, "吴清源九段", "吴清源九段"),
            album(2, "?", None),
            album(3, "崔珪昞]BR[九段", ""),
        ],
        "scopes": {"all": {
            "album_ids": [1, 2, 3],
            "values": {"player": [
                {"value": None, "occurrences": 1, "affected_games": 1},
                {"value": "", "occurrences": 1, "affected_games": 1},
                {"value": "?", "occurrences": 1, "affected_games": 1},
                {"value": "吴清源九段", "occurrences": 2, "affected_games": 1},
                {"value": "崔珪昞]BR[九段", "occurrences": 1, "affected_games": 1},
            ]},
        }},
    }


def test_prepare_groups_every_slot_preserves_raw_and_extracts_rank():
    rows = prepare_player_raw_values(_inventory())
    assert sum(row["parsed_data"]["slot_count"] for row in rows) == 5  # one null slot has no table row
    by_raw = {row["raw_value"]: row for row in rows}
    assert set(by_raw) == {"", "?", "吴清源九段", "崔珪昞]BR[九段"}
    ranked = by_raw["吴清源九段"]
    assert ranked["category"] == "readable_unlinked"
    assert ranked["parser_version"] == PLAYER_PARSER_VERSION
    assert ranked["parsed_data"]["base_name"] == "吴清源"
    assert ranked["parsed_data"]["embedded_rank"] == "九段"
    assert ranked["parsed_data"]["slot_count"] == 2
    assert ranked["parsed_data"]["affected_games"] == 1
    assert by_raw["?"]["category"] == "placeholder"
    assert by_raw[""]["category"] == "placeholder"
    assert by_raw["崔珪昞]BR[九段"]["category"] == "corrupt_pending"
    assert not any("player_id" in row for row in rows)


@pytest.mark.parametrize("inventory_format", [2, 3, 4])
def test_prepare_accepts_all_inventory_formats_with_same_player_scope(inventory_format):
    inv = _inventory()
    inv["inventory_format"] = inventory_format
    assert len(prepare_player_raw_values(inv)) == 4


@pytest.mark.parametrize("mutation", [
    lambda inv: inv["album_associations"].pop(),
    lambda inv: inv["album_associations"].append(inv["album_associations"][0]),
    lambda inv: inv["scopes"]["all"]["values"]["player"][3].update(occurrences=1),
    lambda inv: inv["scopes"]["all"]["values"]["player"].append(
        dict(inv["scopes"]["all"]["values"]["player"][0])),
    lambda inv: inv.update(inventory_format=1),
])
def test_prepare_rejects_incomplete_duplicate_or_wrong_scope(mutation):
    inv = deepcopy(_inventory())
    mutation(inv)
    with pytest.raises(ValueError):
        prepare_player_raw_values(inv)


def test_upsert_is_idempotent_and_preserves_reviewed_and_foreign_parser_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    Base.metadata.create_all(engine)
    rows = prepare_player_raw_values(_inventory())
    with Session(engine) as db:
        db.add_all([
            KifuRawPlayerValue(
                raw_value="吴清源九段", category="reviewed_person", parsed_data={"owner": 7},
                parser_version="reviewed-v1", review_status="approved", review_metadata={"decision": "keep"},
            ),
            KifuRawPlayerValue(
                raw_value="?", category="legacy_pending", parsed_data={"keep": True},
                parser_version="other-v1", review_status="pending",
            ),
        ])
        db.commit()
        first = upsert_player_raw_values(db, rows)
        assert first == {"inserted": 2, "updated": 0, "unchanged": 0, "protected": 2}
        second = upsert_player_raw_values(db, rows)
        assert second == {"inserted": 0, "updated": 0, "unchanged": 2, "protected": 2}
        stored = {row.raw_value: row for row in db.scalars(select(KifuRawPlayerValue)).all()}
        assert len(stored) == 4
        assert stored["吴清源九段"].category == "reviewed_person"
        assert stored["吴清源九段"].parsed_data == {"owner": 7}
        assert stored["吴清源九段"].review_metadata == {"decision": "keep"}
        assert stored["?"].parsed_data == {"keep": True}
        assert stored[""].parsed_data["slot_count"] == 1
        assert all(row.review_status == "pending" for raw, row in stored.items() if raw not in {"吴清源九段"})
        db.rollback()  # helper leaves transaction ownership with caller
    with Session(engine) as db:
        assert {row.raw_value for row in db.scalars(select(KifuRawPlayerValue))} == {"吴清源九段", "?"}


def test_upsert_refreshes_only_its_own_pending_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    Base.metadata.create_all(engine)
    rows = prepare_player_raw_values(_inventory())
    with Session(engine) as db:
        db.add(KifuRawPlayerValue(
            raw_value="吴清源九段", category="old", parsed_data={"slot_count": 1},
            parser_version=PLAYER_PARSER_VERSION, review_status="pending", review_metadata={"note": "retain"},
        ))
        db.commit()
        result = upsert_player_raw_values(db, rows)
        assert result["updated"] == 1
        refreshed = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "吴清源九段"))
        assert refreshed.category == "readable_unlinked"
        assert refreshed.parsed_data["slot_count"] == 2
        assert refreshed.review_metadata == {"note": "retain"}
