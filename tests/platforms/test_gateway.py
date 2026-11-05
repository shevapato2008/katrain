"""Gateway state machine tests: pending -> confirmed, pending -> rejected, timeout."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from katrain.web.platforms.gateway import PlatformCommandGateway, PlatformMoveRejectedError
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import GamePhase, PlatformGameContext


class MockAdapter:
    platform_name = "mock"
    supports_scoring = False

    async def submit_move(self, game_id, col, row):
        return True

    async def submit_pass(self, game_id):
        return True

    async def resign(self, game_id):
        pass


class MockSession:
    def __init__(self):
        self.moves = []
        self.resigned = False
        self.katrain_calls = []

    def katrain(self, command, coords=None):
        self.katrain_calls.append((command, coords))
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
            self.sessions[session_id] = MockSession()
        return self.sessions[session_id]

    def broadcast_to_session(self, session_id, msg):
        self.broadcasts.append((session_id, msg))


@pytest.fixture
def setup():
    sm = MockSessionManager()
    pm = PlatformManager(sm)
    adapter = MockAdapter()
    pm._adapters["mock"] = adapter

    ctx = PlatformGameContext(
        session_id="session-1",
        platform="mock",
        remote_game_id="game-42",
        my_color="B",
    )
    pm._active_games["game-42"] = ctx
    pm._session_to_game["session-1"] = "game-42"

    gateway = PlatformCommandGateway(pm, sm)
    return gateway, pm, sm, adapter, ctx


class TestGatewayPlayMove:
    @pytest.mark.asyncio
    async def test_platform_move_confirmed(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        result = await gateway.play_move("session-1", 3, 3, user_id=1)
        assert result == {"status": "ok"}
        assert ctx.last_confirmed_move == 1
        assert ctx.pending_action is None
        # Should have broadcast pending then confirmed
        types = [msg["type"] for _, msg in sm.broadcasts]
        assert "platform_move_pending" in types
        assert "platform_move_confirmed" in types

    @pytest.mark.asyncio
    async def test_platform_move_rejected(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        adapter.submit_move = AsyncMock(return_value=False)
        with pytest.raises(PlatformMoveRejectedError):
            await gateway.play_move("session-1", 3, 3, user_id=1)
        assert ctx.pending_action is None
        types = [msg["type"] for _, msg in sm.broadcasts]
        assert "platform_move_rejected" in types

    @pytest.mark.asyncio
    async def test_platform_move_exception(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        adapter.submit_move = AsyncMock(side_effect=ConnectionError("network"))
        with pytest.raises(PlatformMoveRejectedError, match="network"):
            await gateway.play_move("session-1", 3, 3, user_id=1)
        assert ctx.pending_action is None

    @pytest.mark.asyncio
    async def test_reject_while_pending(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        ctx.set_pending("move")
        with pytest.raises(PlatformMoveRejectedError, match="pending"):
            await gateway.play_move("session-1", 5, 5, user_id=1)

    @pytest.mark.asyncio
    async def test_local_game_passthrough(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        # For a non-platform session, pass through locally
        result = gateway._local_play("session-1", 3, 3)
        assert result == {"status": "ok"}
        session = sm.get_session("session-1")
        assert (3, 3) in session.moves


class TestGatewayPass:
    @pytest.mark.asyncio
    async def test_pass_confirmed(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        result = await gateway.pass_move("session-1", user_id=1)
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_pass_rejected(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        adapter.submit_pass = AsyncMock(return_value=False)
        with pytest.raises(PlatformMoveRejectedError):
            await gateway.pass_move("session-1", user_id=1)


class TestGatewayResign:
    @pytest.mark.asyncio
    async def test_resign_success(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        result = await gateway.resign("session-1", user_id=1)
        assert result == {"status": "ok"}
        session = sm.get_session("session-1")
        assert session.resigned

    @pytest.mark.asyncio
    async def test_resign_failure(self, setup):
        gateway, pm, sm, adapter, ctx = setup
        adapter.resign = AsyncMock(side_effect=ConnectionError("offline"))
        with pytest.raises(PlatformMoveRejectedError, match="offline"):
            await gateway.resign("session-1", user_id=1)


class TestGameContext:
    def test_pending_state(self):
        ctx = PlatformGameContext(session_id="s", platform="p", remote_game_id="g")
        assert ctx.is_pending is False
        ctx.set_pending("move")
        assert ctx.is_pending is True
        assert ctx.pending_action == "move"
        ctx.clear_pending()
        assert ctx.is_pending is False

    def test_recover_from_snapshot(self):
        ctx = PlatformGameContext(session_id="s", platform="p", remote_game_id="g")
        ctx.set_pending("move")
        ctx.needs_resync = True
        ctx.recover_from_snapshot({"phase": "playing", "move_number": 42})
        assert ctx.game_phase == GamePhase.PLAYING
        assert ctx.last_confirmed_move == 42
        assert ctx.is_pending is False
        assert ctx.needs_resync is False


def bound_vision_gateway(platform="mock"):
    """Real Go rules, service, gateway and manager; only the network adapter is fake."""
    import threading
    from types import SimpleNamespace
    from katrain.core.game import BaseGame
    from katrain.core.sgf_parser import Move
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService
    from katrain.web.core.physical_play import PhysicalPlayConfig
    from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
    from katrain.web.platforms.models import PlatformGameSnapshot

    class Core:
        def __init__(self):
            self.ai_ladder_commit_lock = threading.RLock()
            self.update_state_callback = None
            self.game = BaseGame(self, game_properties={"SZ": 19, "RU": "japanese"}, bypass_config=True)

        def config(self, *_):
            return None

        def get_state(self):
            return {
                "game_id": self.game.game_id,
                "current_node_id": id(self.game.current_node),
                "board_size": [19, 19],
                "player_to_move": self.game.current_node.next_player,
                "end_result": self.game.end_result,
                "stones": [[m.player, list(m.coords), None, i + 1] for i, m in enumerate(self.game.stones)],
            }

        def next_player_to_move(self):
            return self.game.current_node.next_player

        @property
        def next_player_info(self):
            return SimpleNamespace(player=self.game.current_node.next_player)

        def __call__(self, command, coords=None, **kwargs):
            with self.ai_ladder_commit_lock:
                if command == "play":
                    self.game.play(Move(coords=coords, player=self.game.current_node.next_player))
                elif command == "end_by_resignation":
                    self.game.current_node.end_state = f"{kwargs['winner']}+R"
                else:
                    raise AssertionError(command)
            if self.update_state_callback:
                self.update_state_callback(self.get_state())

    class Adapter:
        is_connected = True

        def __init__(self):
            self.sent = []
            self.snapshot = PlatformGameSnapshot("g", 19, (), (), GamePhase.PLAYING)

        async def submit_move(self, game_id, col, row):
            self.sent.append((game_id, col, row))
            if platform == "ogs":
                raise ConnectionError("uncertain transport")
            return True

        async def fetch_game_snapshot(self, _):
            return self.snapshot

        def get_game_snapshot(self, _):
            return self.snapshot

    session = SimpleNamespace(session_id="s", katrain=Core(), lock=threading.RLock(), user_id=7)
    session.last_state = session.katrain.get_state()
    session.katrain.update_state_callback = lambda state: setattr(session, "last_state", state)
    manager = SimpleNamespace(get_session=lambda sid: session, broadcast_to_session=lambda *_: None)
    pm = PlatformManager(manager)
    adapter = Adapter()
    pm._adapters[platform] = adapter
    ctx = PlatformGameContext(session_id="s", platform=platform, remote_game_id="g", my_color="B")
    pm._active_games["g"] = ctx
    pm._session_to_game["s"] = "g"
    gateway = PlatformCommandGateway(pm, manager)
    vision = VisionService(VisionServiceConfig())
    vision._worker = MagicMock()
    vision.get_board_observation = lambda: (None, 0)
    vision.bind_session("s", session=session)
    orch = PhysicalPlayOrchestrator(config=PhysicalPlayConfig(), led=None, vision=vision, session_manager=manager)
    orch.on_bind("s", session)
    app = SimpleNamespace(state=SimpleNamespace(session_manager=manager, platform_gateway=gateway, physical_play=orch))
    return app, session, vision, orch, pm, adapter, ctx


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["mock", "ogs"])
@pytest.mark.parametrize("callback_delivered", [False, True])
async def test_real_gateway_releases_vision_ownership_without_overwriting_platform_pending(
    platform, callback_delivered
):
    import logging
    from katrain.vision.ipc import CommandType, ConfirmedMove
    from katrain.web.server import _handle_confirmed_move

    app, session, vision, orch, pm, adapter, ctx = bound_vision_gateway(platform)
    initial_revision = vision.expected_revision
    if not callback_delivered:
        session.katrain.update_state_callback = None  # the real broadcast can be throttled
    move = ConfirmedMove(3, 3, 1, 9, vision.binding_epoch, initial_revision)
    await _handle_confirmed_move(app, vision, "s", move, logging.getLogger(__name__))
    commands = [call.args[0] for call in vision._worker.send_command.call_args_list]
    assert commands[-1].action == CommandType.RELEASE_CONFIRMED_MOVE
    assert commands[-1].data == {"token": move.token}
    assert adapter.sent == [("g", 3, 15)]
    if platform == "mock":
        assert session.katrain.game.current_node.depth == 1
        assert vision.expected_revision == initial_revision + 1
        assert commands[-2].action == CommandType.SET_EXPECTED_BOARD
    else:
        assert session.katrain.game.current_node.depth == 0
        assert ctx.is_pending and ctx.needs_resync
        assert vision.expected_revision == initial_revision
        # The next attempt is refused as the previous platform action is still pending.
        pending = ctx.pending_action
        second = ConfirmedMove(3, 3, 1, 10, vision.binding_epoch, initial_revision)
        await _handle_confirmed_move(app, vision, "s", second, logging.getLogger(__name__))
        assert ctx.pending_action == pending and ctx.needs_resync
        assert adapter.sent == [("g", 3, 15)]
        assert vision._worker.send_command.call_args.args[0].data == {"token": second.token}
    await orch.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [False, True])
async def test_real_engine_gateway_flushes_committed_turn_or_terminal_before_release(terminal):
    import logging
    from katrain.vision.ipc import CommandType, ConfirmedMove
    from katrain.web.platforms.models import PlatformMove, PlatformResign
    from katrain.web.server import _handle_confirmed_move

    app, session, vision, orch, pm, adapter, ctx = bound_vision_gateway()
    ctx.is_engine = True
    adapter.rebuild_engine_moves = MagicMock()
    adapter.discard_engine_game = MagicMock()
    adapter.submit_engine_move = AsyncMock(
        return_value=(PlatformResign("W", "B", 1, "g") if terminal else PlatformMove(4, 15, "W", 2, "g"))
    )
    session.katrain.update_state_callback = None
    move = ConfirmedMove(3, 3, 1, 9, vision.binding_epoch, vision.expected_revision)
    await _handle_confirmed_move(app, vision, "s", move, logging.getLogger(__name__))
    commands = [call.args[0] for call in vision._worker.send_command.call_args_list]
    assert commands[-1].action == CommandType.RELEASE_CONFIRMED_MOVE
    expected = [cmd for cmd in commands if cmd.action == CommandType.SET_EXPECTED_BOARD][-1]
    assert expected.data["board"][3][3] == 1
    assert session.katrain.game.current_node.depth == (1 if terminal else 2)
    if terminal:
        assert session.katrain.game.end_result == "B+R"
        assert orch.PAUSE_REASON_GAME_OVER in orch._pause_reasons
    else:
        assert expected.data["board"][3][4] == 2
    await orch.shutdown()
