"""A shared board must write each game under its owning cloud account."""

import asyncio
import json
from functools import partial
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core.repository import RemoteUserGameRepository, RepositoryDispatcher, enqueue_sync_item
from katrain.web.core.sync_worker import SyncWorker
from katrain.web.core.user_game_repo import UserGameRepository

JIA, YI = 7, 8
CLOUD_ACCOUNT_BY_BEARER = {"tok-jia": "甲", "tok-jia-new": "甲", "tok-yi": "乙", "tok-yi-new": "乙"}


def _box(cloud_handler=None):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    library = {}

    def cloud(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/v1/user-games/":
            return httpx.Response(404)
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        account = CLOUD_ACCOUNT_BY_BEARER.get(token)
        if account is None:
            return httpx.Response(401, json={"detail": "Not authenticated"})
        library.setdefault(account, []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": f"cloud-{sum(map(len, library.values()))}"})

    remote = RemoteAPIClient(base_url="http://cloud.test", device_id="box-1")
    remote._client = httpx.AsyncClient(
        base_url="http://cloud.test", transport=httpx.MockTransport(cloud_handler or cloud)
    )
    connectivity = SimpleNamespace(is_online=True)
    dispatcher = RepositoryDispatcher(
        connectivity_manager=connectivity,
        remote_tsumego=None,
        remote_kifu=None,
        remote_user_games=RemoteUserGameRepository(remote),
        local_user_game_repo=UserGameRepository(factory),
        sync_enqueue_fn=partial(enqueue_sync_item, factory, device_id="box-1"),
        remote_client=remote,
    )
    return SimpleNamespace(
        factory=factory,
        library=library,
        remote=remote,
        connectivity=connectivity,
        dispatcher=dispatcher,
        worker=SyncWorker(factory, remote),
    )


def _sign_in(box, token, user_id):
    box.remote.set_tokens(token, f"refresh-{token}")
    box.remote.bind_user(user_id)


def _game(black):
    return {"sgf_content": f"(;GM[1]PB[{black}])", "source": "play_ai", "player_black": black, "result": "W+R"}


def _local_blacks(box, user_id):
    return [game["player_black"] for game in box.dispatcher._local_user_game_repo.list(user_id=user_id)["items"]]


def _queue(box):
    with box.factory() as db:
        rows = db.query(models_db.SyncQueueEntry).order_by(models_db.SyncQueueEntry.id).all()
        return [(row.operation, row.user_id, row.status) for row in rows]


async def test_a_game_that_ends_after_the_box_switched_to_yi_stays_out_of_yis_cloud_library():
    box = _box()
    _sign_in(box, "tok-yi", YI)

    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))

    assert box.library == {}, "甲的棋谱进了乙的云端棋谱库"
    assert _local_blacks(box, JIA) == ["甲"]
    assert _queue(box) == [("create_user_game", str(JIA), "pending")]


async def test_a_queued_game_waits_for_its_owner_without_holding_up_anyone_else():
    box = _box()
    _sign_in(box, "tok-jia", JIA)
    box.connectivity.is_online = False
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
    _sign_in(box, "tok-yi", YI)
    await box.dispatcher.user_games_create(user_id=YI, data=_game("乙"))
    box.connectivity.is_online = True

    synced = await box.worker.run_sync()

    assert box.library == {"乙": ["乙"]}, "重放把甲的棋谱发进了乙的云端棋谱库"
    assert synced == 1
    assert _queue(box) == [
        ("create_user_game", str(JIA), "pending"),
        ("create_user_game", str(YI), "completed"),
    ]

    _sign_in(box, "tok-jia", JIA)
    assert await box.worker.run_sync() == 1
    assert box.library == {"乙": ["乙"], "甲": ["甲"]}


async def test_the_owners_own_session_still_goes_straight_to_the_cloud():
    box = _box()
    _sign_in(box, "tok-jia", JIA)

    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))

    assert box.library == {"甲": ["甲"]}
    assert _local_blacks(box, JIA) == [] and _queue(box) == []


