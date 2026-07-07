"""record_multiplayer_game must not choke on the engine AI's synthetic id.

Engine (human-vs-AI) games record the bot as player id -1, which has no `users`
row. Creating a UserGame for it raises a ForeignKeyViolation on Postgres and
rolls back the whole transaction -- losing the human's record too. The repo must
skip synthetic (id <= 0) players and still record the human.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.game_repo import GameRepository


@pytest.fixture
def factory_and_user():
    engine = create_engine("sqlite:///:memory:")

    # SQLite ignores FKs unless asked -- turn them ON so this test actually
    # reproduces the ForeignKeyViolation the fix prevents.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_con, _rec):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    user = models_db.User(username="human", hashed_password="x")
    s.add(user)
    s.commit()
    s.refresh(user)
    uid = user.id
    s.close()
    return SessionLocal, uid


def _count_games(factory) -> int:
    s = factory()
    try:
        return s.query(models_db.UserGame).count()
    finally:
        s.close()


def test_engine_game_human_black_records_only_human(factory_and_user):
    factory, uid = factory_and_user
    repo = GameRepository(factory)

    rec = repo.record_multiplayer_game(
        sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
        result="W+R",
        game_type="free",
        black_id=uid,  # human
        white_id=-1,  # engine AI (synthetic)
        black_name="Me",
        white_name="[golaxy] 星铠虾",
    )

    assert rec["id"] is not None
    assert _count_games(factory) == 1  # only the human's row, no -1 row, no rollback


def test_engine_game_human_white_records_only_human(factory_and_user):
    factory, uid = factory_and_user
    repo = GameRepository(factory)

    rec = repo.record_multiplayer_game(
        sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
        result="B+R",
        game_type="free",
        black_id=-1,  # engine AI (synthetic)
        white_id=uid,  # human
        black_name="[golaxy] 星铠虾",
        white_name="Me",
    )

    assert rec["id"] is not None
    assert _count_games(factory) == 1


def test_human_vs_human_still_records_both(factory_and_user):
    factory, uid = factory_and_user
    s = factory()
    other = models_db.User(username="opponent", hashed_password="x")
    s.add(other)
    s.commit()
    s.refresh(other)
    other_id = other.id
    s.close()

    repo = GameRepository(factory)
    repo.record_multiplayer_game(
        sgf_content="(;FF[4]SZ[19];B[pd];W[dp])",
        result="B+R",
        game_type="free",
        black_id=uid,
        white_id=other_id,
    )
    assert _count_games(factory) == 2  # both real players get a row (unchanged)
