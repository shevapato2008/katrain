"""The account history outbox never borrows a different board user's session."""

import asyncio
import copy
import importlib.util
import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.remote_client import RemoteAPIClient
from katrain.web.core.sync_worker import SyncWorker

SGF = "(;GM[1]FF[4]SZ[19];B[aa];W[bb];B[cc])"
OPEN = {"sgf_content": SGF, "source_id": "kifu_1", "name": "Example"}
JIA, YI, CLOUD_JIA = 1, 2, 101


def test_history_service_exists():
    assert importlib.util.find_spec("katrain.web.core.baipu_history_sync") is not None


def _factory(path):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add_all(models_db.User(id=i, username=f"u{i}", hashed_password="x") for i in (JIA, YI, CLOUD_JIA))
    return engine, factory


@pytest.fixture
def box(tmp_path):
    from katrain.web.core.baipu_history import BaipuHistoryRepository
    from katrain.web.core.baipu_history_sync import BaipuHistoryService

    engines, local_factory = _factory(tmp_path / "local.db")
    cloud_engine, cloud_factory = _factory(tmp_path / "cloud.db")
    repo, cloud_repo = BaipuHistoryRepository(local_factory), BaipuHistoryRepository(cloud_factory)
    calls = []

    def cloud(request):
        from katrain.web.core.baipu_history import BaipuHistoryConflict, BaipuHistoryNotFound

        calls.append(request)
        path = request.url.path
        try:
            if request.method == "GET" and path == "/api/v1/baipu/history":
                summaries = cloud_repo.list(CLOUD_JIA, 30)
                summaries = [{k: v for k, v in row.items() if k != "sgf_content"} for row in summaries]
                return httpx.Response(200, json={"items": summaries, "authority": "this_node"})
            record_id = path.split("/")[-2 if path.endswith("/sync") else -1]
            if request.method == "GET":
                return httpx.Response(200, json=cloud_repo.get(CLOUD_JIA, record_id))
            if request.method == "PUT" and path.endswith("/sync"):
                return httpx.Response(
                    200, json=cloud_repo.accept_sync(CLOUD_JIA, record_id, json.loads(request.content))
                )
            return httpx.Response(404)
        except BaipuHistoryNotFound:
            return httpx.Response(404)
        except BaipuHistoryConflict as exc:
            return httpx.Response(409, json={"detail": {"code": exc.code, "current": exc.current}})

    remote = RemoteAPIClient("http://cloud.test", "box-1")
    remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(cloud))
    remote.set_tokens("tok-jia", "refresh-jia", user_id=JIA)
    connectivity = SimpleNamespace(is_online=False)
    service = BaipuHistoryService(repo, remote, connectivity)
    yield SimpleNamespace(
        service=service,
        repo=repo,
        cloud=cloud_repo,
        remote=remote,
        connectivity=connectivity,
        calls=calls,
        factory=local_factory,
        default_cloud=cloud,
    )
    engines.dispose()
    cloud_engine.dispose()


async def _open_local(box, k=1):
    row = await box.service.open(JIA, OPEN)
    if k:
        row = await _save(box, row, k)
    return row


async def _save(box, row, k, mutation=None):
    return await box.service.save(
        JIA,
        row["id"],
        {
            "k": k,
            "expected_local_revision": row["local_revision"],
            "mutation_id": mutation or f"m-{row['local_revision']}-{k}",
        },
    )


def _handler(box, handler):
    box.remote._client = httpx.AsyncClient(base_url="http://cloud.test", transport=httpx.MockTransport(handler))


async def test_authoritative_service_uses_repository_without_transport(box):
    from katrain.web.core.baipu_history_sync import BaipuHistoryService

    service = BaipuHistoryService(box.cloud)
    row = await service.open(CLOUD_JIA, OPEN)
    row = await service.save(CLOUD_JIA, row["id"], {"k": 2, "expected_local_revision": 0, "mutation_id": "direct"})
    assert (row["k"], row["cloud_revision"], row["authority"]) == (2, 1, "this_node")
    assert (await service.list(CLOUD_JIA, 30))["items"][0]["id"] == row["id"]
    assert (await service.get(CLOUD_JIA, row["id"]))["k"] == 2
    assert box.calls == []


@pytest.mark.parametrize("bound", [None, YI])
async def test_absent_or_other_binding_only_returns_own_durable_cache(box, bound):
    row = await _open_local(box)
    box.repo.open(YI, {"sgf_content": SGF.replace("cc", "dd"), "name": "Other"})
    box.remote.bind_user(bound)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 0
    result = await box.service.list(JIA, 30)
    assert [item["id"] for item in result["items"]] == [row["id"]]
    assert result["authority"] == "local_cache" and result["items"][0]["sync_state"] == "pending"
    assert (await box.service.get(JIA, row["id"]))["k"] == 1
    assert box.calls == []


