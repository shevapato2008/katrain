"""Getting a board's settled ranked game to the cloud, and the cloud's answer back.

The board settles its own games (it played them). The cloud is the merge point for the
rank, because one account can play on more than one device and only one number can be
right. Everything here is about the seam between those two facts:

  - the queue has to keep moving while online, not only across a reconnect
  - an item may only be posted while the cloud session belongs to its owner
  - the same game must not be submitted twice under two names
  - rank events for one user must land in the order they happened
  - what the cloud replies supersedes the local profile
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
from katrain.web.core.connectivity import ConnectivityManager
from katrain.web.core.repository import enqueue_sync_item
from katrain.web.core.sync_worker import SyncWorker


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _client(*, bound_user_id="1", status_code=200, body=None):
    client = SimpleNamespace()
    client.auth_required = False
    client.bound_user_id = bound_user_id
    response = MagicMock()
    response.status_code = status_code
    response.text = "ok"
    response.json = MagicMock(return_value=body if body is not None else {})
    client._request = AsyncMock(return_value=response)
    return client


def _enqueue(factory, *, user_id="1", game_id="g1", operation="settle_ai_ladder_ranked"):
    enqueue_sync_item(
        factory,
        operation=operation,
        endpoint="/api/v1/ai-ladder/settlements",
        method="POST",
        payload={"game_id": game_id},
        user_id=user_id,
        idempotency_key=f"ladder-settlement:{game_id}",
    )


def _rows(factory):
    with factory() as db:
        return db.query(models_db.SyncQueueEntry).order_by(models_db.SyncQueueEntry.id).all()


def test_the_same_game_cannot_be_queued_twice_under_two_names(factory):
    _enqueue(factory, game_id="same-game")
    _enqueue(factory, game_id="same-game")

    rows = _rows(factory)
    assert len(rows) == 1
    assert rows[0].idempotency_key == "ladder-settlement:same-game"


def test_enqueue_reports_both_insert_and_idempotent_duplicate_as_durable(factory):
    common = dict(
        operation="settle_ai_ladder_ranked",
        endpoint="/api/v1/ai-ladder/settlements",
        method="POST",
        payload={"game_id": "durable"},
        user_id="1",
        idempotency_key="ladder-settlement:durable",
    )

    assert enqueue_sync_item(factory, **common) is True
    assert enqueue_sync_item(factory, **common) is True
    assert len(_rows(factory)) == 1


@pytest.mark.asyncio
async def test_a_rank_event_waits_for_its_own_owners_cloud_session(factory):
    """A board is shared. Posting under whoever logged in last moves the wrong rank."""
    _enqueue(factory, user_id="7", game_id="belongs-to-7")
    worker = SyncWorker(factory, _client(bound_user_id="9"))

    assert await worker.run_sync() == 0
    client_calls = worker._remote_client._request.await_count
    assert client_calls == 0
    assert _rows(factory)[0].status == "pending"  # held, not failed

    worker_same_user = SyncWorker(factory, _client(bound_user_id="7"))
    assert await worker_same_user.run_sync() == 1
    assert _rows(factory)[0].status == "completed"


@pytest.mark.asyncio
async def test_an_unbound_cloud_session_is_not_good_enough_to_post_a_rank_event(factory):
    _enqueue(factory, user_id="7")
    worker = SyncWorker(factory, _client(bound_user_id=None))

    assert await worker.run_sync() == 0
    assert _rows(factory)[0].status == "pending"


@pytest.mark.asyncio
async def test_ranked_settlement_409_is_a_permanent_failure_not_a_duplicate_success(factory):
    _enqueue(factory, user_id="1", game_id="conflict")
    worker = SyncWorker(factory, _client(bound_user_id="1", status_code=409))

    assert await worker.run_sync() == 0
    row = _rows(factory)[0]
    assert row.status == "failed"
    assert "409" in row.last_error


@pytest.mark.asyncio
async def test_one_users_stuck_game_holds_their_later_games_but_not_another_users(factory):
    _enqueue(factory, user_id="1", game_id="a1")
    _enqueue(factory, user_id="1", game_id="a2")
    _enqueue(factory, user_id="2", game_id="b1")

    client = _client(bound_user_id="1")
    fail_once = MagicMock(status_code=500, text="boom")
    fail_once.json = MagicMock(return_value={})
    ok = MagicMock(status_code=200, text="ok")
    ok.json = MagicMock(return_value={})
    client._request = AsyncMock(side_effect=[fail_once, ok])
    # user 2's item is skipped for a different reason (not their session), so only
    # user 1's two items are candidates; the second must not go out ahead of the first.
    worker = SyncWorker(factory, client)

    await worker.run_sync()

    rows = {r.payload["game_id"]: r for r in _rows(factory)}
    assert rows["a1"].status == "pending" and rows["a1"].retry_count == 1
    assert rows["a2"].status == "pending" and rows["a2"].retry_count == 0  # never attempted
    assert client._request.await_count == 1


@pytest.mark.asyncio
async def test_an_unordered_operation_does_not_stall_behind_a_failure(factory):
    enqueue_sync_item(
        factory,
        operation="create_user_game",
        endpoint="/api/v1/user-games/",
        method="POST",
        payload={"id": "kifu-1"},
        user_id="1",
    )
    enqueue_sync_item(
        factory,
        operation="create_user_game",
        endpoint="/api/v1/user-games/",
        method="POST",
        payload={"id": "kifu-2"},
        user_id="1",
    )
    client = _client(bound_user_id="1")
    boom = MagicMock(status_code=500, text="boom")
    boom.json = MagicMock(return_value={})
    ok = MagicMock(status_code=200, text="ok")
    ok.json = MagicMock(return_value={})
    client._request = AsyncMock(side_effect=[boom, ok])
    worker = SyncWorker(factory, client)

    synced = await worker.run_sync()

    assert synced == 1
    assert client._request.await_count == 2


@pytest.mark.parametrize(
    ("http_status", "revived"),
    [
        (None, True),  # never got an answer at all
        (503, True),  # server had a bad moment
        (404, True),  # the cloud does not have this endpoint YET -- boards run ahead
        (405, True),  # what the real cloud actually answers for an unrouted POST
        (429, True),  # asked to slow down, not to stop
        (422, False),  # the server understood and refused
        (403, False),
    ],
)
def test_revive_tells_not_now_apart_from_not_ever(factory, http_status, revived):
    _enqueue(factory, game_id="g")
    with factory() as db:
        row = db.query(models_db.SyncQueueEntry).one()
        row.status, row.retry_count, row.last_http_status = "failed", 5, http_status
        db.commit()

    assert SyncWorker(factory, _client()).revive_retryable_failures() == (1 if revived else 0)
    assert _rows(factory)[0].status == ("pending" if revived else "failed")


def test_reviving_after_an_outage_skips_what_the_server_refused_on_the_merits(factory):
    _enqueue(factory, game_id="network-victim")
    _enqueue(factory, game_id="server-said-no")
    with factory() as db:
        rows = db.query(models_db.SyncQueueEntry).order_by(models_db.SyncQueueEntry.id).all()
        rows[0].status, rows[0].retry_count, rows[0].last_http_status = "failed", 5, None
        rows[1].status, rows[1].retry_count, rows[1].last_http_status = "failed", 5, 422
        db.commit()

    worker = SyncWorker(factory, _client())
    assert worker.revive_retryable_failures() == 1

    states = {r.payload["game_id"]: (r.status, r.retry_count) for r in _rows(factory)}
    assert states["network-victim"] == ("pending", 0)
    assert states["server-said-no"] == ("failed", 5)


@pytest.mark.asyncio
async def test_the_queue_keeps_moving_while_online_without_a_reconnect(monkeypatch):
    """Backoff needs something to wake it. Reconnection alone is not that something."""
    from katrain.web.core import connectivity as connectivity_module

    monkeypatch.setattr(connectivity_module, "HEALTH_CHECK_INTERVAL", 0)
    monkeypatch.setattr(connectivity_module, "SYNC_DRAIN_INTERVAL", 0)
    client = SimpleNamespace(check_health=AsyncMock(return_value={"ok": True, "rtt_ms": 1}))
    worker = SimpleNamespace(run_sync=AsyncMock(return_value=0), revive_retryable_failures=MagicMock(return_value=0))
    manager = ConnectivityManager(client, worker)

    manager.start()
    for _ in range(200):
        await asyncio.sleep(0)
        if worker.run_sync.await_count >= 2:
            break
    await manager.stop()

    assert manager.is_online
    # More than the single reconnection drain: the loop keeps draining while online.
    assert worker.run_sync.await_count >= 2
    worker.revive_retryable_failures.assert_called()


@pytest.mark.asyncio
async def test_the_cloud_profile_in_the_reply_replaces_the_local_one(factory):
    with factory() as db:
        db.add(models_db.User(id=1, username="fan", hashed_password="x", rank="5d"))
        db.add(
            models_db.AiLadderProfile(
                user_id=1, ai_ladder_rung=None, placement_lo=1, placement_hi=32, placement_completed=0, net_score=0
            )
        )
        db.commit()
    _enqueue(factory, user_id="1", game_id="synced")
    repo = AiLadderRankedRepository(factory)
    client = _client(
        bound_user_id="1",
        body={
            "game_id": "synced",
            "counted": True,
            "profile": {
                "ai_ladder_rung": None,
                "placement_lo": 17,
                "placement_hi": 32,
                "placement_completed": 3,
                "net_score": 0,
            },
        },
    )

    assert await SyncWorker(factory, client, ai_ladder_repo=repo).run_sync() == 1

    with factory() as db:
        profile = db.get(models_db.AiLadderProfile, 1)
        assert (profile.placement_lo, profile.placement_completed) == (17, 3)
        assert profile.version == 1


@pytest.mark.asyncio
async def test_a_200_terminal_replay_still_adopts_the_cloud_profile(factory):
    with factory() as db:
        db.add(models_db.User(id=1, username="fan", hashed_password="x", rank="5d"))
        db.add(
            models_db.AiLadderProfile(
                user_id=1, ai_ladder_rung=20, placement_lo=1, placement_hi=41,
                placement_completed=5, net_score=2
            )
        )
        db.commit()
    _enqueue(factory, user_id="1", game_id="remote-end-won")
    repo = AiLadderRankedRepository(factory)
    client = _client(
        bound_user_id="1",
        body={
            "game_id": "remote-end-won",
            "counted": True,
            "replayed": True,
            "lifecycle": {
                "state": "settled",
                "game_id": "remote-end-won",
                "receipt": {"counted": True, "reason": None},
            },
            "profile": {
                "ai_ladder_rung": 19,
                "placement_lo": 1,
                "placement_hi": 41,
                "placement_completed": 5,
                "net_score": 0,
            },
        },
    )

    assert await SyncWorker(factory, client, ai_ladder_repo=repo).run_sync() == 1
    with factory() as db:
        profile = db.get(models_db.AiLadderProfile, 1)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (19, 0, 1)


@pytest.mark.asyncio
async def test_a_settlement_the_cloud_did_not_count_carries_no_profile_to_adopt(factory):
    with factory() as db:
        db.add(models_db.User(id=1, username="fan", hashed_password="x", rank="5d"))
        db.add(
            models_db.AiLadderProfile(
                user_id=1, ai_ladder_rung=20, placement_lo=1, placement_hi=41, placement_completed=5, net_score=2
            )
        )
        db.commit()
    _enqueue(factory, user_id="1", game_id="not-counted")
    repo = AiLadderRankedRepository(factory)
    client = _client(
        bound_user_id="1",
        body={
            "game_id": "not-counted",
            "counted": False,
            "reason": "opponent_not_eligible",
            "profile": {
                "ai_ladder_rung": None,
                "placement_lo": None,
                "placement_hi": None,
                "placement_completed": None,
                "net_score": None,
            },
        },
    )

    await SyncWorker(factory, client, ai_ladder_repo=repo).run_sync()

    with factory() as db:
        profile = db.get(models_db.AiLadderProfile, 1)
        assert (profile.ai_ladder_rung, profile.net_score, profile.version) == (20, 2, 0)
