"""星阵扫码登录五步链的契约。

**存在性不是可用性**:`/api/auth/scan/code` 返回 200 不等于我们拿到了 uuid ——
星阵的 code 字段是字符串 "0" 表示成功,非 "0" 的 200 一样是失败。

结构:
- `TestGolaxyScanLogin*`: `scan_login.py` 里的只读五步链客户端(①③⑤),用
  `httpx.MockTransport` 假网络,照抄 `test_golaxy_engine_client.py` 的既有模式
  (仓里没装 pytest-httpx,不能用计划草稿里的 `httpx_mock` fixture)。
- `TestAdapterScanCodeLogin`: `GolaxyAdapter.connect()` 的扫码分支(第④步复用
  短信登录同一路径),照抄 `test_golaxy_sms_connect.py` 的模式,在
  `GolaxyRestClient` 边界打 AsyncMock。
- `TestScanEndpoints`: 三个 HTTP 端点,FastAPI TestClient + 假 `PlatformManager`
  (`FakeManager`),`get_current_user` 用可变身份覆盖切换调用者,验 R-28/R-30。
- `TestPrincipalVsNickname`: R-29 —— 扫码登录存的 `username` 留空这件事,顺着
  `GolaxyAdapter` 一路传导到 `fetch_item_counts()` 诚实地"不可用",而不是拿
  昵称拼一个假 principal。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.platforms.golaxy.adapter import GOLAXY_API_BASE, GolaxyAdapter
from katrain.web.platforms.golaxy.engine_client import Fatal
from katrain.web.platforms.golaxy.scan_login import (
    GolaxyScanLogin,
    ScanSession,
    ScanSessionStore,
    ScanStart,
    ScanState,
)
from katrain.web.platforms.models import PlatformCredentials
from katrain.web.server import create_app

# asyncio_mode=auto (pyproject.toml) — async test functions need no marker.


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def json_handler(url_suffix: str, body: dict, expect_params: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(f"{GOLAXY_API_BASE}{url_suffix}")
        if expect_params:
            for k, v in expect_params.items():
                assert request.url.params.get(k) == v
        return httpx.Response(200, json=body)

    return handler


# --------------------------------------------------------------------------- #
# GolaxyScanLogin: ① start, ③ poll, ⑤ username                               #
# --------------------------------------------------------------------------- #


class TestGolaxyScanLoginStart:
    async def test_start_returns_uuid_and_payload(self):
        client = make_client(json_handler("/api/auth/scan/code", {"code": "0", "data": "abc-123"}))
        r = await GolaxyScanLogin(client=client).start()
        assert r.uuid == "abc-123"
        # 二维码里编的是这个字符串,不是一张图的 URL —— 星阵没有出图接口。
        assert r.payload == "golaxy_url&&&abc-123"

    async def test_non_zero_code_is_a_failure_even_with_http_200(self):
        client = make_client(json_handler("/api/auth/scan/code", {"code": "5001", "msg": "服务忙"}))
        with pytest.raises(RuntimeError):
            await GolaxyScanLogin(client=client).start()


class TestGolaxyScanLoginPoll:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (0, ScanState.WAITING),
            (1, ScanState.SCANNED),
            (2, ScanState.CONFIRMED),
            (6016, ScanState.EXPIRED),
            (6019, ScanState.CANCELLED),
        ],
    )
    async def test_poll_maps_every_documented_state(self, raw, expected):
        client = make_client(
            json_handler("/api/auth/scan/state", {"code": "0", "data": raw}, expect_params={"uuid": "abc-123"})
        )
        assert await GolaxyScanLogin(client=client).poll("abc-123") == expected

    async def test_unknown_state_is_not_silently_treated_as_waiting(self):
        """星阵加了一个新状态码时,我们必须能看出来 (R-32).

        映射成 WAITING 会让用户对着一个永远转圈的二维码等下去 ——
        坏了和好着在用户那里长得一模一样。
        """
        client = make_client(json_handler("/api/auth/scan/state", {"code": "0", "data": 7777}))
        assert await GolaxyScanLogin(client=client).poll("abc-123") == ScanState.UNKNOWN


class TestGolaxyScanLoginUsername:
    async def test_username_returns_the_nickname_string(self):
        client = make_client(json_handler("/api/auth/scan/username", {"code": "0", "data": "阿范"}))
        assert await GolaxyScanLogin(client=client).username("abc-123") == "阿范"


# --------------------------------------------------------------------------- #
# GolaxyAdapter.connect() — scan-code branch (step ④, reuses login token path) #
# --------------------------------------------------------------------------- #


class TestAdapterScanCodeLogin:
    async def test_scan_code_login_success(self):
        adapter = GolaxyAdapter()
        adapter._rest.login_scan_code = AsyncMock(return_value={"access_token": "tok", "refresh_token": "ref"})

        events: list = []

        async def cb(*args):
            events.append(args)

        adapter.on_token_refreshed(cb)

        creds = PlatformCredentials("golaxy", "", {"scan_uuid": "abc-123"})
        result = await adapter.connect(creds)

        assert result is True
        assert adapter.is_connected is True
        adapter._rest.login_scan_code.assert_awaited_once_with("abc-123")
        assert len(events) == 1

    async def test_scan_code_login_failure(self):
        adapter = GolaxyAdapter()
        adapter._rest.login_scan_code = AsyncMock(side_effect=RuntimeError("uuid expired"))

        creds = PlatformCredentials("golaxy", "", {"scan_uuid": "abc-123"})
        result = await adapter.connect(creds)

        assert result is False
        assert adapter.is_connected is False

    async def test_scan_uuid_takes_priority_over_password_fallback_but_not_over_sms(self):
        """sms_code (if present) still wins — scan_uuid is checked strictly after it,
        matching the plan's ordering. Guards against a future edit silently reordering
        the branches and breaking whichever login path used to come first."""
        adapter = GolaxyAdapter()
        adapter._rest.login_sms = AsyncMock(return_value={"access_token": "tok", "refresh_token": "ref"})
        adapter._rest.login_scan_code = AsyncMock()

        creds = PlatformCredentials("golaxy", "13800138000", {"sms_code": "1234", "scan_uuid": "abc-123"})
        result = await adapter.connect(creds)

        assert result is True
        adapter._rest.login_sms.assert_awaited_once()
        adapter._rest.login_scan_code.assert_not_awaited()


# --------------------------------------------------------------------------- #
# HTTP endpoints: /scan/start, /scan/state, /scan/confirm                    #
# --------------------------------------------------------------------------- #


class _User:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeCredentialStore:
    """In-memory stand-in, keyed by (user_id, platform) — same shape as
    `test_manager_token_persist.py`'s fake."""

    def __init__(self):
        self._store: dict[tuple[int, str], PlatformCredentials] = {}

    def save_credentials(self, user_id: int, credentials: PlatformCredentials) -> None:
        self._store[(user_id, credentials.platform)] = credentials

    def load_credentials(self, user_id: int, platform: str):
        return self._store.get((user_id, platform))

    def list_platforms(self, user_id: int):
        return [
            {"platform": p, "username": c.username, "updated_at": None}
            for (uid, p), c in self._store.items()
            if uid == user_id
        ]


