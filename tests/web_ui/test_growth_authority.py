"""屏 22 成长那几个数的**出处**:`GET /api/v1/growth/summary` 的 `authority`。

## 这条闸挡的是什么

「一个数」在屏上天然读作「全部」。盒子上账在云端、本机库只是缓存,所以同一个
`ranked_total` 可能少几局 —— 而少了的时候屏上**没有任何东西会说**。
`authority` 就是那句话的出口(界面据它写「本机记录」)。

2026-08-26 之前这里**从来不问云端**:盒子上永远数本机、永远标 `local_cache`。
于是同一台盒子上,复盘屏那张列表来自云端(`user_games_list` 在线走 remote)、
成长屏那几个数来自本机 —— **两屏对不上,两边都没说自己从哪儿数的。**

## 三档,每一档都要有用例走到

`this_node`(普通服务端) · `cloud`(盒子在线,云端那份) ·
`local_cache`(盒子拿不到云端,退回本机)。

退回**不是静默的** —— 它的出口是屏上那句「本机记录」。但「为什么退」有四种
(没联网 / 云端不可达 / 云端 404 / 云端 5xx),它们在用户屏上长得一模一样、
在运维那儿却完全不同 ⇒ 各写各的日志。这里连日志一起断言,
否则「404 和 5xx 分开处理」这件事写了等于没写。
"""

import logging

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.api.v1.endpoints.growth import router as growth_router
from katrain.web.core.repository import RepositoryDispatcher
from katrain.web.models import User

CLOUD = {
    "window_days": 30,
    "games_in_window": 41,
    "ranked_total": 12,
    "ranked_wins_in_window": 7,
    "ranked_losses_in_window": 3,
    "by_opponent_rung": [{"rung": 18, "rank_name": "3级", "wins": 2, "losses": 1}],
    # 云端自己就是权威,所以它答的是 `this_node`。**盒子必须把这句话改掉** ——
    # 原样转出去的话,屏上会以为这几个数是本机数出来的。
    "authority": "this_node",
}

LOCAL_LADDER = {
    "ranked_total": 2,
    "ranked_wins_in_window": 1,
    "ranked_losses_in_window": 1,
    "by_opponent_rung": [],
}


class _FakeGameRepo:
    def count_since(self, user_id, since):  # noqa: ARG002
        return 5


class _FakeLadderRepo:
    def growth_summary(self, user_id, since):  # noqa: ARG002
        return dict(LOCAL_LADDER)


class _FakeConnectivity:
    def __init__(self, online: bool):
        self.is_online = online


class _FakeRemoteClient:
    """`get_growth_summary` 要么返回一份 payload,要么抛一个真的 httpx 异常。"""

    def __init__(self, *, payload=None, raises=None):
        self._payload = payload
        self._raises = raises
        self.calls = []

    async def get_growth_summary(self, days: int):
        self.calls.append(days)
        if self._raises is not None:
            raise self._raises
        return self._payload


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://cloud.example/api/v1/growth/summary")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


def _client(*, dispatcher=None) -> TestClient:
    app = FastAPI()
    app.include_router(growth_router, prefix="/api/v1/growth")
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="tester")
    app.state.user_game_repo = _FakeGameRepo()
    app.state.ai_ladder_repo = _FakeLadderRepo()
    if dispatcher is not None:
        app.state.repository_dispatcher = dispatcher
    return TestClient(app)


def _dispatcher(*, online: bool, remote_client=None) -> RepositoryDispatcher:
    return RepositoryDispatcher(
        connectivity_manager=_FakeConnectivity(online),
        remote_tsumego=None,
        remote_kifu=None,
        remote_user_games=None,
        local_user_game_repo=None,
        remote_client=remote_client,
    )


# ── 三档 ──


def test_没有_dispatcher_就是这台机器自己的账():
    body = _client().get("/api/v1/growth/summary").json()
    assert body["authority"] == "this_node"
    assert body["ranked_total"] == LOCAL_LADDER["ranked_total"]


def test_盒子在线_数来自云端_并且改口成_cloud():
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    body = _client(dispatcher=_dispatcher(online=True, remote_client=remote)).get(
        "/api/v1/growth/summary"
    ).json()

    assert remote.calls == [30], "盒子根本没问云端"
    # 数是云端那份(12),不是本机那份(2)。
    assert body["ranked_total"] == 12
    assert body["games_in_window"] == 41
    # ⚠️ 云端答的是 `this_node`;原样转出去屏上就会以为这是本机数的。
    assert body["authority"] == "cloud"


def test_盒子离线_退回本机缓存_并且说自己是缓存():
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    body = _client(dispatcher=_dispatcher(online=False, remote_client=remote)).get(
        "/api/v1/growth/summary"
    ).json()

    assert remote.calls == [], "离线还去问了云端"
    assert body["ranked_total"] == LOCAL_LADDER["ranked_total"]
    assert body["authority"] == "local_cache"


# ── 退回的四种原因:屏上一样,日志必须不一样 ──


@pytest.mark.parametrize(
    "raises,needle",
    [
        (httpx.ConnectError("no route"), "cloud unreachable"),
        (_http_error(404), "no /growth/summary"),
        (_http_error(503), "cloud failed with 503"),
        (_http_error(401), "cloud refused with 401"),
    ],
    ids=["不可达", "云端少这个端点", "云端 5xx", "云端拒绝"],
)
def test_云端给不出时退回本机_而且四种原因各写各的日志(caplog, raises, needle):
    remote = _FakeRemoteClient(raises=raises)
    with caplog.at_level(logging.INFO):
        body = _client(dispatcher=_dispatcher(online=True, remote_client=remote)).get(
            "/api/v1/growth/summary"
        ).json()

    # 用户看到的:本机那份,而且**屏上会说是本机记录**。四种原因在这一层是同一句话。
    assert body["ranked_total"] == LOCAL_LADDER["ranked_total"]
    assert body["authority"] == "local_cache"
    # 运维看到的:四句不同的话。「盒子没联网」和「云端少了这个端点」不是同一件事 ——
    # 后者是部署歪了,重启网络一万次也好不了。
    assert needle in caplog.text


def test_云端答_200_却给了半截_payload_一样退回本机(caplog):
    # **答 200 不等于答对了。** 少一格就照转,前端会在渲染 `by_opponent_rung.map` 时抛,
    # 而那一屏上面没有 error boundary。
    remote = _FakeRemoteClient(payload={"window_days": 30, "games_in_window": 41})
    with caplog.at_level(logging.INFO):
        body = _client(dispatcher=_dispatcher(online=True, remote_client=remote)).get(
            "/api/v1/growth/summary"
        ).json()

    assert body["authority"] == "local_cache"
    assert body["ranked_total"] == LOCAL_LADDER["ranked_total"]
    assert "unrecognised shape" in caplog.text


def test_云端答_200_却给了一页_HTML_也退回本机():
    remote = _FakeRemoteClient(payload="<html>gateway</html>")
    body = _client(dispatcher=_dispatcher(online=True, remote_client=remote)).get(
        "/api/v1/growth/summary"
    ).json()
    assert body["authority"] == "local_cache"


def test_盒子没配远端客户端时不当成在线():
    body = _client(dispatcher=_dispatcher(online=True, remote_client=None)).get(
        "/api/v1/growth/summary"
    ).json()
    assert body["authority"] == "local_cache"


def test_days_原样带给云端():
    remote = _FakeRemoteClient(payload=dict(CLOUD))
    _client(dispatcher=_dispatcher(online=True, remote_client=remote)).get(
        "/api/v1/growth/summary?days=7"
    )
    assert remote.calls == [7]
