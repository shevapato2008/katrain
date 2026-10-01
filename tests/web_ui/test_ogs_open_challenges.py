"""OGS public seek graph contract: only supported real-time games are offered."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.platforms.ogs.adapter import OGSAdapter
from katrain.web.platforms.ogs.realtime_client import OGSRealtimeClient
from katrain.web.platforms.manager import PlatformManager
from tests.web_ui._helpers import _create_user_and_login


# Anonymized 2026-09-30 seekgraph/global live entry. The paths and timing
# values were observed on the public WebSocket; IDs and username are replaced.
LIVE_SEEK = {
    "challenge_id": 123,
    "game_id": 789,
    "user_id": 456,
    "username": "anonymous",
    "rank": 26.25,
    "width": 19,
    "height": 19,
    "rengo": False,
    "invite_only": False,
    "private": False,
    "time_control": "byoyomi",
    "time_control_parameters": {
        "system": "byoyomi", "time_control": "byoyomi", "speed": "live",
        "main_time": 900, "period_time": 30, "periods": 5,
    },
    "rules": "japanese",
    "ranked": True,
    "handicap": 0,
    "komi": None,
}


def seek(**changes):
    value = deepcopy(LIVE_SEEK)
    value.update(changes)
    return value


@pytest.mark.asyncio
async def test_seek_graph_filters_unsupported_games_and_preserves_observed_rank():
    adapter = OGSAdapter()
    entries = [
        seek(challenge_id=1),
        seek(challenge_id=2, width=9, height=9),
        seek(challenge_id=3, width=13, height=13),
        seek(challenge_id=4, time_control_parameters={"system": "byoyomi", "speed": "correspondence"}),
        seek(challenge_id=5, rengo=True),
        seek(challenge_id=6, width=19, height=13),
        seek(challenge_id=7, width=25, height=25),
        seek(challenge_id=8, time_control_parameters={"system": "byoyomi"}),
        seek(challenge_id=9, rengo=None),
        seek(challenge_id=10, invite_only=True),
    ]

    await adapter._on_seekgraph(entries)
    challenges = await adapter.get_open_challenges()

    assert [ch.challenge_id for ch in challenges] == ["1", "2", "3"]
    assert [ch.board_size for ch in challenges] == [19, 9, 13]
    assert challenges[0].from_user.rank == "4k"
    assert challenges[0].from_user.rank_numeric == 26.25
    assert challenges[0].from_user.user_id == "456"


@pytest.mark.asyncio
async def test_seek_graph_empty_snapshot_is_ready_but_missing_snapshot_is_error():
    adapter = OGSAdapter()
    with pytest.raises(RuntimeError, match="seek graph"):
        await adapter.get_open_challenges()

    await adapter._on_seekgraph([])
    assert await adapter.get_open_challenges() == []

    await adapter._on_connection_lost_internal(None)
    with pytest.raises(RuntimeError, match="seek graph"):
        await adapter.get_open_challenges()


@pytest.mark.asyncio
async def test_first_small_snapshot_replaces_cache_and_incremental_delete_removes_entry():
    adapter = OGSAdapter()
    await adapter._on_seekgraph([seek(challenge_id=1), seek(challenge_id=2)])
    assert [ch.challenge_id for ch in await adapter.get_open_challenges()] == ["1", "2"]
    await adapter._on_seekgraph([{"challenge_id": 1, "delete": True}])
    assert [ch.challenge_id for ch in await adapter.get_open_challenges()] == ["2"]


@pytest.mark.asyncio
async def test_challenge_endpoint_reports_upstream_unavailable_instead_of_empty(app):
    headers, _, _ = await _create_user_and_login(app, "ogs-list")
    adapter = SimpleNamespace(is_connected=True, get_open_challenges=AsyncMock(side_effect=RuntimeError("seek graph unavailable")))
    app.state.platform_manager = SimpleNamespace(get_adapter=lambda platform: adapter)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/platforms/ogs/challenges", headers=headers)

    assert response.status_code == 502
    assert "challenges" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_normal_websocket_close_invalidates_seek_cache():
    adapter = OGSAdapter()
    client = OGSRealtimeClient()

    class ClosedSocket:
        def __aiter__(self):
            self.messages = iter([json.dumps(["seekgraph/global", [seek()]])])
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration

    client._ws = ClosedSocket()
    client._connected = True
    client.on("seekgraph/global", adapter._on_seekgraph)
    client.on("_connection_lost", adapter._on_connection_lost_internal)
    client._reconnect_loop = AsyncMock()

    await client._receive_loop()

    assert not client.is_connected
    with pytest.raises(RuntimeError, match="seek graph"):
        await adapter.get_open_challenges()
    if client._reconnect_task:
        await client._reconnect_task


@pytest.mark.asyncio
async def test_challenge_endpoint_uses_502_when_owned_ogs_connection_drops(app):
    headers, user_id, _ = await _create_user_and_login(app, "ogs-drop")
    adapter = SimpleNamespace(platform_name="ogs", is_connected=False, get_open_challenges=AsyncMock())
    manager = PlatformManager(app.state.session_manager)
    manager.register_adapter(adapter)
    manager._platform_user_ids["ogs"] = user_id
    app.state.platform_manager = manager

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/platforms/ogs/challenges", headers=headers)

    assert response.status_code == 502
    adapter.get_open_challenges.assert_not_awaited()