@pytest.mark.parametrize("pause_at", ["first", "refresh", "response"])
async def test_account_switch_during_request_or_refresh_discards_response(box, pause_at):
    row = await _open_local(box)
    entered, release = asyncio.Event(), asyncio.Event()
    sends = []

    async def cloud(request):
        sends.append(request)
        if request.url.path == "/api/v1/auth/refresh":
            if pause_at == "refresh":
                entered.set()
                await release.wait()
            return httpx.Response(200, json={"access_token": "tok-jia-new"})
        if pause_at == "first":
            entered.set()
            await release.wait()
            return httpx.Response(401)
        if pause_at == "refresh":
            return httpx.Response(401)
        response = box.default_cloud(request)
        entered.set()
        await release.wait()
        return response

    _handler(box, cloud)
    box.connectivity.is_online = True
    draining = asyncio.create_task(box.service.sync_pending())
    await asyncio.wait_for(entered.wait(), 2)
    box.remote.set_tokens("tok-yi", "refresh-yi", user_id=YI)
    release.set()
    assert await draining == 0
    assert box.repo.get(JIA, row["id"])["sync_state"] == "pending"
    assert box.remote._access_token == "tok-yi" and not box.remote.auth_required
    assert not any(request.headers.get("authorization") == "Bearer tok-yi" for request in sends)


async def test_same_owner_401_refresh_still_syncs(box):
    row = await _open_local(box)

    def cloud(request):
        if request.url.path == "/api/v1/auth/refresh":
            return httpx.Response(200, json={"access_token": "tok-jia-new"})
        if request.headers.get("authorization") == "Bearer tok-jia":
            return httpx.Response(401)
        return box.default_cloud(request)

    _handler(box, cloud)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 1
    assert box.repo.get(JIA, row["id"])["sync_state"] == "synced"


async def test_progress_advancing_during_http_keeps_new_cursor_and_original_base(box):
    first = await _open_local(box)
    entered, release = asyncio.Event(), asyncio.Event()

    async def cloud(request):
        result = box.default_cloud(request)
        entered.set()
        await release.wait()
        return result

    _handler(box, cloud)
    box.connectivity.is_online = True
    draining = asyncio.create_task(box.service.sync_pending())
    await asyncio.wait_for(entered.wait(), 2)
    second = await _save(box, first, 2)
    release.set()
    assert await draining == 1
    current = box.repo.get(JIA, first["id"])
    assert (current["k"], current["sync_state"], current["pending_base_revision"]) == (2, "pending", 0)
    assert current["writer_id"] == first["writer_id"] == second["writer_id"]
    _handler(box, box.default_cloud)
    assert await box.service.sync_pending() == 1
    assert box.cloud.get(CLOUD_JIA, first["id"])["k"] == 2


async def test_process_restart_retries_accepted_payload_with_durable_writer(box):
    from katrain.web.core.baipu_history import BaipuHistoryRepository
    from katrain.web.core.baipu_history_sync import BaipuHistoryService

    row = await _open_local(box)

    def interrupted(request):
        box.default_cloud(request)
        raise httpx.ReadError("process lost the receipt", request=request)

    _handler(box, interrupted)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 0
    accepted = box.cloud.get(CLOUD_JIA, row["id"])
    reopened = BaipuHistoryRepository(box.factory)
    assert reopened.get(JIA, row["id"])["writer_id"] == row["writer_id"]
    box.service = BaipuHistoryService(reopened, box.remote, box.connectivity)
    _handler(box, box.default_cloud)
    assert await box.service.sync_pending() == 1
    assert box.cloud.get(CLOUD_JIA, row["id"])["cloud_revision"] == accepted["cloud_revision"]
    assert reopened.get(JIA, row["id"])["sync_state"] == "synced"


async def test_undo_sends_smaller_cursor_as_a_newer_causal_write(box):
    row = await _open_local(box, 2)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 1
    row = await _save(box, box.repo.get(JIA, row["id"]), 0)
    assert await box.service.sync_pending() == 1
    assert box.cloud.get(CLOUD_JIA, row["id"])["k"] == 0
    assert box.repo.get(JIA, row["id"])["sync_state"] == "synced"


async def _conflict(box):
    row = await _open_local(box, 2)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 1
    cloud = box.cloud.get(CLOUD_JIA, row["id"])
    box.cloud.save(
        CLOUD_JIA,
        row["id"],
        {"k": 1, "expected_local_revision": cloud["local_revision"], "mutation_id": "other-device"},
    )
    local = await _save(box, box.repo.get(JIA, row["id"]), 3)
    assert await box.service.sync_pending() == 0
    return box.repo.get(JIA, local["id"])


