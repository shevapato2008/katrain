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
        # 会话是进程级的,不跟着 TestClient 走。不收掉的话它们连同各自的引擎会活到本次
        # pytest 结束 —— 全量跑时那是**跨文件污染**,而且落在看着毫不相干的文件里。
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def _seat_two_humans(client, sid):
    """两边都坐人。

    **不是可有可无的布景**：只要有一边是 AI，落子就会开一条后台线程去生成回招
    （`interface.py` 的 `_do_ai_move_and_broadcast`），而那条线程活得比本条用例长。
    全量跑时它会在后面某个**看着毫不相干**的文件里冒出来 —— 实测把
    `tests/web_ui/test_ladder_injection.py::test_new_game_serialized_against_inflight_ai_move`
    打红了（它 monkeypatch 了全局 `generate_ai_move`，被我这边的残留线程抢先写了
    `captured`）。游客跟 AI 对弈那条链由真浏览器那一关证（AI 回招经 WS 推回来），
    这里要证的是鉴权，两件事分开。
    """

    for bw, name in (("B", "游客"), ("W", "游客2")):
        r = client.post(
            "/api/player",
            json={"session_id": sid, "bw": bw, "player_type": "player:human", "player_subtype": "human", "name": name},
        )
        assert r.status_code == 200, r.text


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

    _seat_two_humans(client, sid)

    r = client.get("/api/state", params={"session_id": sid})
    assert r.status_code == 200, r.text

    r = client.post("/api/move", json={"session_id": sid, "coords": [3, 3], "pass_move": False})
    assert r.status_code == 200, r.text
    assert len(r.json()["state"]["history"]) >= 1


def test_guest_can_undo_in_a_free_game(client):
    """自由对弈的悔棋对游客同样开放（升降级局另有 403，不在这条路上）。"""

    sid = _guest_session(client)
    assert client.post("/api/new-game", json={"session_id": sid}).status_code == 200
    _seat_two_humans(client, sid)
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
    # 2026-08-27 补上鉴权的那四个：在此之前它们**完全不看调用者**，任何人拿到 session_id
    # 就能改别人在跑的对局的配置和座位（session_id 也不用猜 ——
    # `GET /api/v1/games/active/multiplayer` 至今不鉴权，返回的正是全部多人局的 id）。
    assert client.post("/api/config", json={"session_id": sid, "setting": "timer/main_time", "value": 1}).status_code == 401
    assert client.post("/api/config/bulk", json={"session_id": sid, "updates": {"timer/paused": True}}).status_code == 401
    assert client.post("/api/player", json={"session_id": sid, "bw": "W", "player_type": "player:ai"}).status_code == 401
    assert client.post("/api/player/swap", json={"session_id": sid}).status_code == 401
    assert client.get("/api/config", params={"session_id": sid, "setting": "ai/ai:human"}).status_code == 401


def test_a_claimed_session_still_refuses_a_different_account(client):
    """「是不是这局的参与者」这一格没有被顺手放掉。"""

    session = client.app.state.session_manager.create_session(user_id=7)
    sid = session.session_id
    stranger = types.SimpleNamespace(id=999, username="stranger", uuid="u-999")
    client.app.dependency_overrides[get_current_user_optional] = lambda: stranger
    try:
        assert client.get("/api/state", params={"session_id": sid}).status_code == 403
        assert client.post("/api/new-game", json={"session_id": sid}).status_code == 403
        assert client.post("/api/player/swap", json={"session_id": sid}).status_code == 403
        assert client.post(
            "/api/config", json={"session_id": sid, "setting": "timer/main_time", "value": 1}
        ).status_code == 403
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


# --- 放开对弈，不等于放开分析 -----------------------------------------------------


def _analysis_bearing_fields(state):
    """state 里所有承载引擎分析结论的位置。"""

    return {
        "analysis": state.get("analysis"),
        "commentary": state.get("commentary"),
        "history_scores": [h.get("score") for h in state.get("history", [])],
        "history_winrates": [h.get("winrate") for h in state.get("history", [])],
        "stone_score_losses": [s[2] for s in state.get("stones", [])],
    }


def test_an_unclaimed_session_is_never_handed_analysis(client):
    """游客能下棋，但拿不到引擎的胜率/目差/候选点。

    这一条守的是反作弊：升降级对弈期间禁止分析（`guard_user_has_no_pending_ranked_game`），
    而那道闸是按 user_id 判的 —— 一个正在下升降级的人只要开一个不带凭据的窗口、把当前
    局面按手顺摆出来，就能从这里读到引擎的最佳点。`/api/analysis/*` 与 `/api/v1/hint`
    至今都要求登录，这条只是把同一条线补到 `get_state` 上。
    """

    sid = _guest_session(client)
    assert client.post("/api/new-game", json={"session_id": sid}).status_code == 200
    _seat_two_humans(client, sid)
    state = client.post("/api/move", json={"session_id": sid, "coords": [3, 3], "pass_move": False}).json()["state"]

    # 服务端如实说出这一局交不交付分析 —— 前端靠它置灰那三个键，不靠自己推。
    assert state["analysis_delivered"] is False

    fields = _analysis_bearing_fields(state)
    assert fields["analysis"] is None
    assert fields["commentary"] == ""
    assert all(v is None for v in fields["history_scores"])
    assert all(v is None for v in fields["history_winrates"])
    assert all(v is None for v in fields["stone_score_losses"])
    # 同一份状态经 GET /api/state 再取一次也一样 —— 两条路读的是同一个 get_state。
    assert _analysis_bearing_fields(client.get("/api/state", params={"session_id": sid}).json()["state"]) == fields


