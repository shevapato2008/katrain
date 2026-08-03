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

from katrain.core.base_katrain import KaTrainBase
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

    def create_multiplayer_session(self, player_b_id, player_w_id, b_name, w_name, skip_initial_analysis=False):
        self.create_calls.append(
            {
                "player_b_id": player_b_id,
                "player_w_id": player_w_id,
                "b_name": b_name,
                "w_name": w_name,
                "skip_initial_analysis": skip_initial_analysis,
            }
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
        assert sm.create_calls[0]["skip_initial_analysis"] is True

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

    @pytest.mark.asyncio
    async def test_new_game_resets_platform_engine_color(self):
        """A session that finishes an engine game and then starts a plain local game
        (same WebKaTrain instance, e.g. via POST /api/new-game) must not retain the
        stale engine color — otherwise Task 2's LED orchestrator would treat a purely
        local game as having an engine-controlled color."""
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)
        assert session.katrain.get_state()["platform_engine_color"] == "W"

        session.katrain("new_game")

        assert session.katrain.get_state()["platform_engine_color"] is None


class TestEngineGameHandicapConfigLeak:
    """Part 1 (Task 5 investigation): a kiosk with a local free-play `game/handicap`
    preference > 0 must not leak stray handicap placements into an even
    (handicap=0) Golaxy engine game's LOCAL board.

    Root-cause fix (superseding an earlier, overly-broad patch to
    `_do_edit_game`'s gate): `BaseGame.__init__` (katrain/core/game.py) now sets
    the SGF "HA" property when it config-seeds a freshly-created session's
    handicap placements from `katrain.config("game/handicap")`, so
    `root.handicap` correctly reports 9 (not 0) even though only placements were
    written. That lets `_do_edit_game`'s original, narrow "did anything change"
    gate (`self.game.root.handicap != handicap`) fire correctly on its own: 9 != 0
    is True, so `place_handicap_stones(0)` runs and the stray stones are cleared
    -- staying in sync with Golaxy's `ctx.moves`, which correctly starts empty for
    an even game.

    A broader version of this fix once widened the edit_game gate itself to
    `handicap == 0 and placements`, which also fired on legitimately-loaded
    positions (tsumego/teaching setups with AB but no HA) and wiped their setup
    stones -- see `TestEditGameHandicapZeroPreservesSetupPlacements` below.
    """

    @pytest.mark.asyncio
    async def test_engine_game_clears_stale_config_seeded_handicap(self, monkeypatch):
        original_config = KaTrainBase.config

        def _leaky_config(self, setting, default=None):
            if setting == "game/handicap":
                return 9  # simulates a box with a local free-play preference set
            return original_config(self, setting, default)

        monkeypatch.setattr(KaTrainBase, "config", _leaky_config)

        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B", handicap=0)

        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)

        assert session.katrain.game.root.placements == []
        assert session.katrain.game.root.handicap == 0


class TestEditGameHandicapZeroPreservesSetupPlacements:
    """Reviewer-reproduced regression guard for the collateral damage caused by an
    earlier, overly-broad fix for `TestEngineGameHandicapConfigLeak` above.

    A legitimately-loaded position with AB/AW setup stones but no "HA" property
    (tsumego, teaching setups, custom boards loaded from SGF) must survive a plain
    `edit_game(handicap=0, ...)` call. The frontend's NewGameDialog always submits
    `handicap` explicitly (pre-filled 0), so merely saving a komi/rules tweak on
    such a position must never clear the board.
    """

    def test_setup_placements_without_ha_survive_edit_game_handicap_zero(self):
        sm = SessionManager(enable_engine=False)
        session = sm.create_multiplayer_session(player_b_id=1, player_w_id=2, b_name="A", w_name="B")

        # Simulate a loaded setup position: AB/AW placements present, but no HA
        # property -- e.g. a tsumego/teaching SGF, or any board built without
        # going through the config-seeded new-game path.
        root = session.katrain.game.root
        root.set_property("AB", ["pd", "pp"])  # BQ16, BQ4 in SGF coords
        root.set_property("AW", ["dd", "dp"])  # WD16, WD4 in SGF coords
        assert root.handicap == 0
        assert len(root.placements) == 4

        session.katrain("edit_game", handicap=0, komi=6.5)

        assert len(session.katrain.game.root.placements) == 4


class TestPlatformEngineColorContractFixture:
    """Dumps a real engine-game get_state() JSON for frontend Task 3 to consume as a
    contract fixture.

    `game_id` (timestamp+uuid) and every `id()`-derived node id (`current_node_id`,
    `history[].node_id`) are run-to-run non-deterministic — regenerating the raw
    get_state() output is NOT identical between runs. This test normalizes those
    fields to fixed placeholders before dumping (preserving each field's original
    JSON type) so the *normalized* output is deterministic, and only rewrites the
    fixture file when the normalized content actually differs from what's on disk,
    so a clean run never dirties the tree.
    """

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

    # Keys whose values are id()-derived memory addresses (int) rather than stable
    # identifiers. Normalized to a fixed int placeholder, keeping the JSON type intact.
    _NODE_ID_KEYS = frozenset({"current_node_id", "node_id"})
    _NODE_ID_PLACEHOLDER = 0
    _GAME_ID_PLACEHOLDER = "golaxy-engine-FIXTURE"

    @classmethod
    def _normalize(cls, value):
        """Recursively replace run-varying fields (game_id, id()-derived node ids)
        with stable placeholders of the same JSON type, leaving everything else
        untouched."""
        if isinstance(value, dict):
            normalized = {}
            for key, val in value.items():
                if key == "game_id" and isinstance(val, str):
                    normalized[key] = cls._GAME_ID_PLACEHOLDER
                elif key in cls._NODE_ID_KEYS and isinstance(val, int):
                    normalized[key] = cls._NODE_ID_PLACEHOLDER
                else:
                    normalized[key] = cls._normalize(val)
            return normalized
        if isinstance(value, list):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    async def _start_engine_game_state():
        sm, pm, adapter = _build_real_stack()
        config = EngineGameConfig(level=1100, human_color="B")
        session_id = await pm.start_engine_game("golaxy", config, user_id=1)
        session = sm.get_session(session_id)
        return session.katrain.get_state()

    @pytest.mark.asyncio
    async def test_dump_engine_game_state_fixture(self):
        state = await self._start_engine_game_state()
        assert state["platform_engine_color"] == "W"

        dumped = json.dumps(self._normalize(state), sort_keys=True, indent=2, ensure_ascii=False)

        # Determinism guard: a second, independently-created engine game has its own
        # game_id (timestamp+uuid) and id()-derived node ids, yet must normalize to
        # byte-identical output. This is what actually protects the checked-in
        # fixture from being rewritten (and the tree dirtied) on every test run.
        state_again = await self._start_engine_game_state()
        dumped_again = json.dumps(self._normalize(state_again), sort_keys=True, indent=2, ensure_ascii=False)
        assert dumped == dumped_again

        dumped_with_trailing_newline = dumped + "\n"

        fixture_path = os.path.abspath(self.FIXTURE_PATH)
        os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
        existing = None
        if os.path.exists(fixture_path):
            with open(fixture_path, "r", encoding="utf-8") as f:
                existing = f.read()
        if existing != dumped_with_trailing_newline:
            with open(fixture_path, "w", encoding="utf-8") as f:
                f.write(dumped_with_trailing_newline)
