from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import asyncio

import pytest

from katrain.web.platforms.manager import PlatformManager
from katrain.web.platforms.models import (
    GamePhase, OnlineUser, PlatformGameContext, PlatformGameSession, PlatformGameSnapshot, TimeControl,
)
from katrain.web.platforms.ogs.adapter import OGSAdapter
from katrain.web import server


@pytest.mark.asyncio
async def test_finished_ogs_rest_result_commits_to_session_and_broadcasts():
    katrain = MagicMock()
    katrain.game.terminal = None
    katrain.get_state.return_value = {"end_result": "W+R", "terminal_result": "W+R"}
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain, game_ended=False, last_state={})
    sessions = SimpleNamespace(
        get_session=lambda _: session,
        broadcast_to_session=MagicMock(),
    )
    manager = PlatformManager(sessions)
    ctx = PlatformGameContext("local", "ogs", "42", my_color="B")
    manager._active_games["42"] = ctx
    manager._session_to_game["local"] = "42"
    saved = AsyncMock(return_value=True)
    manager.on_online_game_finished = saved

    await manager._on_game_ended("42", "W+R", "W")

    katrain._commit_end_state.assert_called_once_with("W+R")
    assert session.game_ended is True
    assert session.last_state["terminal_result"] == "W+R"
    saved.assert_awaited_once()
    assert "42" not in manager._active_games
    assert any(call.args[1]["type"] == "game_end" for call in sessions.broadcast_to_session.call_args_list)


@pytest.mark.asyncio
async def test_finished_ogs_result_retries_record_without_second_commit(monkeypatch):
    katrain = MagicMock()
    katrain.game.terminal = None
    katrain.get_state.return_value = {"end_result": "B+T"}
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain, game_ended=False, last_state={})
    sessions = SimpleNamespace(get_session=lambda _: session, broadcast_to_session=MagicMock())
    manager = PlatformManager(sessions)
    ctx = PlatformGameContext("local", "ogs", "42")
    manager._active_games["42"] = ctx
    manager._session_to_game["local"] = "42"
    manager.on_online_game_finished = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr("katrain.web.platforms.manager.ONLINE_RECORD_RETRY_DELAYS", (0,), raising=False)

    await manager._on_game_ended("42", "B+T", "B")
    assert "42" in manager._active_games
    katrain.game.terminal = SimpleNamespace(result="B+T")
    await manager._record_retry_tasks["42"]
    katrain._commit_end_state.assert_called_once_with("B+T")
    assert "42" not in manager._active_games


@pytest.mark.asyncio
async def test_missing_session_and_failed_commit_keep_final_result_retryable():
    missing = SimpleNamespace(get_session=lambda _: (_ for _ in ()).throw(KeyError("local")),
                              broadcast_to_session=MagicMock())
    manager = PlatformManager(missing)
    manager._active_games["42"] = PlatformGameContext("local", "ogs", "42")
    with pytest.raises(KeyError):
        await manager._on_game_ended("42", "B+R", "B")

    katrain = MagicMock()
    katrain.game.terminal = None
    katrain._commit_end_state.side_effect = RuntimeError("temporary failure")
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain)
    manager._session_manager = SimpleNamespace(get_session=lambda _: session,
                                               broadcast_to_session=MagicMock())
    with pytest.raises(RuntimeError, match="temporary failure"):
        await manager._on_game_ended("42", "B+R", "B")
    assert "42" in manager._active_games


@pytest.mark.asyncio
async def test_partial_terminal_broadcast_retries_without_repeating_game_end():
    katrain = MagicMock()
    katrain.game.terminal = None
    katrain._commit_end_state.side_effect = lambda result: setattr(
        katrain.game, "terminal", SimpleNamespace(result=result))
    katrain.get_state.return_value = {"terminal_result": "B+R"}
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain,
                              game_ended=False, last_state={})
    broadcasts = []

    def broadcast(_session_id, payload):
        if payload["type"] == "platform_game_ended" and not any(
            item["type"] == "failed_attempt" for item in broadcasts):
            broadcasts.append({"type": "failed_attempt"})
            raise RuntimeError("temporary broadcast failure")
        broadcasts.append(payload)

    sessions = SimpleNamespace(get_session=lambda _: session, broadcast_to_session=broadcast)
    manager = PlatformManager(sessions)
    manager._active_games["42"] = PlatformGameContext("local", "ogs", "42")
    manager.on_online_game_finished = AsyncMock(return_value=True)

    with pytest.raises(RuntimeError, match="broadcast failure"):
        await manager._on_game_ended("42", "B+R", "B")
    manager.on_online_game_finished.assert_not_awaited()
    assert session.last_state["terminal_result"] == "B+R"

    await manager._on_game_ended("42", "B+R", "B")
    assert [item["type"] for item in broadcasts].count("game_end") == 1
    assert [item["type"] for item in broadcasts].count("platform_game_ended") == 1
    manager.on_online_game_finished.assert_awaited_once()


