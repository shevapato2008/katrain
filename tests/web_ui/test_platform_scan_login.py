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

import time
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


def _refuse_real_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(
        f"test tried to make a REAL network call to {request.url} — "
        "pass transport=httpx.MockTransport(...) explicitly, or inject client=/monkeypatch "
        "GolaxyScanLogin's methods, to opt back into a controlled response."
    )


@pytest.fixture(autouse=True)
def _forbid_real_golaxy_network(monkeypatch):
    """Structural network guard (team-lead ruling ③, task-6b round 2).

    A per-test opt-in helper (like the `_forbid_golaxy_network` static method
    on `TestScanPlatformValidationF4`) only protects the tests that remember
    to call it — and "remember to" is exactly what failed TWICE in two
    rounds on this same module (once during the task-6a review, once again
    during THIS round's own F4 mutation testing, before this fixture
    existed: a mutation left `poll` unmocked and it made a real GET to
    api.19x19.com). The fix has to make the DEFAULT state safe, not rely on
    every test author noticing they need protecting.

    Patches `httpx.AsyncClient` for the duration of each test in this module
    so that any instance created WITHOUT an explicit `transport=` kwarg gets
    one that raises instead of touching the network. Every test that
    legitimately needs real request/response shaping already passes
    `transport=httpx.MockTransport(...)` explicitly (`make_client()` below,
    `httpx.ASGITransport` for the concurrency probes) — `setdefault` leaves
    those completely alone. Tests that monkeypatch `GolaxyScanLogin.start`/
    `poll`/`username` directly never reach `httpx.AsyncClient` construction
    at all, also unaffected.
    """
    real_async_client_init = httpx.AsyncClient.__init__

    def _guarded_init(self, *args, **kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(_refuse_real_network))
        real_async_client_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _guarded_init)


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
# ScanSession/ScanSessionStore TTL + cap semantics (F5, task-6a review)       #
# --------------------------------------------------------------------------- #


class TestScanSessionTTLSemanticsF5:
    """Review's M-I: making `ScanSession.expired` always return `False`
    survived all 107 pre-existing mutation-judge tests — TTL/expiry had ZERO
    coverage. These are direct, no-HTTP unit tests on `ScanSession`/
    `ScanSessionStore` themselves, closing that gap at its source."""

    def test_expired_property_reflects_the_ttl(self):
        from katrain.web.platforms.golaxy.scan_login import ScanSession

        fresh = ScanSession(scan_id="s1", golaxy_uuid="u1", initiating_user_id=1, expires_at=time.time() + 60)
        assert fresh.expired is False

        already_past = ScanSession(scan_id="s2", golaxy_uuid="u2", initiating_user_id=1, expires_at=time.time() - 1)
        assert already_past.expired is True

    def test_store_sweeps_expired_sessions_on_create(self):
        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=100)
        stale = store.create(golaxy_uuid="u-stale", initiating_user_id=1)
        stale.expires_at = time.time() - 86400  # force-expire without waiting

        store.create(golaxy_uuid="u-fresh", initiating_user_id=2)  # triggers the sweep

        assert store.get(stale.scan_id) is None
        assert len(store._sessions) == 1