def test_a_claimed_session_still_gets_its_analysis(client):
    """变异闸：把交付条件写成「一律不交付」时这条必须红。登录用户的自由局照旧有分析字段。"""

    session = client.app.state.session_manager.create_session(user_id=7)
    assert session.katrain.deliver_analysis is True
    state = session.katrain.get_state()
    assert state["analysis_delivered"] is True
    # 引擎在测试里是 NullEngine，不会真的算出胜率；能证明的是这些位置**没有被抹掉**：
    # `history` 每项都带 score/winrate 两个键，`stones` 每项都是四格。
    assert all("score" in h and "winrate" in h for h in state["history"])
    assert all(len(s) == 4 for s in state["stones"])
    assert state["commentary"] is not None


def test_guest_sgf_load_never_runs_a_whole_game_scan(client, monkeypatch):
    """灌 SGF 对游客是通的（摆谱/打谱要用），但不给它做全盘扫描。

    `skip_analysis` 默认 False，一份 400 手的棋谱就是 400 次引擎查询，而这条路不需要任何
    凭据、也不占任何按 user 记账的租约 —— 谁都能无上限地点。落子那条路每手一次、有一局
    的上限，是另一回事。
    """

    seen = {}

    sid = _guest_session(client)
    # 从**活对象**上取类，不要 `from katrain.web.interface import WebKaTrain`：
    # `tests/web_ui/conftest.py` 会把 `sys.modules["katrain.web.interface"]` 整个换成
    # MagicMock（进程级、collect 期就生效），全量跑时按模块路径导入拿到的是那个替身，
    # patch 上去对真正在跑的类毫无作用 —— 这条用例会在单跑时绿、全量跑时红。
    katrain_cls = type(client.app.state.session_manager.get_session(sid).katrain)
    real_load = katrain_cls._do_load_sgf

    def spy(self, sgf, skip_initial_analysis=False, **kwargs):
        seen["skip"] = skip_initial_analysis
        return real_load(self, sgf, skip_initial_analysis=skip_initial_analysis, **kwargs)

    monkeypatch.setattr(katrain_cls, "_do_load_sgf", spy)
    r = client.post("/api/sgf/load", json={"session_id": sid, "sgf": "(;GM[1]FF[4]SZ[19];B[dd];W[pp])"})
    assert r.status_code == 200, r.text
    assert seen["skip"] is True


def test_no_unauthenticated_endpoint_hands_out_an_unclaimed_session_id(client):
    """「匿名会话的 id 不会漏给第三方」是放行无主会话的承重前提，钉在操作数这一侧。

    `GET /api/v1/games/active/multiplayer` 至今不鉴权。它今天只列 `player_b_id is not None`
    的局，所以匿名局不在其中 —— 但那是 `session.py` 里一句可以被改掉的过滤条件，
    改掉的那天这条会红。
    """

    guest_sid = _guest_session(client)
    manager = client.app.state.session_manager
    multiplayer = manager.create_multiplayer_session(player_b_id=1, player_w_id=2)

    r = client.get("/api/v1/games/active/multiplayer")
    assert r.status_code == 200, r.text
    listed = {row["session_id"] for row in r.json()}
    # 正对照：这条端点确实在返回东西，不是空列表或挂了。
    assert multiplayer.session_id in listed
    assert guest_sid not in listed


def test_get_config_refuses_keys_that_are_not_session_settings(client):
    """`GET /api/config` 读的是**进程的整份 config**，不是「这个会话的设置」。

    归属闸挡不住这一条：会话的主人本人问同样读得到 `server/database_url` 和
    `contribute/password`。所以那里是白名单 —— 漏写一个黑名单条目 = 漏一个密钥，
    漏写一个白名单条目 = 某个设置读不到（会被立刻发现）。
    """

    sid = _guest_session(client)  # 无人认领，归属闸放行；挡下来的只能是白名单
    assert client.get("/api/config", params={"session_id": sid, "setting": "ai/ai:human"}).status_code == 200
    for secret in ("server/database_url", "contribute/password", "contribute/username", "engine/command"):
        r = client.get("/api/config", params={"session_id": sid, "setting": secret})
        assert r.status_code == 403, f"{secret} -> {r.status_code} {r.text}"


def test_guest_can_still_configure_its_own_session(client):
    """反向：这四个端点对游客自己的匿名会话必须照常放行（游客开局链路要用它们）。"""

    sid = _guest_session(client)
    assert client.post(
        "/api/config", json={"session_id": sid, "setting": "timer/main_time", "value": 1}
    ).status_code == 200
    assert client.post(
        "/api/config/bulk", json={"session_id": sid, "updates": {"timer/paused": True}}
    ).status_code == 200
    assert client.post("/api/player/swap", json={"session_id": sid}).status_code == 200