async def test_other_device_conflict_stops_automatic_sends_and_keeps_local_overlay(box):
    row = await _conflict(box)
    assert row["sync_state"] == "conflict" and row["conflict_remote"]["k"] == 1
    count = len(box.calls)
    assert await box.service.sync_pending() == 0
    assert len(box.calls) == count
    listed = await box.service.list(JIA, 30)
    assert listed["items"][0]["k"] == 3 and listed["items"][0]["sync_state"] == "conflict"


async def test_delayed_get_after_save_and_sync_returns_the_merged_winner(box):
    row = await _open_local(box, 1)
    box.connectivity.is_online = True
    await box.service.sync_pending()
    entered, release = asyncio.Event(), asyncio.Event()

    async def cloud(request):
        response = box.default_cloud(request)
        if request.method == "GET":
            entered.set()
            await release.wait()
        return response

    _handler(box, cloud)
    reading = asyncio.create_task(box.service.get(JIA, row["id"]))
    await asyncio.wait_for(entered.wait(), 2)
    await _save(box, box.repo.get(JIA, row["id"]), 2)
    await box.service.sync_pending()
    release.set()
    result = await reading
    assert (result["k"], result["sync_state"]) == (2, "synced")


async def test_open_discovers_cloud_before_creating_zero_and_list_does_not_prefetch_sgf(box):
    cloud = box.cloud.open(CLOUD_JIA, OPEN)
    box.cloud.save(CLOUD_JIA, cloud["id"], {"k": 2, "expected_local_revision": 0, "mutation_id": "cloud-step"})
    box.connectivity.is_online = True
    listed = await box.service.list(JIA, 30)
    assert listed["items"][0]["k"] == 2
    assert len(box.calls) == 1 and "sgf_content" not in listed["items"][0]
    assert box.repo.list(JIA, 30) == []
    row = await box.service.open(JIA, OPEN)
    assert row["k"] == 2 and row["sync_state"] == "synced"
    assert box.repo.get(JIA, row["id"])["sgf_content"] == SGF
    assert not any(request.method == "PUT" for request in box.calls)


async def test_resolve_fetch_cas_does_not_discard_a_concurrent_local_step(box):
    from katrain.web.core.baipu_history import BaipuHistoryConflict

    row = await _conflict(box)
    entered, release = asyncio.Event(), asyncio.Event()

    async def cloud(request):
        response = box.default_cloud(request)
        entered.set()
        await release.wait()
        return response

    _handler(box, cloud)
    resolving = asyncio.create_task(box.service.resolve(JIA, row["id"], "use_cloud", row["local_revision"]))
    await asyncio.wait_for(entered.wait(), 2)
    await _save(box, row, 2, "racing-local-step")
    release.set()
    with pytest.raises(BaipuHistoryConflict) as stale:
        await resolving
    assert stale.value.code == "stale_local_revision"
    assert stale.value.current["authority"] == "local_cache"
    assert box.repo.get(JIA, row["id"])["k"] == 2


@pytest.mark.parametrize("strategy,expected_k", [("use_cloud", 1), ("keep_local", 3)])
async def test_explicit_resolution_rotates_writer_and_old_receipts_are_ignored(box, strategy, expected_k):
    row = await _conflict(box)
    before = copy.deepcopy(row)
    resolved = await box.service.resolve(JIA, row["id"], strategy, row["local_revision"])
    assert resolved["k"] == expected_k and resolved["writer_id"] != before["writer_id"]
    box.repo.absorb_success(JIA, row["id"], before, dict(before, cloud_revision=100))
    assert box.repo.get(JIA, row["id"])["writer_id"] == resolved["writer_id"]
    assert box.repo.get(JIA, row["id"])["k"] == expected_k


@pytest.mark.parametrize(
    "status,body,state",
    [
        (200, {"ok": True}, "pending"),
        (503, {"detail": "later"}, "pending"),
        (422, {"detail": "unsupported replay"}, "refused"),
        (409, {"detail": "invalid conflict"}, "pending"),
    ],
)
async def test_malformed_success_and_transient_failures_retry_but_refusal_does_not_loop(box, status, body, state):
    row = await _open_local(box)
    attempts = []

    def response(request):
        attempts.append(request)
        return httpx.Response(status, json=body)

    _handler(box, response)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 0
    assert box.repo.get(JIA, row["id"])["sync_state"] == state
    assert len(attempts) == 1
    await box.service.sync_pending()
    assert len(attempts) == (1 if state == "refused" else 2)


async def test_history_callback_runs_under_existing_worker_lock_without_overlapping(box):
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def drain():
        calls.append(worker._sync_lock.locked())
        entered.set()
        await release.wait()
        return 2

    worker = SyncWorker(box.factory, box.remote, baipu_sync=drain)
    first = asyncio.create_task(worker.run_sync())
    await asyncio.wait_for(entered.wait(), 2)
    assert await worker.run_sync() == 0
    release.set()
    assert await first == 2 and calls == [True]


