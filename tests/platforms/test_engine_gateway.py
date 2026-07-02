"""Engine-play gateway tests.

The single most important property here is the [human, then AI] local play order:
the gateway must apply the human's move to the local game tree FIRST, then the AI's
reply, and both ONLY after the adapter has already returned the AI move. Any other
order corrupts the game tree (this was the #1 blocking bug flagged in review).
"""

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.gateway import PlatformCommandGateway, PlatformMoveRejectedError
from katrain.web.platforms.golaxy.adapter import GolaxyEngineTerminal
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameContext, PlatformMove


class MockSession:
    def __init__(self, session_id="s"):
        self.session_id = session_id
        self.moves = []  # ordered list of coords played, e.g. (col, row)
        self.resigned = False
        self.katrain_calls = []  # ordered list of (command, kwargs)

    def katrain(self, command, coords=None, **kwargs):
        self.katrain_calls.append((command, {"coords": coords, **kwargs}))
        if command == "play":
            self.moves.append(coords)
        elif command == "resign":
            self.resigned = True


class MockSessionManager:
    def __init__(self):
        self.sessions = {}
        self.broadcasts = []

    def get_session(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = MockSession(session_id)
        return self.sessions[session_id]

    def broadcast_to_session(self, session_id, msg):
        self.broadcasts.append((session_id, msg))


class MockEngineAdapter:
    platform_name = "golaxy"
    supports_engine_play = True

    def __init__(self):
        self.submit_engine_move = AsyncMock()
        self.resign_engine_game = AsyncMock()


@pytest.fixture
def setup():
    sm = MockSessionManager()
    session = sm.get_session("s")  # pre-create so we can inspect its plays
    pm = PlatformManager(sm)
    adapter = MockEngineAdapter()
    pm._adapters["golaxy"] = adapter

    ctx = PlatformGameContext(
        session_id="s",
        platform="golaxy",
        remote_game_id="g",
        my_color="B",
        is_engine=True,
    )
    pm._active_games["g"] = ctx
    pm._session_to_game["s"] = "g"

    gateway = PlatformCommandGateway(pm, sm)
    return gateway, pm, sm, adapter, ctx, session


class TestEnginePlayMove:
    @pytest.mark.asyncio
    async def test_human_then_ai_order(self, setup):
        """Regression: human move applied locally BEFORE the AI reply, both after ACK."""
        gateway, pm, sm, adapter, ctx, session = setup
        adapter.submit_engine_move.return_value = PlatformMove(col=15, row=3, color="W", move_number=2, game_id="g")

        result = await gateway.play_move("s", 3, 3, user_id=1)

        # Human first (3,3) then AI (15,3), in that exact order.
        assert session.moves == [(3, 3), (15, 3)]

        # Adapter was asked for the AI reply with the human's coords.
        adapter.submit_engine_move.assert_awaited_once_with("g", 3, 3)

        # Broadcasts: a pending, then two confirmed with move_numbers 1 then 2.
        types = [msg["type"] for _, msg in sm.broadcasts]
        assert types[0] == "platform_move_pending"
        confirmed = [msg for _, msg in sm.broadcasts if msg["type"] == "platform_move_confirmed"]
        assert [m["move_number"] for m in confirmed] == [1, 2]
        assert (confirmed[0]["col"], confirmed[0]["row"]) == (3, 3)
        assert (confirmed[1]["col"], confirmed[1]["row"]) == (15, 3)

        assert ctx.pending_action is None
        assert ctx.last_confirmed_move == 2
        assert result == {"status": "ok", "ai_move": {"col": 15, "row": 3, "move_number": 2}}

    @pytest.mark.asyncio
    async def test_engine_failure_does_not_apply_human_move(self, setup):
        """On engine failure the human move must NOT be applied locally."""
        gateway, pm, sm, adapter, ctx, session = setup
        adapter.submit_engine_move.side_effect = Exception("boom")

        with pytest.raises(PlatformMoveRejectedError):
            await gateway.play_move("s", 3, 3, user_id=1)

        assert session.moves == []  # nothing applied
        assert ctx.pending_action is None
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "engine_error" in reasons

    @pytest.mark.asyncio
    async def test_engine_terminal_ends_game(self, setup):
        """AI pass/resign/special-coord -> GolaxyEngineTerminal -> game_ended, no local plays."""
        gateway, pm, sm, adapter, ctx, session = setup
        adapter.submit_engine_move.side_effect = GolaxyEngineTerminal("AI resigned")

        with pytest.raises(PlatformMoveRejectedError):
            await gateway.play_move("s", 3, 3, user_id=1)

        assert session.moves == []
        assert ctx.pending_action is None
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "game_ended" in reasons

    @pytest.mark.asyncio
    async def test_pass_rejected(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        with pytest.raises(PlatformMoveRejectedError, match="pass_not_supported"):
            await gateway.pass_move("s", user_id=1)
        # No local pass recorded.
        assert session.moves == []
        assert ("play", {"coords": None}) not in session.katrain_calls

    @pytest.mark.asyncio
    async def test_engine_resign(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        result = await gateway.resign("s", user_id=1)
        adapter.resign_engine_game.assert_awaited_once_with("g")
        assert session.resigned
        assert result == {"status": "ok"}
