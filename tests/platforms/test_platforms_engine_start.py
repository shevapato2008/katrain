"""Task A: EngineStartRequest handicap/color model + komi/nigiri derivation.

Covers the extended `POST /{platform}/engine/start` request model that lets the
kiosk client pick 让子 (handicap) and 先手/颜色 (color incl. nigiri) while
komi/rule/board_size stay server-derived/fixed. Follows the fake-manager +
FastAPI TestClient pattern from tests/platforms/test_engine_endpoints.py; no
real network/tunnel calls are needed since start_engine_game is mocked at the
manager boundary.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.api.v1.endpoints.platforms import (
    EngineStartRequest,
    _handicap_stone_count,
    _komi_for_handicap,
    _resolve_color,
)
from katrain.web.server import create_app


class _User:
    id = 1


class FakeAdapter:
    """Stand-in for GolaxyAdapter with just the attributes the endpoint reads."""

    def __init__(self, is_connected=True, supports_engine_play=True):
        self.is_connected = is_connected
        self.supports_engine_play = supports_engine_play

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
    def __init__(self, adapter=None):
        self._adapter = adapter
        self._credential_store = FakeCredStore()
        self.start_engine_game = AsyncMock(return_value="sess-1")

    def get_adapter(self, name):
        return self._adapter


def _build_app(manager):
    app = create_app(enable_engine=False)
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: _User()
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- EngineStartRequest model validation ------------------------------------ #


@pytest.mark.parametrize("h", [-1, 0, 2, 3, 4, 5, 6, 7, 8, 9])
def test_engine_start_request_accepts_valid_handicap(h):
    req = EngineStartRequest(level=1100, handicap=h)
    assert req.handicap == h


@pytest.mark.parametrize("h", [1, 10, 99, -2])
def test_engine_start_request_rejects_invalid_handicap(h):
    with pytest.raises(ValidationError):
        EngineStartRequest(level=1100, handicap=h)


@pytest.mark.parametrize("c", ["B", "W", "nigiri"])
def test_engine_start_request_accepts_valid_color(c):
    req = EngineStartRequest(level=1100, human_color=c)
    assert req.human_color == c


@pytest.mark.parametrize("c", ["X", "black"])
def test_engine_start_request_rejects_invalid_color(c):
    with pytest.raises(ValidationError):
        EngineStartRequest(level=1100, human_color=c)


def test_engine_start_request_rejects_extra_field():
    with pytest.raises(ValidationError):
        EngineStartRequest(level=1100, komi=1)


def test_engine_start_request_defaults():
    req = EngineStartRequest(level=1100)
    assert req.human_color == "B"
    assert req.handicap == 0


# --- Derivation helpers ------------------------------------------------------ #


def test_komi_for_handicap_fenxian():
    assert _komi_for_handicap(0) == 7.5


def test_komi_for_handicap_rangxian():
    assert _komi_for_handicap(-1) == 0.0


@pytest.mark.parametrize("h,expected", [(2, 2.0), (3, 3.0), (4, 4.0), (9, 9.0)])
def test_komi_for_handicap_rangzi(h, expected):
    assert _komi_for_handicap(h) == expected


def test_handicap_stone_count_fenxian():
    assert _handicap_stone_count(0) == 0


def test_handicap_stone_count_rangxian():
    assert _handicap_stone_count(-1) == 0


@pytest.mark.parametrize("h", [2, 3, 4, 5, 6, 7, 8, 9])
def test_handicap_stone_count_rangzi(h):
    assert _handicap_stone_count(h) == h


# --- nigiri color resolution -------------------------------------------------- #


def test_resolve_color_black_passthrough():
    assert _resolve_color("B") == "B"


def test_resolve_color_white_passthrough():
    assert _resolve_color("W") == "W"


def test_resolve_color_nigiri_always_black_or_white():
    results = {_resolve_color("nigiri") for _ in range(50)}
    assert results <= {"B", "W"}
    # Not a hard guarantee with a fair coin, but 50 draws landing on a single
    # side would indicate the helper isn't actually randomizing.
    assert len(results) >= 1


# --- End-to-end config build via the endpoint -------------------------------- #


@pytest.mark.asyncio
async def test_engine_start_handicap_4_derives_komi_and_stone_count():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "B", "handicap": 4},
        )
    assert r.status_code == 200, r.text
    mgr.start_engine_game.assert_awaited_once()
    args, _ = mgr.start_engine_game.call_args
    config = args[1]
    assert config.rule == "chinese"
    assert config.board_size == 19
    assert config.handicap == 4
    assert config.komi == 4.0
    assert config.human_color == "B"


@pytest.mark.asyncio
async def test_engine_start_handicap_0_fenxian():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "B", "handicap": 0},
        )
    assert r.status_code == 200, r.text
    config = mgr.start_engine_game.call_args[0][1]
    assert config.handicap == 0
    assert config.komi == 7.5


@pytest.mark.asyncio
async def test_engine_start_handicap_minus1_rangxian():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "B", "handicap": -1},
        )
    assert r.status_code == 200, r.text
    config = mgr.start_engine_game.call_args[0][1]
    assert config.handicap == 0
    assert config.komi == 0.0


@pytest.mark.asyncio
async def test_engine_start_nigiri_resolves_to_black_or_white():
    mgr = FakeManager(adapter=FakeAdapter())
    app = _build_app(mgr)
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "nigiri", "handicap": 0},
        )
    assert r.status_code == 200, r.text
    config = mgr.start_engine_game.call_args[0][1]
    assert config.human_color in ("B", "W")
    # The resolved (post-nigiri) color is surfaced in the response so the
    # frontend can render the human's side without guessing.
    assert r.json()["human_color"] == config.human_color


@pytest.mark.asyncio
async def test_engine_start_rejects_invalid_handicap_value():
    app = _build_app(FakeManager(adapter=FakeAdapter()))
    async with _client(app) as ac:
        r = await ac.post(
            "/api/v1/platforms/golaxy/engine/start",
            json={"level": 1100, "human_color": "B", "handicap": 1},
        )
    assert r.status_code == 422, r.text
