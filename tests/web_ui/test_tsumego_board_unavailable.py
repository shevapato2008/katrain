"""Board-mode tsumego reads (N9): 盒上题库是在线直读的,连不上云端必须说出来。

改之前 `RepositoryDispatcher.tsumego_get_*` 在离线 / 连不上 / 云端回错时一律回 `[]` / `None`,
端点把它当真结果 ⇒ 训练营写「这台盒子上还没有题 · 题库随云端同步下来」,做题屏写「Problem not found」。
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints import tsumego as tsumego_endpoints
from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.core.db import get_db
from katrain.web.core.repository import (
    RemoteServiceUnavailableError,
    RemoteTsumegoRepository,
    RepositoryDispatcher,
)
from katrain.web.models import User

REMOTE_METHODS = ("get_levels", "get_all_problems", "get_problems", "get_problem")
CALLS = [
    ("tsumego_get_levels", ()),
    ("tsumego_get_all_problems", ("15k",)),
    ("tsumego_get_problems", ("15k", "capturing")),
    ("tsumego_get_problem", ("p1",)),
]


class _Connectivity:
    def __init__(self, online: bool):
        self.is_online = online


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://cloud.test/api/v1/tsumego/levels")
    return httpx.HTTPStatusError(str(code), request=request, response=httpx.Response(code, request=request))


def _remote(side_effect=None, value=None):
    remote = MagicMock()
    for name in REMOTE_METHODS:
        setattr(remote, name, AsyncMock(side_effect=side_effect, return_value=value))
    return remote


def _dispatcher(online: bool, remote_tsumego) -> RepositoryDispatcher:
    # `remote_client` 必须传:`_remote_only` 把「没注入 remote_client」也当成不可用。生产 server.py 恒注入。
    return RepositoryDispatcher(
        connectivity_manager=_Connectivity(online),
        remote_tsumego=remote_tsumego,
        remote_kifu=MagicMock(),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        remote_client=MagicMock(),
    )


def _app(dispatcher: RepositoryDispatcher) -> FastAPI:
    app = FastAPI()
    app.include_router(tsumego_endpoints.router, prefix="/api/v1/tsumego")
    app.dependency_overrides[get_db] = lambda: None
    app.state.repository_dispatcher = dispatcher
    return app


# ── dispatcher ──


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
async def test_offline_raises_unavailable_and_never_calls_cloud(method, args):
    remote = _remote(value=[])
    with pytest.raises(RemoteServiceUnavailableError):
        await getattr(_dispatcher(False, remote), method)(*args)
    for name in REMOTE_METHODS:
        getattr(remote, name).assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
@pytest.mark.parametrize("error", [httpx.ConnectError("boom"), httpx.ReadTimeout("slow"), _status_error(503)])
async def test_transport_failure_or_cloud_5xx_raises_unavailable(method, args, error):
    with pytest.raises(RemoteServiceUnavailableError):
        await getattr(_dispatcher(True, _remote(side_effect=error)), method)(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,args", CALLS)
async def test_cloud_4xx_is_passed_through_not_swallowed(method, args):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await getattr(_dispatcher(True, _remote(side_effect=_status_error(404))), method)(*args)
    assert exc_info.value.response.status_code == 404


@pytest.mark.asyncio
async def test_online_success_is_returned_as_is():
    levels = [{"level": "15k", "categories": {"capturing": 3}, "total": 3}]
    assert await _dispatcher(True, _remote(value=levels)).tsumego_get_levels() == levels


@pytest.mark.asyncio
async def test_all_problems_fails_whole_when_one_category_fails():
    """改之前 `gather(return_exceptions=True)` 静默丢掉失败的分类:列表缺一块,`total` 还是全量。"""
    client = MagicMock()
    client.get_levels = AsyncMock(
        return_value=[{"level": "15k", "categories": {"capturing": 2, "tesuji": 1}, "total": 3}]
    )

    async def get_problems(level, category, offset=0, limit=20):
        if category == "tesuji":
            raise httpx.ConnectError("boom")
        return [{"id": "c1", "category": "capturing", "hint": ""}, {"id": "c2", "category": "capturing", "hint": ""}]

    client.get_problems = AsyncMock(side_effect=get_problems)
    with pytest.raises(httpx.ConnectError):
        await RemoteTsumegoRepository(client).get_all_problems("15k")


# ── endpoints ──


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tsumego/levels",
        "/api/v1/tsumego/levels/15k/categories",
        "/api/v1/tsumego/levels/15k/problems",
        "/api/v1/tsumego/levels/15k/categories/capturing",
        "/api/v1/tsumego/problems/p1",
    ],
)
async def test_every_board_read_endpoint_offline_is_503(path):
    app = _app(_dispatcher(False, _remote(value=[])))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 503, response.text


@pytest.mark.asyncio
async def test_problem_endpoint_cloud_404_stays_404():
    app = _app(_dispatcher(True, _remote(side_effect=_status_error(404))))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/problems/nope")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_levels_endpoint_online_returns_cloud_payload():
    levels = [{"level": "15k", "categories": {"capturing": 3}, "total": 3}]
    app = _app(_dispatcher(True, _remote(value=levels)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/levels")
    assert response.status_code == 200
    assert response.json() == levels


# ── progress:盒上这一份是谁给的(Codex 对抗审查第 2 轮 #2)──
#
# 盒上 `GET /progress` 离线 / 云端读失败时回的是 **200 + 本机缓存**,而在线写成功不落本机缓存 ⇒ 那份常常是 `{}`。
# 不说是哪一份,前端就把它当「读到了、一道没做」:错题页说「这一类现在没有做错过的题」、入口灰掉、不给重试。
# 字面量两边各钉一次。前端那一半:`katrain/web/ui/src/context/__tests__/TsumegoProgressContext.test.tsx`
# 的「盒子退回本机缓存」那一组(`X-Data-Authority: local_cache` ⇒ `serverLoadFailed`)。


def _progress_app(online: bool, remote_get_progress: AsyncMock) -> FastAPI:
    remote = MagicMock()
    remote.get_progress = remote_get_progress
    local = MagicMock()
    local.list = MagicMock(return_value={})  # 这个人在线时做的题一条都没落进本机缓存
    dispatcher = RepositoryDispatcher(
        connectivity_manager=_Connectivity(online),
        remote_tsumego=remote,
        remote_kifu=MagicMock(),
        remote_user_games=MagicMock(),
        local_user_game_repo=MagicMock(),
        local_tsumego_progress_repo=local,
        remote_client=MagicMock(),
    )
    app = _app(dispatcher)
    app.dependency_overrides[get_current_user] = lambda: User(id=7, username="tester")
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "online,error",
    [(False, None), (True, httpx.ConnectError("boom")), (True, _status_error(502))],
    ids=["offline", "cloud-unreachable", "cloud-5xx"],
)
async def test_board_progress_fallback_is_marked_local_cache(online, error):
    app = _progress_app(online, AsyncMock(side_effect=error, return_value={}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/progress")
    assert response.status_code == 200
    assert response.json() == {}
    assert response.headers["X-Data-Authority"] == "local_cache"


@pytest.mark.asyncio
async def test_board_progress_from_cloud_is_marked_cloud():
    cloud = {"p1": {"problemId": "p1", "completed": False, "attempts": 2}}
    app = _progress_app(True, AsyncMock(return_value=cloud))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tsumego/progress")
    assert response.status_code == 200
    assert response.json()["p1"]["attempts"] == 2
    assert response.headers["X-Data-Authority"] == "cloud"
