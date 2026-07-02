"""Part A: engine-play REST endpoint tests (fake manager, FastAPI TestClient).

Covers the new endpoints the kiosk frontend needs:
  - POST /{platform}/engine/start   (schema REJECTS unknown/out-of-range fields)
  - GET  /{platform}/engine/levels
  - POST /{platform}/sms/request
  - POST /{platform}/login          (sms_code path)
  - GET  /status                    (supports_engine_play capability)

Follows the tests/web_ui/test_billing_api.py pattern: create_app(enable_engine=False),
override get_current_user with a stub, and inject a fake PlatformManager on
app.state. Only the network genmove boundary and the manager are faked here — the
real-stack proof lives in test_engine_integration.py.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.server import create_app


class _User:
    id = 1


class FakeAdapter:
    """A stand-in for GolaxyAdapter with just the attributes the endpoints read."""

    def __init__(self, is_connected=True, supports_engine_play=True, has_sms=True):
        self.is_connected = is_connected
        self.supports_engine_play = supports_engine_play
        if has_sms:
            self.request_sms_code = AsyncMock(return_value=True)

    def get_engine_levels(self):
        return [
            {"elo_score": 1100, "level_name": "1级", "name": "星铠虾"},
            {"elo_score": 1000, "level_name": "2级", "name": "星夜鹰"},
        ]


class FakeCredStore:
    def load_credentials(self, user_id, platform):
        return None

    def list_platforms(self, user_id):
        return []


class FakeManager:
    def __init__(self, adapter=None, platforms=None):
        self._adapter = adapter
        self._platforms = platforms if platforms is not None else []
        self._credential_store = FakeCredStore()
        self.connect_platform = AsyncMock(return_value=True)
        self.start_engine_game = AsyncMock(return_value="sess-1")

    def get_adapter(self, name):
        return self._adapter

    def list_platforms(self):
        # Return copies so the endpoint can mutate (saved_username) without clobbering.
        return [dict(p) for p in self._platforms]


def _build_app(manager):
    app = create_app(enable_engine=False)
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: _User()
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- engine/start ---------------------------------------------------------- #


@pytest.mark.asyncio
async def test_engine_start_ok():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/engine/start", json={"level": 1100, "human_color": "B"})
    assert r.status_code == 200, r.text
    assert r.json() == {"session_id": "sess-1"}
    # Manager awaited with a config carrying the level + human_color.
    mgr.start_engine_game.assert_awaited_once()
    args, kwargs = mgr.start_engine_game.call_args
    assert args[0] == "golaxy"
    config = args[1]
    assert config.level == 1100
    assert config.human_color == "B"
    # Fixed non-default game config (never surfaced through the request).
    assert config.komi == 7.5
    assert config.rule == "chinese"
    assert config.handicap == 0
    assert config.board_size == 19


@pytest.mark.asyncio
async def test_engine_start_rejects_extra_field():
    app = _build_app(FakeManager(adapter=FakeAdapter()))
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "B", "komi": 7.5},
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_engine_start_rejects_bad_color():
    app = _build_app(FakeManager(adapter=FakeAdapter()))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/engine/start", json={"level": 1100, "human_color": "X"})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_engine_start_rejects_unknown_level():
    app = _build_app(FakeManager(adapter=FakeAdapter()))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/engine/start", json={"level": 9999, "human_color": "B"})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_engine_start_not_connected():
    app = _build_app(FakeManager(adapter=FakeAdapter(is_connected=False)))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/engine/start", json={"level": 1100, "human_color": "B"})
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_engine_start_unknown_platform():
    app = _build_app(FakeManager(adapter=None))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/nope/engine/start", json={"level": 1100, "human_color": "B"})
    assert r.status_code == 400, r.text


# --- engine/levels --------------------------------------------------------- #


@pytest.mark.asyncio
async def test_engine_levels_ok():
    app = _build_app(FakeManager(adapter=FakeAdapter()))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/levels")
    assert r.status_code == 200, r.text
    levels = r.json()["levels"]
    assert {l["elo_score"] for l in levels} == {1100, 1000}


@pytest.mark.asyncio
async def test_engine_levels_no_engine_support():
    app = _build_app(FakeManager(adapter=FakeAdapter(supports_engine_play=False)))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/levels")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_engine_levels_unknown_platform():
    app = _build_app(FakeManager(adapter=None))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/nope/engine/levels")
    assert r.status_code == 404, r.text


# --- sms/request ----------------------------------------------------------- #


@pytest.mark.asyncio
async def test_sms_request_ok():
    adapter = FakeAdapter()
    app = _build_app(FakeManager(adapter=adapter))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/sms/request", json={"phone": "13800000000"})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "sent"}
    adapter.request_sms_code.assert_awaited_once_with("13800000000")


@pytest.mark.asyncio
async def test_sms_request_unsupported_adapter():
    app = _build_app(FakeManager(adapter=FakeAdapter(has_sms=False)))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/golaxy/sms/request", json={"phone": "13800000000"})
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_sms_request_unknown_platform():
    app = _build_app(FakeManager(adapter=None))
    async with _client(app) as ac:
        r = await ac.post("/api/v1/platforms/nope/sms/request", json={"phone": "13800000000"})
    assert r.status_code == 404, r.text


# --- login (sms_code path) ------------------------------------------------- #


@pytest.mark.asyncio
async def test_login_with_sms_code():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/login",
            json={"username": "13800000000", "sms_code": "1234"},
        )
    assert r.status_code == 200, r.text
    mgr.connect_platform.assert_awaited_once()
    args, _ = mgr.connect_platform.call_args
    credentials = args[1]
    assert credentials.username == "13800000000"
    assert credentials.auth_data == {"sms_code": "1234"}


# --- status capability ----------------------------------------------------- #


@pytest.mark.asyncio
async def test_status_includes_supports_engine_play():
    platforms = [
        {"platform": "golaxy", "connected": True, "supports_engine_play": True},
        {"platform": "ogs", "connected": False, "supports_engine_play": False},
    ]
    app = _build_app(FakeManager(adapter=None, platforms=platforms))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/status")
    assert r.status_code == 200, r.text
    for p in r.json()["platforms"]:
        assert "supports_engine_play" in p


def test_real_manager_list_platforms_exposes_supports_engine_play():
    """The REAL manager (not a fake) surfaces supports_engine_play per platform."""
    from katrain.web.platforms.manager import PlatformManager
    from katrain.web.platforms.golaxy.adapter import GolaxyAdapter

    pm = PlatformManager(session_manager=None)
    pm.register_adapter(GolaxyAdapter())
    entry = next(p for p in pm.list_platforms() if p["platform"] == "golaxy")
    assert entry["supports_engine_play"] is True
