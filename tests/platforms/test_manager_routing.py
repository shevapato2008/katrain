"""PlatformManager._on_opponent_move routing tests: direct game_id lookup, no active-games scan.

Anti-cross-contamination: with multiple concurrent PLAYING contexts, an opponent move
tagged with a specific game_id must land ONLY in that game's session.
"""

from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import GamePhase, PlatformGameContext, PlatformMove


class MockSession:
    def __init__(self):
        self.moves = []
        self.katrain_calls = []

    def katrain(self, command, coords=None):
        self.katrain_calls.append((command, coords))
        if command == "play":
            self.moves.append(coords)


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


def make_manager():
    sm = MockSessionManager()
    pm = PlatformManager(sm)
    return pm, sm


async def test_direct_routing_two_concurrent_contexts_no_cross_contamination():
    pm, sm = make_manager()
    ctx_a = PlatformGameContext(session_id="sA", platform="mock", remote_game_id="game-A")
    ctx_b = PlatformGameContext(session_id="sB", platform="mock", remote_game_id="game-B")
    pm._active_games["game-A"] = ctx_a
    pm._active_games["game-B"] = ctx_b

    await pm._on_opponent_move(PlatformMove(col=3, row=3, color="W", move_number=1, game_id="game-B"))

    session_b = sm.get_session("sB")
    session_a = sm.get_session("sA")
    assert session_b.moves == [(3, 3)]
    assert session_a.moves == []


async def test_unknown_game_id_dropped():
    pm, sm = make_manager()
    ctx_a = PlatformGameContext(session_id="sA", platform="mock", remote_game_id="game-A")
    pm._active_games["game-A"] = ctx_a

    await pm._on_opponent_move(PlatformMove(col=3, row=3, color="W", move_number=1, game_id="nope"))

    assert "sA" not in sm.sessions or sm.sessions["sA"].moves == []
    assert sm.broadcasts == []


async def test_non_playing_context_dropped():
    pm, sm = make_manager()
    ctx_a = PlatformGameContext(
        session_id="sA", platform="mock", remote_game_id="game-A", game_phase=GamePhase.FINISHED
    )
    pm._active_games["game-A"] = ctx_a

    await pm._on_opponent_move(PlatformMove(col=3, row=3, color="W", move_number=1, game_id="game-A"))

    assert "sA" not in sm.sessions or sm.sessions["sA"].moves == []
    assert sm.broadcasts == []


async def test_last_confirmed_move_and_broadcast_on_success():
    pm, sm = make_manager()
    ctx_a = PlatformGameContext(session_id="sA", platform="mock", remote_game_id="game-A")
    pm._active_games["game-A"] = ctx_a

    await pm._on_opponent_move(PlatformMove(col=5, row=6, color="B", move_number=7, game_id="game-A"))

    assert ctx_a.last_confirmed_move == 7
    assert len(sm.broadcasts) == 1
    session_id, msg = sm.broadcasts[0]
    assert session_id == "sA"
    assert msg == {"type": "platform_move_confirmed", "col": 5, "row": 6, "move_number": 7}