class TestScanSessionSupersedeF5:
    """F5 revised (team-lead ruling ①, this round): a hard per-user cap with
    NO supersede would trap a user who just keeps clicking "换一张" behind a
    429 with nothing on screen they could do about it — same dead-end shape
    as the D2 finding. `_supersede_unconsumed` is the PRIMARY defense: a new
    `create()` for the SAME user retires their own not-yet-consumed session
    first, so under normal use at most one unconsumed session per user ever
    exists. `MAX_SESSIONS_PER_USER` remains only as a backstop for abnormal
    accumulation (tested separately below)."""

    def test_new_scan_start_supersedes_the_same_users_unconsumed_session(self):
        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=5)
        old = store.create(golaxy_uuid="u-old", initiating_user_id=1)
        new = store.create(golaxy_uuid="u-new", initiating_user_id=1)

        assert store.get(old.scan_id) is None, "clicking 换一张 must retire the old QR code"
        assert store.get(new.scan_id) is new

    def test_new_scan_start_does_not_supersede_an_already_consumed_session(self):
        """A successful (consumed) login must survive a later scan_start —
        its cached result may still be legitimately replayed by a
        network-retried confirm within the TTL window."""
        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=5)
        old = store.create(golaxy_uuid="u-old", initiating_user_id=1)
        old.consumed = True
        old.result = {"connected": True, "display_name": "阿范"}

        store.create(golaxy_uuid="u-new", initiating_user_id=1)

        assert store.get(old.scan_id) is old

    def test_supersede_does_not_touch_another_users_session(self):
        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=5)
        other = store.create(golaxy_uuid="u-other", initiating_user_id=2)
        store.create(golaxy_uuid="u-mine", initiating_user_id=1)

        assert store.get(other.scan_id) is other

    def test_scan_start_endpoint_invalidates_the_previous_scan_id(self, monkeypatch):
        """Same property as above, but through the real HTTP boundary: the
        first `scan_id` a caller gets must stop being usable once they start
        a second scan (mirrors clicking "换一张" on the kiosk screen)."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        n = {"v": 0}

        async def fake_start(self):
            n["v"] += 1
            return ScanStart(uuid=f"g-{n['v']}", payload=f"golaxy_url&&&g-{n['v']}")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)

        app = _build_app(FakeManager())
        client = _client_with_user(app, _CurrentUser(1))

        first_scan_id = client.post("/api/v1/platforms/golaxy/scan/start").json()["scan_id"]
        client.post("/api/v1/platforms/golaxy/scan/start")  # "换一张"

        r = client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={first_scan_id}")
        assert r.status_code == 404


class TestScanSessionCapF5:
    """F5: the `MAX_SESSIONS_PER_USER` backstop, for the cases the supersede
    logic above deliberately does NOT cover — an accumulation of several
    already-CONSUMED (i.e. successful) sessions for the same user, which
    `_supersede_unconsumed` leaves alone on purpose."""

    def test_check_capacity_raises_once_consumed_sessions_reach_the_cap(self):
        from katrain.web.platforms.golaxy.scan_login import ScanRateLimited

        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=3)
        for i in range(3):
            s = store.create(golaxy_uuid=f"u{i}", initiating_user_id=1)
            s.consumed = True  # simulate several completed logins in a row

        with pytest.raises(ScanRateLimited):
            store.check_capacity(1)
        # A different user is unaffected — the cap is per-user, not global.
        store.check_capacity(2)

    def test_create_also_enforces_the_cap_as_a_backstop(self):
        from katrain.web.platforms.golaxy.scan_login import ScanRateLimited

        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=2)
        for i in range(2):
            s = store.create(golaxy_uuid=f"u{i}", initiating_user_id=1)
            s.consumed = True
        with pytest.raises(ScanRateLimited):
            store.create(golaxy_uuid="u3", initiating_user_id=1)
        assert len(store._sessions) == 2

    def test_expired_sessions_do_not_count_against_the_cap(self):
        store = ScanSessionStore(ttl_seconds=300.0, max_per_user=2)
        s1 = store.create(golaxy_uuid="u1", initiating_user_id=1)
        s1.consumed = True
        s1.expires_at = time.time() - 86400
        s2 = store.create(golaxy_uuid="u2", initiating_user_id=1)
        s2.consumed = True
        # s1 is expired -> only 1 LIVE session for user 1 -> room for one more.
        store.create(golaxy_uuid="u3", initiating_user_id=1)

    def test_scan_start_endpoint_returns_429_once_rate_limited(self, monkeypatch):
        """The only realistic way to reach this now is several successful
        (consumed) logins already sitting in the store — pre-seeded here
        rather than driven through repeated `scan/start` calls, since those
        would just supersede each other (see `TestScanSessionSupersedeF5`)."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        call_count = {"n": 0}

        async def fake_start(self):
            call_count["n"] += 1
            return ScanStart(uuid=f"g-{call_count['n']}", payload=f"golaxy_url&&&g-{call_count['n']}")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)

        app = _build_app(FakeManager())
        store = ScanSessionStore(max_per_user=2)
        for i in range(2):
            s = store.create(golaxy_uuid=f"prior-{i}", initiating_user_id=1)
            s.consumed = True
        app.state.golaxy_scan_sessions = store
        client = _client_with_user(app, _CurrentUser(1))

        r = client.post("/api/v1/platforms/golaxy/scan/start")
        assert r.status_code == 429
        # Rejected by check_capacity BEFORE ever calling Golaxy.
        assert call_count["n"] == 0


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


