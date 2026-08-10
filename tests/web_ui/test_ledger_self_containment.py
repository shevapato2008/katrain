"""The immutable ledger must identify its own owner without the rest of the database.

Cross-track principle, approved 2026-08-10. Reached independently by the chess (国象) and Go
tracks; see superpowers/tracks/golaxy-ai-ladder-parity/identity-p3-preconditions.md §E.

    Any append-only ledger row must carry an `account_subject` snapshot in the row itself,
    not merely a row reference.

Falsifiable criterion (chess track):

    Take the whole database away and keep only this row -- can you still tell whose it is?

Three qualifications, each asserted below because a principle nobody can fail is not a principle:

  1. The snapshot is NOT authoritative. `user_id` is the runtime operational key;
     `account_subject` is a historical fact frozen at settlement -- written once, never updated,
     no FK, never joined on. An audit row is ALLOWED to disagree with the present; that is the
     entire point, because it records the past.
  2. Scope is immutable ledgers ONLY. Mutable profiles are derived state (the present IS the
     truth) and short-lived reservations are not audit objects. Widening the scope degrades this
     into "add a uuid column to every table", which would undo "row references never leave the DB".
  3. `display_name` is NOT copied. It is mutable and explicitly non-deciding
     (identity-vocabulary-freeze-2026-08-10.md §2); copying it invites future code to match on it.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import (
    AI_LADDER_GAME_TYPE,
    AiLadderOpponentSnapshot,
    AiLadderRankedRepository,
    initial_placement_window,
)

ACCOUNT_SUBJECT_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def user(session_factory):
    with session_factory() as db:
        row = models_db.User(username="fan", hashed_password="x", rank="5d")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


@pytest.fixture
def opponent(user):
    lo, _hi = initial_placement_window(user.rank)
    return AiLadderOpponentSnapshot(
        rung=lo,
        rank_name="fixture",
        config_snapshot={"config_digest": "fixture", "config_version": "v1"},
        certification_status="certified",
        availability="available",
        route="server",
    )


def _settle(repo, user_id, game_id, opponent, result="B+R"):
    return repo.settle_game(
        user_id=user_id,
        game_id=game_id,
        user_color="B",
        result=result,
        game_type=AI_LADDER_GAME_TYPE,
        opponent=opponent,
    )


def _ledger(session_factory, game_id):
    with session_factory() as db:
        return db.query(models_db.AiLadderGameLedger).filter(models_db.AiLadderGameLedger.game_id == game_id).one()


def test_ledger_row_carries_account_subject(session_factory, user, opponent):
    """The row records WHO, in the row."""
    repo = AiLadderRankedRepository(session_factory)
    _settle(repo, user.id, "g1", opponent)

    row = _ledger(session_factory, "g1")
    assert row.account_subject == user.uuid
    assert ACCOUNT_SUBJECT_RE.match(row.account_subject), f"not a frozen subject: {row.account_subject!r}"


def test_orphan_row_still_identifies_its_owner(session_factory, user, opponent):
    """THE criterion: delete the entire rest of the database; the row still names its owner."""
    repo = AiLadderRankedRepository(session_factory)
    _settle(repo, user.id, "g2", opponent)
    subject = user.uuid

    with session_factory() as db:
        # Take the whole database away -- every table except the ledger itself.
        db.execute(text("DELETE FROM ai_ladder_profiles"))
        db.execute(text("DELETE FROM users"))
        db.commit()

    with session_factory() as db:
        row = db.query(models_db.AiLadderGameLedger).filter(models_db.AiLadderGameLedger.game_id == "g2").one()
        assert row.account_subject == subject, "ledger row lost its owner when the account row went away"
        # Sanity: the row reference really is dangling, so the subject is doing the work.
        assert row.user is None
        assert db.get(models_db.User, row.user_id) is None


def test_account_subject_is_not_a_foreign_key(session_factory):
    """Qualification 1, executable form: a FK would mean somebody is joining on it."""
    engine = session_factory.kw["bind"]
    fks = inspect(engine).get_foreign_keys("ai_ladder_game_ledger")
    offenders = [fk for fk in fks if "account_subject" in (fk.get("constrained_columns") or [])]
    assert offenders == [], f"account_subject must not be a FK; found {offenders}"


def test_account_subject_is_frozen_and_never_follows_the_account(session_factory, user, opponent):
    """Qualification 1: the audit row is ALLOWED to disagree with the present."""
    repo = AiLadderRankedRepository(session_factory)
    _settle(repo, user.id, "g3", opponent)
    original = user.uuid

    with session_factory() as db:
        account = db.get(models_db.User, user.id)
        account.uuid = "ffffffffffffffffffffffffffffffff"  # account re-subjected upstream
        db.commit()

    row = _ledger(session_factory, "g3")
    assert row.account_subject == original, "ledger followed the account instead of recording the past"


def test_mutable_tables_do_not_carry_a_subject(session_factory):
    """Qualification 2: scope is immutable ledgers only, not profiles or reservations."""
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)
    for table in ("ai_ladder_profiles", "ai_ladder_pending_games"):
        cols = {c["name"] for c in inspector.get_columns(table)}
        assert "account_subject" not in cols, (
            f"{table} is mutable/short-lived and must NOT carry a frozen subject -- "
            "widening the scope undoes 'row references never leave the DB'"
        )


def test_display_name_is_not_copied_into_the_ledger(session_factory):
    """Qualification 3: only the immutable subject is frozen, never the display name."""
    engine = session_factory.kw["bind"]
    cols = {c["name"] for c in inspect(engine).get_columns("ai_ladder_game_ledger")}
    for forbidden in ("display_name", "username"):
        assert forbidden not in cols, f"{forbidden} is mutable and non-deciding; it must not be frozen here"


def test_ignored_games_also_carry_the_subject(session_factory, user, opponent):
    """An ignored settlement still writes a ledger row, so it must be identifiable too."""
    repo = AiLadderRankedRepository(session_factory)
    # A non-ladder game type is recorded but not counted.
    repo.settle_game(
        user_id=user.id,
        game_id="g4",
        user_color="B",
        result="B+R",
        game_type="casual",
        opponent=opponent,
    )
    row = _ledger(session_factory, "g4")
    assert row.counted is False, "sanity: this settlement should have been ignored"
    assert row.account_subject == user.uuid, "ignored rows are audit rows too"