class FakeManager:
    """Stands in for `PlatformManager` at the boundary the endpoint actually
    calls (`connect_platform`) — records every call so tests can assert it was
    NEVER reached for an unauthorized confirm (R-28) and reached EXACTLY ONCE
    across a retried confirm (R-30)."""

    def __init__(self, connect_result: bool = True):
        self._credential_store = FakeCredentialStore()
        self.connect_calls: list[tuple[str, PlatformCredentials, int]] = []
        self._connect_result = connect_result

    async def connect_platform(self, platform: str, credentials: PlatformCredentials, user_id: int) -> bool:
        self.connect_calls.append((platform, credentials, user_id))
        if self._connect_result:
            self._credential_store.save_credentials(user_id, credentials)
        return self._connect_result


def _build_app(manager):
    app = create_app(enable_engine=False)
    app.state.platform_manager = manager
    return app


class _CurrentUser:
    """Mutable holder so a single test can switch "who is making this
    request" between calls without rebuilding the app/dependency override."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    def __call__(self):
        return _User(self.user_id)


def _client_with_user(app, current_user: _CurrentUser) -> TestClient:
    app.dependency_overrides[get_current_user] = current_user
    return TestClient(app)


class TestScanStart:
    def test_pins_initiating_user_and_returns_local_payload(self, monkeypatch):
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_start(self):
            return ScanStart(uuid="golaxy-uuid-1", payload="golaxy_url&&&golaxy-uuid-1")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)

        manager = FakeManager()
        app = _build_app(manager)
        client = _client_with_user(app, _CurrentUser(1))

        r = client.post("/api/v1/platforms/golaxy/scan/start")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["payload"] == "golaxy_url&&&golaxy-uuid-1"
        assert "scan_id" in body and body["scan_id"]

        store = app.state.golaxy_scan_sessions
        session = store.get(body["scan_id"])
        assert session.initiating_user_id == 1
        assert session.golaxy_uuid == "golaxy-uuid-1"

    def test_start_then_state_is_reachable_across_separate_requests(self, monkeypatch):
        """Not a reachability fixture (R-team-lead review, task-6a): `start` and
        `state` must find the SAME session through the real HTTP boundary
        (`request.app.state.golaxy_scan_sessions`), not through a store the
        test manufactured and handed to both sides. Every other test in this
        module that exercises `state`/`confirm` seeds its own `ScanSessionStore`
        directly (`_seeded_store`) — that proves each endpoint's OWN logic given
        a session, but says nothing about whether `start`'s session is actually
        the one `state` looks up on a real device. This is the one test that
        drives both through the same `TestClient` end to end."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_start(self):
            return ScanStart(uuid="golaxy-uuid-1", payload="golaxy_url&&&golaxy-uuid-1")

        async def fake_poll(self, uuid):
            assert uuid == "golaxy-uuid-1"
            return ScanState.WAITING

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)
        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "poll", fake_poll)

        app = _build_app(FakeManager())
        client = _client_with_user(app, _CurrentUser(1))

        started = client.post("/api/v1/platforms/golaxy/scan/start")
        scan_id = started.json()["scan_id"]

        polled = client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")
        assert polled.status_code == 200, polled.text
        assert polled.json() == {"state": "waiting"}

    def test_upstream_failure_is_a_502_not_a_silent_pending_session(self, monkeypatch):
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_start(self):
            raise RuntimeError("星阵返回 code=5001")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)

        app = _build_app(FakeManager())
        client = _client_with_user(app, _CurrentUser(1))
        r = client.post("/api/v1/platforms/golaxy/scan/start")
        assert r.status_code == 502


