# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs. Starlette's TestClient bridges sync<->async via a
# background "portal" thread, and WebKaTrain.__init__ does `from kivymd.app
# import MDApp` on first use — importing kivymd for the first time from that
# background thread triggers real SDL2/Cocoa window creation off the main
# thread, which aborts the process on macOS (NSInternalInconsistencyException:
# "setting the main menu on a non-main thread"). Importing here, before the
# portal thread exists, makes the (cached) module import a no-op later.
import kivymd.app  # noqa: F401

import types
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import katrain.web.server as server

# `_record_ai_game` is a closure defined inside `create_app()`; the module-level
# test hook `server._RECORD_FN` (see server.py, set via `globals()["_RECORD_FN"]
# = _record_ai_game` right after the def) is only populated as a side effect of
# calling `create_app()` at least once. Build one throwaway app here so this
# file's tests pass in isolation, regardless of whether another test module
# (e.g. test_ai_game_autosave.py) happens to have called create_app() first.
# `_record_ai_game` takes `app` as a parameter rather than closing over it, so
# which app instance triggered the assignment doesn't matter.
server.create_app(enable_engine=False)


class _Info:
    def __init__(self, human, name):
        self.human = human
        self.ai = not human
        self.name = name
        self.calculated_rank = None
        self.sgf_rank = None


def _make_session(both_human=True):
    s = MagicMock()
    s.user_id = 42
    s.player_b_id = None
    s.player_w_id = None
    # A raw MagicMock's auto-created `_recorded` attribute is itself a truthy Mock, so
    # `getattr(session, "_recorded", False)` in the idempotency guard would never see the
    # `False` default without this — every test would short-circuit as "already recorded".
    s._recorded = False
    s.game_type = "pvp_local" if both_human else "free"
    s.katrain.get_sgf.return_value = "(;GM[1])"
    s.katrain.get_state.return_value = {"board_size": [19, 19], "history": [1, 2, 3], "komi": 7.5, "ruleset": "chinese"}
    s.katrain.players_info = {"B": _Info(True, "小明"), "W": _Info(both_human, "小红" if both_human else "")}
    return s


@pytest.mark.asyncio
async def test_record_routes_through_dispatcher_with_play_local_source():
    session = _make_session(both_human=True)
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "B+3.5")

    app.state.repository_dispatcher.user_games_create.assert_awaited_once()
    kwargs = app.state.repository_dispatcher.user_games_create.await_args.kwargs
    assert kwargs["user_id"] == 42
    data = kwargs["data"]
    assert data["source"] == "play_local"
    assert "user_id" not in data
    assert isinstance(data["board_size"], int) and data["board_size"] == 19
    assert data["result"] == "B+3.5"


@pytest.mark.asyncio
async def test_record_falls_back_to_local_repo_when_no_dispatcher():
    session = _make_session(both_human=False)  # AI game → play_ai
    app = MagicMock()
    app.state = types.SimpleNamespace(user_game_repo=MagicMock())
    # no repository_dispatcher attribute at all
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "W+R")

    app.state.user_game_repo.create.assert_called_once()
    ckwargs = app.state.user_game_repo.create.call_args.kwargs
    assert ckwargs["source"] == "play_ai"
    assert ckwargs["user_id"] == 42


@pytest.mark.asyncio
async def test_record_is_idempotent_within_session():
    session = _make_session(both_human=True)
    session._recorded = False
    app = MagicMock()
    app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
    current_user = types.SimpleNamespace(id=42, username="小明")

    await server._RECORD_FN(session, app, current_user, "board-game-end")
    await server._RECORD_FN(session, app, current_user, "board-game-end")

    assert app.state.repository_dispatcher.user_games_create.await_count == 1


# --- Regression coverage: `_recorded` must be reset whenever a session is reused
# for a new game (e.g. ZenMode's long-lived session calling /api/game/setup or
# /api/new-game again), otherwise the 2nd+ game on that session is silently
# never recorded (idempotency guard from game 1 stays latched forever).


@pytest.fixture
def client():
    app = server.create_app(enable_engine=False)
    with TestClient(app) as c:
        yield c


def _new_session(client):
    r = client.post("/api/session", json={})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def test_new_game_resets_recorded_flag(client):
    sid = _new_session(client)
    session = client.app.state.session_manager.get_session(sid)
    session._recorded = True  # simulate game 1 already recorded

    r = client.post("/api/new-game", json={"session_id": sid})
    assert r.status_code == 200, r.text

    assert session._recorded is False


def test_game_setup_resets_recorded_flag(client):
    sid = _new_session(client)
    session = client.app.state.session_manager.get_session(sid)
    session._recorded = True  # simulate game 1 already recorded

    r = client.post(
        "/api/game/setup",
        json={
            "session_id": sid,
            "mode": "pvp_local",
            "settings": {
                "board_size": 19,
                "rules": "chinese",
                "handicap": 0,
                "komi": 7.5,
                "black_name": "小明",
                "white_name": "小红",
                "time_enabled": False,
            },
        },
    )
    assert r.status_code == 200, r.text

    assert session._recorded is False
