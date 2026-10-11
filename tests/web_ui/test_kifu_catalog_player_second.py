"""Exact reviewed second-batch links, rollback, and stale-preimage rejection."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerName, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_second import capture_second_plan, run_second_plan
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'second.db'}")
    Base.metadata.create_all(engine)
    inventory_rows = []
    decisions = []
    original_players = []
    with Session(engine) as db:
        for index in range(1, 21):
            canonical = f"棋手{index}"
            old_name = "旧名一" if index == 1 else canonical
            target_id = None if index == 20 else index
            if target_id is not None:
                db.add(KifuPlayer(id=target_id, canonical_name=old_name))
                original_players.append({"id": target_id, "canonical_name": old_name})
            raw = f"原文{index}"
            existing_fk = 2 if index == 2 else None
            db.add(KifuAlbum(id=index, player_black=raw, player_white="对手",
                             black_player_id=existing_fk, date_played="2020-01-01",
                             source_path=f"{index}.sgf", sgf_content="(;GM[1])"))
            db.add(KifuRawPlayerValue(raw_value=raw, category="readable_unlinked", review_status="pending"))
            row = dict.fromkeys(ASSOCIATION_COLUMNS)
            row.update(id=index, player_black=raw, player_white="对手", black_player_id=existing_fk,
                       date_played="2020-01-01", sources=[])
            inventory_rows.append([row[key] for key in ASSOCIATION_COLUMNS])
            duplicates = [99] if index == 3 else []
            decisions.append({
                "canonical_chinese_name": canonical,
                "reviewed_name_identity": "same_person_for_allowlisted_raw_values",
                "game_fk_decision": "approved_after_fresh_snapshot_preflight",
                "proposed_target": {"action": "create_player" if index == 20 else
                                    "rename_player" if index == 1 else "retain_player",
                                    "player_id": target_id, "current_canonical_name": old_name if target_id else None,
                                    "new_canonical_name": canonical},
                "duplicate_catalog_ids_to_fold": duplicates,
                "raw_allowlist": [{"raw_value": raw, "slots": 1,
                                   "name_identity_decision": "same_person"}],
                "excluded_prefix_raw_values": [], "allowlisted_slots": 1,
                "scope_review": {"slot_count": 1, "source_key_counts": {},
                                 "existing_target_fk_slots": 1 if index == 2 else 0},
            })
        db.add(KifuPlayer(id=99, canonical_name="旧名三"))
        db.add(KifuPlayerName(player_id=3, lang="en", display_name="Version A", status="review"))
        db.add(KifuPlayerName(player_id=99, lang="en", display_name="Version B", status="review"))
        db.commit()
    original_players.append({"id": 99, "canonical_name": "旧名三"})
    inventory = {"sha256": "frozen-test", "counts": {"all": 20},
                 "association_columns": list(ASSOCIATION_COLUMNS), "album_associations": inventory_rows}
    review = {"format": "kifu-player-second-batch-review-v2", "decisions": decisions,
              "summary": {"raw_allowlist_values": 20, "raw_allowlist_slots": 20},
              "input": {"inventory_sha256": "inventory-file-test"}}
    catalog = {"kifu_players": original_players}
    return engine, inventory, review, catalog


def test_second_batch_dry_run_then_apply_preserves_duplicate_translation(tmp_path):
    engine, inventory, review, catalog = fixture(tmp_path)
    plan = capture_second_plan(inventory, review, catalog, "review-sha", engine)
    assert plan["counts"]["new_fk_slots"] == 19
    assert plan["counts"]["existing_target_fk_slots"] == 1
    assert plan["counts"]["duplicate_ids_held"] == 1
    assert run_second_plan(inventory, review, catalog, "review-sha", plan, engine)["new_fk_slots"] == 19
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None
        assert db.get(KifuPlayer, 1).canonical_name == "旧名一"
        assert db.scalar(select(KifuPlayer).where(KifuPlayer.canonical_name == "棋手20")) is None
    result = run_second_plan(inventory, review, catalog, "review-sha", plan, engine, apply=True)
    assert result["new_fk_slots"] == 19 and result["canonical_names_renamed"] == 1
    with Session(engine) as db:
        new_id = db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == "棋手20"))
        assert db.get(KifuAlbum, 1).black_player_id == 1
        assert db.get(KifuAlbum, 20).black_player_id == new_id
        assert db.get(KifuPlayer, 1).canonical_name == "棋手1"
        assert db.get(KifuPlayer, 99).canonical_name == "旧名三"
        assert {row.display_name for row in db.scalars(select(KifuPlayerName).where(
            KifuPlayerName.player_id.in_((3, 99))))} == {"Version A", "Version B"}
        raw = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "原文1"))
        assert raw.review_status == "approved" and raw.review_metadata["player_id"] == 1
        assert db.get(KifuAlbum, 1).player_black == "原文1"


def test_second_batch_rejects_changed_live_slot(tmp_path):
    engine, inventory, review, catalog = fixture(tmp_path)
    plan = capture_second_plan(inventory, review, catalog, "review-sha", engine)
    with Session(engine) as db:
        db.get(KifuAlbum, 1).date_played = "2021-01-01"
        db.commit()
    with pytest.raises(ValueError, match="scope differs"):
        run_second_plan(inventory, review, catalog, "review-sha", plan, engine, apply=True)
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None
        assert db.get(KifuPlayer, 1).canonical_name == "旧名一"
