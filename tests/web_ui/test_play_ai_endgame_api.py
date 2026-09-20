"""对弈·AI/升降级赛道的 HTTP 端点测试(superpowers/tracks/kiosk-go-play-ai)。

会话一律手工注入、katrain 是 MagicMock(`tests/web_ui/conftest.py` 把 interface 换成了替身):
这里证的是**端点把什么交给了 katrain、按什么顺序**;katrain 自己怎么判在 tests/test_play_ai_endgame.py 用真类证。
"""

import threading
import uuid
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from katrain.web.models import EndgameConflict
from katrain.web.server import create_app


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory  # 必须在 TestClient 之前:lifespan 用它重建全部 repo
    with TestClient(app) as c:
        yield c
        for s in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager._sessions.pop(s.session_id, None)


def _make_user(client, name: str):
    from passlib.context import CryptContext

    unique = f"{name}-{uuid.uuid4().hex[:8]}"
    hashed = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password")
    user = client.app.state.user_repo.create_user(unique, hashed)
    return user["id"], unique


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _inject_session(client, *, user_id=None, player_b_id=None, player_w_id=None, game_type="free"):
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = user_id
    session.player_b_id = player_b_id
    session.player_w_id = player_w_id
    session.mode = "play"
    session.game_type = game_type
    session.lock = threading.Lock()
    session.sockets = set()
    session.last_access = 0.0
    session.last_state = {"end_result": None}
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session.game_ended = False
    session._recorded = False

    katrain = MagicMock()
    katrain.game_type = game_type
    katrain.get_sgf.return_value = "(;FF[4]SZ[19];B[pd])"
    katrain.get_state.return_value = {"end_result": None, "history": []}
    katrain.game.end_result = None
    session.katrain = katrain
    client.app.state.session_manager._sessions[session.session_id] = session
    return session


# ---------------------------------------------------------------- N21


def test_lobby_resign_is_decided_by_the_seat_of_the_player_who_pressed_it(client):
    black_id, _ = _make_user(client, "alice")
    white_id, white_name = _make_user(client, "bob")
    session = _inject_session(client, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, white_name))

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign", "W")


def test_single_player_resign_leaves_the_loser_to_the_seats(client):
    """正对照:单机局不传认输方,交给 `_do_resign` 从座位推。"""
    session = _inject_session(client)

    resp = client.post("/api/resign", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("resign")


# ---------------------------------------------------------------- r1 端点接线(真判定在 tests/test_play_ai_endgame.py)


def test_a_move_refused_by_the_runtime_is_a_409_not_a_500(client):
    session = _inject_session(client)

    def refuse(action, *args, **kwargs):
        if action == "play":
            raise EndgameConflict("already_ended")

    session.katrain.side_effect = refuse

    resp = client.post("/api/move", json={"session_id": session.session_id, "coords": [3, 3]})

    assert resp.status_code == 409, resp.text
    assert "already over" in resp.json()["detail"]
    session.katrain.assert_any_call("play", (3, 3), guard=True)


class _PlatformGateway:
    """跨平台网关替身:`resign` 远端成功后走本地 `_local_resign`(即 `session.katrain("resign")`)。
    `local_conflict=True` 模拟本地这一局早已结束 —— 远端认输成功,本地写入撞上 `already_ended`。"""

    def __init__(self, session, local_conflict):
        self.session = session
        self.local_conflict = local_conflict
        self.resigned = []

    def is_platform_game(self, session_id):
        return session_id == self.session.session_id

    async def resign(self, session_id, user_id):
        self.resigned.append((session_id, user_id))
        if self.local_conflict:
            raise EndgameConflict("already_ended")
        self.session.katrain("resign")
        return {"status": "ok"}


@pytest.mark.parametrize("where", ["lobby", "platform"])
@pytest.mark.parametrize("already_ended", [False, True])
def test_resign_writes_one_ledger_row_or_none(client, monkeypatch, where, already_ended):
    """评审 r1 M4 + S8:认输真的写出了终局 → 多人局恰好记一行、广播一次 `game_end`;撞上已结束的局 → 200 空操作,
    不记、不广播。平台局(OGS / 星阵)也走多人局落账那一行 —— `wrote` 若只在非平台分支里赋值,这里就是 500。"""
    me, my_name = _make_user(client, "resigner")
    if where == "lobby":
        other, _ = _make_user(client, "opponent")
        session = _inject_session(client, user_id=me, player_b_id=me, player_w_id=other)
        if already_ended:

            def refuse(action, *args, **kwargs):
                if action == "resign":
                    raise EndgameConflict("already_ended")

            session.katrain.side_effect = refuse
    else:
        session = _inject_session(client, user_id=me, player_b_id=me, player_w_id=-1)
        client.app.state.platform_gateway = _PlatformGateway(session, local_conflict=already_ended)
    client.app.state.game_repo = MagicMock()
    sent = []
    monkeypatch.setattr(
        client.app.state.session_manager, "_schedule_broadcast", lambda s, payload: sent.append(payload)
    )

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, my_name))

    assert resp.status_code == 200, resp.text
    expected_rows = 0 if already_ended else 1
    assert client.app.state.game_repo.record_multiplayer_game.call_count == expected_rows
    assert [p["type"] for p in sent if p.get("type") == "game_end"] == ["game_end"] * expected_rows


