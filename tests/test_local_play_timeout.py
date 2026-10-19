"""本地对局 v2 · 超时判负契约（spec D3、附录 A `is_time_exhausted`）。

全部走真 `WebKaTrain` + 真 HTTP，`session` 的造法与打桩方式照 `tests/test_local_play_game_end.py`
（`isolated_session_factory` + `save_config` 打桩，防止改动开发机 `~/.katrain/config.json`）。
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


def _start_pvp_local(client, monkeypatch, *, time_enabled, main_time=0, byo_length=30, byo_periods=3):
    """建一个归 OWNER 的 pvp_local 会话并开局，用时设置照参数。"""
    session = client.app.state.session_manager.create_session(user_id=OWNER.id)
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    sid = session.session_id
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
                "black_name": "",
                "white_name": "",
                "time_enabled": time_enabled,
                "main_time": main_time,
                "byo_length": byo_length,
                "byo_periods": byo_periods,
            },
        },
    )
    assert r.status_code == 200, r.text
    return session


def _start_free(client, monkeypatch):
    """建一个归 OWNER 的自由对弈（`free`）会话，用来核实非 pvp_local 行为不变。"""
    session = client.app.state.session_manager.create_session(user_id=OWNER.id)
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    HUMAN = {"name": "", "player_type": "player:human", "player_subtype": "player:human"}
    r = client.post(
        "/api/new-game",
        json={
            "session_id": session.session_id,
            "size": 19,
            "rules": "chinese",
            "komi": 7.5,
            "players": {"B": HUMAN, "W": HUMAN},
        },
    )
    assert r.status_code == 200, r.text
    return session


def _recorded_results(client):
    return [call.kwargs["result"] for call in client.app.state.user_game_repo.create.call_args_list]


def test_local_geometry_pause_discards_only_paused_interval(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=10)
    katrain = session.katrain
    katrain.timer_paused = False
    katrain.start_clock()
    before = katrain.main_time_used_by_player["B"]
    katrain.last_timer_update -= 4
    assert katrain.set_local_geometry_paused(True, expected_game_id=katrain.game.game_id)
    settled = katrain.main_time_used_by_player["B"]
    assert settled >= before + 4
    assert katrain.get_state()["timer"]["paused"] is True
    katrain.last_timer_update -= 80
    katrain.update_timer()
    assert katrain.main_time_used_by_player["B"] == settled
    assert katrain.clock_exhausted() is False
    katrain.set_local_geometry_paused(False, expected_game_id=katrain.game.game_id)
    assert katrain.main_time_used_by_player["B"] == settled
    assert katrain.timer_paused is False
    katrain.timer_paused = True
    katrain.set_local_geometry_paused(True, expected_game_id=katrain.game.game_id)
    katrain.set_local_geometry_paused(False, expected_game_id=katrain.game.game_id)
    assert katrain.get_state()["timer"]["paused"] is True


def test_geometry_callback_pauses_only_current_bound_physical_local_game(client, monkeypatch):
    from katrain.web.server import _set_bound_local_geometry_pause

    session = _start_pvp_local(client, monkeypatch, time_enabled=True)
    app = client.app
    app.state.vision = types.SimpleNamespace(bound_session_id=session.session_id, stop=lambda: None)
    controller = types.SimpleNamespace(ready_game_id=session.katrain.game.game_id, input="physical", close=lambda: None)
    session.local_confirmation_controller = controller
    controller.input = "screen"
    _set_bound_local_geometry_pause(app, True)
    assert session.katrain.local_geometry_paused is False
    controller.input = "physical"
    _set_bound_local_geometry_pause(app, True)
    assert session.katrain.local_geometry_paused is True
    controller.ready_game_id = "old-game"
    _set_bound_local_geometry_pause(app, False)
    assert session.katrain.local_geometry_paused is True


def test_timeout_judges_loss_when_clock_exhausted(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=1, byo_length=30, byo_periods=1)
    turn_player = session.katrain.next_player_info.player
    session.katrain.main_time_used_by_player[turn_player] = 60
    session.katrain.next_player_info.periods_used = 1

    r = client.post("/api/timeout", json={"session_id": session.session_id})

    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["end_result"] == f"{'W' if turn_player == 'B' else 'B'}+T"
    assert _recorded_results(client) == [state["end_result"]]


def test_move_after_clock_exhausted_judges_loss_before_changing_turn(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=1, byo_length=30, byo_periods=1)
    turn_player = session.katrain.next_player_info.player
    session.katrain.main_time_used_by_player[turn_player] = 60
    session.katrain.next_player_info.periods_used = 1

    r = _confirm(client, session)

    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["end_result"] == f"{'W' if turn_player == 'B' else 'B'}+T"
    assert state["stones"] == []  # 超时后提交的那颗子没有落上去
    assert _recorded_results(client) == [state["end_result"]]


def test_move_cannot_resume_local_game_after_timeout_result(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=1, byo_length=30, byo_periods=1)
    turn_player = session.katrain.next_player_info.player
    session.katrain.main_time_used_by_player[turn_player] = 60
    session.katrain.next_player_info.periods_used = 1
    first = _confirm(client, session)
    assert first.status_code == 200, first.text
    state = first.json()["state"]

    second = _confirm(client, session, request_id="resume-ended-game")

    assert second.status_code == 409, second.text
    assert "no longer current" in second.json()["detail"]
    assert _recorded_results(client) == [state["end_result"]]


def test_timeout_rejected_with_409_while_main_time_remains(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=1, byo_length=30, byo_periods=1)

    r = client.post("/api/timeout", json={"session_id": session.session_id})

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "time_not_expired"
    assert detail["state"]  # 附带最新局面，前端拿它重算钟
    assert session.katrain.game.end_result in (None, "")
    assert _recorded_results(client) == []


def test_timeout_does_not_overwrite_an_already_ended_game(client, monkeypatch):
    session = _start_pvp_local(client, monkeypatch, time_enabled=True, main_time=1, byo_length=30, byo_periods=1)
    resign_r = client.post("/api/resign", json={"session_id": session.session_id, "color": "B"})
    assert resign_r.status_code == 200, resign_r.text
    resigned_result = resign_r.json()["state"]["end_result"]
    assert resigned_result  # W+R

    r = client.post("/api/timeout", json={"session_id": session.session_id})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["end_result"] == resigned_result
    assert _recorded_results(client) == [resigned_result]  # 没有因为 timeout 再落一次账


def test_free_game_timeout_unchanged_regardless_of_clock(client, monkeypatch):
    session = _start_free(client, monkeypatch)

    r = client.post("/api/timeout", json={"session_id": session.session_id})

    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["end_result"].endswith("+T")
    assert _recorded_results(client) == [state["end_result"]]


def _confirm(client, session, request_id=None):
    state = session.katrain.get_state()
    client.post(
        "/api/local/ready",
        json={"session_id": session.session_id, "expected_game_id": state["game_id"], "input": "screen"},
    )
    return client.post(
        "/api/local/confirm",
        json={
            "session_id": session.session_id,
            "expected_game_id": state["game_id"],
            "expected_node_id": state["current_node_id"],
            "color": state["player_to_move"],
            "request_id": request_id or f"confirm-{state['current_node_id']}",
            "input": "screen",
            "action": "move",
            "coords": [3, 3],
        },
    )