@pytest.mark.asyncio
async def test_finished_phase_uses_nested_rest_result_not_outer_fields():
    adapter = OGSAdapter()
    outer = {
        "id": 42, "width": 9, "height": 9,
        "players": {"black": {"id": 7}, "white": {"id": 8}},
        "outcome": "Resignation",  # Outer field alone is not decisive.
        "gamedata": {
            "game_id": 42, "width": 9, "height": 9, "phase": "finished",
            "moves": [], "initial_state": {"black": "", "white": ""},
            "players": {"black": {"id": 7}, "white": {"id": 8}},
            "winner": 8, "outcome": "Timeout",
        },
    }
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value=outer))
    events = []
    async def on_end(*args):
        events.append(args)
    adapter.on_game_ended(on_end)

    await adapter._on_phase(42, "finished")

    assert events == [("42", "W+T", "W")]


@pytest.mark.asyncio
async def test_finished_phase_reconciles_missing_last_move_before_result():
    adapter = OGSAdapter()
    initial = {
        "game_id": 42, "width": 9, "height": 9, "phase": "play",
        "moves": [], "initial_state": {"black": "", "white": ""},
        "players": {"black": {"id": 7}, "white": {"id": 8}},
    }
    adapter._game_data[42] = initial
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, initial)
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value={
        "id": 42, "width": 9, "height": 9,
        "players": {"black": {"id": 7}, "white": {"id": 8}},
        "gamedata": {
            **initial, "phase": "finished", "moves": [[0, 0]],
            "winner": 7, "outcome": "Resignation",
        },
    }))
    events = []

    async def on_snapshot(game_id, snapshot):
        events.append(("snapshot", game_id, snapshot.move_number))

    async def on_end(game_id, result, winner):
        events.append(("ended", game_id, result, winner))

    adapter.on_game_snapshot(on_snapshot)
    adapter.on_game_ended(on_end)

    await adapter._on_phase(42, "finished")

    assert events == [("snapshot", "42", 1), ("ended", "42", "B+R", "B")]


@pytest.mark.asyncio
async def test_failed_final_snapshot_restore_blocks_record_until_reconciled():
    adapter = OGSAdapter()
    initial = {
        "game_id": 42, "width": 9, "height": 9, "phase": "play",
        "moves": [], "initial_state": {"black": "", "white": ""},
        "players": {"black": {"id": 7}, "white": {"id": 8}},
    }
    adapter._game_data[42] = initial
    adapter._snapshots[42] = adapter.parse_game_snapshot(42, initial)
    adapter._rest = SimpleNamespace(get_game=AsyncMock(return_value={
        "id": 42, "width": 9, "height": 9,
        "players": initial["players"],
        "gamedata": {**initial, "phase": "finished", "moves": [[0, 0]],
                     "winner": 7, "outcome": "Resignation"},
    }))
    katrain = MagicMock()
    katrain.game.terminal = None
    katrain.get_state.return_value = {"end_result": "B+R"}
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain, game_ended=False, last_state={})
    sessions = SimpleNamespace(get_session=lambda _: session, broadcast_to_session=MagicMock())
    manager = PlatformManager(sessions)
    manager.register_adapter(adapter)
    manager._setup_callbacks(adapter)
    ctx = PlatformGameContext("local", "ogs", "42", my_color="B")
    ctx.remote_session = SimpleNamespace(board_size=9)
    manager._active_games["42"] = ctx
    manager._session_to_game["local"] = "42"
    manager._restore_ogs_snapshot = MagicMock(side_effect=[RuntimeError("restore failed"), None])
    saved = AsyncMock(return_value=True)
    manager.on_online_game_finished = saved

    assert await adapter._read_finished_result(42) is False
    assert ctx.needs_resync is True
    assert ctx.last_confirmed_move == 0
    saved.assert_not_awaited()
    katrain._commit_end_state.assert_not_called()

    assert await adapter._read_finished_result(42) is True
    assert ctx.last_confirmed_move == 1
    saved.assert_awaited_once()
    katrain._commit_end_state.assert_called_once_with("B+R")


