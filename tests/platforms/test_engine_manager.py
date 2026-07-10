"""Manager.start_engine_game tests.

Verifies the manager creates + configures the local KaTrain session (via edit_game,
preserving player names), registers an is_engine context, and plays the AI's opening
move locally only when the human is White.

Also covers Task 1 (kiosk-golaxy-physical-play track): `platform_engine_color`, the
single source of truth marking which color (B/W) is the remote engine opponent. The
LED orchestrator (Task 2) and frontend (Task 3) both read this off get_state().
"""

import json
import os
from unittest.mock import AsyncMock

import pytest

from katrain.web.platforms.golaxy.adapter import EngineGameConfig, EngineGameStart, GolaxyAdapter
from katrain.web.platforms.golaxy.coords import katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import GenmoveResult
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import OnlineUser, PlatformGameSession, PlatformMove, TimeControl
from katrain.web.session import SessionManager


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
    async def test_human_black_marks_white_as_platform_engine(self, setup):
        """Human plays Black => the remote engine is White (G1 source of truth)."""
        pm, sm, adapter = setup
        gs = make_session("B")
        adapter.start_engine_game.return_value = EngineGameStart(session=gs, first_ai_move=None)

        await pm.start_engine_game("golaxy", object(), user_id=7)

        edit_calls = [(cmd, kw) for cmd, kw in sm.session.katrain_calls if cmd == "edit_game"]
        assert len(edit_calls) == 1  # still folded into the single edit_game call, not a second dispatch
        _, kw = edit_calls[0]
        assert kw["platform_engine_color"] == "W"

    @pytest.mark.asyncio
    async def test_human_white_marks_black_as_platform_engine(self, setup):
        """Human plays White => the remote engine is Black (G1 source of truth)."""
        pm, sm, adapter = setup
        gs = make_session("W")
        first = PlatformMove(col=15, row=15, color="B", move_number=1, game_id="g")
        adapter.start_engine_game.return_value = EngineGameStart(session=gs, first_ai_move=first)

        await pm.start_engine_game("golaxy", object(), user_id=7)

        edit_calls = [(cmd, kw) for cmd, kw in sm.session.katrain_calls if cmd == "edit_game"]
        assert len(edit_calls) == 1
        _, kw = edit_calls[0]
        assert kw["platform_engine_color"] == "B"

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


def _genmove_for(col, row, board_size=19, prob=0.5):
    """A GenmoveResult whose coord decodes to KaTrain (col, row)."""
    return GenmoveResult(coord=katrain_to_golaxy(col, row, board_size), prob=prob)


def _build_real_stack():
    """Real SessionManager (NullEngine) + real PlatformManager + real GolaxyAdapter.

    Mirrors tests/platforms/test_engine_integration.py's real-stack helper. The only
    thing mocked is the network genmove boundary; no httpx call is ever made.
    """
    sm = SessionManager(enable_engine=False)
    pm = PlatformManager(sm)
    adapter = GolaxyAdapter()
    pm.register_adapter(adapter)
    adapter._rest.set_tokens("tok", "refresh")
    adapter._rest.engine_genmove = AsyncMock(return_value=_genmove_for(15, 3))
    return sm, pm, adapter


class TestPlatformEngineColorRealSession:
    """Real-stack coverage of `platform_engine_color` on the actual get_state() contract.

    `platform_engine_color` is the G1/G2 single source of truth for which color is the
    remote engine opponent. It must: reflect the correct color for both human colors,
    stay None for non-engine sessions, survive a later plain edit_game call (M6
    persistence), and never leak into a freshly-created session.
    """

    @pytest.mark.asyncio
    async def test_human_black_get_state_platform_engine_color_is_white(self):
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)

        assert session.katrain.get_state()["platform_engine_color"] == "W"

    @pytest.mark.asyncio
    async def test_human_white_get_state_platform_engine_color_is_black(self):
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="W")

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)

        assert session.katrain.get_state()["platform_engine_color"] == "B"

    def test_non_engine_session_platform_engine_color_is_none(self):
        sm = SessionManager(enable_engine=False)
        session = sm.create_multiplayer_session(player_b_id=1, player_w_id=2, b_name="A", w_name="B")

        assert session.katrain.get_state()["platform_engine_color"] is None

    @pytest.mark.asyncio
    async def test_platform_engine_color_persists_across_edit_game(self):
        """M6: the field hangs off the interface, not a Player, so a later plain
        edit_game call (e.g. a board-size tweak) must not clear it."""
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)
        assert session.katrain.get_state()["platform_engine_color"] == "W"

        # A later edit_game call that does NOT mention platform_engine_color at all.
        session.katrain("edit_game", komi=6.5)

        assert session.katrain.get_state()["platform_engine_color"] == "W"

    @pytest.mark.asyncio
    async def test_fresh_session_no_leakage(self):
        """A brand-new session must never inherit a previous session's engine color."""
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")
        await pm.start_engine_game("golaxy", config, user_id=1)

        fresh_session = sm.create_multiplayer_session(player_b_id=3, player_w_id=4, b_name="A", w_name="B")

        assert fresh_session.katrain.get_state()["platform_engine_color"] is None


class TestPlatformEngineColorContractFixture:
    """Dumps a real engine-game get_state() JSON for frontend Task 3 to consume as a
    contract fixture. Deterministic (sort_keys + indent) so re-running regenerates an
    identical file."""

    FIXTURE_PATH = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "katrain",
        "web",
        "ui",
        "src",
        "kiosk",
        "__tests__",
        "fixtures",
        "engine_game_state.json",
    )

    @pytest.mark.asyncio
    async def test_dump_engine_game_state_fixture(self):
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)
        state = session.katrain.get_state()

        assert state["platform_engine_color"] == "W"

        fixture_path = os.path.abspath(self.FIXTURE_PATH)
        os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
        with open(fixture_path, "w", encoding="utf-8") as f:
            json.dump(state, f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write("\n")
