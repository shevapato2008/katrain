"""Task 3 (§13 Phase 3): POST /{platform}/engine/analysis endpoint tests.

Covers the endpoint (platforms.py) + PlatformManager.engine_analysis delegate that
wire the Task-2 GolaxyAdapter.engine_analysis(game_id, kind) over HTTP. Mirrors the
fake-manager + FastAPI TestClient pattern from test_platforms_engine_start.py for
the endpoint-boundary cases, and additionally exercises the REAL PlatformManager's
session_id -> game_id resolution (the mapping logic this task adds) with a stub
adapter, so that logic isn't mocked away.
"""

import dataclasses
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.platforms.golaxy.adapter import (
    AreaAnalysis,
    Candidate,
    JudgeAnalysis,
    JudgePoint,
    OptionsAnalysis,
    OwnershipPoint,
    Point,
    VariationAnalysis,
)
from katrain.web.platforms.golaxy.engine_client import QuotaExhausted
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameContext
from katrain.web.server import create_app


class _User:
    id = 1


def _area_result():
    return AreaAnalysis(ownership=[OwnershipPoint(col=3, row=4, value=0.87)], winrate=0.61, delta=1.2)


def _options_result():
    return OptionsAnalysis(candidates=[Candidate(col=2, row=2, prob=0.5, winrate=0.55, delta=0.3)])


def _variation_result():
    return VariationAnalysis(sequence=[Point(col=15, row=3)], winrate=0.48, delta=-0.4)


def _judge_result():
    return JudgeAnalysis(ownership=[JudgePoint(col=0, row=0, owner="B")], winner="B", delta=6.5)


RESULT_BY_KIND = {
    "area": _area_result,
    "options": _options_result,
    "variation": _variation_result,
    "judge": _judge_result,
}


# --- FakeManager / FakeAdapter (endpoint-boundary tests) -------------------- #


class FakeAdapter:
    """Stand-in for GolaxyAdapter with just the attributes the endpoint reads."""

    def __init__(self, is_connected=True, supports_engine_play=True):
        self.is_connected = is_connected
        self.supports_engine_play = supports_engine_play


class FakeManager:
    def __init__(self, adapter=None):
        self._adapter = adapter
        self.engine_analysis = AsyncMock()

    def get_adapter(self, name):
        return self._adapter


def _build_app(manager):
    app = create_app(enable_engine=False)
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: _User()
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- success per kind -------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["area", "options", "variation", "judge"])
async def test_engine_analysis_success_per_kind(kind):
    mgr = FakeManager(adapter=FakeAdapter())
    mgr.engine_analysis.return_value = RESULT_BY_KIND[kind]()
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": kind},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["kind"] == kind
    expected = dataclasses.asdict(RESULT_BY_KIND[kind]())
    assert body["data"] == expected
    mgr.engine_analysis.assert_awaited_once_with("golaxy", "sess-1", kind)


@pytest.mark.asyncio
async def test_engine_analysis_area_data_point_survives_roundtrip():
    """Assert a decoded point value actually survives the asdict/JSON round-trip
    (not just top-level keys)."""
    mgr = FakeManager(adapter=FakeAdapter())
    mgr.engine_analysis.return_value = _area_result()
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "area"},
        )
    assert r.status_code == 200, r.text
    point = r.json()["data"]["ownership"][0]
    assert point == {"col": 3, "row": 4, "value": 0.87}


# --- QuotaExhausted -> 200 {ok:false, reason:"insufficient"} ------------------ #


@pytest.mark.asyncio
async def test_engine_analysis_quota_exhausted_returns_200_insufficient():
    mgr = FakeManager(adapter=FakeAdapter())
    mgr.engine_analysis.side_effect = QuotaExhausted("no quota left")
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "options"},
        )
    assert r.status_code == 200, r.text  # NOT a 5xx
    assert r.json() == {"ok": False, "reason": "insufficient", "kind": "options"}


# --- invalid kind -> 422 ------------------------------------------------------ #


@pytest.mark.asyncio
async def test_engine_analysis_invalid_kind_422():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "winrate"},
        )
    assert r.status_code == 422, r.text
    mgr.engine_analysis.assert_not_awaited()


# --- unknown/expired session -> 404 ------------------------------------------ #


