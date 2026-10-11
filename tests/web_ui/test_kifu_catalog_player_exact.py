import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_exact import capture_exact_plan, run_exact_plan
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'exact.db'}")
    Base.metadata.create_all(engine)
    rows = []
    with Session(engine) as db:
        db.add(KifuPlayer(id=1, canonical_name="井山裕太"))
        db.add(KifuRawPlayerValue(raw_value="井山裕太", category="readable_unlinked", review_status="pending"))
        for i, white, fk in [(1, "对手", None), (2, "对手", 1), (3, "井山裕太", None)]:
            db.add(
                KifuAlbum(
                    id=i,
                    player_black="井山裕太",
                    player_white=white,
                    date_played="2020-01-01",
                    black_player_id=fk,
                    source_path=f"{i}.sgf",
                    sgf_content="(;GM[1])",
                )
            )
            row = dict.fromkeys(ASSOCIATION_COLUMNS)
            row.update(
                id=i,
                player_black="井山裕太",
                player_white=white,
                date_played="2020-01-01",
                black_player_id=fk,
                sources=[],
            )
            rows.append([row[k] for k in ASSOCIATION_COLUMNS])
        db.commit()
    inv = {
        "counts": {"all": 3},
        "sha256": "inv",
        "association_columns": list(ASSOCIATION_COLUMNS),
        "album_associations": rows,
    }
    spec = {
        "environment": "test",
        "targets": {"井山裕太": 1},
        "exact_raw_to_canonical": {"井山裕太": "井山裕太"},
        "candidate_slots": [[1, "black", "井山裕太", "2020-01-01", None, 1]],
        "protected_already_linked": [[2, "black", "井山裕太", "2020-01-01", 1]],
        "held_slots": [[3, s, "井山裕太", "2020-01-01", None] for s in ["black", "white"]],
    }
    return engine, inv, spec


def test_exact_rollback_apply_and_partial_raw(tmp_path):
    e, i, s = setup(tmp_path)
    p = capture_exact_plan(i, s, "review", "test", e)
    assert run_exact_plan(i, s, "review", "test", p, e)["new_fk_slots"] == 1
    with Session(e) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None
    run_exact_plan(i, s, "review", "test", p, e, apply=True, plan_sha256="pin", approved_plan_sha256="pin")
    with Session(e) as db:
        assert db.get(KifuAlbum, 1).black_player_id == 1
        assert db.get(KifuAlbum, 2).black_player_id == 1
        assert db.get(KifuAlbum, 3).black_player_id is None and db.get(KifuAlbum, 3).white_player_id is None
        raw = db.scalar(select(KifuRawPlayerValue))
        assert raw.review_status == "pending"
        assert raw.review_metadata["held_album_ids"] == [3]


def test_stale_fk_and_approval_gate(tmp_path):
    e, i, s = setup(tmp_path)
    p = capture_exact_plan(i, s, "review", "test", e)
    with pytest.raises(ValueError, match="approval"):
        run_exact_plan(i, s, "review", "test", p, e, apply=True)
    with Session(e) as db:
        db.get(KifuAlbum, 3).white_player_id = 1
        db.commit()
    with pytest.raises(ValueError, match="preimage"):
        run_exact_plan(i, s, "review", "test", p, e)


def test_alias_and_raw_metadata_conflicts(tmp_path):
    from katrain.web.core.models_db import KifuPlayerAlias

    e, i, s = setup(tmp_path)
    with Session(e) as db:
        db.add(KifuPlayer(id=2, canonical_name="异人"))
        db.add(KifuPlayerAlias(player_id=2, alias="井山裕太", normalized_alias="井山裕太"))
        db.commit()
    with pytest.raises(ValueError, match="alias identity conflict"):
        capture_exact_plan(i, s, "review", "test", e)
    with Session(e) as db:
        db.delete(db.scalar(select(KifuPlayerAlias)))
        db.scalar(select(KifuRawPlayerValue)).review_metadata = {"player_id": 2}
        db.commit()
    with pytest.raises(ValueError, match="metadata identity conflict"):
        capture_exact_plan(i, s, "review", "test", e)


@pytest.mark.parametrize("collision", ["canonical", "alias"])
def test_exact_raw_other_id_collision(tmp_path, collision):
    from katrain.web.core.models_db import KifuPlayerAlias

    e, i, s = setup(tmp_path)
    s["exact_raw_to_canonical"] = {"井山裕太": "井山裕太", "井山裕太九段": "井山裕太"}
    with Session(e) as db:
        db.get(KifuAlbum, 1).player_black = "井山裕太九段"
        db.add(KifuRawPlayerValue(raw_value="井山裕太九段", category="readable_unlinked", review_status="pending"))
        db.add(KifuPlayer(id=2, canonical_name="井山裕太九段" if collision == "canonical" else "异人"))
        if collision == "alias":
            db.add(KifuPlayerAlias(player_id=2, alias="井山裕太九段", normalized_alias="井山裕太九段"))
        db.commit()
    columns = {k: n for n, k in enumerate(i["association_columns"])}
    i["album_associations"][0][columns["player_black"]] = "井山裕太九段"
    s["candidate_slots"][0][2] = "井山裕太九段"
    with pytest.raises(ValueError, match="exact raw.*identity conflict"):
        capture_exact_plan(i, s, "review", "test", e)
