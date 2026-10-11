"""Exact rollback of a false-person provisional player, with valid links intact."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_auto import build_safe_chinese_batch, run_safe_chinese_batch
from katrain.web.kifu.catalog_player_repair import capture_repair_plan, run_repair_plan
from katrain.web.kifu.catalog_preprocess_players import prepare_player_raw_values
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def test_repair_rolls_back_only_exact_raw_slot_and_orphan_id(tmp_path):
    row = dict.fromkeys(ASSOCIATION_COLUMNS)
    row.update(id=1, player_black="初段", player_white="常昊", sources=[])
    inventory = {"inventory_format": 4, "sha256": "fixture-sha", "counts": {"all": 1},
                 "detail_ids": [1], "association_columns": list(ASSOCIATION_COLUMNS),
                 "album_associations": [[row[key] for key in ASSOCIATION_COLUMNS]],
                 "scopes": {"all": {"album_ids": [1], "values": {"player": [
                     {"value": "初段", "occurrences": 1, "affected_games": 1},
                     {"value": "常昊", "occurrences": 1, "affected_games": 1},
                 ]}}}}
    catalog = {"kifu_players": [], "kifu_player_aliases": []}
    engine = create_engine(f"sqlite:///{tmp_path / 'repair.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuAlbum(id=1, player_black="初段", player_white="常昊",
                         source_path="one.sgf", sgf_content="(;GM[1])"))
        for prepared in prepare_player_raw_values(inventory):
            db.add(KifuRawPlayerValue(raw_value=prepared["raw_value"], category=prepared["category"],
                                      parsed_data=prepared["parsed_data"],
                                      parser_version=prepared["parser_version"], review_status="pending"))
        db.commit()
    batch = build_safe_chinese_batch(inventory, catalog, lambda value: value, set())
    assert run_safe_chinese_batch(inventory, batch, engine, apply=True)["new_album_links"] == 2
    plan = capture_repair_plan(inventory, batch, [{"raw_value": "初段", "reason": "rank_label"}], engine)
    assert plan["counts"] == {"raw_values": 1, "album_slots": 1, "new_ids_to_delete": 1,
                              "reused_ids_to_keep": 0}
    assert run_repair_plan(inventory, batch, plan, engine, apply=False)["album_slots_restored_to_null"] == 1
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is not None
    assert run_repair_plan(inventory, batch, plan, engine, apply=True)["provisional_ids_deleted"] == 1
    with Session(engine) as db:
        album = db.get(KifuAlbum, 1)
        assert album.black_player_id is None
        assert album.white_player_id is not None
        assert db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "初段")) is None
        assert db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "常昊")) is not None
        raw = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "初段"))
        assert raw.review_metadata is None and raw.review_status == "pending"