async def test_non_json_success_is_retryable_and_does_not_escape_the_drain(box):
    row = await _open_local(box)
    _handler(box, lambda request: httpx.Response(200, text="<html>upstream proxy</html>"))
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 0
    assert box.repo.get(JIA, row["id"])["sync_state"] == "pending"


async def test_invalid_detail_id_never_reaches_the_cloud(box):
    from katrain.web.core.baipu_history import BaipuHistoryValidationError

    box.connectivity.is_online = True
    with pytest.raises(BaipuHistoryValidationError):
        await box.service.get(JIA, "../auth/logout")
    assert box.calls == []


async def test_logout_and_return_to_same_owner_during_get_discards_the_old_response(box):
    row = await _open_local(box)
    box.connectivity.is_online = True
    await box.service.sync_pending()
    entered, release = asyncio.Event(), asyncio.Event()

    async def cloud(request):
        response = box.default_cloud(request)
        entered.set()
        await release.wait()
        # An old response with otherwise valid newer cursor/revision.
        body = response.json()
        body.update(k=3, completed=True, completed_at=body["updated_at"], cloud_revision=50)
        return httpx.Response(200, json=body)

    _handler(box, cloud)
    reading = asyncio.create_task(box.service.get(JIA, row["id"]))
    await asyncio.wait_for(entered.wait(), 2)
    box.remote.clear_tokens()
    box.remote.set_tokens("tok-jia", "refresh-jia", user_id=JIA)
    release.set()
    assert (await reading)["k"] == 1
    assert box.repo.get(JIA, row["id"])["cloud_revision"] < 50


async def test_same_sgf_with_different_offline_labels_syncs_to_existing_cloud_labels(box):
    cloud = box.cloud.open(CLOUD_JIA, dict(OPEN, name="Cloud label", source_id="cloud-source"))
    local = await _open_local(box)
    assert local["id"] == cloud["id"]
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 1
    current = box.repo.get(JIA, local["id"])
    assert current["sync_state"] == "synced"
    assert (current["name"], current["source_id"]) == ("Cloud label", "cloud-source")


async def test_save_returns_before_the_existing_worker_wake_finishes(box):
    row = await _open_local(box)
    entered, release = asyncio.Event(), asyncio.Event()

    async def wake():
        entered.set()
        await release.wait()

    box.service.wake_sync = wake
    saved = await asyncio.wait_for(_save(box, row, 2), 1)
    await asyncio.wait_for(entered.wait(), 1)
    assert saved["k"] == box.repo.get(JIA, row["id"])["k"] == 2
    release.set()
    await box.service._wake_task


async def test_older_other_owner_rows_cannot_starve_the_active_owner_outbox(box):
    for index in range(100):
        box.repo.open(YI, dict(OPEN, sgf_content=SGF.replace("FF[4]", f"FF[4]C[{index}]")), board=True)
    row = await _open_local(box)
    box.connectivity.is_online = True
    assert await box.service.sync_pending() == 1
    assert box.repo.get(JIA, row["id"])["sync_state"] == "synced"
    assert all(item["user_id"] == YI for item in box.repo.pending_snapshots())


@pytest.mark.parametrize("board", [True, False])
@pytest.mark.parametrize("operation", ["save", "resolve"])
async def test_stale_api_conflicts_keep_truthful_authority_and_bounded_current(box, board, operation):
    from fastapi import HTTPException
    from katrain.web.api.v1.endpoints.baipu_history import invoke
    from katrain.web.core.baipu_history_sync import BaipuHistoryService

    if board:
        row = await _open_local(box)
        box.connectivity.is_online = True
        assert await box.service.sync_pending() == 1
        service = box.service
    else:
        service = BaipuHistoryService(box.repo)
        row = await service.open(JIA, OPEN)
        row = await service.save(JIA, row["id"], {"k": 1, "expected_local_revision": 0, "mutation_id": "server"})
    assert box.repo.get(JIA, row["id"])["sync_state"] == "synced"
    if operation == "save":
        request = service.save(JIA, row["id"], {"k": 2, "expected_local_revision": 0, "mutation_id": "stale"})
    else:
        request = service.resolve(JIA, row["id"], "use_cloud", 0)
    with pytest.raises(HTTPException) as failure:
        await invoke(request)
    assert failure.value.status_code == 409
    assert failure.value.detail["code"] == "stale_local_revision"
    current = failure.value.detail["current"]
    assert current["authority"] == ("local_cache" if board else "this_node")
    assert current["k"] == 1
    assert (
        not {"user_id", "writer_id", "writer_seq", "last_writer_id", "last_writer_seq", "pending_base_revision"}
        & current.keys()
    )