class TestCrossUserPrincipalLeakF1:
    """F1 (task-6a review, high, release-blocking): `GolaxyAdapter` is a
    per-platform SINGLETON, registered once at startup and never rebuilt
    (`manager.py`'s `register_adapter`) — so a login with no principal
    (scan-login) run on an adapter instance a PREVIOUS user already logged
    into via SMS/password must not silently keep serving that previous
    user's `0086-{phone}` for account-level calls like `/items/{username}`.

    Deliberately does NOT construct a fresh `GolaxyAdapter()` and assert
    `_username is None` — that was F1's own root cause (`_username`'s
    constructor default is `None`, so that assertion can't tell "correctly
    cleared" from "nobody ever set it"). Both tests below drive a real
    principal through the SAME adapter instance first, so a green result
    here is actually informative.
    """

    async def test_disconnect_then_second_user_scan_login_does_not_inherit_first_principal(self):
        from katrain.web.platforms.manager import PlatformManager

        class FakeStore:
            def __init__(self):
                self.rows: dict = {}

            def save_credentials(self, user_id, credentials):
                self.rows[(user_id, credentials.platform)] = credentials

            def load_credentials(self, user_id, platform):
                return self.rows.get((user_id, platform))

            def list_platforms(self, user_id):
                return []

        pm = PlatformManager(None, credential_store=FakeStore())
        adapter = GolaxyAdapter()
        pm.register_adapter(adapter)
        adapter._rest.login_sms = AsyncMock(return_value={"access_token": "A", "refresh_token": "a"})
        adapter._rest.login_scan_code = AsyncMock(return_value={"access_token": "B", "refresh_token": "b"})

        # User A (id=1) logs in via SMS — a real, verified principal.
        await pm.connect_platform("golaxy", PlatformCredentials("golaxy", "13800138000", {"sms_code": "1234"}), 1)
        assert adapter._rest._username == "0086-13800138000"

        # A disconnects (the box's "断开" button).
        await pm.disconnect_platform("golaxy", 1)

        # User B (id=2) scans in — no principal available at this layer.
        ok = await pm.connect_platform("golaxy", PlatformCredentials("golaxy", "", {"scan_uuid": "B-uuid"}), 2)
        assert ok is True
        assert adapter._rest._username is None, "B's scan login inherited A's Golaxy login principal"

    async def test_same_user_switching_to_scan_login_without_disconnect_also_clears_principal(self):
        """F1's second half: `close()` alone is insufficient, because a user
        re-logging in WITHOUT an intervening disconnect never reaches it —
        this drives that path directly through `adapter.connect()` twice."""
        adapter = GolaxyAdapter()
        adapter._rest.login_sms = AsyncMock(return_value={"access_token": "A", "refresh_token": "a"})
        adapter._rest.login_scan_code = AsyncMock(return_value={"access_token": "B", "refresh_token": "b"})

        await adapter.connect(PlatformCredentials("golaxy", "13800138000", {"sms_code": "1234"}))
        assert adapter._rest._username == "0086-13800138000"

        # No disconnect()/close() call in between.
        await adapter.connect(PlatformCredentials("golaxy", "", {"scan_uuid": "B-uuid"}))
        assert adapter._rest._username is None


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


