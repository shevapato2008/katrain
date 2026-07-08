"""GET /{platform}/engine/items endpoint tests (remaining-道具 counts badges).

The endpoint calls adapter.fetch_item_counts() directly (account-level, like
engine/levels — not routed through the manager's session→game resolution).
Same FakeAdapter + FastAPI TestClient pattern as test_engine_analysis_endpoint.py.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.api.v1.endpoints.auth import get_current_user
from katrain.web.platforms.golaxy.engine_client import ItemCountsResult
from katrain.web.server import create_app


class _User:
    id = 1


class FakeAdapter:
    def __init__(self, is_connected=True, supports_engine_play=True, counts=None):
        self.is_connected = is_connected
        self.supports_engine_play = supports_engine_play
        self.fetch_item_counts = AsyncMock(
            return_value=counts if counts is not None else ItemCountsResult(area=396, options=398, variation=3)
        )


class FakeManager:
    def __init__(self, adapter=None):
        self._adapter = adapter

    def get_adapter(self, name):
        return self._adapter


def _build_app(manager):
    app = create_app(enable_engine=False)
    app.state.platform_manager = manager
    app.dependency_overrides[get_current_user] = lambda: _User()
    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_items_success_returns_counts():
    adapter = FakeAdapter()
    app = _build_app(FakeManager(adapter=adapter))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/items")
    assert r.status_code == 200, r.text
    assert r.json() == {"area": 396, "options": 398, "variation": 3}
    adapter.fetch_item_counts.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_items_null_counts_survive_roundtrip():
    """A missing/unknown count must serialize as JSON null, never 0."""
    adapter = FakeAdapter(counts=ItemCountsResult(area=5, options=None, variation=None))
    app = _build_app(FakeManager(adapter=adapter))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/items")
    assert r.status_code == 200, r.text
    assert r.json() == {"area": 5, "options": None, "variation": None}


@pytest.mark.asyncio
async def test_items_not_connected_400():
    adapter = FakeAdapter(is_connected=False)
    app = _build_app(FakeManager(adapter=adapter))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/items")
    assert r.status_code == 400, r.text
    adapter.fetch_item_counts.assert_not_awaited()


@pytest.mark.asyncio
async def test_items_unknown_platform_400():
    app = _build_app(FakeManager(adapter=None))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/items")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_items_unsupported_engine_play_400():
    adapter = FakeAdapter(supports_engine_play=False)
    app = _build_app(FakeManager(adapter=adapter))
    async with _client(app) as ac:
        r = await ac.get("/api/v1/platforms/golaxy/engine/items")
    assert r.status_code == 400, r.text
    adapter.fetch_item_counts.assert_not_awaited()