def test_count_uses_the_same_atomic_result_writer(client):
    """Count must not bypass the result lock used by resignation and AI commits."""
    session = _inject_session(client)
    session.katrain.config.return_value = 0
    session.katrain.game.current_node.score = 3.5
    session.katrain._commit_end_state.side_effect = EndgameConflict("already_ended")

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 409, resp.text
    session.katrain._commit_end_state.assert_called_once()
    assert session.katrain._commit_end_state.call_args.args == ("B+3.5",)


@pytest.mark.parametrize("action", ["resign", "timeout"])
def test_already_ended_single_player_request_does_not_retry_recording(client, action):
    """An already-ended response is a no-op even if a prior save has not completed."""
    me, my_name = _make_user(client, "already-ended-solo")
    session = _inject_session(client, user_id=me)
    session.katrain.game.end_result = "W+R"
    session.katrain.get_state.return_value = {"end_result": "W+R", "history": []}

    def refuse(received_action, *args, **kwargs):
        if received_action == action:
            raise EndgameConflict("already_ended")

    session.katrain.side_effect = refuse
    resp = client.post(f"/api/{action}", json={"session_id": session.session_id}, headers=_login(client, my_name))

    assert resp.status_code == 200, resp.text
    # Recording always starts by obtaining this game's SGF; no-op requests must not enter it.
    session.katrain.get_sgf.assert_not_called()
    assert session._recorded is False


# ---------------------------------------------------------------- N23


def test_count_refuses_with_the_threshold_the_session_reports(client):
    """门槛只有一个来源:`get_state()` 下发的 `count_min_moves`(前端读的也是它)。"""
    session = _inject_session(client)
    session.katrain.config.return_value = 100
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 21, "count_min_moves": 22}

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == {
        "code": "below_min_moves",
        "message": "Cannot count before 22 moves",
    }


# ---------------------------------------------------------------- A12


def _countable(session):
    session.katrain.get_state.return_value = {"end_result": None, "history": [{}] * 101, "count_min_moves": 100}
    session.katrain.game.current_node.score = None


def test_count_fills_the_missing_score_before_counting(client):
    session = _inject_session(client)
    _countable(session)

    def fill_score(*_args, **_kwargs):
        session.katrain.game.current_node.score = 2.5
        return 2.5

    session.katrain.ensure_current_score.side_effect = fill_score

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "B+2.5"
    counted = session.katrain.game.current_node
    # C2:补的、数的、写的都是 await 之前取的那一手;写入只经唯一写入口(在对局提交锁里复核)
    session.katrain.ensure_current_score.assert_called_once_with(node=counted)
    session.katrain._commit_end_state.assert_called_once_with("B+2.5", node=counted, fill_pending=False)


def test_a_count_refused_by_the_runtime_is_a_409(client):
    """`_commit_end_state` 在锁里发现局面已结束 / 变了 → 处理器回 409,不是 500、也不是 200。"""
    session = _inject_session(client)
    _countable(session)
    session.katrain.ensure_current_score.return_value = 2.5
    session.katrain.game.current_node.score = 2.5
    session.katrain._commit_end_state.side_effect = EndgameConflict("position_changed")

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Position changed while counting"


def test_count_still_says_why_when_no_score_can_be_had(client):
    """补不出来(升降级局 / 引擎不可用)时照旧 400,detail 原样 —— 前端靠它说对原因。"""
    session = _inject_session(client)
    _countable(session)
    session.katrain.ensure_current_score.return_value = None

    resp = client.post("/api/count/request", json={"session_id": session.session_id})

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "analysis_pending"
    assert resp.json()["detail"]["message"].startswith("Analysis not available")


# ---------------------------------------------------------------- r1 C1 超时绑定(端点接线)


def test_timeout_passes_the_expected_turn_and_maps_a_refusal_to_409(client):
    session = _inject_session(client)

    def refuse(action, *args, **kwargs):
        if action == "timeout":
            raise EndgameConflict("stale_turn")

    session.katrain.side_effect = refuse

    resp = client.post(
        "/api/timeout",
        json={"session_id": session.session_id, "expected_game_id": "g", "expected_node_id": 5, "color": "W"},
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "timeout rejected: stale_turn"
    session.katrain.assert_any_call("timeout", expected_game_id="g", expected_node_id=5, color="W")


@pytest.mark.parametrize("conflict", [None, "already_ended"])
def test_an_unbound_timeout_keeps_the_old_call_and_an_ended_game_is_a_no_op(client, conflict):
    """galaxy 的旧调用只带 session_id:照旧 `katrain("timeout")`;撞上已结束的局是 200 空操作,不弹红条。"""
    session = _inject_session(client)
    if conflict is not None:

        def refuse(action, *args, **kwargs):
            if action == "timeout":
                raise EndgameConflict(conflict)

        session.katrain.side_effect = refuse

    resp = client.post("/api/timeout", json={"session_id": session.session_id})

    assert resp.status_code == 200, resp.text
    session.katrain.assert_any_call("timeout")


@pytest.mark.parametrize(
    "fields",
    [
        {"expected_node_id": 5},
        {"expected_game_id": "g"},
        {"color": "W"},
        {"expected_game_id": "g", "expected_node_id": 5},
        {"expected_game_id": "g", "color": "W"},
        {"expected_node_id": 5, "color": "W"},
        {"expected_game_id": "g", "expected_node_id": 5, "color": "X"},
    ],
)
def test_timeout_expectations_come_all_or_nothing(client, fields):
    session = _inject_session(client)

    resp = client.post("/api/timeout", json={"session_id": session.session_id, **fields})

    assert resp.status_code == 422, resp.text
