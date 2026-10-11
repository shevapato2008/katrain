import copy

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue
from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS
from katrain.web.kifu.player_next15 import capture, run


def fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'next15.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuPlayer(id=1, canonical_name="旧字"))
        db.add(KifuPlayerName(player_id=1, lang="cn", display_name="旧字", status="review"))
        for raw in ("新人", "改字", "暂缓"):
            db.add(KifuRawPlayerValue(raw_value=raw, category="readable_unlinked", review_status="pending"))
        for album_id, raw, opponent, date, fk in [
            (1, "新人", "旧字", "2020-01-01", None),
            (2, "改字", "对手", "2020-01-02", None),
            (3, "新人", "对手", "1900-01-01", None),
            (4, "暂缓", "对手", "2020-01-04", None),
            (5, "改字", "对手", "2020-01-05", 1),
        ]:
            db.add(KifuAlbum(id=album_id, player_black=raw, player_white=opponent,
                             black_player_id=fk, date_played=date, source_path=f"{album_id}.sgf",
                             sgf_content=f"(;GM[1]PB[{raw}]PW[{opponent}]DT[{date}])"))
        db.commit()
    with Session(engine) as db:
        rows = []
        for album in db.scalars(select(KifuAlbum).order_by(KifuAlbum.id)):
            row = dict.fromkeys(ASSOCIATION_COLUMNS)
            row.update(id=album.id, player_black=album.player_black, player_white=album.player_white,
                       date_played=album.date_played, black_player_id=album.black_player_id, sources=[])
            rows.append([row[k] for k in ASSOCIATION_COLUMNS])
    inventory = {"counts": {"all": 5}, "sha256": "inventory", "association_columns": list(ASSOCIATION_COLUMNS),
                 "album_associations": rows}
    decision = {"format": "kifu-player-independent-identity-target-decision-v1", "entries": [
        {"raw": "新人", "canonical": "新人", "official_name": "新人", "slots": 2,
         "decision": "approved_exact_identity_subject_to_slot_guards", "test_target": "new", "prod_target": "new",
         "known_slot_holds": []},
        {"raw": "改字", "canonical": "改字", "official_name": "改字", "current_canonical": "旧字",
         "slots": 2, "decision": "approved_exact_identity_subject_to_slot_guards", "test_target": 1,
         "prod_target": 1, "known_slot_holds": []},
        {"raw": "暂缓", "canonical": "暂缓", "slots": 1, "decision": "hold", "test_target": None,
         "prod_target": None, "known_slot_holds": []},
    ]}
    return engine, inventory, decision


def test_capture_dry_and_apply_preserve_holds_and_names(tmp_path):
    engine, inventory, decision = fixture(tmp_path)
    plan = capture(engine, inventory, decision, "test", "review")
    assert plan["counts"] == {"approved_raws": 2, "new_ids": 1, "candidate_slots": 2,
                              "held_slots": 1, "protected_slots": 1, "whole_raw_held_slots": 1}
    assert run(engine, inventory, decision, "test", "review", plan)["committed"] is False
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id is None
    assert run(engine, inventory, decision, "test", "review", plan, apply=True,
               plan_sha256="pin", approved_plan_sha256="pin")["committed"] is True
    with Session(engine) as db:
        assert db.get(KifuAlbum, 1).black_player_id != 1
        assert db.get(KifuAlbum, 2).black_player_id == 1
        assert db.get(KifuAlbum, 3).black_player_id is None
        assert db.get(KifuAlbum, 4).black_player_id is None
        assert db.get(KifuAlbum, 5).black_player_id == 1
        assert db.get(KifuPlayer, 1).canonical_name == "旧字"
        assert db.scalar(select(KifuPlayerName.display_name)) == "旧字"


def test_collision_stale_scope_and_approval_guard(tmp_path):
    engine, inventory, decision = fixture(tmp_path)
    plan = capture(engine, inventory, decision, "test", "review")
    with pytest.raises(ValueError, match="approval"):
        run(engine, inventory, decision, "test", "review", plan, apply=True)
    with Session(engine) as db:
        db.get(KifuAlbum, 2).sgf_content += " "
        db.commit()
    with pytest.raises(ValueError, match="preimage"):
        run(engine, inventory, decision, "test", "review", plan)
    with Session(engine) as db:
        db.get(KifuAlbum, 2).sgf_content = "(;GM[1]PB[改字]PW[对手]DT[2020-01-02])"
        db.add(KifuPlayer(id=9, canonical_name="其他"))
        db.add(KifuPlayerAlias(player_id=9, alias="新人", normalized_alias="新人"))
        db.commit()
    with pytest.raises(ValueError, match="collision"):
        capture(engine, inventory, decision, "test", "review")


@pytest.mark.parametrize("collision", ["old_canonical", "normalized_alias"])
def test_reused_identity_checks_all_spellings_and_normalized_alias(tmp_path, collision):
    engine, inventory, decision = fixture(tmp_path)
    with Session(engine) as db:
        db.add(KifuPlayer(id=9, canonical_name="旧字" if collision == "old_canonical" else "其他"))
        if collision == "normalized_alias":
            db.add(KifuPlayerAlias(player_id=9, alias="unrelated", normalized_alias="改字"))
        db.commit()
    with pytest.raises(ValueError, match="collision"):
        capture(engine, inventory, decision, "test", "review")
