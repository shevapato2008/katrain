"""Engine-play gateway tests.

The single most important property here is the [human, then AI] local play order:
the gateway must apply the human's move to the local game tree FIRST, then the AI's
reply, and both ONLY after the adapter has already returned the AI move. Any other
order corrupts the game tree (this was the #1 blocking bug flagged in review).

Task 4 (B1/B2/D5/D7 — commit protocol hardening) adds:
  - B1: local pre-validation (occupied/ko/suicide) BEFORE the tunnel call.
  - B2: a position token recorded at pre-validation time, re-checked atomically
    right before the [human, AI] apply — if the tree moved out from under the
    tunnel wait (a guard bypass), both moves are discarded instead of mis-applied.
  - D7: on a GolaxyEngineTerminal (AI pass/resign/special coord), the human's move
    IS played locally (it's real) before the game_ended broadcast.
  - PlatformMoveRejectedError.reason: a stable machine-readable code.
"""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from katrain.core.game import Game
from katrain.core.sgf_parser import Move
from katrain.web.platforms.gateway import PlatformCommandGateway, PlatformMoveRejectedError
from katrain.web.platforms.golaxy.adapter import GolaxyEngineTerminal
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import PlatformGameContext, PlatformMove


class MockNode:
    """Bare stand-in for a GameNode — only enough surface for
    PlatformManager.rebuild_engine_context's traversal (nodes_from_root/.moves).
    These gateway tests don't exercise the rebuild feature itself (that's
    test_engine_rebuild.py); an empty path here just needs to not raise."""

    def __init__(self):
        self.moves = []

    @property
    def nodes_from_root(self):
        return [self]


class MockGame:
    """Minimal stand-in for katrain.core.game.Game — just enough surface for the
    gateway's pre-validation (_check_move_legal) and position-token logic.

    Board starts empty (19x19). `current_node` starts as a MockNode (so the
    rebuild-history call added in B3/G4 has a traversable, empty path); tests
    simulating an interleaving tree mutation (e.g. undo racing the tunnel wait)
    swap it for a fresh sentinel — only its IDENTITY matters there (the
    gateway's position token is `id(current_node)`).

    `_validate_move_and_update_chains` is the REAL unbound method from
    katrain.core.game.Game — reused as-is (not reimplemented) so pre-validation
    tests exercise the actual Go chain/ko/suicide rules, matching production
    fidelity, without needing a real GameNode tree.
    """

    _validate_move_and_update_chains = Game._validate_move_and_update_chains

    def __init__(self, size=19):
        self.board_size = (size, size)
        self.board = [[-1] * size for _ in range(size)]
        self.chains = []
        self.last_capture = []
        self.prisoners = []
        self.current_node = MockNode()
        self.rules = "japanese"  # read (before the length check) by the real suicide-rule branch


class MockKatrain:
    """Callable stand-in for WebKaTrain: `session.katrain(cmd, ...)` dispatches
    commands (as before), while `session.katrain.game` / `.next_player_info` give
    the gateway's pre-validation/position-token logic the attributes it reads on
    the real object.
    """

    def __init__(self, session):
        self._session = session
        self.game = MockGame()
        self.next_player_info = SimpleNamespace(player="B")

    def __call__(self, command, coords=None, **kwargs):
        self._session.katrain_calls.append((command, {"coords": coords, **kwargs}))
        if command == "play":
            self._session.moves.append(coords)
        elif command == "resign":
            self._session.resigned = True


