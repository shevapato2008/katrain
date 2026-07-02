"""Manager.start_engine_game tests.

Verifies the manager creates + configures the local KaTrain session (via edit_game,
preserving player names), registers an is_engine context, and plays the AI's opening
move locally only when the human is White.
"""

from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.golaxy.adapter import EngineGameStart
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import OnlineUser, PlatformGameSession, PlatformMove, TimeControl


class MockSession:
    def __init__(self, session_id="local-session-1"):
        self.session_id = session_id
        self.moves = []
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
        self.session = MockSession()
        self.create_calls = []
        self.broadcasts = []

    def create_multiplayer_session(self, player_b_id, player_w_id, b_name, w_name):
        self.create_calls.append(
            {"player_b_id": player_b_id, "player_w_id": player_w_id, "b_name": b_name, "w_name": w_name}
        )
        return self.session

    def broadcast_to_session(self, session_id, msg):
        self.broadcasts.append((session_id, msg))


class MockEngineAdapter:
    platform_name = "golaxy"
    supports_engine_play = True

    def __init__(self):
        self.start_engine_game = AsyncMock()


class UnsupportedAdapter:
    platform_name = "nope"
    supports_engine_play = False


def make_session(my_color, game_id="g", board_size=19, komi=7.5, rules="chinese", handicap=0):
    return PlatformGameSession(
        platform="golaxy",
        game_id=game_id,
        board_size=board_size,
        my_color=my_color,
        opponent=OnlineUser(platform="golaxy", user_id="7", username="星阵-7", rank="7d", rank_numeric=7.0),
        time_control=TimeControl(system="absolute", main_time=0),
        rules=rules,
        ranked=False,
        handicap=handicap,
        komi=komi,
    )


@pytest.fixture
def setup():
    sm = MockSessionManager()
    pm = PlatformManager(sm)
    adapter = MockEngineAdapter()
    pm._adapters["golaxy"] = adapter
    return pm, sm, adapter


class TestStartEngineGame:
    @pytest.mark.asyncio
    async def test_human_black_start(self, setup):
        pm, sm, adapter = setup
        gs = make_session("B", board_size=19, komi=7.5, rules="chinese", handicap=0)
        adapter.start_engine_game.return_value = EngineGameStart(session=gs, first_ai_move=None)

        session_id = await pm.start_engine_game("golaxy", object(), user_id=7)

        assert session_id == sm.session.session_id
        ctx = pm._active_games["g"]
        assert ctx.is_engine is True
        assert ctx.my_color == "B"
        assert pm._session_to_game[session_id] == "g"

        # edit_game configured the local game to match, NOT new_game.
        edit_calls = [(cmd, kw) for cmd, kw in sm.session.katrain_calls if cmd == "edit_game"]
        assert len(edit_calls) == 1
        _, kw = edit_calls[0]
        assert kw["size"] == 19
        assert kw["komi"] == 7.5
        assert kw["handicap"] == 0
        assert kw["rules"] == "chinese"
        assert not any(cmd == "new_game" for cmd, _ in sm.session.katrain_calls)

        # Human plays Black => no opening AI move.
        assert not any(cmd == "play" for cmd, _ in sm.session.katrain_calls)
        assert sm.session.moves == []

        # Player names preserved via create_multiplayer_session (human=Black=Me).
        assert sm.create_calls[0]["b_name"] == "Me"
        assert sm.create_calls[0]["w_name"] == "[golaxy] 星阵-7"

    @pytest.mark.asyncio
    async def test_human_white_start_plays_ai_opening(self, setup):
        pm, sm, adapter = setup
        gs = make_session("W")
        first = PlatformMove(col=15, row=15, color="B", move_number=1, game_id="g")
        adapter.start_engine_game.return_value = EngineGameStart(session=gs, first_ai_move=first)

        session_id = await pm.start_engine_game("golaxy", object(), user_id=7)
        ctx = pm._active_games["g"]

        # AI opening move applied locally.
        assert (15, 15) in sm.session.moves
        assert ctx.last_confirmed_move == 1

        # Broadcast the confirmed opening move.
        confirmed = [msg for _, msg in sm.broadcasts if msg["type"] == "platform_move_confirmed"]
        assert len(confirmed) == 1
        assert confirmed[0]["move_number"] == 1
        assert (confirmed[0]["col"], confirmed[0]["row"]) == (15, 15)

        # Human=White=Me, bot is Black.
        assert sm.create_calls[0]["w_name"] == "Me"
        assert sm.create_calls[0]["b_name"] == "[golaxy] 星阵-7"

    @pytest.mark.asyncio
    async def test_unsupported_platform_raises(self, setup):
        pm, sm, adapter = setup
        pm._adapters["nope"] = UnsupportedAdapter()
        with pytest.raises(ValueError):
            await pm.start_engine_game("nope", object(), user_id=7)

    @pytest.mark.asyncio
    async def test_unknown_platform_raises(self, setup):
        pm, sm, adapter = setup
        with pytest.raises(ValueError):
            await pm.start_engine_game("does-not-exist", object(), user_id=7)
