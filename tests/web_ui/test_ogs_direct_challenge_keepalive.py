"""Direct live invitations follow the OGS web client's waiting protocol."""

import asyncio
import json
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.ogs.adapter import OGSAdapter
from katrain.web.platforms.ogs.realtime_client import OGSRealtimeClient


class FakeRealtime:
    def __init__(self):
        self.callbacks = defaultdict(list)
        self.frames = []
        self.game_connect = AsyncMock(side_effect=lambda game_id: self.frames.append(("game/connect", game_id)))
        self.game_disconnect = AsyncMock(side_effect=lambda game_id: self.frames.append(("game/disconnect", game_id)))
        self.challenge_keepalive = AsyncMock(
            side_effect=lambda challenge_id, game_id: self.frames.append(
                ("challenge/keepalive", challenge_id, game_id)
            )
        )
        self.disconnect = AsyncMock()

    def on(self, event, callback):
        self.callbacks[event].append(callback)

    def off(self, event, callback):
        self.callbacks[event].remove(callback)

    async def emit(self, event, data):
        for callback in list(self.callbacks[event]):
            await callback(data)


def waiting_adapter():
    adapter = OGSAdapter()
    rt = FakeRealtime()
    adapter._rt = rt
    adapter._rest = SimpleNamespace(
        challenge_player=AsyncMock(return_value=(4, 42)),
        decline_challenge=AsyncMock(), close=AsyncMock(),
    )
    adapter._challenge_keepalive_interval = 0.01
    return adapter, rt


@pytest.mark.asyncio
async def test_realtime_keepalive_has_exact_ogs_frame():
    rt = OGSRealtimeClient()
    rt._ws = SimpleNamespace(send=AsyncMock())
    await rt.challenge_keepalive(4, 42)
    rt._ws.send.assert_awaited_once_with(json.dumps([
        "challenge/keepalive", {"challenge_id": 4, "game_id": 42},
    ]))


@pytest.mark.asyncio
async def test_failed_disconnect_does_not_rejoin_expired_challenge_game():
    rt = OGSRealtimeClient()
    rt._connected_games.add(42)
    rt._ws = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("socket closed")))
    with pytest.raises(RuntimeError, match="socket closed"):
        await rt.game_disconnect(42)
    assert 42 not in rt._connected_games


@pytest.mark.asyncio
async def test_direct_challenge_waits_with_keepalive_then_stops_on_gamedata():
    adapter, rt = waiting_adapter()
    adapter._on_active_game = AsyncMock()
    assert await adapter.send_challenge("8", {"board_size": 19}) == "4"
    assert rt.frames[0] == ("game/connect", 42)
    await asyncio.sleep(0.025)
    assert ("challenge/keepalive", 4, 42) in rt.frames

    await rt.emit("game/42/gamedata", {"id": 42})
    assert rt.frames[-1] == ("game/disconnect", 42)
    assert not rt.callbacks["game/42/gamedata"]
    rt.challenge_keepalive.reset_mock()
    await asyncio.sleep(0.025)
    rt.challenge_keepalive.assert_not_awaited()
    adapter._on_active_game.assert_awaited_once_with({"id": 42})


@pytest.mark.asyncio
async def test_acceptance_does_not_disconnect_an_already_restored_game_stream():
    adapter, rt = waiting_adapter()
    adapter._on_active_game = AsyncMock()
    await adapter.send_challenge("8", {})
    adapter._game_handlers[42] = []  # active-game restoration subscribed first
    await rt.emit("game/42/gamedata", {"id": 42})
    assert ("game/disconnect", 42) not in rt.frames
    assert not adapter._pending_challenges
    adapter._on_active_game.assert_awaited_once_with({"id": 42})


@pytest.mark.asyncio
async def test_direct_challenge_rejection_and_cancel_clean_wait_state():
    adapter, rt = waiting_adapter()
    await adapter.send_challenge("8", {})
    assert adapter.pending_direct_challenge_id() == "4"
    await adapter._on_notification({"type": "gameOfferRejected", "game_id": 42})
    assert rt.frames[-1] == ("game/disconnect", 42)
    assert not adapter._pending_challenges
    assert adapter.pending_direct_challenge_id() is None

    await adapter.send_challenge("8", {})
    await adapter.decline_challenge("4")
    adapter._rest.decline_challenge.assert_awaited_once_with(4)
    assert rt.frames[-1] == ("game/disconnect", 42)
    assert not adapter._pending_challenges
    assert adapter.pending_direct_challenge_id() is None


@pytest.mark.asyncio
async def test_direct_challenge_disconnect_stops_keepalive():
    adapter, rt = waiting_adapter()
    await adapter.send_challenge("8", {})
    await adapter.disconnect()
    assert not adapter._pending_challenges
    assert rt.frames[-1] == ("game/disconnect", 42)
    rt.challenge_keepalive.reset_mock()
    await asyncio.sleep(0.025)
    rt.challenge_keepalive.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_challenge_subscription_failure_cancels_remote_offer():
    adapter, rt = waiting_adapter()
    rt.game_connect.side_effect = RuntimeError("socket closed")
    with pytest.raises(RuntimeError, match="socket closed"):
        await adapter.send_challenge("8", {})
    adapter._rest.decline_challenge.assert_awaited_once_with(4)
    assert not adapter._pending_challenges
    assert not rt.callbacks["game/42/gamedata"]


@pytest.mark.asyncio
async def test_direct_challenge_keepalive_failure_cleans_subscription():
    adapter, rt = waiting_adapter()
    rt.challenge_keepalive.side_effect = RuntimeError("socket closed")
    await adapter.send_challenge("8", {})
    await asyncio.sleep(0.025)
    assert not adapter._pending_challenges
    assert rt.frames[-1] == ("game/disconnect", 42)