class RaisingManager(FakeManager):
    """F4 (task-6a review): the real `PlatformManager.connect_platform`
    raises a bare `ValueError` for an unregistered platform name. Used to
    prove that `scan_confirm` no longer lets that reach the caller as an
    unhandled 500, and (via the `connect_calls` tracking it inherits) that a
    REGISTERED-but-wrong platform's `connect_platform` is never even called —
    the `session.platform` check must reject it before either can happen."""

    async def connect_platform(self, platform: str, credentials: PlatformCredentials, user_id: int) -> bool:
        if platform != "golaxy":
            raise ValueError(f"Unknown platform: {platform}")
        return await super().connect_platform(platform, credentials, user_id)


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
        """F7 (task-6a review, gate-was-blind): originally used caller id 1,
        which coincides with a literal `1` — a mutation hardcoding
        `initiating_user_id=1` in the endpoint (instead of `user.id`) survived
        every one of the 107 mutation-judge tests, because the ONLY test that
        could have caught it used the constant its own assertion checked for.
        Caller id 7 (review's own probe used the same value) makes a hardcoded
        `1` observably wrong."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_start(self):
            return ScanStart(uuid="golaxy-uuid-1", payload="golaxy_url&&&golaxy-uuid-1")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)

        manager = FakeManager()
        app = _build_app(manager)
        client = _client_with_user(app, _CurrentUser(7))

        r = client.post("/api/v1/platforms/golaxy/scan/start")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["payload"] == "golaxy_url&&&golaxy-uuid-1"
        assert "scan_id" in body and body["scan_id"]

        store = app.state.golaxy_scan_sessions
        session = store.get(body["scan_id"])
        assert session.initiating_user_id == 7
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

    def test_unregistered_platform_is_rejected_before_any_golaxy_call(self, monkeypatch):
        """The `platform != "golaxy"` gate itself had no test (review's M-J:
        deleting it left all 107 mutation-judge tests green). Also asserts
        Golaxy is never even touched for an unsupported platform name."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def explode(self):
            raise AssertionError("must not call Golaxy for an unsupported platform")

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", explode)

        app = _build_app(FakeManager())
        client = _client_with_user(app, _CurrentUser(1))
        r = client.post("/api/v1/platforms/fantasy/scan/start")
        assert r.status_code == 400


def _seeded_store(
    app, *, initiating_user_id: int, state: ScanState = ScanState.WAITING
) -> tuple[ScanSessionStore, ScanSession]:
    store = app.state.golaxy_scan_sessions = ScanSessionStore()
    session = store.create(golaxy_uuid="golaxy-uuid-1", initiating_user_id=initiating_user_id)
    session.state = state
    return store, session