def _seeded_store(
    app, *, initiating_user_id: int, state: ScanState = ScanState.WAITING
) -> tuple[ScanSessionStore, ScanSession]:
    store = app.state.golaxy_scan_sessions = ScanSessionStore()
    session = store.create(golaxy_uuid="golaxy-uuid-1", initiating_user_id=initiating_user_id)
    session.state = state
    return store, session


class TestScanState:
    def test_poll_by_a_different_user_is_403(self, monkeypatch):
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1)

        # If the endpoint reached out to Golaxy, that would itself be a bug for
        # an unauthorized caller — make the network call explode so any code
        # path that skips the ownership check is caught two ways at once.
        async def explode(self, uuid):
            raise AssertionError("must not poll Golaxy for an unauthorized caller")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "poll", explode)

        client = _client_with_user(app, _CurrentUser(2))
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        r = client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")
        assert r.status_code == 403

    def test_unknown_scan_id_is_404(self):
        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1)
        client = _client_with_user(app, _CurrentUser(1))
        r = client.get("/api/v1/platforms/golaxy/scan/state?scan_id=does-not-exist")
        assert r.status_code == 404

    def test_terminal_state_is_cached_and_never_repolled(self, monkeypatch):
        """Once a session reaches CONFIRMED (even before the user's own
        `confirm` call lands), further `state` polls must stop hitting
        Golaxy: polling again could flip an already-confirmed uuid to
        EXPIRED (Golaxy likely invalidates it once confirmed), which would
        flash "二维码已失效" at a user who just approved the login on their
        phone. Polls twice; the mock explodes on any Golaxy call so a
        regression is caught immediately rather than by a subtler race."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1, state=ScanState.CONFIRMED)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))

        async def explode(self, uuid):
            raise AssertionError("must not poll Golaxy once a session is terminal")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "poll", explode)

        client = _client_with_user(app, _CurrentUser(1))
        r1 = client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")
        r2 = client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")

        assert r1.status_code == 200 and r1.json() == {"state": "confirmed"}
        assert r2.status_code == 200 and r2.json() == {"state": "confirmed"}


class TestScanConfirmOwnership:
    """R-28: the scan_id's owner is whoever STARTED it, not whoever is making
    this particular request."""

    def _app_with_confirmed_session(self, monkeypatch, *, initiating_user_id: int):
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_username(self, uuid):
            return "阿范"

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "username", fake_username)

        manager = FakeManager()
        app = _build_app(manager)
        _seeded_store(app, initiating_user_id=initiating_user_id, state=ScanState.CONFIRMED)
        return app, manager

    def test_confirm_by_a_different_user_is_403_with_no_credential_row_for_them(self, monkeypatch):
        app, manager = self._app_with_confirmed_session(monkeypatch, initiating_user_id=1)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))

        client = _client_with_user(app, _CurrentUser(2))
        r = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})

        assert r.status_code == 403
        # The exchange must never have been attempted on user 2's behalf.
        assert manager.connect_calls == []
        assert manager._credential_store.load_credentials(2, "golaxy") is None
        # And user 1 (the real initiator) still has no row either -- user 2's
        # request must not silently complete user 1's login for them.
        assert manager._credential_store.load_credentials(1, "golaxy") is None

    def test_confirm_by_the_initiating_user_succeeds(self, monkeypatch):
        app, manager = self._app_with_confirmed_session(monkeypatch, initiating_user_id=1)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))

        client = _client_with_user(app, _CurrentUser(1))
        r = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["connected"] is True
        assert body["display_name"] == "阿范"
        assert len(manager.connect_calls) == 1
        assert manager.connect_calls[0][2] == 1


class TestScanConfirmIdempotency:
    """R-30: a retried confirm must return the cached result, not re-exchange
    the (one-shot) scan-code token."""

    def test_confirm_twice_reuses_cached_result_and_does_not_reexchange(self, monkeypatch):
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        username_calls = []

        async def fake_username(self, uuid):
            username_calls.append(uuid)
            return "阿范"

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "username", fake_username)

        manager = FakeManager()
        app = _build_app(manager)
        _seeded_store(app, initiating_user_id=1, state=ScanState.CONFIRMED)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r1 = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})
        r2 = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})

        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()
        # The token exchange (connect_platform, which drives login_scan_code)
        # and the nickname lookup must each have happened exactly once.
        assert len(manager.connect_calls) == 1
        assert len(username_calls) == 1

    def test_confirm_before_state_is_confirmed_is_409(self, monkeypatch):
        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1, state=ScanState.SCANNED)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})
        assert r.status_code == 409


# --------------------------------------------------------------------------- #
# R-29: principal vs nickname — the full chain, from a fresh (post-restart)   #
# adapter, must degrade HONESTLY rather than fabricate a `0086-{昵称}`.       #
# --------------------------------------------------------------------------- #


class TestPrincipalVsNickname:
    async def test_scan_login_persists_empty_username_not_a_guessed_principal(self):
        """`GolaxyAdapter.connect()` with a scan_uuid must leave the REST
        client's login-principal (`_username`) unset — it must NOT derive one
        from the nickname. `set_username("")` is a documented no-op
        (test_golaxy_item_counts_adapter.py::test_empty_string_is_noop)."""
        adapter = GolaxyAdapter()
        adapter._rest.login_scan_code = AsyncMock(return_value={"access_token": "tok", "refresh_token": "ref"})

        creds = PlatformCredentials("golaxy", "", {"scan_uuid": "abc-123"})
        await adapter.connect(creds)

        assert adapter._rest._username is None

    async def test_reconnect_from_stored_scan_credentials_then_item_counts_is_honestly_unavailable(self):
        """Simulates a restart: a FRESH adapter is built, credentials saved by
        a prior scan-login (username="") are handed to `.connect()` for a
        token-based reconnect, and the account-level 道具 lookup that follows
        (`fetch_item_counts`) must raise rather than silently query
        `/items/0086-{昵称}` (which Step 5b flags as the exact bug: "道具角标
        全线坏掉,而全链测试照样绿" if this degrades silently)."""
        stored = PlatformCredentials(
            platform="golaxy",
            username="",  # R-29 path 2: no verified principal on this path, so left blank.
            auth_data={"access_token": "tok", "refresh_token": "ref"},
        )

        fresh_adapter = GolaxyAdapter()
        fresh_adapter._rest.get_all_lives = AsyncMock(return_value=[])  # token-verify probe succeeds

        connected = await fresh_adapter.connect(stored)
        assert connected is True

        with pytest.raises(Fatal):
            await fresh_adapter.fetch_item_counts()