@pytest.mark.asyncio
async def test_unavailable_final_rest_does_not_guess_result():
    adapter = OGSAdapter()
    adapter._rest = SimpleNamespace(get_game=AsyncMock(side_effect=RuntimeError("network")))
    events = []
    async def on_end(*args):
        events.append(args)
    adapter.on_game_ended(on_end)
    await adapter._on_phase(42, "finished")
    assert events == []
    task = adapter._final_retry_tasks[42]
    task.cancel()


@pytest.mark.asyncio
async def test_finished_phase_retries_until_rest_has_authoritative_result(monkeypatch):
    adapter = OGSAdapter()
    outer = {
        "id": 42, "width": 9, "height": 9,
        "players": {"black": {"id": 7}, "white": {"id": 8}},
        "gamedata": {
            "game_id": 42, "width": 9, "height": 9, "phase": "finished",
            "moves": [], "initial_state": {"black": "", "white": ""},
            "players": {"black": {"id": 7}, "white": {"id": 8}},
            "winner": 7, "outcome": "Resignation",
        },
    }
    adapter._rest = SimpleNamespace(get_game=AsyncMock(side_effect=[RuntimeError("late"), outer]))
    events = []
    async def on_end(*args):
        events.append(args)
    adapter.on_game_ended(on_end)
    monkeypatch.setattr("katrain.web.platforms.ogs.adapter.FINAL_RESULT_RETRY_DELAYS", (0,))

    await adapter._on_phase(42, "finished")
    await adapter._final_retry_tasks[42]

    assert events == [("42", "B+R", "B")]
    assert adapter._rest.get_game.await_count == 2


@pytest.mark.asyncio
async def test_ogs_result_records_one_owned_human_game(app):
    user = app.state.user_repo.create_user("me", "hashed-password")
    user_id = user["id"]
    app.state.repository_dispatcher = None
    info = SimpleNamespace(name="", human=True, ai=False, calculated_rank=None, sgf_rank=None)
    katrain = SimpleNamespace(
        game=SimpleNamespace(root=SimpleNamespace(set_property=MagicMock())),
        players_info={"B": info, "W": info},
        get_state=lambda: {"board_size": [9, 9], "history": [1, 2], "komi": 6.5, "ruleset": "japanese"},
        get_sgf=lambda: "(;GM[1]SZ[9]RE[W+R])",
    )
    session = SimpleNamespace(
        user_id=user_id, game_type="pvp_online", katrain=katrain,
        record_game_lock=asyncio.Lock(), _recorded=False,
    )
    ctx = PlatformGameContext("local", "ogs", "42", my_color="W")
    ctx.remote_session = SimpleNamespace(opponent=SimpleNamespace(username="opponent"))

    assert await server._record_ogs_online_game(session, ctx, "W+R", app) is True
    assert await server._record_ogs_online_game(session, ctx, "W+R", app) is True
    rows = app.state.user_game_repo.list(user_id=user_id)
    assert rows["total"] == 1
    row = rows["items"][0]
    assert row["source"] == "play_human"
    assert row["game_type"] == "pvp_online"
    assert row["user_color"] == "W"
    assert row["player_black"] == "opponent"
    assert row["player_white"] == "me"
    assert row["result"] == "W+R"
    assert len(row["id"]) == 32


@pytest.mark.asyncio
async def test_finished_context_rejects_late_play_snapshot_and_phase():
    katrain = MagicMock()
    katrain.game.terminal = SimpleNamespace(result="B+R")
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain)
    sessions = SimpleNamespace(get_session=lambda _: session, broadcast_to_session=MagicMock())
    manager = PlatformManager(sessions)
    ctx = PlatformGameContext("local", "ogs", "42", game_phase=GamePhase.FINISHED)
    ctx.remote_session = SimpleNamespace(board_size=9)
    ctx.last_confirmed_move = 2
    manager._active_games["42"] = ctx
    manager._session_to_game["local"] = "42"

    await manager._on_game_phase_changed("42", GamePhase.PLAYING)
    await manager._on_game_snapshot("42", PlatformGameSnapshot("42", 9, (), (), GamePhase.PLAYING))

    assert ctx.game_phase == GamePhase.FINISHED
    katrain.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_discards_late_play_gamedata_after_finished():
    adapter = OGSAdapter()
    adapter._snapshots[42] = PlatformGameSnapshot("42", 9, (), (), GamePhase.FINISHED)
    await adapter._on_gamedata(42, {
        "game_id": 42, "width": 9, "height": 9, "phase": "play",
        "initial_state": {"black": "", "white": ""}, "moves": [],
    })
    assert adapter._snapshots[42].phase == GamePhase.FINISHED


