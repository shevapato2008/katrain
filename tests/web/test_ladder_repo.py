"""Ladder storage: placement, promotion, and idempotent settlement, against a real DB.

Uses an in-memory SQLite engine rather than mocks, because the two behaviours that
matter most here are transactional: a settlement must move the rank and write its
ledger row together, and a replayed game_id must move nothing at all.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ladder_catalog import position_count, position_of, rung_at
from katrain.web.core.ladder_progress import NET_WIN_THRESHOLD, PLACEMENT_GAMES
from katrain.web.core.ladder_repo import read_state, settle_game


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_user(db, username="p", legacy_rank="20k"):
    user = models_db.User(username=username, hashed_password="x", rank=legacy_rank)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_a_new_user_is_unplaced_and_gets_a_placement_opponent(db):
    user = make_user(db)
    state = read_state(db, user.id)
    assert state.rung is None and state.rank_name is None
    assert state.placement is not None
    assert state.placement.games_done == 0
    assert state.placement.games_total == PLACEMENT_GAMES
    assert 1 <= position_of(state.opponent_rung) <= position_count()


def test_reading_state_does_not_write_to_the_account(db):
    user = make_user(db)
    read_state(db, user.id)
    db.expire_all()
    fresh = db.query(models_db.User).filter_by(id=user.id).one()
    assert fresh.ai_ladder_placement_lo is None
    assert fresh.ai_ladder_placement_games == 0


def test_five_placement_games_assign_a_rung(db):
    user = make_user(db)
    for i in range(PLACEMENT_GAMES):
        state = read_state(db, user.id)
        assert state.rung is None, f"placed early after {i} games"
        assert settle_game(db, user.id, f"g{i}", state.opponent_rung, won=True)

    final = read_state(db, user.id)
    assert final.placement is None
    assert final.rung is not None
    assert final.rank_name
    # A fresh account tops out at the placement window, not at the top of the ladder.
    assert position_of(final.rung) == min(32, position_count())


def test_placement_writes_one_ledger_row_per_game(db):
    user = make_user(db)
    for i in range(PLACEMENT_GAMES):
        state = read_state(db, user.id)
        settle_game(db, user.id, f"g{i}", state.opponent_rung, won=(i % 2 == 0))
    rows = db.query(models_db.AiLadderLedger).filter_by(user_id=user.id).all()
    assert len(rows) == PLACEMENT_GAMES
    assert all(r.is_placement for r in rows)
    assert rows[-1].rung_after is not None, "the last placement game must record the settled rung"


def place_at(db, user, position):
    user.ai_ladder_rung = rung_at(position)
    user.ai_ladder_net_wins = 0
    db.commit()


def test_a_placed_user_plays_their_own_tier(db):
    user = make_user(db)
    place_at(db, user, 10)
    state = read_state(db, user.id)
    assert state.opponent_rung == rung_at(10)
    assert state.rung_below.rung == rung_at(9)
    assert state.rung_above.rung == rung_at(11)


def test_three_net_wins_promote_one_tier(db):
    user = make_user(db)
    place_at(db, user, 10)
    for i in range(NET_WIN_THRESHOLD):
        settle_game(db, user.id, f"w{i}", rung_at(10), won=True)
    state = read_state(db, user.id)
    assert position_of(state.rung) == 11
    assert state.net_wins == 0


def test_three_wins_and_two_losses_do_not_promote(db):
    user = make_user(db)
    place_at(db, user, 10)
    for i, won in enumerate([True, False, True, True, False]):
        settle_game(db, user.id, f"m{i}", rung_at(10), won=won)
    state = read_state(db, user.id)
    assert position_of(state.rung) == 10
    assert state.net_wins == 1


def test_the_bottom_tier_cannot_be_demoted_below_the_ladder(db):
    user = make_user(db)
    place_at(db, user, 1)
    for i in range(NET_WIN_THRESHOLD):
        settle_game(db, user.id, f"l{i}", rung_at(1), won=False)
    state = read_state(db, user.id)
    assert position_of(state.rung) == 1


def test_replaying_a_settlement_moves_nothing(db):
    user = make_user(db)
    place_at(db, user, 10)
    assert settle_game(db, user.id, "same-game", rung_at(10), won=True) is not None
    after_first = read_state(db, user.id)

    assert settle_game(db, user.id, "same-game", rung_at(10), won=True) is None
    after_replay = read_state(db, user.id)

    assert (after_replay.rung, after_replay.net_wins) == (after_first.rung, after_first.net_wins)
    assert db.query(models_db.AiLadderLedger).filter_by(game_id="same-game").count() == 1


def test_recent_form_is_ledger_derived_and_capped(db):
    user = make_user(db)
    place_at(db, user, 10)
    pattern = [True, True, False, True, False, True, False]
    for i, won in enumerate(pattern):
        settle_game(db, user.id, f"r{i}", rung_at(10), won=won)
    state = read_state(db, user.id)
    assert len(state.recent) == 5
    assert [g.won for g in state.recent] == pattern[-5:], "oldest first, most recent last"


def test_a_settlement_reports_the_move_it_made(db):
    """The player is told what happened by the settlement itself, not by diffing
    two reads -- so `settle_game` has to hand back the before AND the after."""
    user = make_user(db)
    place_at(db, user, 10)
    first = settle_game(db, user.id, "s1", rung_at(10), won=True)
    assert (first.won, first.is_placement) == (True, False)
    assert (first.net_wins_before, first.net_wins_after) == (0, 1)
    assert first.rung_before == first.rung_after == rung_at(10)
    assert first.moved == 0

    settle_game(db, user.id, "s2", rung_at(10), won=True)
    third = settle_game(db, user.id, "s3", rung_at(10), won=True)
    assert third.moved == 1, "the third net win is the promotion"
    assert third.rung_before == rung_at(10) and third.rung_after == rung_at(11)
    assert (third.net_wins_before, third.net_wins_after) == (2, 0), "counter resets on promotion"


def test_a_demotion_reports_moved_minus_one(db):
    user = make_user(db)
    place_at(db, user, 10)
    for i in range(NET_WIN_THRESHOLD - 1):
        settle_game(db, user.id, f"d{i}", rung_at(10), won=False)
    last = settle_game(db, user.id, "d-last", rung_at(10), won=False)
    assert last.moved == -1
    assert last.rung_before == rung_at(10) and last.rung_after == rung_at(9)
    assert last.net_wins_after == 0


def test_a_saturated_promotion_reports_no_move(db):
    """At the top the position cannot rise, so `moved` must stay 0 -- a dialog
    announcing 升段 into the same rung would be a lie."""
    user = make_user(db)
    place_at(db, user, position_count())
    for i in range(NET_WIN_THRESHOLD - 1):
        settle_game(db, user.id, f"t{i}", rung_at(position_count()), won=True)
    last = settle_game(db, user.id, "t-last", rung_at(position_count()), won=True)
    assert last.moved == 0
    assert last.rung_before == last.rung_after == rung_at(position_count())
    assert last.net_wins_after == 0, "the counter still resets, so no credit is banked"


def test_placement_settlements_report_placement_progress(db):
    user = make_user(db)
    seen = []
    for i in range(PLACEMENT_GAMES):
        state = read_state(db, user.id)
        seen.append(settle_game(db, user.id, f"p{i}", state.opponent_rung, won=(i % 2 == 0)))
    assert [s.is_placement for s in seen] == [True] * PLACEMENT_GAMES
    assert [s.placement_games_done for s in seen] == [1, 2, 3, 4, 5]
    assert all(s.rung_before is None for s in seen)
    assert all(s.rung_after is None for s in seen[:-1]), "no rank exists until the search collapses"
    assert seen[-1].rung_after is not None
    assert all(s.moved == 0 for s in seen), "placement never counts as a promotion"


def test_an_uncertified_opponent_is_reported_as_not_playable(db):
    """Nothing is certified today, so every tier must fail closed by default."""
    user = make_user(db)
    place_at(db, user, 10)
    state = read_state(db, user.id)
    assert state.playable is False
    assert state.blocked_reason == "not_certified"


def test_the_dev_switch_makes_a_tier_playable_without_lying_about_it(db, monkeypatch):
    from katrain.core.ladder import LADDER_ALLOW_PROVISIONAL_ENV, get_level

    user = make_user(db)
    place_at(db, user, 10)
    monkeypatch.setenv(LADDER_ALLOW_PROVISIONAL_ENV, "1")
    state = read_state(db, user.id)
    assert state.playable is True
    assert state.blocked_reason is None
    # The catalogue keeps reporting the truth; the UI badge depends on it.
    assert get_level(state.opponent_rung).certification_status == "provisional"
    assert get_level(state.opponent_rung).availability == "unavailable"
