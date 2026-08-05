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
from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository


@pytest.fixture
def repo():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    repo = AiLadderRankedRepository(factory)
    repo._factory = factory  # test-side handle for seeding
    return repo


def add_user(repo, *, rank="20k", rung=None, placing=False):
    """Seed a user, optionally with a ladder profile. `placing` gives them a profile
    that exists but has not resolved into a rung yet — the mid-定级赛 state."""
    session = repo._factory()
    try:
        user = models_db.User(username="p", hashed_password="x", rank=rank)
        session.add(user)
        session.flush()
        if rung is not None or placing:
            session.add(
                models_db.AiLadderProfile(
                    user_id=user.id,
                    ai_ladder_rung=rung,
                    placement_lo=1,
                    placement_hi=41,
                    placement_completed=0,
                    net_score=0,
                    version=0,
                )
            )
        session.commit()
        return user.id
    finally:
        session.close()


def test_a_user_with_no_profile_may_not_queue_for_rated_pvp(repo):
    user_id = add_user(repo)
    assert repo.has_ladder_rank(user_id) is False


def test_a_user_still_in_placement_may_not_queue_for_rated_pvp(repo):
    """A profile row exists from the first 定级赛 game, but `ai_ladder_rung` stays
    NULL until the search collapses. Presence of the row must not grant access."""
    user_id = add_user(repo, placing=True)
    assert repo.has_ladder_rank(user_id) is False


def test_a_placed_user_may_queue_for_rated_pvp(repo):
    user_id = add_user(repo, rung=20)
    assert repo.has_ladder_rank(user_id) is True


def test_the_legacy_rank_column_does_not_grant_access(repo):
    """`users.rank` defaults to 20k and is only a placement-window seed now. A user
    carrying some other legacy value must still finish 定级赛 first."""
    user_id = add_user(repo, rank="5d")
    assert repo.has_ladder_rank(user_id) is False
