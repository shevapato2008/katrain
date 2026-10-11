"""Focused coverage for provisional bulk Chinese player IDs and FK backfill."""

from collections import Counter

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_auto import build_safe_chinese_batch, run_safe_chinese_batch
from katrain.web.kifu.catalog_preprocess_players import prepare_player_raw_values
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def fixture():
    games = [
        (1, "常昊九段", "大竹英雄", None, 10, "2020-01-01"),
        (2, "大竹英雄", "常昊", None, None, "1900-01-01"),
        (3, "李小溪", "李小溪（小）", None, None, "2021-01-01"),
        (4, "井山裕太", "井山裕太", None, None, "2022-01-01"),
    ]
    albums = []
    slots = Counter()
    affected = Counter()
    for id_, black, white, black_id, white_id, date in games:
        row = dict.fromkeys(ASSOCIATION_COLUMNS)
        row.update(id=id_, player_black=black, player_white=white, black_player_id=black_id,
                   white_player_id=white_id, date_played=date, sources=[])
        albums.append(row)
        slots.update((black, white))
        affected.update({black, white})
    inventory = {
        "inventory_format": 4, "sha256": "frozen-test-inventory", "counts": {"all": len(games)},
        "detail_ids": [row["id"] for row in albums],
        "association_columns": list(ASSOCIATION_COLUMNS),
        "album_associations": [[row[key] for key in ASSOCIATION_COLUMNS] for row in albums],
        "scopes": {"all": {"album_ids": [row["id"] for row in albums],
                           "values": {"player": [{"value": raw, "occurrences": count,
                                                  "affected_games": affected[raw]}
                                                 for raw, count in slots.items()]}}},
    }
    catalog = {"kifu_players": [{"id": 10, "canonical_name": "大竹英雄"}],
               "kifu_player_aliases": []}
    return inventory, catalog, albums


def database(tmp_path, inventory, albums):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuPlayer(id=10, canonical_name="大竹英雄"))
        for row in albums:
            db.add(KifuAlbum(id=row["id"], player_black=row["player_black"],
                             player_white=row["player_white"],
                             black_player_id=row["black_player_id"], white_player_id=row["white_player_id"],
                             date_played=row["date_played"], source_path=f"{row['id']}.sgf",
                             sgf_content="(;GM[1])"))
        for row in prepare_player_raw_values(inventory):
            db.add(KifuRawPlayerValue(raw_value=row["raw_value"], category=row["category"],
                                      parsed_data=row["parsed_data"], parser_version=row["parser_version"],
                                      review_status="pending"))
        db.commit()
    return engine


def test_safe_batch_excludes_homonym_and_same_name_opponents():
    inventory, catalog, _ = fixture()
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    assert {row["base_name"] for row in batch["selected"]} == {"常昊", "大竹英雄"}
    holds = {row["base_name"]: row["reasons"] for row in batch["holds"]}
    assert "homonym_qualifier" in holds["李小溪"]
    assert "same_name_opponents" in holds["井山裕太"]
    assert batch["counts"]["selected_slots"] == 4
    assert batch["counts"]["new_player_ids"] == 1


def test_reviewed_exact_raw_exclusion_holds_its_whole_base_group():
    inventory, catalog, _ = fixture()
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, {"常昊九段"})
    assert "常昊" not in {row["base_name"] for row in batch["selected"]}
    assert "reviewed_non_person_raw" in next(row["reasons"] for row in batch["holds"]
                                             if row["base_name"] == "常昊")


def test_bulk_dry_run_then_apply_only_null_fks(tmp_path):
    inventory, catalog, albums = fixture()
    engine = database(tmp_path, inventory, albums)
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    preview = run_safe_chinese_batch(inventory, batch, engine, apply=False)
    assert preview["new_player_ids"] == 1
    assert preview["new_album_links"] == 3
    with Session(engine) as db:
        assert db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "常昊")) is None
        assert db.get(KifuAlbum, 1).black_player_id is None
    result = run_safe_chinese_batch(inventory, batch, engine, apply=True)
    assert result["new_album_links"] == 3
    with Session(engine) as db:
        created = db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "常昊"))
        assert created.id != 10
        assert db.get(KifuAlbum, 1).black_player_id == created.id
        assert db.get(KifuAlbum, 1).white_player_id == 10
        assert db.get(KifuAlbum, 2).black_player_id == 10
        assert db.get(KifuAlbum, 2).white_player_id == created.id
        assert db.get(KifuAlbum, 3).black_player_id is None
        assert db.get(KifuAlbum, 4).black_player_id is None
        raw = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "常昊九段"))
        assert raw.review_status == "pending"
        assert raw.review_metadata["player_id"] == created.id
        assert db.get(KifuAlbum, 1).player_black == "常昊九段"


def test_stale_album_or_catalog_rejected_before_writes(tmp_path):
    inventory, catalog, albums = fixture()
    engine = database(tmp_path, inventory, albums)
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    with Session(engine) as db:
        db.get(KifuAlbum, 1).player_black = "other"
        db.commit()
    with pytest.raises(ValueError, match="snapshot differs"):
        run_safe_chinese_batch(inventory, batch, engine, apply=True)
    with Session(engine) as db:
        assert db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "常昊")) is None


def test_catalog_id_collision_is_a_hold():
    inventory, catalog, _ = fixture()
    catalog["kifu_players"].append({"id": 11, "canonical_name": "大竹英雄"})
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    holds = {row["base_name"]: row["reasons"] for row in batch["holds"]}
    assert "catalog_id_collision" in holds["大竹英雄"]
    assert batch["counts"]["catalog_canonical_duplicate_keys"] == 1


def test_existing_different_fk_is_held_and_catalog_title_id_is_held():
    inventory, catalog, _ = fixture()
    black_index = ASSOCIATION_COLUMNS.index("black_player_id")
    inventory["album_associations"][1][black_index] = 11
    catalog["kifu_players"].append({"id": 11, "canonical_name": "另一位"})
    catalog["kifu_players"].append({"id": 12, "canonical_name": "大竹英雄名誉"})
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    holds = {row["base_name"]: row["reasons"] for row in batch["holds"]}
    assert "existing_fk_conflict" in holds["大竹英雄"]
    assert "catalog_related_title_id" in holds["大竹英雄"]