@pytest.mark.asyncio
async def test_engine_analysis_unknown_session_404():
    mgr = FakeManager(adapter=FakeAdapter())
    mgr.engine_analysis.side_effect = KeyError("sess-unknown")
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-unknown", "kind": "area"},
        )
    assert r.status_code == 404, r.text


# --- not connected / unknown platform -> 400 --------------------------------- #


@pytest.mark.asyncio
async def test_engine_analysis_not_connected_400():
    mgr = FakeManager(adapter=FakeAdapter(is_connected=False))
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "area"},
        )
    assert r.status_code == 400, r.text
    mgr.engine_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_analysis_unknown_platform_400():
    mgr = FakeManager(adapter=None)
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "area"},
        )
    assert r.status_code == 400, r.text
    mgr.engine_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_analysis_unsupported_engine_play_400():
    mgr = FakeManager(adapter=FakeAdapter(supports_engine_play=False))
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-1", "kind": "area"},
        )
    assert r.status_code == 400, r.text
    mgr.engine_analysis.assert_not_awaited()


# --- real PlatformManager: session_id -> game_id -> adapter resolution ------- #
#
# The cases above stub pm.engine_analysis directly, which would mock away the
# very mapping this task adds. These exercise the REAL PlatformManager.


class RealAdapterStub:
    """Stand-in GolaxyAdapter for the real-manager tests: only implements what
    PlatformManager.engine_analysis touches (is_connected/supports_engine_play
    at the endpoint layer, engine_analysis at the manager layer)."""

    platform_name = "golaxy"
    is_connected = True
    supports_engine_play = True

    def __init__(self):
        self.engine_analysis = AsyncMock(return_value=_area_result())


def _real_manager_with_engine_game(session_id="sess-real", game_id="golaxy-engine-1", is_engine=True):
    pm = PlatformManager(session_manager=None)
    adapter = RealAdapterStub()
    pm._adapters["golaxy"] = adapter
    pm._session_to_game[session_id] = game_id
    pm._active_games[game_id] = PlatformGameContext(
        session_id=session_id, platform="golaxy", remote_game_id=game_id, is_engine=is_engine
    )
    return pm, adapter


@pytest.mark.asyncio
async def test_engine_analysis_real_manager_resolves_session_to_game():
    pm, adapter = _real_manager_with_engine_game(session_id="sess-real", game_id="golaxy-engine-1")
    app = create_app(enable_engine=False)
    app.state.platform_manager = pm
    app.dependency_overrides[get_current_user] = lambda: _User()
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-real", "kind": "area"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"] == dataclasses.asdict(_area_result())
    # session_id was resolved to the engine game_id, NOT passed through raw.
    adapter.engine_analysis.assert_awaited_once_with("golaxy-engine-1", "area")


@pytest.mark.asyncio
async def test_engine_analysis_real_manager_unknown_session_404():
    pm, adapter = _real_manager_with_engine_game()
    app = create_app(enable_engine=False)
    app.state.platform_manager = pm
    app.dependency_overrides[get_current_user] = lambda: _User()
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "no-such-session", "kind": "area"},
        )
    assert r.status_code == 404, r.text
    adapter.engine_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_analysis_real_manager_non_engine_context_404():
    """A session mapped to a non-engine (regular platform) game must not
    resolve as an engine game."""
    pm, adapter = _real_manager_with_engine_game(is_engine=False)
    app = create_app(enable_engine=False)
    app.state.platform_manager = pm
    app.dependency_overrides[get_current_user] = lambda: _User()
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/analysis",
            json={"session_id": "sess-real", "kind": "area"},
        )
    assert r.status_code == 404, r.text
    adapter.engine_analysis.assert_not_awaited()


# --- direct manager unit tests (no HTTP layer) ------------------------------- #


@pytest.mark.asyncio
async def test_manager_engine_analysis_unknown_platform_raises_valueerror():
    pm, _adapter = _real_manager_with_engine_game()
    with pytest.raises(ValueError):
        await pm.engine_analysis("not-golaxy", "sess-real", "area")


@pytest.mark.asyncio
async def test_manager_engine_analysis_delegates_kind_through():
    pm, adapter = _real_manager_with_engine_game()
    adapter.engine_analysis.return_value = _judge_result()
    result = await pm.engine_analysis("golaxy", "sess-real", "judge")
    assert result == _judge_result()
    adapter.engine_analysis.assert_awaited_once_with("golaxy-engine-1", "judge")
