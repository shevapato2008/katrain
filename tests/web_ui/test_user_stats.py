"""The rated-PvP prerequisite, against a real DB.

This used to be "3 completed `game_type == 'rated'` games". Nothing ever wrote that
value for an AI game, so the counter sat at 0 forever while the lobby told players
to go and earn it — a closed loop with no exit. The prerequisite is now simply
"do you have a ladder rank yet", which is exactly what the 定级赛 produces.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.auth import SQLAlchemyUserRepository
from katrain.web.core.ladder_catalog import rung_at


@pytest.fixture
def repo():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    repo = SQLAlchemyUserRepository(factory)
    repo._factory = factory  # test-side handle for seeding
    return repo


def add_user(repo, **kwargs):
    session = repo._factory()
    try:
        user = models_db.User(username="p", hashed_password="x", **kwargs)
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


def test_an_unplaced_user_may_not_queue_for_rated_pvp(repo):
    user_id = add_user(repo, rank="20k")
    assert repo.has_completed_placement(user_id) is False


def test_a_placed_user_may_queue_for_rated_pvp(repo):
    user_id = add_user(repo, rank="20k", ai_ladder_rung=rung_at(10))
    assert repo.has_completed_placement(user_id) is True


def test_the_legacy_rank_column_does_not_grant_access(repo):
    """`users.rank` defaults to 20k and is only a placement-window seed now. A user
    carrying some other legacy value must still finish 定级赛 first."""
    user_id = add_user(repo, rank="5d")
    assert repo.has_completed_placement(user_id) is False
