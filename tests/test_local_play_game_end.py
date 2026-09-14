"""本地对局 v2 · 终局契约（spec §3.2 认输、§3.4 双 pass 与数子）。

全部走真 `WebKaTrain` + 真 HTTP。落账由 `app.state.user_game_repo` 的 MagicMock 观察：
server 模式的 lifespan 不设 `repository_dispatcher`，`_record_ai_game` 于是走
`app.state.user_game_repo.create(user_id=..., **data)`。

**盒上模式靠 `session.katrain.suppress_auto_eval = True` 模拟**：生产里它由
`settings.KATRAIN_MODE == "board"` 在 `WebKaTrain.__init__` 设（interface.py），
这里建完会话再直接设，免得改进程级 settings。

**`save_config` 必须打桩**：`manager.create_session` 建的 `WebKaTrain` 是
`force_package_config=False`，`/api/game/setup`、`/api/new-game` 里的 `update_config`
会把 `~/.katrain/config.json` 改掉（2026-09-14 实测：跑一次 `test_guest_free_play.py`
就把开发机的 komi/rules 改了）。
"""

# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs — same reason as tests/test_local_play_setup.py: kivymd's
# first import from Starlette's background portal thread creates a real SDL2/Cocoa
# window off the main thread and aborts the process on macOS.
import kivymd.app  # noqa: F401

import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app

OWNER = types.SimpleNamespace(id=7, username="owner", uuid="u-7")
STRANGER = types.SimpleNamespace(id=999, username="stranger", uuid="u-999")
HUMAN = {"name": "", "player_type": "player:human", "player_subtype": "player:human"}


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    # 必须在进 `TestClient` **之前**设：lifespan 会用它建全部 repo 并跑 `init_db()`。
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        c.app.state.user_game_repo = MagicMock()
        c.app.state.repository_dispatcher = None
        c.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
        yield c
        c.app.dependency_overrides.clear()
        # 会话是进程级的，不收掉会连同引擎活到本次 pytest 结束（见 test_guest_free_play.py）。
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def _owned_game(client, monkeypatch, *, game_type, board_mode, size=19, base=100, user_id=OWNER.id):
    """建一个归 OWNER 的会话并开局。两边都坐人：有 AI 座位会起 genmove 后台线程，活得比用例长。"""
    session = client.app.state.session_manager.create_session(user_id=user_id)
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    session.katrain.suppress_auto_eval = board_mode
    sid = session.session_id
    if game_type == "pvp_local":
        r = client.post(
            "/api/game/setup",
            json={
                "session_id": sid,
                "mode": "pvp_local",
                "settings": {
                    "board_size": size,
                    "rules": "chinese",
                    "handicap": 0,
                    "komi": 7.5,
                    "black_name": "",
                    "white_name": "",
                    "time_enabled": False,
                },
            },
        )
    else:
        r = client.post(
            "/api/new-game",
            json={
                "session_id": sid,
                "size": size,
                "rules": "chinese",
                "komi": 7.5,
                "players": {"B": HUMAN, "W": HUMAN},
            },
        )
    assert r.status_code == 200, r.text
    # 显式钉住门槛基数：开发机 ~/.katrain/config.json 里真有 count_min_moves=10。
    session.katrain.update_config("game/count_min_moves", base)
    return session


def _move(client, sid, coords=None):
    r = client.post("/api/move", json={"session_id": sid, "coords": coords, "pass_move": coords is None})
    assert r.status_code == 200, r.text
    return r.json()["state"]


def _recorded_results(client):
    return [call.kwargs["result"] for call in client.app.state.user_game_repo.create.call_args_list]


# ------------------------------------------------------------------ 状态位与门槛下发（§3.4）


@pytest.mark.parametrize("game_type", ["pvp_local", "free"])
def test_board_mode_double_pass_sets_awaiting_count(client, monkeypatch, game_type):
    session = _owned_game(client, monkeypatch, game_type=game_type, board_mode=True)
    _move(client, session.session_id, [3, 3])
    first = _move(client, session.session_id)
    assert first["awaiting_count"] is False  # 只停了一手

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is True
    assert state["end_result"]  # 回落串「终局」照样非空 —— 前端必须以 awaiting_count 为准


def test_galaxy_double_pass_never_sets_awaiting_count(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False


@pytest.mark.parametrize("size, expected", [(19, 100), (13, 47), (9, 22)])
def test_state_count_min_moves_scales_with_board_size(client, monkeypatch, size, expected):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, size=size, base=100)

    state = session.katrain.get_state()

    assert state["board_size"] == [size, size]
    assert state["count_min_moves"] == expected
