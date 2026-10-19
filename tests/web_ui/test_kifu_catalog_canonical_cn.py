"""Pinned canonical Chinese changes for the six reviewed catalog identities."""

import pytest
from sqlalchemy import create_engine, select

from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
)
from katrain.web.kifu.catalog_canonical_cn import apply_canonical_cn, dry_run_canonical_cn
from katrain.web.kifu.identity import normalize_alias


PLAYERS = (
    (1, "Go Seigen", "吴清源"),
    (2, "Honinbo Dosaku", "本因坊道策"),
    (3, "Honinbo Jowa", "本因坊丈和"),
    (4, "Honinbo Shusaku", "本因坊秀策"),
    (5, "Kitani Minoru", "木谷实"),
)
EVENT = (22, "Oteai", "大手合")


@pytest.fixture
def engine():
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    with db_engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert(), [
            {"id": row_id, "canonical_name": old} for row_id, old, _ in PLAYERS
        ])
        conn.execute(KifuEvent.__table__.insert().values(id=EVENT[0], canonical_name=EVENT[1]))
        conn.execute(KifuPlayerName.__table__.insert().values(
            player_id=1, lang="en", display_name="Go Seigen", status="verified"
        ))
        conn.execute(KifuEventName.__table__.insert().values(
            event_id=EVENT[0], lang="jp", display_name="大手合", status="verified"
        ))
        conn.execute(KifuAlbum.__table__.insert().values(
            id=99, black_player_id=1, white_player_id=5, event_id=EVENT[0],
            player_black="Go Seigen", player_white="Kitani Minoru", sgf_content="(;B[aa])",
            source_path="test.sgf",
        ))
    yield db_engine
    db_engine.dispose()


def test_dry_run_previews_six_changes_without_writing(engine):
    report = dry_run_canonical_cn(engine)
    assert len(report) == 6
    assert all(row["action"] == "rename" and row["english_alias"] == "create" for row in report)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == 1)) == "Go Seigen"
        assert conn.scalar(select(KifuPlayerAlias.id)) is None


def test_apply_keeps_ids_album_links_verified_names_and_english_aliases(engine):
    report = apply_canonical_cn(engine)
    assert len(report) == 6
    with engine.connect() as conn:
        for row_id, old, chinese in PLAYERS:
            assert conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == row_id)) == chinese
            assert conn.scalar(select(KifuPlayerAlias.alias).where(
                KifuPlayerAlias.player_id == row_id,
                KifuPlayerAlias.normalized_alias == normalize_alias(old),
            )) == old
        assert conn.scalar(select(KifuEvent.canonical_name).where(KifuEvent.id == EVENT[0])) == EVENT[2]
        assert conn.scalar(select(KifuEventAlias.alias).where(KifuEventAlias.event_id == EVENT[0])) == EVENT[1]
        album = conn.execute(select(
            KifuAlbum.black_player_id, KifuAlbum.white_player_id, KifuAlbum.event_id,
            KifuAlbum.player_black, KifuAlbum.player_white,
        ).where(KifuAlbum.id == 99)).one()
        assert album == (1, 5, 22, "Go Seigen", "Kitani Minoru")
        assert conn.scalar(select(KifuPlayerName.display_name).where(KifuPlayerName.player_id == 1)) == "Go Seigen"
        assert conn.scalar(select(KifuEventName.display_name).where(KifuEventName.event_id == 22)) == "大手合"


def test_reapply_is_idempotent(engine):
    apply_canonical_cn(engine)
    assert all(row["action"] == "already_applied" for row in dry_run_canonical_cn(engine))
    assert all(row["action"] == "already_applied" for row in apply_canonical_cn(engine))
    with engine.connect() as conn:
        assert len(conn.execute(select(KifuPlayerAlias.id)).all()) == 5
        assert len(conn.execute(select(KifuEventAlias.id)).all()) == 1


def test_already_chinese_row_does_not_create_alias_without_old_preimage(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 1).values(canonical_name="吴清源"))
    report = apply_canonical_cn(engine)
    assert report[0]["action"] == "already_applied"
    assert report[0]["english_alias"] == "missing"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.player_id == 1)) is None


def test_stale_preimage_rejects_whole_batch(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.update().where(KifuPlayer.id == 2).values(canonical_name="Changed"))
    with pytest.raises(ValueError, match="preimage"):
        apply_canonical_cn(engine)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == 1)) == "Go Seigen"
        assert conn.scalar(select(KifuPlayerAlias.id)) is None


@pytest.mark.parametrize("collision", ["canonical", "alias"])
def test_chinese_name_collision_rejects_whole_batch(engine, collision):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(
            id=99, canonical_name="吴清源" if collision == "canonical" else "Other"
        ))
        if collision == "alias":
            conn.execute(KifuPlayerAlias.__table__.insert().values(
                player_id=99, alias="吴清源", normalized_alias=normalize_alias("吴清源")
            ))
    with pytest.raises(ValueError, match="collision"):
        apply_canonical_cn(engine)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == 1)) == "Go Seigen"
        assert conn.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.player_id == 1)) is None


def test_old_english_alias_collision_is_skipped(engine):
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=99, canonical_name="Other"))
        conn.execute(KifuPlayerAlias.__table__.insert().values(
            player_id=99, alias="Go Seigen", normalized_alias=normalize_alias("Go Seigen")
        ))
    report = apply_canonical_cn(engine)
    assert report[0]["english_alias"] == "collision_skipped"
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == 1)) == "吴清源"
        assert conn.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.player_id == 1)) is None


def test_oteai_uses_its_unique_actual_id_in_each_environment():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert(), [
            {"id": row_id, "canonical_name": old} for row_id, old, _ in PLAYERS
        ])
        conn.execute(KifuEvent.__table__.insert().values(id=1, canonical_name="Oteai"))
    assert dry_run_canonical_cn(engine)[-1]["id"] == 1
    assert apply_canonical_cn(engine)[-1]["id"] == 1
    with engine.connect() as conn:
        assert conn.scalar(select(KifuEvent.canonical_name).where(KifuEvent.id == 1)) == "大手合"
    engine.dispose()
