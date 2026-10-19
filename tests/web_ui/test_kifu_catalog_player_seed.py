"""One-time player identity seed is narrow, atomic, and repeatable."""

import pytest
from sqlalchemy import create_engine, select

from katrain.web.core.models_db import Base, KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_seed import PLAYER_SOURCES, apply_player_seed, dry_run_player_seed
from katrain.web.kifu.identity import normalize_alias


@pytest.fixture
def engine():
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    with db_engine.begin() as conn:
        conn.execute(
            KifuRawPlayerValue.__table__.insert(),
            [{"raw_value": name, "category": "readable"} for name in PLAYER_SOURCES],
        )
    yield db_engine
    db_engine.dispose()


def test_dry_run_and_apply_only_create_four_people(engine):
    assert [row["action"] for row in dry_run_player_seed(engine)] == ["create"] * 4
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.id)) is None

    report = apply_player_seed(engine)
    assert [row["canonical_name"] for row in report] == list(PLAYER_SOURCES)
    assert all(row["id"] is not None for row in report)
    with engine.connect() as conn:
        assert set(conn.scalars(select(KifuPlayer.canonical_name))) == set(PLAYER_SOURCES)
        assert conn.scalar(select(KifuPlayerAlias.id)) is None
        assert conn.scalar(select(KifuPlayerName.id)) is None
        assert conn.scalar(select(KifuAlbum.id)) is None


def test_reapply_is_idempotent(engine):
    first = apply_player_seed(engine)
    second = apply_player_seed(engine)
    assert [row["action"] for row in second] == ["already_exists"] * 4
    assert [row["id"] for row in second] == [row["id"] for row in first]
    with engine.connect() as conn:
        assert len(conn.execute(select(KifuPlayer.id)).all()) == 4


def test_missing_raw_anchor_rejects_whole_batch(engine):
    with engine.begin() as conn:
        conn.execute(KifuRawPlayerValue.__table__.delete().where(KifuRawPlayerValue.raw_value == "藤泽秀行"))
    with pytest.raises(ValueError, match="missing exact raw Chinese player anchor"):
        apply_player_seed(engine)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.id)) is None


@pytest.mark.parametrize("kind", ["canonical", "alias"])
def test_normalized_collision_rejects_whole_batch(engine, kind):
    with engine.begin() as conn:
        conn.execute(
            KifuPlayer.__table__.insert().values(
                id=99, canonical_name=(" 藤泽秀行 " if kind == "canonical" else "Other")
            )
        )
        if kind == "alias":
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=99, alias="藤泽秀行", normalized_alias=normalize_alias("藤泽秀行")
                )
            )
    with pytest.raises(ValueError, match="collision"):
        apply_player_seed(engine)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == "常昊")) is None
