"""共用盒子换人:用户 2 看不到、动不了、断不掉用户 1 的平台连接。

## 为什么不测凭据表

凭据表 `PlatformCredentialStore` 本来就按 user_id 分行,单测它一定是绿的 ——
**堵点在更外面**:运行时的 adapter 是按平台全局一个,`list_platforms()` 不看调用者。
只测最里面那一层,等于给断掉的那一段发通行证。

## 夹具设计

每条用例都经真实 HTTP + 真实两个已登录用户(真 `/api/v1/auth/login`,不是
`dependency_overrides[get_current_user]` 换身份的近道)。`platform_manager`
是**真的** `PlatformManager`,只有 adapter 是一个记连接次数的 spy
(`SpyGolaxyAdapter`),这样 manager 里的授权/串行逻辑一处都不被绕过。

`connected_golaxy_for_user1` 直接摆状态(不经 adapter.connect()),这样
`golaxy_adapter_spy.connect_calls` 在测试主体开始时就是干净的 0 —— 后续
「拒得早不早」的断言才有意义。
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db
from katrain.web.platforms.base import PlatformAdapter
from katrain.web.platforms.credentials import PlatformCredentialStore
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformCredentials

from tests.web_ui._helpers import _create_user_and_login


# --- Spy adapter ------------------------------------------------------------ #


class SpyGolaxyAdapter(PlatformAdapter):
    """A minimal concrete adapter that counts calls and can optionally emit a
    `token_refreshed` event MID-connect (before `connect()` returns) — the
    exact window the brief calls out as dangerous."""

    platform_name = "golaxy"
    supports_engine_play = True

    def __init__(self, emit_token_refresh_on_connect: bool = False):
        super().__init__()
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.emit_token_refresh_on_connect = emit_token_refresh_on_connect

    async def connect(self, credentials: PlatformCredentials) -> bool:
        self.connect_calls += 1
        if self.emit_token_refresh_on_connect:
            await self._emit("token_refreshed", {"access_token": "NEW-FROM-THIS-LOGIN"})
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False

    async def submit_move(self, game_id: str, col: int, row: int) -> bool:
        return True

    async def submit_pass(self, game_id: str) -> bool:
        return True

    async def resign(self, game_id: str) -> None:
        return None

    async def get_online_users(self, room=None):
        return []

    async def get_open_challenges(self):
        return []

    def get_engine_levels(self):
        return [{"elo_score": 1100, "level_name": "1级", "name": "星铠虾"}]

    async def start_engine_game(self, config):
        from katrain.web.platforms.golaxy.adapter import EngineGameStart
        from katrain.web.platforms.models import OnlineUser, PlatformGameSession, TimeControl

        session = PlatformGameSession(
            platform="golaxy",
            game_id="g1",
            board_size=19,
            my_color=config.human_color,
            opponent=OnlineUser(platform="golaxy", user_id="bot", username="bot", rank="1d", rank_numeric=1.0),
            time_control=TimeControl(system="absolute", main_time=600),
            rules=config.rule,
            ranked=False,
            handicap=config.handicap,
            komi=config.komi,
        )
        return EngineGameStart(session=session, first_ai_move=None)

    async def fetch_item_counts(self):
        from katrain.web.platforms.golaxy.engine_client import ItemCountsResult

        return ItemCountsResult(area=5, options=5, variation=5)

    @property
    def token_refreshed_handlers(self) -> int:
        return len(self._callbacks.get("token_refreshed", []))


class _NullSessionManager:
    """Not exercised by these tests — only connect/disconnect/status paths are."""


# --- App / DB fixtures ------------------------------------------------------ #


@pytest.fixture
def _test_app():
    """Fresh sqlite-backed app (pattern copied from
    tests/web_ui/test_report_retry_authorization.py's `_test_app`): a uuid'd
    db file avoids collection-order collisions with sibling test modules that
    also assign `settings.DATABASE_URL` at module scope."""
    previous_database_url = settings.DATABASE_URL
    db_path = f"./test_platform_isolation_{uuid.uuid4().hex}.db"
    settings.DATABASE_URL = f"sqlite:///{db_path}"

    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository
    from katrain.web.core.user_game_repo import UserGameAnalysisRepository, UserGameRepository
    from katrain.web.platforms.gateway import PlatformCommandGateway
    from katrain.web.server import create_app
    from katrain.web.session import LobbyManager, Matchmaker

    test_engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    fastapi_app = create_app(enable_engine=False)
    fastapi_app.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)
    fastapi_app.state.game_repo = GameRepository(TestSessionLocal)
    fastapi_app.state.user_game_repo = UserGameRepository(TestSessionLocal)
    fastapi_app.state.user_game_analysis_repo = UserGameAnalysisRepository(TestSessionLocal)
    fastapi_app.state.report_session_factory = TestSessionLocal
    # `/auth/logout` (non-strict path) touches lobby_manager/matchmaker directly;
    # create_app() itself sets session_manager already.
    fastapi_app.state.lobby_manager = LobbyManager()
    fastapi_app.state.matchmaker = Matchmaker()

    # PlatformCredentialStore defaults to ~/.katrain/platform_credentials.db;
    # give this test its own file so it can't collide with real credentials.
    from pathlib import Path

    cred_db_path = f"./test_platform_isolation_creds_{uuid.uuid4().hex}.db"
    store = PlatformCredentialStore(secret="test-secret", db_path=Path(cred_db_path))

    adapter = SpyGolaxyAdapter()
    manager = PlatformManager(session_manager=_NullSessionManager(), credential_store=store)
    manager.register_adapter(adapter)
    fastapi_app.state.platform_manager = manager
    fastapi_app.state.platform_gateway = PlatformCommandGateway(manager, fastapi_app.state.session_manager)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    yield fastapi_app, manager, adapter, store

    test_engine.dispose()
    for p in (db_path, cred_db_path):
        if os.path.exists(p):
            os.remove(p)
    settings.DATABASE_URL = previous_database_url


@pytest.fixture
def app(_test_app):
    return _test_app[0]


@pytest.fixture
def manager(_test_app):
    return _test_app[1]


@pytest.fixture
def golaxy_adapter_spy(_test_app):
    return _test_app[2]


@pytest.fixture
def credential_store(_test_app):
    return _test_app[3]


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def user1(app):
    headers, user_id, username = await _create_user_and_login(app, "isoluser1")
    return headers, user_id, username


@pytest.fixture
async def user2(app):
    headers, user_id, username = await _create_user_and_login(app, "isoluser2")
    return headers, user_id, username


@pytest.fixture
def user1_token(user1):
    return user1[0]["Authorization"].split(" ", 1)[1]


@pytest.fixture
def user2_token(user2):
    return user2[0]["Authorization"].split(" ", 1)[1]


@pytest.fixture
def user1_id(user1):
    return user1[1]


@pytest.fixture
def user2_id(user2):
    return user2[1]


@pytest.fixture
def connected_golaxy_for_user1(manager, golaxy_adapter_spy, credential_store, user1_id):
    """golaxy already connected & owned by user1 — set up WITHOUT going through
    adapter.connect(), so `golaxy_adapter_spy.connect_calls` stays a clean
    signal for what happens during the test body itself."""
    golaxy_adapter_spy._connected = True
    manager._platform_user_ids["golaxy"] = user1_id
    credential_store.save_credentials(
        user1_id,
        PlatformCredentials(platform="golaxy", username="13800000000", auth_data={"access_token": "OLD"}),
    )
    return golaxy_adapter_spy


@pytest.fixture
def golaxy_adapter_emitting_token_refresh(manager):
    """A fresh adapter (registered in place of the default spy) that fires
    `token_refreshed` mid-`connect()`."""
    adapter = SpyGolaxyAdapter(emit_token_refresh_on_connect=True)
    manager._adapters["golaxy"] = adapter
    return adapter


# --- Group 1: user2 must not see/use/kill user1's connection ---------------- #


@pytest.mark.asyncio
async def test_user2_does_not_see_user1_connection(client, user1_token, user2_token, connected_golaxy_for_user1):
    r1 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user1_token}"})
    r2 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user2_token}"})
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    g1 = next(p for p in r1.json()["platforms"] if p["platform"] == "golaxy")
    g2 = next(p for p in r2.json()["platforms"] if p["platform"] == "golaxy")
    assert g1["connected"] is True
    assert g2["connected"] is False, "用户 2 看见了用户 1 的连接"
    assert "saved_username" not in g2 or not g2["saved_username"]


@pytest.mark.asyncio
async def test_user2_cannot_disconnect_user1(client, user1_token, user2_token, connected_golaxy_for_user1):
    r = await client.delete("/api/v1/platforms/golaxy/logout", headers={"Authorization": f"Bearer {user2_token}"})
    assert r.status_code in (403, 404), f"用户 2 把用户 1 断开了(HTTP {r.status_code})"
    r1 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user1_token}"})
    assert next(p for p in r1.json()["platforms"] if p["platform"] == "golaxy")["connected"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/platforms/golaxy/users"),
        ("GET", "/api/v1/platforms/golaxy/challenges"),
        ("GET", "/api/v1/platforms/golaxy/engine/items"),
        ("POST", "/api/v1/platforms/golaxy/engine/start"),
    ],
)
async def test_user2_cannot_act_through_user1_session(client, user2_token, connected_golaxy_for_user1, method, path):
    body = {"level": 1100, "human_color": "B"} if path.endswith("engine/start") else {}
    r = await client.request(method, path, headers={"Authorization": f"Bearer {user2_token}"}, json=body)
    assert r.status_code in (403, 404), f"{method} {path} 让用户 2 用上了用户 1 的会话 (got {r.status_code})"


# --- Group 2: the login path itself, and callback wiring -------------------- #


@pytest.mark.asyncio
async def test_user2_login_while_user1_connected_is_refused_before_touching_adapter(
    client, user2_token, connected_golaxy_for_user1, golaxy_adapter_spy
):
    r = await client.post(
        "/api/v1/platforms/golaxy/login",
        headers={"Authorization": f"Bearer {user2_token}"},
        json={"username": "13900000000", "password": "x"},
    )
    assert r.status_code == 409, r.text
    assert golaxy_adapter_spy.connect_calls == 0, "已经去连了 —— 拒得太晚"


@pytest.mark.asyncio
async def test_token_refresh_during_user2_login_never_writes_into_user1_row(
    client,
    credential_store,
    manager,
    user1_token,
    user2_token,
    user1_id,
    user2_id,
    golaxy_adapter_emitting_token_refresh,
):
    """就算将来放开了换人,刷新出来的 token 也必须落在**发起这次连接**的人头上。"""
    manager._platform_user_ids["golaxy"] = user1_id
    golaxy_adapter_emitting_token_refresh._connected = True
    credential_store.save_credentials(
        user1_id,
        PlatformCredentials(platform="golaxy", username="13800000000", auth_data={"access_token": "OLD"}),
    )
    before = credential_store.load_credentials(user1_id, "golaxy")

    # Box-level logout (releases ownership WITHOUT deleting saved credentials —
    # that's the box-SSO "next person's turn" path, distinct from an explicit
    # platform disconnect) then user2 connects fresh.
    logout_resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {user1_token}"})
    assert logout_resp.status_code == 200, logout_resp.text

    r = await client.post(
        "/api/v1/platforms/golaxy/login",
        headers={"Authorization": f"Bearer {user2_token}"},
        json={"username": "13900000000", "password": "x"},
    )
    assert r.status_code == 200, r.text

    after = credential_store.load_credentials(user1_id, "golaxy")
    assert after is not None, "用户 1 的凭据行被误删了"
    assert after.auth_data == before.auth_data, "用户 2 的 token 被写进了用户 1 那一行"


@pytest.mark.asyncio
async def test_callbacks_are_wired_once(manager, golaxy_adapter_spy, user1_id):
    """`_setup_callbacks` 原来每次连接都再挂一遍 ⇒ 回调累积 ⇒ 一次刷新写 N 遍。"""
    creds = PlatformCredentials(platform="golaxy", username="u", auth_data={})
    for _ in range(3):
        await manager.disconnect_platform("golaxy", user1_id)
        await manager.connect_platform("golaxy", creds, user1_id)
    assert golaxy_adapter_spy.token_refreshed_handlers == 1


@pytest.mark.asyncio
async def test_box_user_logout_releases_the_platform(client, user1_token, user2_token, connected_golaxy_for_user1):
    """不清运行时归属的话:上一个人登出了,下一个人登录平台被 409 挡住,而屏上没有任何解释。"""
    r = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {user1_token}"})
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/platforms/golaxy/login",
        headers={"Authorization": f"Bearer {user2_token}"},
        json={"username": "13900000000", "password": "x"},
    )
    assert r.status_code != 409, "上一个人登出了,平台还占着"
