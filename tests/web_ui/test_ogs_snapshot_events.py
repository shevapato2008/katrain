"""OGS snapshot and event continuity at the platform boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from katrain.core.sgf_parser import Move
from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import OnlineUser, PlatformGameSession, TimeControl
from katrain.web.platforms.ogs.adapter import OGSAdapter, ogs_to_core, core_to_ogs


def _raw_game(size=9, moves=None, initial_state=None, **overrides):
    game = {
        "width": size, "height": size, "phase": "play", "moves": moves if moves is not None else [],
        "initial_state": initial_state if initial_state is not None else {"black": "", "white": ""},
        "players": {"black": {"id": 7, "username": "me", "ranking": 30}, "white": {"id": 8, "username": "you", "ranking": 20}},
        "rules": "japanese", "komi": 6.5, "handicap": 0,
        "time_control": {"system": "fischer", "main_time": 600},
    }
    game.update(overrides)
    return game


def _rest_game(game_id=42, **inner_overrides):
    outer = _raw_game()
    inner = {"phase": outer.pop("phase"), "moves": outer.pop("moves"),
             "initial_state": outer.pop("initial_state")}
    inner.update(inner_overrides)
    outer["id"] = game_id
    outer["gamedata"] = inner
    return outer


@pytest.mark.parametrize("size", [9, 13, 19])
def test_ogs_and_core_y_coordinates_are_inverse_at_both_corners(size):
    assert ogs_to_core(0, 0, size) == (0, size - 1)
    assert ogs_to_core(size - 1, size - 1, size) == (size - 1, 0)
    assert core_to_ogs(0, size - 1, size) == (0, 0)
    assert core_to_ogs(size - 1, 0, size) == (size - 1, size - 1)
    assert Move.from_sgf("aa", (size, size)).coords == ogs_to_core(0, 0, size)


def test_nested_moves_and_initial_state_are_parsed_without_flattening():
    adapter = OGSAdapter()
    snapshot = adapter.parse_game_snapshot(42, _raw_game(
        moves=[[0, 0, 42], {"x": 8, "y": 8}, [-1, -1]],
        initial_state={"black": "bc", "white": "de"},
        handicap=1,
    ))
    assert snapshot.game_id == "42"
    assert snapshot.move_number == 3
    assert snapshot.setup == (("B", 1, 6), ("W", 3, 4))
    assert [(m.color, m.col, m.row) for m in snapshot.moves] == [
        ("W", 0, 8), ("B", 8, 0), ("W", -1, -1),
    ]


def test_empty_initial_state_may_be_omitted_without_handicap():
    adapter = OGSAdapter()
    raw = _raw_game(moves=[[0, 0]])
    del raw["initial_state"]
    snapshot = adapter.parse_game_snapshot(42, raw)
    assert snapshot.setup == ()
    assert snapshot.moves[0].row == 8


@pytest.mark.asyncio
async def test_nested_rest_gamedata_is_used_for_authoritative_snapshot():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value=_rest_game(
        moves=[[0, 0], [-1, -1]], phase="finished", winner=7, outcome="Resignation",
    )))
    await adapter.fetch_game_snapshot("42")
    snapshot = adapter.get_game_snapshot("42")
    assert snapshot.move_number == 2
    assert snapshot.phase.value == "finished"
    assert adapter._game_data[42]["winner"] == 7


@pytest.mark.asyncio
async def test_nested_rest_mismatched_board_or_identity_fails_closed():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value=_rest_game(width=13)))
    with pytest.raises(ValueError):
        await adapter.fetch_game_snapshot("42")


@pytest.mark.asyncio
async def test_resume_rejects_remote_game_without_current_account_seat():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=9, get_game=AsyncMock(return_value=_rest_game()))
    with pytest.raises(ValueError, match="not seated"):
        await adapter.refresh_game_session("42")
    adapter._rest.get_game.return_value = _rest_game(game_id=43)
    with pytest.raises(ValueError):
        await adapter.fetch_game_snapshot("42")


@pytest.mark.asyncio
@pytest.mark.parametrize("players", [
    {"black": {"id": 7}, "white": {}},
    {"black": {"id": 7}, "white": {"id": 7}},
])
async def test_resume_rejects_missing_or_duplicate_seats(players):
    adapter = OGSAdapter()
    raw = _rest_game()
    raw["players"] = players
    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=raw))
    with pytest.raises(ValueError, match="verified seats|not seated"):
        await adapter.refresh_game_session("42")


@pytest.mark.asyncio
async def test_finished_phase_uses_nested_authoritative_result_and_seat_color():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value=_rest_game(
        phase="finished", winner=7, outcome="Resignation",
    )))
    seen = []
    async def on_end(*args):
        seen.append(args)
    adapter.on_game_ended(on_end)
    await adapter._on_phase(42, "finished")
    assert seen == [("42", "B+R", "B")]


@pytest.mark.asyncio
async def test_finished_phase_without_authoritative_winner_does_not_emit_result():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value=_rest_game(phase="finished")))
    seen = []
    async def on_end(*args):
        seen.append(args)
    adapter.on_game_ended(on_end)
    await adapter._on_phase(42, "finished")
    assert seen == []


@pytest.mark.asyncio
async def test_unknown_remote_phase_does_not_resume_play():
    adapter = OGSAdapter()
    seen = []
    async def on_phase(*args):
        seen.append(args)
    adapter.on_game_phase_changed(on_phase)
    await adapter._on_phase(42, "unrecognized")
    assert seen == []


def test_session_uses_inner_fischer_initial_time():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=7)
    raw = _rest_game()
    raw["time_control"] = "fischer"
    raw["time_control_parameters"] = '{"initial_time":180}'
    raw["gamedata"]["time_control"] = {"system": "fischer", "initial_time": 180, "time_increment": 15}
    session = adapter._session_from_game_data(42, adapter._normalize_rest_game(42, raw))
    assert session.time_control.system == "fischer"
    assert session.time_control.main_time == 180
    assert session.time_control.time_increment == 15


@pytest.mark.parametrize("time_control", ["fischer", {}])
def test_session_rejects_flat_time_control_without_parameters(time_control):
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=7)
    raw = _raw_game(time_control=time_control)
    with pytest.raises(ValueError):
        adapter._session_from_game_data(42, raw)


def test_public_seek_without_game_id_is_not_actionable():
    from tests.web_ui.test_ogs_open_challenges import seek
    adapter = OGSAdapter()
    entry = seek()
    entry.pop("game_id")
    assert adapter._parse_seek(entry) is None


@pytest.mark.parametrize("bad", [
    {"moves": [0, 0, 42]},
    {"moves": [[99, 0]]},
    {"moves": [{"x": 0}]},
    {"initial_state": {"black": "a", "white": ""}},
    {"phase": "unverified"},
])
def test_unsupported_snapshot_fails_closed(bad):
    adapter = OGSAdapter()
    with pytest.raises(ValueError):
        adapter.parse_game_snapshot(42, _raw_game(**bad))


@pytest.mark.asyncio
async def test_failed_subscription_validation_cleans_handlers_stream_and_early_data():
    adapter = OGSAdapter()
    callbacks = {}
    disconnect = AsyncMock()
    adapter._rt = SimpleNamespace(
        on=lambda name, cb: callbacks.setdefault(name, []).append(cb),
        off=lambda name, cb: callbacks[name].remove(cb),
        game_connect=AsyncMock(), game_disconnect=disconnect,
    )
    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=_raw_game(height=13)))
    with pytest.raises(ValueError):
        await adapter._connect_to_game(42)
    assert not any(callbacks.values())
    disconnect.assert_awaited_once_with(42)
    assert 42 not in adapter._game_data
    adapter._rest.get_game.return_value = _raw_game()
    await adapter._connect_to_game(42)
    assert all(len(handlers) == 1 for handlers in callbacks.values())


@pytest.mark.asyncio
async def test_early_delta_not_in_rest_snapshot_refuses_to_expose_stale_session():
    adapter = OGSAdapter()
    callbacks = {}
    async def game_connect(game_id):
        await adapter._on_move(game_id, {"game_id": game_id, "move_number": 1, "move": [0, 0]})
    adapter._rt = SimpleNamespace(
        on=lambda name, cb: callbacks.setdefault(name, []).append(cb),
        off=lambda name, cb: callbacks[name].remove(cb),
        game_connect=game_connect, game_disconnect=AsyncMock(),
    )
    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=_raw_game()))
    with pytest.raises(RuntimeError, match="early OGS move"):
        await adapter._connect_to_game(42)
    assert adapter._snapshots == {}
    assert adapter._game_data == {}


@pytest.mark.asyncio
async def test_active_game_first_frame_is_registered_before_socket_connect(monkeypatch):
    from katrain.web.platforms.models import PlatformCredentials
    class FakeRealtime:
        def __init__(self):
            self.callbacks = {}
        def on(self, event, callback):
            self.callbacks.setdefault(event, []).append(callback)
        async def connect(self, **kwargs):
            for callback in self.callbacks.get("active_game", []):
                await callback({"id": 42})
        async def game_connect(self, game_id):
            pass
        async def seek_graph_connect(self):
            pass
        async def disconnect(self):
            pass
    monkeypatch.setattr("katrain.web.platforms.ogs.adapter.OGSRealtimeClient", FakeRealtime)
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(
        login_with_token=AsyncMock(return_value={}), user_jwt="jwt", user_id=7,
        username="me", get_game=AsyncMock(return_value=_raw_game()),
        get_auth_data_for_storage=lambda: {},
    )
    started = []
    async def on_start(session):
        started.append(session.game_id)
    adapter.on_game_started(on_start)
    assert await adapter.connect(PlatformCredentials("ogs", "me", {"user_jwt": "jwt"}))
    assert started == ["42"]


@pytest.mark.asyncio
async def test_login_pending_owner_creates_only_one_local_session_for_duplicate_start():
    class Sessions:
        def __init__(self):
            self.created = 0
            self.sessions = {}
        def create_multiplayer_session(self, **kwargs):
            self.created += 1
            class K:
                def __call__(self, *args, **kwargs):
                    pass
            session = SimpleNamespace(session_id="local-1", user_id=7, katrain=K())
            self.sessions[session.session_id] = session
            return session
        def get_session(self, session_id):
            return self.sessions[session_id]
        def remove_session(self, session_id):
            del self.sessions[session_id]
    sessions = Sessions()
    manager = PlatformManager(sessions)
    adapter = OGSAdapter()
    manager.register_adapter(adapter)
    manager._pending_owner["ogs"] = 7
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, _raw_game())
    game_session = PlatformGameSession(
        platform="ogs", game_id="42", board_size=9, my_color="B",
        opponent=OnlineUser("ogs", "8", "other", "1d", 30),
        time_control=TimeControl("fischer", 600), rules="japanese",
        ranked=False, handicap=0, komi=6.5,
    )
    await manager._on_game_started(game_session)
    await manager._on_game_started(game_session)
    assert sessions.created == 1
    assert manager._active_games["42"].session_id == "local-1"


def test_active_game_lookup_requires_platform_and_session_owner():
    from katrain.web.platforms.models import PlatformGameContext
    sessions = SimpleNamespace(get_session=lambda sid: SimpleNamespace(user_id=7))
    manager = PlatformManager(sessions)
    adapter = OGSAdapter()
    adapter._connected = True
    manager.register_adapter(adapter)
    manager._platform_user_ids["ogs"] = 7
    manager._active_games["42"] = PlatformGameContext("local-1", "ogs", "42")
    assert manager.active_game_for_owner("ogs", 7) == "local-1"
    assert manager.active_game_for_owner("ogs", 8) is None


@pytest.mark.asyncio
async def test_duplicate_and_gap_move_events_reconcile_from_authoritative_snapshot():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=7, get_game=AsyncMock(return_value=_raw_game(moves=[[0, 0], [8, 8]])))
    adapter._game_data[42] = _raw_game(moves=[[0, 0]])
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, adapter._game_data[42])
    observed = []
    async def record(move):
        observed.append(move)
    adapter.on_opponent_move(record)
    await adapter._on_move(42, {"game_id": 42, "move_number": 1, "move": [0, 0]})
    assert observed == []
    await adapter._on_move(42, {"game_id": 42, "move_number": 3, "move": [4, 4]})
    assert observed == []
    assert adapter._rest.get_game.await_count == 1
    assert adapter.get_game_snapshot("42").move_number == 2


@pytest.mark.asyncio
async def test_own_echo_is_emitted_for_manager_confirmation_with_core_coordinates():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(user_id=7)
    adapter._game_data[42] = _raw_game()
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, adapter._game_data[42])
    seen = []
    async def record(move):
        seen.append(move)
    adapter.on_opponent_move(record)
    await adapter._on_move(42, {"game_id": 42, "move_number": 1, "move": [0, 0]})
    assert [(m.game_id, m.move_number, m.color, m.col, m.row) for m in seen] == [("42", 1, "B", 0, 8)]


@pytest.mark.asyncio
async def test_clock_update_only_reaches_matching_game():
    class Sessions:
        def __init__(self):
            self.broadcasts = []
        def broadcast_to_session(self, session_id, payload):
            self.broadcasts.append((session_id, payload))
    from katrain.web.platforms.models import ClockState, PlatformGameContext
    sessions = Sessions()
    manager = PlatformManager(sessions)
    manager._active_games = {
        "1": PlatformGameContext(session_id="local-1", platform="ogs", remote_game_id="1"),
        "2": PlatformGameContext(session_id="local-2", platform="ogs", remote_game_id="2"),
    }
    await manager._on_clock_update(ClockState({}, {}, "B", game_id="2"))
    assert [sid for sid, _ in sessions.broadcasts] == ["local-2"]


@pytest.mark.asyncio
async def test_public_challenge_accept_uses_verified_seek_game_id():
    from katrain.web.platforms.models import PlatformChallenge
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(accept_open_challenge=AsyncMock())
    adapter._connect_to_game = AsyncMock(return_value="joined")
    adapter._seek_graph["123"] = PlatformChallenge(
        platform="ogs", challenge_id="123",
        from_user=OnlineUser("ogs", "8", "other", "1d", 30),
        board_size=9, time_control=TimeControl("fischer", 600),
        rules="japanese", ranked=False, handicap=0, game_id="42",
    )
    assert await adapter.accept_challenge("123") == "joined"
    adapter._rest.accept_open_challenge.assert_awaited_once_with(123)
    adapter._connect_to_game.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_public_challenge_accept_rejects_missing_or_unverified_game_id():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(accept_open_challenge=AsyncMock())
    with pytest.raises(ValueError):
        await adapter.accept_challenge("123")
    adapter._rest.accept_open_challenge.assert_not_awaited()


@pytest.mark.asyncio
async def test_scoring_reject_uses_ogs_resume_play_command():
    adapter = OGSAdapter()
    reject = AsyncMock()
    adapter._rt = SimpleNamespace(game_removed_stones_reject=reject)
    assert await adapter.submit_scoring_action("42", {"action": "reject"}) is True
    reject.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_ogs_snapshot_restores_setup_passes_and_remote_scoring_phase():
    class FakeKatrain:
        def __init__(self):
            self.calls = []
        def __call__(self, action, **kwargs):
            self.calls.append((action, kwargs))
    class Sessions:
        def __init__(self):
            self.sessions = {}
            self.broadcasts = []
        def create_multiplayer_session(self, **kwargs):
            session = SimpleNamespace(session_id="local-1", user_id=7, katrain=FakeKatrain())
            self.sessions[session.session_id] = session
            return session
        def get_session(self, session_id):
            return self.sessions[session_id]
        def remove_session(self, session_id):
            del self.sessions[session_id]
        def broadcast_to_session(self, session_id, payload):
            self.broadcasts.append((session_id, payload))
    sessions = Sessions()
    manager = PlatformManager(sessions)
    adapter = OGSAdapter()
    manager.register_adapter(adapter)
    raw = _raw_game(initial_state={"black": "aa", "white": ""}, moves=[[-1, -1], [-1, -1]], phase="stone removal")
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, raw)
    game_session = PlatformGameSession(
        platform="ogs", game_id="42", board_size=9, my_color="B",
        opponent=OnlineUser("ogs", "8", "other", "1d", 30),
        time_control=TimeControl("fischer", 600), rules="japanese",
        ranked=False, handicap=0, komi=6.5,
    )
    session_id = await manager.start_platform_game("ogs", game_session, 7)
    session = sessions.get_session(session_id)
    assert session.katrain.platform_phase == "scoring"
    ctx = manager.get_game_context(session_id)
    assert ctx.last_confirmed_move == 2
    assert ctx.game_phase.value == "scoring"
    tree = session.katrain.calls[-1][1]["move_tree"]
    assert [(stone.player, stone.coords) for stone in tree.placements] == [("B", (0, 8))]
    assert tree.children[0].move.is_pass
    assert tree.children[0].children[0].move.is_pass

    resumed = adapter.parse_game_snapshot(42, _raw_game(
        initial_state={"black": "aa", "white": ""},
        moves=[[-1, -1], [-1, -1], [8, 8]], phase="play",
    ))
    await manager._on_game_snapshot("42", resumed)
    assert ctx.last_confirmed_move == 3
    assert ctx.game_phase.value == "playing"
    assert session.katrain.platform_phase == "playing"
    assert session.katrain.calls[-1][1]["move_tree"].children[0].children[0].children[0].move.coords == (8, 0)


@pytest.mark.asyncio
async def test_ogs_own_echo_confirms_only_matching_pending_move():
    from katrain.web.platforms.models import PlatformGameContext, PlatformMove
    class Sessions:
        def __init__(self):
            self.katrain = lambda *args, **kwargs: None
        def get_session(self, session_id):
            return SimpleNamespace(katrain=self.katrain)
        def broadcast_to_session(self, session_id, payload):
            pass
    sessions = Sessions()
    manager = PlatformManager(sessions)
    ctx = PlatformGameContext("local", "ogs", "42", my_color="B")
    manager._active_games["42"] = ctx
    ctx.set_pending("move")
    ctx.pending_coords = (0, 8)
    await manager._on_opponent_move(PlatformMove(1, 8, "B", 1, "42"))
    assert ctx.needs_resync
    assert ctx.last_confirmed_move == 0
    ctx.needs_resync = False
    await manager._on_opponent_move(PlatformMove(0, 8, "B", 1, "42"))
    assert ctx.last_confirmed_move == 1
    assert ctx.pending_confirmation.is_set()
