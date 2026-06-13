"""Tests for merge_tsumego_progress + LocalTsumegoProgressRepository.

Mirrors tests/test_user_game_repo.py (in-memory SQLite). Verifies the field
merge invariants (completed never regresses, attempts takes max, last_duration
overwrites, first_completed_at is earliest non-null) and that the local repo
upsert/list round-trips in the camelCase shape GET /progress returns.

Also exercises R1: a progress row with an unknown problem_id (no matching
tsumego_problems row) inserts cleanly because SQLite FK enforcement is OFF.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.tsumego_progress_repo import (
    LocalTsumegoProgressRepository,
    merge_tsumego_progress,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database with one test user."""
    engine = create_engine("sqlite:///:memory:")
    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    user = models_db.User(username="testuser", hashed_password="fakehash")
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id
    session.close()

    return SessionLocal, user_id


# ── merge_tsumego_progress (pure function) ──


class TestMergeTsumegoProgress:
    def test_new_record_not_completed(self):
        now = datetime(2026, 6, 13, 12, 0, 0)
        merged = merge_tsumego_progress(None, {"completed": False, "attempts": 1}, now=now)
        assert merged["completed"] is False
        assert merged["attempts"] == 1
        assert merged["first_completed_at"] is None
        assert merged["last_attempt_at"] == now
        assert merged["last_duration"] is None

    def test_new_record_completed_sets_first_completed_at(self):
        now = datetime(2026, 6, 13, 12, 0, 0)
        merged = merge_tsumego_progress(None, {"completed": True, "attempts": 2, "lastDuration": 30}, now=now)
        assert merged["completed"] is True
        assert merged["attempts"] == 2
        assert merged["first_completed_at"] == now
        assert merged["last_attempt_at"] == now
        assert merged["last_duration"] == 30

    def test_completed_or_never_regresses(self):
        existing = {"completed": True, "attempts": 3, "first_completed_at": datetime(2026, 1, 1)}
        merged = merge_tsumego_progress(existing, {"completed": False, "attempts": 5})
        # completed = existing OR incoming → stays True
        assert merged["completed"] is True

    def test_attempts_takes_max(self):
        existing = {"completed": False, "attempts": 7}
        # incoming has fewer attempts — max wins
        merged = merge_tsumego_progress(existing, {"completed": False, "attempts": 2})
        assert merged["attempts"] == 7
        # incoming has more attempts — max wins
        merged2 = merge_tsumego_progress(existing, {"completed": False, "attempts": 10})
        assert merged2["attempts"] == 10

    def test_last_duration_overwrites_when_provided(self):
        existing = {"completed": True, "attempts": 1, "last_duration": 99}
        merged = merge_tsumego_progress(existing, {"completed": True, "attempts": 1, "lastDuration": 12})
        assert merged["last_duration"] == 12

    def test_last_duration_keeps_existing_when_none(self):
        existing = {"completed": True, "attempts": 1, "last_duration": 99}
        merged = merge_tsumego_progress(existing, {"completed": True, "attempts": 1, "lastDuration": None})
        assert merged["last_duration"] == 99

    def test_first_completed_at_is_earliest_non_null(self):
        earlier = datetime(2026, 1, 1)
        later = datetime(2026, 6, 13, 12, 0, 0)
        existing = {"completed": True, "attempts": 1, "first_completed_at": earlier}
        # Already had a first_completed_at — must not be overwritten by a later now
        merged = merge_tsumego_progress(existing, {"completed": True, "attempts": 1}, now=later)
        assert merged["first_completed_at"] == earlier

    def test_first_completed_at_set_on_first_completion(self):
        now = datetime(2026, 6, 13, 12, 0, 0)
        existing = {"completed": False, "attempts": 1, "first_completed_at": None}
        merged = merge_tsumego_progress(existing, {"completed": True, "attempts": 2}, now=now)
        assert merged["first_completed_at"] == now

    def test_last_attempt_at_is_now(self):
        now = datetime(2026, 6, 13, 12, 0, 0)
        merged = merge_tsumego_progress({"attempts": 1}, {"completed": False, "attempts": 1}, now=now)
        assert merged["last_attempt_at"] == now


# ── LocalTsumegoProgressRepository ──


class TestLocalTsumegoProgressRepository:
    def test_upsert_insert_new(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        result = repo.upsert(user_id, "p1", {"completed": True, "attempts": 1, "lastDuration": 42})

        assert result["problemId"] == "p1"
        assert result["completed"] is True
        assert result["attempts"] == 1
        assert result["lastDuration"] == 42
        assert result["firstCompletedAt"] is not None
        assert result["lastAttemptAt"] is not None

    def test_upsert_unknown_problem_id_does_not_fail_r1(self, db_session):
        """R1: progress for a problem_id with no tsumego_problems row inserts OK
        because SQLite FK enforcement is off by default."""
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        # "ghost-problem" has no row in tsumego_problems
        result = repo.upsert(user_id, "ghost-problem", {"completed": False, "attempts": 1})
        assert result["problemId"] == "ghost-problem"

    def test_upsert_completed_never_regresses(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        repo.upsert(user_id, "p1", {"completed": True, "attempts": 2, "lastDuration": 10})
        # A later update with completed=False must not flip it back
        result = repo.upsert(user_id, "p1", {"completed": False, "attempts": 5})
        assert result["completed"] is True
        assert result["attempts"] == 5  # attempts still takes max

    def test_upsert_attempts_takes_max(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        repo.upsert(user_id, "p1", {"completed": False, "attempts": 9})
        result = repo.upsert(user_id, "p1", {"completed": False, "attempts": 3})
        assert result["attempts"] == 9

    def test_upsert_first_completed_at_preserved(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        first = repo.upsert(user_id, "p1", {"completed": True, "attempts": 1, "lastDuration": 5})
        first_completed = first["firstCompletedAt"]
        # Re-complete later — firstCompletedAt must be unchanged
        second = repo.upsert(user_id, "p1", {"completed": True, "attempts": 2, "lastDuration": 7})
        assert second["firstCompletedAt"] == first_completed
        assert second["lastDuration"] == 7

    def test_list_shape_matches_get_progress(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)

        repo.upsert(user_id, "p1", {"completed": True, "attempts": 1, "lastDuration": 10})
        repo.upsert(user_id, "p2", {"completed": False, "attempts": 3})

        listed = repo.list(user_id)
        assert set(listed.keys()) == {"p1", "p2"}
        entry = listed["p1"]
        assert set(entry.keys()) == {
            "problemId",
            "completed",
            "attempts",
            "firstCompletedAt",
            "lastAttemptAt",
            "lastDuration",
        }
        assert listed["p1"]["completed"] is True
        assert listed["p2"]["completed"] is False
        assert listed["p2"]["attempts"] == 3

    def test_list_empty_for_new_user(self, db_session):
        factory, user_id = db_session
        repo = LocalTsumegoProgressRepository(factory)
        assert repo.list(user_id) == {}
