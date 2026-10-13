"""Focused exact Latin raw linking, rollback, and stale-FK checks."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_nonhan import capture_nonhan_plan, run_nonhan_plan
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def fixture(tmp_path, selected_count=17, new_count=2):
    engine = create_engine(f"sqlite:///{tmp_path / 'nonhan.db'}")
    Base.metadata.create_all(engine)
    rows = []
    review_rows = []
    with Session(engine) as db:
        for number in range(1, selected_count + 4):
            selected = number <= selected_count
            raw = f"Latin {number}" if selected else f"Hold {number}"
            white_side = number == selected_count
            black, white = ("Opponent", raw) if white_side else (raw, "Opponent")
            db.add(KifuAlbum(id=number, player_black=black, player_white=white,
                             date_played="2020-01-01", source_path=f"{number}.sgf", sgf_content="(;GM[1])"))
            db.add(KifuRawPlayerValue(raw_value=raw, category="readable_unlinked", review_status="pending"))
            inventory_row = dict.fromkeys(ASSOCIATION_COLUMNS)
            inventory_row.update(id=number, player_black=black, player_white=white,
                                 date_played="2020-01-01", sources=[])
            rows.append([inventory_row[key] for key in ASSOCIATION_COLUMNS])
            if selected:
                new = number > selected_count - new_count
                if not new:
                    db.add(KifuPlayer(id=number, canonical_name=f"棋手{number}"))
                review_rows.append({"raw_value": raw, "expected_slots_each_environment": 1,
                                    "chinese_name": f"棋手{number}", "target_player_id_test": None if new else number,
                                    "target_player_id_prod": None if new else number,
                                    "new_player_needed": new, "expected_existing_fk": "NULL",
                                    **({"catalog_action": "create_catalog_player" if new else
                                       "retain_observed_id"} if selected_count == 15 else {}),
                                    "identity_evidence_url": f"https://example.org/{number}"})
        db.commit()
    inventory = {"sha256": "fixture-inventory", "counts": {"all": selected_count + 3},
                 "association_columns": list(ASSOCIATION_COLUMNS), "album_associations": rows}
    format_name = {17: "kifu-player-nonhan-first17-exact-allowlist-v1",
                   18: "kifu-player-nonhan-next18-exact-allowlist-v1",
                   15: "kifu-player-nonhan-ranks-41-60-safe15-exact-allowlist-v1",
                   14: "kifu-player-nonhan-ranks-81-100-exact-allowlist-v1",
                   16: "kifu-player-nonhan-ranks-121-140-exact-allowlist-v1"}[selected_count]
    allowlist = {"format": format_name, "rows": review_rows,
                 "summary": ({"raw_values": 17, "slots_test": 17, "slots_prod": 17} if selected_count == 17 else
                             {"raw_values": selected_count, "slots_each_environment": selected_count})}
    return engine, inventory, allowlist


def test_nonhan_exact_dry_run_and_apply(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path)
    plan = capture_nonhan_plan(inventory, allowlist, "review-sha", "test", engine)
    assert plan["counts"] == {"games": 20, "raw_values": 17, "slots": 17,
                              "black_slots": 16, "white_slots": 1, "new_player_ids": 2}
    assert run_nonhan_plan(inventory, allowlist, "review-sha", "test", plan, engine)["new_fk_slots"] == 17
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None
        assert db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == "棋手16")) is None
    result = run_nonhan_plan(inventory, allowlist, "review-sha", "test", plan, engine, apply=True)
    assert result["new_fk_slots"] == 17 and result["new_player_ids"] == 2
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id == 1
        assert db.get(KifuAlbum, 17).white_player_id == db.scalar(select(KifuPlayer.id).where(
            KifuPlayer.canonical_name == "棋手17"))
        assert db.get(KifuAlbum, 18).black_player_id is None
        assert db.get(KifuAlbum, 17).player_white == "Latin 17"
        raw = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "Latin 17"))
        assert raw.review_status == "approved" and raw.review_metadata["kind"] == "reviewed_nonhan_person_link"
        held = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == "Hold 18"))
        assert held.review_status == "pending" and held.review_metadata is None


def test_nonhan_rejects_new_existing_fk(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path)
    plan = capture_nonhan_plan(inventory, allowlist, "review-sha", "test", engine)
    with Session(engine) as db:
        db.get(KifuAlbum, 1).black_player_id = 2
        db.commit()
    with pytest.raises(ValueError, match="existing FK differs"):
        run_nonhan_plan(inventory, allowlist, "review-sha", "test", plan, engine, apply=True)
    with Session(engine) as db:
        assert db.get(KifuAlbum, 2).black_player_id is None
        assert db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == "棋手16")) is None


def test_next18_review_format_keeps_same_exact_preflight(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=18)
    plan = capture_nonhan_plan(inventory, allowlist, "next-review-sha", "test", engine)
    assert plan["counts"] == {"games": 21, "raw_values": 18, "slots": 18,
                              "black_slots": 17, "white_slots": 1, "new_player_ids": 2}
    assert run_nonhan_plan(inventory, allowlist, "next-review-sha", "test", plan, engine)["new_fk_slots"] == 18
    with Session(engine) as db:
        assert db.get(KifuAlbum, 18).white_player_id is None


def test_safe15_isolates_catalog_rename_action(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=15, new_count=3)
    plan = capture_nonhan_plan(inventory, allowlist, "safe15-sha", "test", engine)
    assert plan["counts"]["new_player_ids"] == 3
    assert run_nonhan_plan(inventory, allowlist, "safe15-sha", "test", plan, engine)["new_fk_slots"] == 15
    allowlist["rows"][0]["catalog_action"] = "rename_existing_catalog_player"
    with pytest.raises(ValueError, match="rename or unsupported action"):
        capture_nonhan_plan(inventory, allowlist, "safe15-sha", "test", engine)


def test_ranks_61_80_four_new_ids_dry_run(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=15, new_count=4)
    allowlist["format"] = "kifu-player-nonhan-ranks-61-80-exact-allowlist-v1"
    for row in allowlist["rows"]:
        row.pop("catalog_action")
    plan = capture_nonhan_plan(inventory, allowlist, "ranks-61-80-sha", "test", engine)
    assert plan["counts"]["new_player_ids"] == 4
    assert run_nonhan_plan(inventory, allowlist, "ranks-61-80-sha", "test", plan, engine)["new_fk_slots"] == 15
    with Session(engine) as db:
        assert db.get(KifuAlbum, 15).white_player_id is None


def test_ranks_81_100_fourteen_exact_values_dry_run(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=14)
    plan = capture_nonhan_plan(inventory, allowlist, "ranks-81-100-sha", "test", engine)
    assert plan["counts"] == {"games": 17, "raw_values": 14, "slots": 14,
                              "black_slots": 13, "white_slots": 1, "new_player_ids": 2}
    assert run_nonhan_plan(inventory, allowlist, "ranks-81-100-sha", "test", plan, engine)["new_fk_slots"] == 14
    with Session(engine) as db:
        assert db.get(KifuAlbum, 14).white_player_id is None


def test_ranks_101_120_safe14_excludes_catalog_rename(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=14, new_count=4)
    allowlist["format"] = "kifu-player-nonhan-ranks-101-120-safe14-exact-allowlist-v1"
    for row in allowlist["rows"]:
        row["catalog_action"] = "create_catalog_player" if row["new_player_needed"] else "retain_observed_id"
    plan = capture_nonhan_plan(inventory, allowlist, "safe14-sha", "test", engine)
    assert plan["counts"]["new_player_ids"] == 4
    assert run_nonhan_plan(inventory, allowlist, "safe14-sha", "test", plan, engine)["new_fk_slots"] == 14
    allowlist["rows"][0]["catalog_action"] = "rename_existing_catalog_player"
    with pytest.raises(ValueError, match="rename or unsupported action"):
        capture_nonhan_plan(inventory, allowlist, "safe14-sha", "test", engine)


@pytest.mark.parametrize("format_name,count,new_count", [
    ("kifu-player-nonhan-ranks-121-140-exact-allowlist-v1", 16, 6),
    ("kifu-player-nonhan-ranks-141-160-exact-allowlist-v1", 17, 5),
    ("kifu-player-nonhan-ranks-161-180-corrected17-exact-allowlist-v1", 17, 5),
    ("kifu-player-nonhan-ranks-181-200-exact-allowlist-v1", 18, 7),
    ("kifu-player-nonhan-ranks-201-220-exact-allowlist-v1", 17, 5),
    ("kifu-player-nonhan-ranks-221-240-safe18-exact-allowlist-v1", 18, 7),
    ("kifu-player-nonhan-ranks-241-260-corrected17-exact-allowlist-v1", 17, 8),
    ("kifu-player-nonhan-ranks-261-280-safe17-exact-allowlist-v1", 17, 4),
    ("kifu-player-nonhan-ranks-281-300-corrected18-exact-allowlist-v1", 18, 8),
    ("kifu-player-nonhan-ranks-301-320-exact-allowlist-v1", 16, 4),
    ("kifu-player-nonhan-ranks-321-340-safe17-exact-allowlist-v1", 17, 4),
    ("kifu-player-nonhan-ranks-341-360-exact-allowlist-v1", 16, 3),
])
def test_later_reviewed_formats_dry_run(tmp_path, format_name, count, new_count):
    engine, inventory, allowlist = fixture(tmp_path, selected_count=count, new_count=new_count)
    allowlist["format"] = format_name
    allowlist["summary"] = {"raw_values": count, "slots_each_environment": count}
    plan = capture_nonhan_plan(inventory, allowlist, "later-sha", "test", engine)
    assert plan["counts"]["new_player_ids"] == new_count
    assert run_nonhan_plan(inventory, allowlist, "later-sha", "test", plan, engine)["new_fk_slots"] == count
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None


def test_obsolete_ranks_161_180_allowlist_rejected(tmp_path):
    engine, inventory, allowlist = fixture(tmp_path)
    allowlist["format"] = "kifu-player-nonhan-ranks-161-180-exact-allowlist-v1"
    with pytest.raises(ValueError, match="review format or row count differs"):
        capture_nonhan_plan(inventory, allowlist, "obsolete-sha", "test", engine)
