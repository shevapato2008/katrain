"""Tests for board-mode tsumego progress offline routing + sync coalescing.

Covers RepositoryDispatcher.tsumego_update_progress:
  - online  → remote.update_progress called, no local write, no enqueue
  - offline → local upsert + exactly one sync_queue row (correct
              operation/endpoint/method/payload)
  - coalescing → two offline updates for the same problem leave ONE pending row
  - distinct problems do NOT coalesce
  - tsumego_get_progress_local reads back the local cache
  - remote failure (httpx error) falls back to local + enqueue
"""

from functools import partial

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, MagicMock

from katrain.web.core import models_db
from katrain.web.core.repository import RepositoryDispatcher, enqueue_sync_item
from katrain.web.core.tsumego_progress_repo import LocalTsumegoProgressRepository


class FakeConnectivity:
    """Minimal connectivity manager with a toggleable is_online flag."""

    def __init__(self, online: bool):
        self._online = online

    @property
    def is_online(self) -> bool:
        return self._online


@pytest.fixture
def factory_and_user():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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


def _make_dispatcher(SessionLocal, online: bool):
    remote_tsumego = MagicMock()
    remote_tsumego.update_progress = AsyncMock(return_value={"success": True})
    local_repo = LocalTsumegoProgressRepository(SessionLocal)
    sync_fn = partial(enqueue_sync_item, SessionLocal, device_id="dev-1")
    dispatcher = RepositoryDispatcher(
        connectivity_manager=FakeConnectivity(online),
        remote_tsumego=remote_tsumego,
        remote_kifu=MagicMock(),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        sync_enqueue_fn=sync_fn,
        local_tsumego_progress_repo=local_repo,
    )
    return dispatcher, remote_tsumego, SessionLocal


def _pending_rows(SessionLocal):
    session = SessionLocal()
    try:
        return session.query(models_db.SyncQueueEntry).filter(models_db.SyncQueueEntry.status == "pending").all()
    finally:
        session.close()


@pytest.mark.asyncio
async def test_online_routes_to_remote(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, remote, _ = _make_dispatcher(SessionLocal, online=True)

    data = {"completed": True, "attempts": 1, "lastDuration": 30}
    result = await dispatcher.tsumego_update_progress(user_id, "p1", data)

    remote.update_progress.assert_awaited_once_with("p1", data)
    assert result == {"success": True}
    # No local write, no enqueue when online succeeds
    assert _pending_rows(SessionLocal) == []
    assert dispatcher._local_tsumego_progress_repo.list(user_id) == {}


@pytest.mark.asyncio
async def test_offline_writes_local_and_enqueues_one(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, remote, _ = _make_dispatcher(SessionLocal, online=False)

    data = {"completed": True, "attempts": 1, "lastDuration": 30}
    result = await dispatcher.tsumego_update_progress(user_id, "p1", data)

    # Remote never called
    remote.update_progress.assert_not_called()

    # Local write happened
    assert result["problemId"] == "p1"
    assert result["completed"] is True
    listed = dispatcher._local_tsumego_progress_repo.list(user_id)
    assert "p1" in listed

    # Exactly one pending sync row with correct fields
    rows = _pending_rows(SessionLocal)
    assert len(rows) == 1
    row = rows[0]
    assert row.operation == "update_tsumego_progress"
    assert row.endpoint == "/api/v1/tsumego/progress/p1"
    assert row.method == "POST"
    assert row.payload == data
    assert row.user_id == str(user_id)


@pytest.mark.asyncio
async def test_offline_coalesces_same_problem(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, _, _ = _make_dispatcher(SessionLocal, online=False)

    await dispatcher.tsumego_update_progress(user_id, "p1", {"completed": False, "attempts": 1})
    await dispatcher.tsumego_update_progress(user_id, "p1", {"completed": True, "attempts": 2, "lastDuration": 12})

    rows = _pending_rows(SessionLocal)
    assert len(rows) == 1  # coalesced to latest
    # Latest payload wins
    assert rows[0].payload["completed"] is True
    assert rows[0].payload["attempts"] == 2


@pytest.mark.asyncio
async def test_offline_distinct_problems_do_not_coalesce(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, _, _ = _make_dispatcher(SessionLocal, online=False)

    await dispatcher.tsumego_update_progress(user_id, "p1", {"completed": True, "attempts": 1})
    await dispatcher.tsumego_update_progress(user_id, "p2", {"completed": True, "attempts": 1})

    rows = _pending_rows(SessionLocal)
    endpoints = sorted(r.endpoint for r in rows)
    assert endpoints == ["/api/v1/tsumego/progress/p1", "/api/v1/tsumego/progress/p2"]


@pytest.mark.asyncio
async def test_get_progress_local_reads_cache(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, _, _ = _make_dispatcher(SessionLocal, online=False)

    await dispatcher.tsumego_update_progress(user_id, "p1", {"completed": True, "attempts": 3, "lastDuration": 20})
    progress = await dispatcher.tsumego_get_progress_local(user_id)
    assert "p1" in progress
    assert progress["p1"]["completed"] is True
    assert progress["p1"]["attempts"] == 3
    assert progress["p1"]["lastDuration"] == 20


@pytest.mark.asyncio
async def test_online_remote_failure_falls_back_to_local(factory_and_user):
    SessionLocal, user_id = factory_and_user
    dispatcher, remote, _ = _make_dispatcher(SessionLocal, online=True)
    remote.update_progress.side_effect = httpx.ConnectError("boom")

    data = {"completed": True, "attempts": 1, "lastDuration": 5}
    result = await dispatcher.tsumego_update_progress(user_id, "p1", data)

    # Fell back to local
    assert result["problemId"] == "p1"
    rows = _pending_rows(SessionLocal)
    assert len(rows) == 1
    assert rows[0].endpoint == "/api/v1/tsumego/progress/p1"
