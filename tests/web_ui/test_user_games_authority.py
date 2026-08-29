"""对局列表的**出处**:`GET /api/v1/user-games/` 的 `authority`。

复盘屏(屏 19)组标题右端写着「本机 N 局」。**它以前是句假话**:
盒子在线时 `RepositoryDispatcher.user_games_list` 走的是云端,那个 `total` 是
**跨设备**的总数;只有断网那一档它才碰巧是真的 —— 而用户没有任何办法分辨自己看的是哪一档。

口径和 `growth/summary` 的 `authority` **同名同义**(`this_node` / `cloud` / `local_cache`)。
一个概念只许有一套词:两处各起一套名字的话,前端就得写两份映射,而那两份迟早会走散。

⚠️ 这一格是**选填**:老服务端不带它。前端读不到时要退到最保守的那句话(「本机」),
不许当成 `cloud` —— 判据在 `ReportsPage.test.tsx`。
"""

import httpx
import pytest

from katrain.web.core.repository import RepositoryDispatcher


class _FakeConnectivity:
    def __init__(self, online: bool):
        self.is_online = online


class _FakeRemoteUserGames:
    def __init__(self, *, payload=None, raises=None):
        self._payload = payload
        self._raises = raises
        self.calls = []

    async def list_games(self, **params):
        self.calls.append(params)
        if self._raises is not None:
            raise self._raises
        return self._payload


class _FakeLocalRepo:
    def __init__(self):
        self.calls = []

    def list(self, **params):
        self.calls.append(params)
        return {"items": [{"id": "local-1"}], "total": 1, "page": 1, "page_size": 12}


def _dispatcher(*, online: bool, remote):
    local = _FakeLocalRepo()
    dispatcher = RepositoryDispatcher(
        connectivity_manager=_FakeConnectivity(online),
        remote_tsumego=None,
        remote_kifu=None,
        remote_user_games=remote,
        local_user_game_repo=local,
    )
    return dispatcher, local


CLOUD_PAGE = {"items": [{"id": "cloud-1"}, {"id": "cloud-2"}], "total": 37, "page": 1, "page_size": 12}


@pytest.mark.asyncio
async def test_在线那一份来自云端_标成_cloud():
    remote = _FakeRemoteUserGames(payload=dict(CLOUD_PAGE))
    dispatcher, local = _dispatcher(online=True, remote=remote)

    page = await dispatcher.user_games_list(user_id=1, page=1, page_size=12)

    assert page["total"] == 37, "拿的不是云端那份"
    assert page["authority"] == "cloud"
    assert local.calls == [], "在线还去数了本机"


@pytest.mark.asyncio
async def test_离线那一份是本机的_标成_local_cache():
    remote = _FakeRemoteUserGames(payload=dict(CLOUD_PAGE))
    dispatcher, local = _dispatcher(online=False, remote=remote)

    page = await dispatcher.user_games_list(user_id=1, page=1, page_size=12)

    assert remote.calls == [], "离线还去问了云端"
    assert page["total"] == 1
    assert page["authority"] == "local_cache"
    assert local.calls, "本机也没数"


@pytest.mark.asyncio
async def test_云端拿不到时退回本机_而且不冒充云端():
    # 这一档最要紧:数**变小了**,而屏上原来照旧写「本机 N 局」——
    # 说对了词,却是碰巧说对的。现在它带着自己的出处。
    remote = _FakeRemoteUserGames(raises=httpx.ConnectError("no route"))
    dispatcher, _ = _dispatcher(online=True, remote=remote)

    page = await dispatcher.user_games_list(user_id=1, page=1, page_size=12)

    assert page["total"] == 1
    assert page["authority"] == "local_cache"


@pytest.mark.asyncio
async def test_不覆盖云端已经给的其它字段():
    remote = _FakeRemoteUserGames(payload={**CLOUD_PAGE, "page": 3})
    dispatcher, _ = _dispatcher(online=True, remote=remote)

    page = await dispatcher.user_games_list(user_id=1, page=3, page_size=12)

    assert page["page"] == 3
    assert page["items"] == CLOUD_PAGE["items"]


# ── 端点这一层:没有 dispatcher = 这台机器就是权威 ──


def test_普通服务端答_this_node():
    """`this_node` 这一档只有走端点才量得到 —— dispatcher 根本不存在。

    三档里少量一档,那一档在真实树上就一次都没执行过。
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from katrain.web.api.v1.endpoints.auth import get_current_user
    from katrain.web.api.v1.endpoints.user_games import router as user_games_router
    from katrain.web.models import User

    app = FastAPI()
    app.include_router(user_games_router, prefix="/api/v1/user-games")
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="tester")
    app.state.user_game_repo = _FakeLocalRepo()

    body = TestClient(app).get("/api/v1/user-games/").json()

    assert body["authority"] == "this_node"
    assert body["total"] == 1
    assert body["items"] == [{"id": "local-1"}]
