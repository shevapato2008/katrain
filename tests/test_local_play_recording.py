import types
import pytest
from unittest.mock import AsyncMock, MagicMock

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