class MockSession:
    def __init__(self, session_id="s"):
        self.session_id = session_id
        self.moves = []  # ordered list of coords played, e.g. (col, row)
        self.resigned = False
        self.katrain_calls = []  # ordered list of (command, kwargs)
        self.lock = threading.Lock()
        self.katrain = MockKatrain(self)


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
        self.rebuild_engine_moves = MagicMock()  # called by PlatformManager.rebuild_engine_context


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

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.play_move("s", 3, 3, user_id=1)

        assert session.moves == []  # nothing applied
        assert ctx.pending_action is None
        assert exc_info.value.reason == "engine_error"
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "engine_error" in reasons

    @pytest.mark.asyncio
    async def test_engine_terminal_ends_game(self, setup):
        """D7: AI pass/resign/special-coord -> GolaxyEngineTerminal -> the human's
        move IS played locally FIRST (it's real — the adapter already committed it
        before raising), THEN the game_ended rejection is broadcast. Only the AI's
        (nonexistent) reply is naturally absent; there is no half-committed pair."""
        gateway, pm, sm, adapter, ctx, session = setup
        adapter.submit_engine_move.side_effect = GolaxyEngineTerminal("AI resigned")

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.play_move("s", 3, 3, user_id=1)

        assert session.moves == [(3, 3)]  # human's final move IS recorded (D7)
        assert ctx.pending_action is None
        assert exc_info.value.reason == "game_ended"
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
    async def test_local_play_failure_after_ai_move_clears_pending(self, setup):
        """FIX 2 regression: if a local play raises AFTER the adapter already
        returned the AI move, pending must still be cleared (not wedged in
        "pending" forever) and the exception must still propagate."""
        gateway, pm, sm, adapter, ctx, session = setup
        adapter.submit_engine_move.return_value = PlatformMove(col=15, row=3, color="W", move_number=2, game_id="g")

        original_katrain = session.katrain
        call_count = {"n": 0}

        class FlakyKatrain:
            """Wraps the real MockKatrain: forwards attribute access (.game,
            .next_player_info — read by the gateway's pre-validation/position-token
            logic) unchanged, but injects a failure into the SECOND `play` call."""

            def __getattr__(self, name):
                return getattr(original_katrain, name)

            def __call__(self, command, coords=None, **kwargs):
                if command == "play":
                    call_count["n"] += 1
                    if call_count["n"] == 2:
                        raise RuntimeError("boom")
                return original_katrain(command, coords=coords, **kwargs)

        session.katrain = FlakyKatrain()

        with pytest.raises(RuntimeError, match="boom"):
            await gateway.play_move("s", 3, 3, user_id=1)

        assert ctx.pending_action is None

    @pytest.mark.asyncio
    async def test_engine_resign(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        result = await gateway.resign("s", user_id=1)
        adapter.resign_engine_game.assert_awaited_once_with("g")
        assert session.resigned
        assert result == {"status": "ok"}


class TestPreValidation:
    """B1: local legality pre-check runs BEFORE the tunnel call. An illegal move
    (occupied/ko/suicide) never reaches the adapter, wastes no tunnel round trip,
    and leaves ctx.moves/session.moves untouched."""

    @pytest.mark.asyncio
    async def test_occupied_point_rejected_locally_no_tunnel_call(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        # Mark (col=3, row=3) as already occupied by a black stone.
        game = session.katrain.game
        game.board[3][3] = 0  # board is [row][col]
        game.chains = [[Move(coords=(3, 3), player="B")]]

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.play_move("s", 3, 3, user_id=1)

        assert exc_info.value.reason == "illegal_move"
        adapter.submit_engine_move.assert_not_awaited()
        assert session.moves == []
        assert ctx.pending_action is None  # never even entered "pending"
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "illegal_move" in reasons

    @pytest.mark.asyncio
    async def test_suicide_move_rejected_locally_no_tunnel_call(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        game = session.katrain.game
        # Corner (0, 0) has exactly two neighbours: (0, 1) and (1, 0). Occupy both
        # with White (separate chains, each with other liberties elsewhere on the
        # otherwise-empty board) so a lone Black stone at (0, 0) has zero liberties
        # and captures nothing -> single-stone suicide.
        game.chains = [[Move(coords=(0, 1), player="W")], [Move(coords=(1, 0), player="W")]]
        game.board[1][0] = 0  # (col=0, row=1) -> chain 0
        game.board[0][1] = 1  # (col=1, row=0) -> chain 1

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await gateway.play_move("s", 0, 0, user_id=1)

        assert exc_info.value.reason == "illegal_move"
        adapter.submit_engine_move.assert_not_awaited()
        assert session.moves == []
        assert ctx.pending_action is None


class TestAtomicPositionAssert:
    """B2: a controlled interleaving reproduces the exact race the review flagged —
    something mutates the tree WHILE the genmove tunnel is in flight (up to ~180s).
    When the AI's reply finally arrives, the position token no longer matches the
    node it was recorded against, so BOTH moves are discarded (never half-committed,
    never misapplied to the wrong node)."""

    @pytest.mark.asyncio
    async def test_position_changed_during_tunnel_wait_discards_both_moves(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup

        release = asyncio.Event()
        ai_result = PlatformMove(col=15, row=3, color="W", move_number=2, game_id="g")

        async def slow_genmove(game_id, col, row):
            await release.wait()
            return ai_result

        adapter.submit_engine_move.side_effect = slow_genmove

        task = asyncio.create_task(gateway.play_move("s", 3, 3, user_id=1))
        # Let the coroutine run past pre-validation/position-token capture and into
        # the tunnel await (both synchronous, no intermediate suspension point).
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Simulate a tree mutation that bypassed the (Task 4) pending guard — e.g. a
        # stale undo/nav request that raced the 409 check.
        session.katrain.game.current_node = object()

        release.set()

        with pytest.raises(PlatformMoveRejectedError) as exc_info:
            await task

        assert exc_info.value.reason == "position_changed"
        assert session.moves == []  # neither move landed — no half-commit, no mis-apply
        assert ctx.pending_action is None
        reasons = [msg.get("reason") for _, msg in sm.broadcasts if msg["type"] == "platform_move_rejected"]
        assert "position_changed" in reasons


class TestGuardQueries:
    """gateway.is_engine_move_pending / is_engine_game — the predicates server.py's
    undo/redo/nav/ai-move guards call into."""

    def test_is_engine_move_pending_reflects_ctx_pending(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        assert gateway.is_engine_move_pending("s") is False
        ctx.set_pending("move")
        assert gateway.is_engine_move_pending("s") is True
        ctx.clear_pending()
        assert gateway.is_engine_move_pending("s") is False

    def test_is_engine_game_true_regardless_of_pending(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        assert gateway.is_engine_game("s") is True
        ctx.set_pending("move")
        assert gateway.is_engine_game("s") is True

    def test_non_engine_non_platform_session_unaffected(self):
        sm = MockSessionManager()
        pm = PlatformManager(sm)
        gateway = PlatformCommandGateway(pm, sm)
        assert gateway.is_engine_move_pending("no-such-session") is False
        assert gateway.is_engine_game("no-such-session") is False

    def test_get_game_id_returns_remote_game_id_for_engine_session(self, setup):
        gateway, pm, sm, adapter, ctx, session = setup
        assert gateway.get_game_id("s") == ctx.remote_game_id

    def test_get_game_id_none_for_unknown_session(self):
        sm = MockSessionManager()
        pm = PlatformManager(sm)
        gateway = PlatformCommandGateway(pm, sm)
        assert gateway.get_game_id("no-such-session") is None