class TestScanPlatformValidationF4:
    """F4 (task-6a review, medium): `scan_state`/`scan_confirm` trusted the
    `platform` URL path param unconditionally — a golaxy `scan_id` posted to
    an unregistered platform reached `connect_platform` and raised a bare
    `ValueError` -> unhandled 500; against a REGISTERED-but-wrong platform
    (e.g. "ogs"), it would make a real network call with empty credentials.
    Fixed by recording `platform` on `ScanSession` and checking it before
    ANY manager call, plus a `ValueError` backstop as defense in depth.

    Relies on the module's autouse `_forbid_real_golaxy_network` fixture for
    network safety under mutation — no per-test opt-in needed (that used to
    be a `staticmethod` helper here; superseded, see team-lead ruling ③)."""

    def test_state_for_a_mismatched_platform_is_404_not_leaked(self):
        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1)  # creates a "golaxy" session
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r = client.get(f"/api/v1/platforms/ogs/scan/state?scan_id={scan_id}")
        assert r.status_code == 404

    def test_confirm_for_an_unregistered_platform_is_400_not_500(self):
        """Mirrors the review's P3 probe."""
        manager = RaisingManager()
        app = _build_app(manager)
        _seeded_store(app, initiating_user_id=1, state=ScanState.CONFIRMED)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r = client.post("/api/v1/platforms/fantasy/scan/confirm", json={"scan_id": scan_id})
        assert r.status_code == 404  # session.platform mismatch catches it first
        assert manager.connect_calls == []

    def test_confirm_for_a_registered_but_different_platform_never_calls_it(self):
        """The scarier half of F4: "ogs" IS a registered platform, so without
        the `session.platform` check this would reach a REAL
        `connect_platform("ogs", ...)` with empty credentials, not just a
        ValueError."""
        manager = FakeManager()
        app = _build_app(manager)
        _seeded_store(app, initiating_user_id=1, state=ScanState.CONFIRMED)  # golaxy session
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r = client.post("/api/v1/platforms/ogs/scan/confirm", json={"scan_id": scan_id})
        assert r.status_code == 404
        assert manager.connect_calls == []


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

    def test_successive_polls_reuse_the_same_http_client(self, monkeypatch):
        """F6 (task-6a review, low but real on RK3562): `scan/state` is
        polled every second for as long as the QR screen is open. Without an
        injected, reused client, each poll opens and closes a fresh
        `httpx.AsyncClient` — one TLS handshake to api.19x19.com per second.
        Captures the `client` kwarg `GolaxyScanLogin` is constructed with
        across two separate polls and asserts it's the SAME object both
        times (and is not `None`, i.e. actually injected)."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        seen_clients: list = []

        class SpyScanLogin:
            def __init__(self, client=None):
                seen_clients.append(client)

            async def poll(self, uuid):
                return scan_login_mod.ScanState.WAITING

        # `scan_state` does `from ...scan_login import GolaxyScanLogin` fresh
        # inside the function body every call, so it always resolves the
        # CURRENT attribute on the scan_login module — patch it there, not on
        # `platforms` (which never holds a module-level reference to it).
        monkeypatch.setattr(scan_login_mod, "GolaxyScanLogin", SpyScanLogin)

        app = _build_app(FakeManager())
        _seeded_store(app, initiating_user_id=1, state=ScanState.WAITING)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")
        client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")

        assert len(seen_clients) == 2
        assert seen_clients[0] is not None
        assert seen_clients[0] is seen_clients[1], "each poll opened its own httpx.AsyncClient"


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

    def test_consumed_success_does_not_replay_forever_once_the_session_expires(self, monkeypatch):
        """F3 (task-6a review, medium): R-30's idempotency window is meant to
        cover a network-retry timescale, not the session's whole
        `DEFAULT_SCAN_TTL_SECONDS` lifetime. Before the fix, `consumed` was
        checked BEFORE `expired`, so a successfully-confirmed session's cached
        `{"connected": True}` could be replayed forever regardless of TTL —
        even after the platform connection it refers to might have been torn
        down or handed to someone else."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_username(self, uuid):
            return "阿范"

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "username", fake_username)

        manager = FakeManager()
        app = _build_app(manager)
        _seeded_store(app, initiating_user_id=1, state=ScanState.CONFIRMED)
        scan_id = next(iter(app.state.golaxy_scan_sessions._sessions))
        client = _client_with_user(app, _CurrentUser(1))

        r1 = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})
        assert r1.status_code == 200
        assert len(manager.connect_calls) == 1

        # Push the session's TTL a day into the past — simulates the retry
        # arriving long after the scan session should have died.
        app.state.golaxy_scan_sessions.get(scan_id).expires_at = time.time() - 86400

        r2 = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})
        assert r2.status_code == 410, r2.text
        # Must not have re-exchanged the token either.
        assert len(manager.connect_calls) == 1


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

    def test_confirm_endpoint_never_sends_the_nickname_as_the_login_principal(self, monkeypatch):
        """F2 (task-6a review, medium-high): R-29's decision is made at
        `platforms.py`'s `scan_confirm` — `username=""` on the
        `PlatformCredentials` it hands to `connect_platform` — but nothing
        in the original 24 tests looked AT that line: both other
        `TestPrincipalVsNickname` tests construct their OWN
        `PlatformCredentials(username="")` directly, which is the value the
        endpoint is supposed to PRODUCE, not evidence that it does. A
        one-line "optimization" (`username=display_name` instead of `""`) —
        exactly the thing R-29 forbids — survives all of them. This test
        drives the real endpoint end to end and inspects what `FakeManager`
        actually received."""
        import katrain.web.platforms.golaxy.scan_login as scan_login_mod

        async def fake_start(self):
            return ScanStart(uuid="golaxy-uuid-1", payload="golaxy_url&&&golaxy-uuid-1")

        async def fake_poll(self, uuid):
            return ScanState.CONFIRMED

        async def fake_username(self, uuid):
            return "阿范"

        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "start", fake_start)
        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "poll", fake_poll)
        monkeypatch.setattr(scan_login_mod.GolaxyScanLogin, "username", fake_username)

        manager = FakeManager()
        app = _build_app(manager)
        client = _client_with_user(app, _CurrentUser(1))

        scan_id = client.post("/api/v1/platforms/golaxy/scan/start").json()["scan_id"]
        client.get(f"/api/v1/platforms/golaxy/scan/state?scan_id={scan_id}")
        r = client.post("/api/v1/platforms/golaxy/scan/confirm", json={"scan_id": scan_id})

        assert r.status_code == 200, r.text
        assert len(manager.connect_calls) == 1
        credentials_sent = manager.connect_calls[0][1]
        assert credentials_sent.username == "", "scan/confirm sent the nickname as the login principal"

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
