# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs — same reason as tests/test_local_play_setup.py: kivymd's
# first import from Starlette's background portal thread creates a real SDL2/Cocoa
# window off the main thread and aborts the process on macOS.
import kivymd.app  # noqa: F401

import types

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    # 必须在进 `TestClient` **之前**设：lifespan 会用它建全部 repo 并跑 `init_db()`。
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        yield c


def _guest_session(client):
    """未登录建会话 —— 三个 id 全 None，也就是「无人认领」。"""

    r = client.post("/api/session", json={})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    session = client.app.state.session_manager.get_session(sid)
    assert (session.user_id, session.player_b_id, session.player_w_id) == (None, None, None)
    return sid


# --- 游客能把自由对弈走完 -------------------------------------------------------


def test_guest_walks_the_whole_free_play_chain(client):
    """galaxy 的「自由对弈设置 → 对局」按顺序打的就是这几个端点。

    在这之前它停在第三步：`/api/new-game` 挂的是**必需**的 `get_current_user`，游客拿到
    401 `{"detail":"Not authenticated"}`，而前两步已经成功 —— 于是每点一次都在服务端留下
    一个再也用不了的匿名会话壳。这条用例从头走到落子，任何一步退回鉴权都会红。
    """

    sid = _guest_session(client)

    r = client.post(
        "/api/config/bulk",
        json={"session_id": sid, "updates": {"timer/main_time": 0, "timer/byo_length": 0, "timer/paused": True}},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/new-game",
        json={"session_id": sid, "size": 19, "handicap": 0, "komi": 6.5, "rules": "japanese"},
    )
    assert r.status_code == 200, r.text

    for bw, ptype, subtype, name in (
        ("B", "player:human", "human", "游客"),
        ("W", "player:ai", "ai:human", "AI (Human-like)"),
    ):
        r = client.post(
            "/api/player",
            json={"session_id": sid, "bw": bw, "player_type": ptype, "player_subtype": subtype, "name": name},
        )
        assert r.status_code == 200, r.text

    r = client.get("/api/state", params={"session_id": sid})
    assert r.status_code == 200, r.text

    r = client.post("/api/move", json={"session_id": sid, "coords": [3, 3], "pass_move": False})
    assert r.status_code == 200, r.text
    assert len(r.json()["state"]["history"]) >= 1


def test_guest_can_undo_in_a_free_game(client):
    """自由对弈的悔棋对游客同样开放（升降级局另有 403，不在这条路上）。"""

    sid = _guest_session(client)
    assert client.post("/api/new-game", json={"session_id": sid}).status_code == 200
    assert client.post("/api/move", json={"session_id": sid, "coords": [3, 3], "pass_move": False}).status_code == 200
    r = client.post("/api/undo", json={"session_id": sid, "n_times": 1})
    assert r.status_code == 200, r.text


# --- 放开的只是「没有主人」的那一类 ---------------------------------------------


def test_a_claimed_session_still_refuses_a_credential_less_caller(client):
    """变异闸：把放行条件写成「一律放行」而不是「无人认领才放行」时，这条必须红。"""

    session = client.app.state.session_manager.create_session(user_id=7)
    sid = session.session_id

    assert client.get("/api/state", params={"session_id": sid}).status_code == 401
    assert client.post("/api/new-game", json={"session_id": sid}).status_code == 401
    assert client.post("/api/move", json={"session_id": sid, "coords": [3, 3], "pass_move": False}).status_code == 401
    assert client.post("/api/undo", json={"session_id": sid, "n_times": 1}).status_code == 401


def test_a_claimed_session_still_refuses_a_different_account(client):
    """「是不是这局的参与者」这一格没有被顺手放掉。"""

    session = client.app.state.session_manager.create_session(user_id=7)
    sid = session.session_id
    stranger = types.SimpleNamespace(id=999, username="stranger", uuid="u-999")
    client.app.dependency_overrides[get_current_user_optional] = lambda: stranger
    try:
        assert client.get("/api/state", params={"session_id": sid}).status_code == 403
        assert client.post("/api/new-game", json={"session_id": sid}).status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_current_user_optional, None)


def test_rated_ladder_still_requires_an_account(client):
    """升降级对弈没有跟着放开：段位记在账号上，没有账号就无处可记。"""

    assert client.get("/api/v1/ai-ladder/status").status_code == 401
    r = client.post(
        "/api/v1/ai-ladder/start",
        json={"color": "black", "time_enabled": False, "main_time": 0, "byo_length": 0, "byo_periods": 0},
    )
    assert r.status_code == 401


# --- WebSocket：AI 的每一手只经这条通道推过来 -----------------------------------


def test_guest_websocket_connects_to_its_own_anonymous_session(client):
    """这条是承重的：AI 落子由服务端后台线程广播，WS 连不上 = 棋盘从第一手起就不动了。"""

    sid = _guest_session(client)
    with client.websocket_connect(f"/ws/{sid}") as ws:
        assert ws.receive_json()["type"] == "game_update"


def test_websocket_on_a_claimed_session_still_rejects_a_credential_less_client(client):
    session = client.app.state.session_manager.create_session(user_id=7)
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/{session.session_id}") as ws:
            ws.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_still_rejects_a_bad_credential(client):
    """「没带凭据」放行，不等于「带了坏凭据」也放行。"""

    sid = _guest_session(client)
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/{sid}?token=not-a-real-token") as ws:
            ws.receive_json()
    assert excinfo.value.code == 1008


def test_anonymous_socket_is_told_it_cannot_chat_and_stays_alive(client):
    """身份两项由服务端填，游客没有可填的身份 —— 拒绝并说一句，而不是让这条通道当场死掉。"""

    def _next(ws, wanted, limit=5):
        """跳过与本条无关的房间广播（`spectator_count` 会先到）。"""

        for _ in range(limit):
            frame = ws.receive_json()
            if frame.get("type") == wanted:
                return frame
        raise AssertionError(f"never received a {wanted!r} frame")

    sid = _guest_session(client)
    with client.websocket_connect(f"/ws/{sid}") as ws:
        _next(ws, "game_update")
        ws.send_json({"type": "chat", "text": "hi"})
        assert _next(ws, "error") == {"type": "error", "code": "chat_requires_identity"}
        ws.send_json({"type": "ping"})
        _next(ws, "pong")