@pytest.mark.parametrize("pause_at", ["first_post", "refresh"])
async def test_switching_cloud_user_during_401_keeps_both_games_with_their_owners(pause_at):
    entered, release = asyncio.Event(), asyncio.Event()
    box = None

    async def cloud(request):
        path = request.url.path
        if path == "/api/v1/auth/refresh":
            refresh = json.loads(request.content)["refresh_token"]
            if pause_at == "refresh" and refresh == "refresh-tok-jia":
                entered.set()
                await release.wait()
            token = "tok-jia-new" if refresh == "refresh-tok-jia" else "tok-yi-new"
            return httpx.Response(200, json={"access_token": token})
        if path != "/api/v1/user-games/":
            return httpx.Response(404)
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            if pause_at == "first_post":
                entered.set()
                await release.wait()
            return httpx.Response(401)
        account = CLOUD_ACCOUNT_BY_BEARER[bearer]
        box.library.setdefault(account, []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    pending = asyncio.create_task(box.dispatcher.user_games_create(user_id=JIA, data=_game("甲")))
    await asyncio.wait_for(entered.wait(), timeout=2)
    _sign_in(box, "tok-yi", YI)
    release.set()
    await pending
    assert box.remote._access_token == "tok-yi" and box.remote.bound_user_id == str(YI)
    assert not box.remote.auth_required
    assert _local_blacks(box, JIA) == ["甲"]
    assert _queue(box) == [("create_user_game", str(JIA), "pending")]
    await box.dispatcher.user_games_create(user_id=YI, data=_game("乙"))
    assert box.library == {"乙": ["乙"]}


async def test_queued_game_returns_to_pending_when_owner_changes_during_401():
    entered, release = asyncio.Event(), asyncio.Event()
    box = None

    async def cloud(request):
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "tok-yi-new"})
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            entered.set()
            await release.wait()
            return httpx.Response(401)
        box.library.setdefault("乙", []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    box.connectivity.is_online = False
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
    box.connectivity.is_online = True
    pending = asyncio.create_task(box.worker.run_sync())
    await asyncio.wait_for(entered.wait(), timeout=2)
    _sign_in(box, "tok-yi", YI)
    release.set()
    assert await pending == 0
    assert box.library == {}
    assert _queue(box) == [("create_user_game", str(JIA), "pending")]
    with box.factory() as db:
        assert db.query(models_db.SyncQueueEntry).one().retry_count == 0


async def test_same_owner_401_still_refreshes_and_writes_directly():
    box = None

    async def cloud(request):
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "tok-jia-new"})
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
        if bearer == "tok-jia":
            return httpx.Response(401)
        box.library.setdefault("甲", []).append(json.loads(request.content)["player_black"])
        return httpx.Response(200, json={"id": "cloud-1"})

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
    assert box.library == {"甲": ["甲"]} and _queue(box) == []


@pytest.mark.parametrize("conflict_code", ["report_bound_game_immutable", "user_game_identity_conflict", None])
async def test_online_explicit_game_refusals_do_not_save_or_enqueue_a_rejected_write(conflict_code):
    body = (
        {"detail": {"code": conflict_code, "message": "请另存棋谱"}}
        if conflict_code
        else {"detail": "Already exists"}
    )

    async def cloud(request):
        return httpx.Response(409, json=body)

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    try:
        if conflict_code:
            with pytest.raises(httpx.HTTPStatusError) as error:
                await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
            assert error.value.response.status_code == 409
            assert error.value.response.json() == body
            assert _local_blacks(box, JIA) == [] and _queue(box) == []
        else:
            # Legacy duplicate conflicts keep their established local fallback.
            await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
            assert _local_blacks(box, JIA) == ["甲"]
            assert _queue(box) == [("create_user_game", str(JIA), "pending")]
    finally:
        await box.remote.close()


@pytest.mark.parametrize("conflict_code", ["report_bound_game_immutable", "user_game_identity_conflict", None])
async def test_sync_explicit_game_refusals_are_failed_instead_of_falsely_synced(conflict_code):
    calls = []
    body = (
        {"detail": {"code": conflict_code, "message": "请另存棋谱"}}
        if conflict_code
        else {"detail": "Already exists"}
    )

    async def cloud(request):
        calls.append(request)
        return httpx.Response(409, json=body)

    box = _box(cloud_handler=cloud)
    _sign_in(box, "tok-jia", JIA)
    try:
        box.connectivity.is_online = False
        await box.dispatcher.user_games_create(user_id=JIA, data=_game("甲"))
        assert _local_blacks(box, JIA) == ["甲"]
        assert _queue(box) == [("create_user_game", str(JIA), "pending")]
        box.connectivity.is_online = True

        assert await box.worker.run_sync() == (0 if conflict_code else 1)
        with box.factory() as db:
            item = db.query(models_db.SyncQueueEntry).one()
            assert item.last_http_status == 409
            assert item.status == ("failed" if conflict_code else "completed")
            assert (item.synced_at is None) == bool(conflict_code)
            if conflict_code:
                assert conflict_code in item.last_error
                assert box.worker.describe(item.idempotency_key, user_id=JIA)["state"] == "refused"
        assert box.worker.revive_retryable_failures() == 0
        assert await box.worker.run_sync() == 0
        assert len(calls) == 1
    finally:
        await box.remote.close()