@pytest.mark.asyncio
async def test_starting_finished_snapshot_rechecks_result_after_context_exists():
    katrain = MagicMock()
    session = SimpleNamespace(session_id="local", user_id=7, katrain=katrain)
    sessions = SimpleNamespace(
        create_multiplayer_session=lambda **_: session,
        get_session=lambda _: session,
        remove_session=MagicMock(),
    )
    manager = PlatformManager(sessions)
    manager._restore_ogs_snapshot = MagicMock()
    adapter = SimpleNamespace(
        platform_name="ogs",
        get_game_snapshot=MagicMock(return_value=PlatformGameSnapshot("42", 9, (), (), GamePhase.FINISHED)),
        fetch_game_snapshot=AsyncMock(return_value={"phase": "finished", "move_number": 0}),
    )
    manager.register_adapter(adapter)
    game = PlatformGameSession(
        platform="ogs", game_id="42", board_size=9, my_color="B",
        opponent=OnlineUser("ogs", "8", "opponent", "1d", 30),
        time_control=TimeControl("fischer", 180), rules="japanese",
        ranked=False, handicap=0, komi=6.5,
    )

    assert await manager.start_platform_game("ogs", game, 7) == "local"
    adapter.fetch_game_snapshot.assert_awaited_once_with("42")
    assert manager.get_game_context("local") is not None


@pytest.mark.asyncio
async def test_expired_local_session_restarts_from_same_remote_snapshot():
    session = SimpleNamespace(session_id="replacement", user_id=7, katrain=MagicMock())
    sessions_by_id = {}

    def create_session(**_kwargs):
        sessions_by_id[session.session_id] = session
        return session

    sessions = SimpleNamespace(
        create_multiplayer_session=create_session,
        get_session=lambda session_id: sessions_by_id[session_id],
        remove_session=MagicMock(),
    )
    manager = PlatformManager(sessions)
    manager._restore_ogs_snapshot = MagicMock()
    snapshot = PlatformGameSnapshot("42", 9, (), (), GamePhase.PLAYING)
    manager.register_adapter(SimpleNamespace(platform_name="ogs", get_game_snapshot=lambda _: snapshot))
    manager._active_games["42"] = PlatformGameContext("expired", "ogs", "42")
    manager._session_to_game["expired"] = "42"
    game = PlatformGameSession(
        platform="ogs", game_id="42", board_size=9, my_color="B",
        opponent=OnlineUser("ogs", "8", "opponent", "1d", 30),
        time_control=TimeControl("fischer", 180), rules="japanese",
        ranked=False, handicap=0, komi=6.5,
    )

    assert await manager.start_platform_game("ogs", game, 7) == "replacement"
    assert manager._active_games["42"].session_id == "replacement"
    assert "expired" not in manager._session_to_game
    manager._restore_ogs_snapshot.assert_called_once_with(session, snapshot, game)


@pytest.mark.asyncio
async def test_active_game_query_recovers_expired_session_without_socket_reconnect():
    session = SimpleNamespace(session_id="replacement", user_id=7, katrain=MagicMock())
    sessions_by_id = {}

    def create_session(**_kwargs):
        sessions_by_id[session.session_id] = session
        return session

    sessions = SimpleNamespace(
        create_multiplayer_session=create_session,
        get_session=lambda session_id: sessions_by_id[session_id],
        remove_session=MagicMock(),
    )
    manager = PlatformManager(sessions)
    manager._restore_ogs_snapshot = MagicMock()
    snapshot = PlatformGameSnapshot("42", 9, (), (), GamePhase.PLAYING)
    game = PlatformGameSession(
        platform="ogs", game_id="42", board_size=9, my_color="B",
        opponent=OnlineUser("ogs", "8", "opponent", "1d", 30),
        time_control=TimeControl("fischer", 180), rules="japanese",
        ranked=False, handicap=0, komi=6.5,
    )
    adapter = SimpleNamespace(
        platform_name="ogs", is_connected=True,
        get_game_snapshot=lambda _: snapshot,
        refresh_game_session=AsyncMock(return_value=game),
    )
    manager.register_adapter(adapter)
    manager._platform_user_ids["ogs"] = 7
    manager._active_games["42"] = PlatformGameContext("expired", "ogs", "42")
    manager._session_to_game["expired"] = "42"

    assert await manager.recover_active_game_for_owner("ogs", 7) == "replacement"
    adapter.refresh_game_session.assert_awaited_once_with("42")
    assert await manager.recover_active_game_for_owner("ogs", 7) == "replacement"
    adapter.refresh_game_session.assert_awaited_once()
