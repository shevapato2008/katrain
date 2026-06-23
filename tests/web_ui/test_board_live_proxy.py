"""Tests for board-mode live match proxy (sbc-live-parity P1).

Covers the read-only `/api/v1/board/live/*` proxy that forwards to the upstream
live service via RemoteAPIClient in board mode:
- All read-only endpoints reachable (matches/featured/{id}/analysis/preload/upcoming/stats/translations)
- Route ordering: /matches/featured is NOT shadowed by /matches/{match_id}
- Status fidelity: upstream 4xx passes through (404), connection errors map to 502
- Param forwarding: move_number / lang
- Not in board mode → 503
"""

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.server import create_app


def _http_status_error(status_code: int, text: str = "") -> httpx.HTTPStatusError:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return httpx.HTTPStatusError(f"{status_code}", request=MagicMock(), response=resp)


@pytest.fixture
def board_app():
    """Board-mode app with a mocked RemoteAPIClient exposing the live read methods."""
    db_path = "test_board_live_proxy.db"
    os.environ["KATRAIN_DATABASE_PATH"] = db_path
    if os.path.exists(db_path):
        os.remove(db_path)

    app = create_app(enable_engine=False)

    client = MagicMock()
    client.get_live_matches = AsyncMock(return_value={"matches": [], "total": 0, "live_count": 0})
    client.get_live_match = AsyncMock(return_value={"id": "m1", "moves": ["B[pd]"], "sgf": "(;)"})
    client.get_live_featured = AsyncMock(return_value={"match": {"id": "feat1"}})
    client.get_live_match_analysis = AsyncMock(
        return_value={"match_id": "m1", "analyzed_moves": [0, 1], "analysis": {}}
    )
    client.preload_live_analysis = AsyncMock(
        return_value={"match_id": "m1", "analyzed_moves": [0], "total_moves": 1, "analysis": {}}
    )
    client.get_live_upcoming = AsyncMock(return_value={"matches": []})
    client.get_live_stats = AsyncMock(return_value={"live_count": 0, "finished_count": 0})
    client.get_live_translations = AsyncMock(return_value={"lang": "zh", "players": {}})
    app.state.remote_client = client

    yield app

    if os.path.exists(db_path):
        os.remove(db_path)


async def _get(app, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path)


@pytest.mark.asyncio
async def test_featured_not_shadowed_by_match_id(board_app):
    """GET /matches/featured must hit get_live_featured, NOT get_live_match('featured')."""
    resp = await _get(board_app, "/api/v1/board/live/matches/featured?lang=zh")
    assert resp.status_code == 200
    assert resp.json() == {"match": {"id": "feat1"}}
    board_app.state.remote_client.get_live_featured.assert_awaited_once_with(lang="zh")
    board_app.state.remote_client.get_live_match.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_detail_proxied(board_app):
    resp = await _get(board_app, "/api/v1/board/live/matches/m1")
    assert resp.status_code == 200
    assert resp.json()["moves"] == ["B[pd]"]
    board_app.state.remote_client.get_live_match.assert_awaited_once_with("m1")


@pytest.mark.asyncio
async def test_analysis_forwards_move_number(board_app):
    resp = await _get(board_app, "/api/v1/board/live/matches/m1/analysis?move_number=5")
    assert resp.status_code == 200
    board_app.state.remote_client.get_live_match_analysis.assert_awaited_once_with("m1", move_number=5)


@pytest.mark.asyncio
async def test_preload_upcoming_stats_translations_reachable(board_app):
    assert (await _get(board_app, "/api/v1/board/live/matches/m1/analysis/preload")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/live/upcoming?limit=5&lang=zh")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/live/stats")).status_code == 200
    assert (await _get(board_app, "/api/v1/board/live/translations?lang=zh")).status_code == 200
    board_app.state.remote_client.get_live_upcoming.assert_awaited_once_with(limit=5, lang="zh")
    board_app.state.remote_client.get_live_translations.assert_awaited_once_with("zh")


@pytest.mark.asyncio
async def test_upstream_404_passes_through(board_app):
    """Missing match upstream → 404 to the kiosk, NOT 502."""
    board_app.state.remote_client.get_live_match.side_effect = _http_status_error(404, "Match not found")
    resp = await _get(board_app, "/api/v1/board/live/matches/__nope__")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upstream_unreachable_maps_502(board_app):
    """Connection error upstream → 502 (distinguishable from 404)."""
    board_app.state.remote_client.get_live_match.side_effect = httpx.ConnectError("refused")
    resp = await _get(board_app, "/api/v1/board/live/matches/m1")
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_not_board_mode_503():
    """No remote_client on app.state → 503 Not in board mode."""
    os.environ["KATRAIN_DATABASE_PATH"] = "test_board_live_proxy_nb.db"
    app = create_app(enable_engine=False)
    # Ensure no remote_client is present.
    if hasattr(app.state, "remote_client"):
        delattr(app.state, "remote_client")
    resp = await _get(app, "/api/v1/board/live/matches")
    assert resp.status_code == 503
