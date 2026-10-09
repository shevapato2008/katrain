"""大厅那三条边界:谁能看见对局、在线列表泄漏多少字段、邀请能不能被凭空捏造。

三条的共同点是**从界面上完全看不出来** —— 前端每一处都老老实实带着 token,
所以点着用永远正常;要看见它们只能直接打接口。

1. `GET /games/active/multiplayer` **完全不鉴权**,而它吐的是 `session_id`。
   `test_game_termination_and_chat_identity.py` 的开头就写着这条是那条利用链的另一半
   (「session_id 也不需要猜:这条端点至今不带鉴权」)。上游已经用
   `guard_session_terminator` 封了判负那一半,这里补上枚举这一半。

2. `GET /users/online` 的 `response_model` 是 `User`,里面带着 `uuid`
   (models.py 的注释写明是发给 KataGo 用的标识)、`credits`、`is_admin`、`net_wins`
   —— 任何登录用户都能连这些一起拉走,而前端一个都没用到。

3. `accept_invite` 拿客户端给的**任意** `target_id` 直接建局并把 `match_found`
   推给对方 ⇒ 任何登录用户都能把任意在线用户拽进一局棋,被拽的人一次点击都没有过。
   ⚠️ 「不是自己 + 对方在线」这类校验是**装饰品**:攻击者传的本来就是在线用户。
   判别位只能是「他到底邀请过我没有」。

每条否定用例都配正对照 —— 没有正对照,「被守卫挡住」和「这条路本来就不通」分不开。

**否定用例怎么同步:** WS 是异步的,「什么都没发生」不能靠等超时。这里用一个
**确定会回消息**的后续请求(邀请一个不存在的人 → `error`)当屏障:同一条连接顺序处理,
那条 `error` 一旦到手,前面那条 `accept_invite` 就一定已经处理完了;而**第一条收到的
消息就是它本身**,也就同时证明了前面没有 `match_found`。
"""

import uuid
import importlib.util
import threading
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.server import create_app


@pytest.fixture
def app(tmp_path):
    """独立的库 + `settings.DATABASE_URL` 用完必还(见同目录 termination 那份的教训)。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository

    db_path = tmp_path / "lobby_boundaries.db"
    previous_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite:///{db_path}"

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    # 注入必须落在 `session_factory` 上 —— lifespan 会用它重建六个 repo。
    application.state.session_factory = Session
    application.state.user_repo = SQLAlchemyUserRepository(Session)
    application.state.game_repo = GameRepository(Session)
    try:
        yield application
    finally:
        settings.DATABASE_URL = previous_url
        engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _make_user(app, name: str):
    from passlib.context import CryptContext

    unique = f"{name}-{uuid.uuid4().hex[:8]}"
    hashed = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password")
    user = app.state.user_repo.create_user(unique, hashed)
    return user["id"], unique


def _token(client, username: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── 1. 进行中的对局列表 ────────────────────────────────────────────────────────


def test_active_multiplayer_requires_auth(client, app):
    _make_user(app, "alice")

    anonymous = client.get("/api/v1/games/active/multiplayer")
    assert anonymous.status_code == 401, anonymous.text

    # 正对照:带上凭据这条端点是通的 —— 否则 401 可能只是这条路本来就不通。
    token = _token(client, _make_user(app, "bob")[1])
    ok = client.get("/api/v1/games/active/multiplayer", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200, ok.text
    assert isinstance(ok.json(), list)


# ── 2. 在线列表的字段面 ────────────────────────────────────────────────────────


def test_follow_lists_do_not_leak_uuid_credits_or_admin(client, app):
    """`/followers` 和 `/following` 和 `/online` 是**同一种泄露**。

    🔴 它们是漏网的:`/online` 2026-08-25 已经收窄成 `OnlineUser`,而**同一个文件里
    上面十一行**的这两条原样留着 `response_model=List[User]` —— 同一种泄露、隔着两个函数。
    ⇒ 判据:收窄一个响应模型时,把同一个文件里回同一种东西的端点**一起数一遍**;
    「我改的这一处」和「这一类」不是同一件事。
    """
    _, alice = _make_user(app, "flw_alice")
    _, bob = _make_user(app, "flw_bob")
    token = _token(client, bob)

    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]
    bob_id = app.state.user_repo.get_user_by_username(bob)["id"]
    app.state.user_repo.follow_user(bob_id, alice_id)

    for path, who in (("/api/v1/users/following", alice), ("/api/v1/users/followers", bob)):
        headers = {"Authorization": f"Bearer {token if path.endswith('following') else _token(client, alice)}"}
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert rows, f"{path} 是空的 —— 下面的断言会全部空过"
        row = rows[0]
        for leaked in ("uuid", "credits", "is_admin", "net_wins"):
            assert leaked not in row, f"{leaked} 不该出现在 {path} 里:{row}"
        # 正对照:面板真正要用的那几个还在,别收窄过头
        # (`galaxy/components/FriendsPanel.tsx` 用 id / username / rank / avatar_url)。
        assert row["username"] == who
        assert "rank" in row and "avatar_url" in row


def test_online_users_does_not_leak_uuid_credits_or_admin(client, app):
    """收窄的是**响应模型**,不是端点里手挑字段 —— 手挑的写法在 `User` 以后加字段时会漏。"""
    _, alice = _make_user(app, "alice")
    _, bob = _make_user(app, "bob")
    token = _token(client, bob)

    # 让 alice 在线(直接动 lobby_manager,不用真开 WS)。
    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]
    app.state.lobby_manager.add_user(alice_id, object())

    resp = client.get("/api/v1/users/online", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert rows, "alice 应该在线 —— 空列表会让下面的断言全部空过"

    row = rows[0]
    for leaked in ("uuid", "credits", "is_admin", "net_wins"):
        assert leaked not in row, f"{leaked} 不该出现在在线列表里:{row}"
    # 正对照:大厅真正要用的那几个还在,别收窄过头。
    assert row["username"] == alice
    assert "rank" in row and "elo_points" in row


def test_public_roster_uses_ai_ladder_rank_and_room_presence(client, app):
    from katrain.web.core.models_db import AiLadderProfile
    from katrain.web.core.pvp_lobby_bots import bot_id, bot_name, playable_rungs

    rung = playable_rungs()[0]
    alice_id, alice = _make_user(app, "placed")
    bob_id, bob = _make_user(app, "unplaced")
    db = app.state.session_factory()
    try:
        db.add(AiLadderProfile(user_id=alice_id, ai_ladder_rung=rung.rung, placement_lo=1,
                               placement_hi=41, placement_completed=5))
        db.commit()
    finally:
        db.close()
    app.state.lobby_manager.add_user(bob_id, object())
    game = app.state.session_manager.create_multiplayer_session(alice_id, bot_id(rung.rung, 1),
                                                                  b_name=alice, w_name=bot_name(rung.rung, 1),
                                                                  skip_initial_analysis=True)
    class FakeRuntime:
        def public_online_rows(self):
            return [{"id": bot_id(rung.rung, 1), "username": bot_name(rung.rung, 1),
                     "ladder_rung": rung.rung, "rank_label": rung.rank_label, "presence": "playing"}]
    original_runtime = app.state.pvp_lobby_bots
    app.state.pvp_lobby_bots = FakeRuntime()

    token = _token(client, bob)
    headers = {"Authorization": f"Bearer {token}"}
    rows = client.get("/api/v1/users/online", headers=headers).json()
    by_id = {row["id"]: row for row in rows}
    assert by_id[alice_id]["ladder_rung"] == rung.rung
    assert by_id[alice_id]["rank_label"] == rung.rank_label
    assert by_id[alice_id]["presence"] == "playing"
    assert by_id[bob_id]["ladder_rung"] is None
    assert by_id[bob_id]["rank_label"] is None
    assert by_id[bob_id]["presence"] == "idle"
    for row in rows:
        assert not {"kind", "is_bot", "uuid", "credits", "hashed_password"}.intersection(row)

    games = client.get("/api/v1/games/active/multiplayer", headers=headers).json()
    found = next(row for row in games if row["session_id"] == game.session_id)
    assert found["player_b_id"] == alice_id and found["player_w_id"] == bot_id(rung.rung, 1)
    assert found["player_b_rung"] == found["player_w_rung"] == rung.rung
    assert found["player_b_rank_label"] == found["player_w_rank_label"] == rung.rank_label
    assert found["player_w"] == bot_name(rung.rung, 1)
    assert not {"kind", "is_bot", "uuid", "credits", "hashed_password"}.intersection(found)
    app.state.pvp_lobby_bots = original_runtime


# ── 3. 邀请不能凭空捏造 ────────────────────────────────────────────────────────


def _ws(client, token: str):
    return client.websocket_connect(f"/ws/lobby?token={token}")


def _next(ws):
    """取下一条**有意义**的消息,只跳过 `lobby_update`。

    有人进出大厅时服务端会广播在线人数,它会插在任何回复前面。
    ⚠️ 只跳这一种:要是顺手写成「跳过所有不认识的类型」,否定用例里的
    `match_found` 就会被一起跳掉 —— 那条断言从此永远绿,而它正是要抓的东西。
    """
    for _ in range(20):
        msg = ws.receive_json()
        if msg.get("type") != "lobby_update":
            return msg
    raise AssertionError("20 条里全是 lobby_update,没等到实质消息")


def _place(app, user_id, rung):
    from katrain.web.core.models_db import AiLadderProfile

    db = app.state.session_factory()
    try:
        db.add(AiLadderProfile(user_id=user_id, ai_ladder_rung=rung, placement_lo=1,
                               placement_hi=41, placement_completed=5))
        db.commit()
    finally:
        db.close()


def test_unplaced_free_matchmaking_requires_placement(client, app):
    _, alice = _make_user(app, "unplaced_free")
    with _ws(client, _token(client, alice)) as ws:
        ws.send_json({"type": "start_matchmaking"})
        ws.send_json({"type": "invite", "target_id": 999999})  # deterministic response barrier
        message = _next(ws)
    assert message["type"] == "error" and message["code"] == "PLACEMENT_REQUIRED"
    assert not app.state.session_manager.list_active_multiplayer_sessions()


def test_legacy_rated_queue_pairs_only_same_rung_as_free(client, app):
    from katrain.web.core.pvp_lobby_bots import playable_rungs

    first, second = playable_rungs()[:2]
    alice_id, alice = _make_user(app, "same_a")
    bob_id, bob = _make_user(app, "other_b")
    carol_id, carol = _make_user(app, "same_c")
    _place(app, alice_id, first.rung)
    _place(app, bob_id, second.rung)
    _place(app, carol_id, first.rung)
    with _ws(client, _token(client, alice)) as a, _ws(client, _token(client, bob)) as b, _ws(client, _token(client, carol)) as c:
        a.send_json({"type": "start_matchmaking", "game_type": "rated"})
        b.send_json({"type": "start_matchmaking", "game_type": "free"})
        c.send_json({"type": "start_matchmaking"})
        match = _next(c)
        assert match["type"] == "match_found"
        assert match["game_type"] == "free"
        assert {match["players"]["player_b"], match["players"]["player_w"]} == {alice_id, carol_id}
        assert match["my_color"] == ("B" if match["players"]["player_b"] == carol_id else "W")
        assert _next(a)["session_id"] == match["session_id"]
        assert app.state.session_manager.get_session(match["session_id"]).game_type == "free"


def test_old_lobby_tab_disconnect_keeps_new_tabs_queue_and_bot_wait(client, app):
    from katrain.web.core.pvp_lobby_bots import playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "two_tabs")
    bob_id, bob = _make_user(app, "two_tabs_peer")
    _place(app, alice_id, rung)
    _place(app, bob_id, rung)
    runtime = app.state.pvp_lobby_bots
    runtime.human_wait_seconds = 30
    token = _token(client, alice)
    with _ws(client, token) as newer:
        with _ws(client, token) as older:
            older.send_json({"type": "start_matchmaking"})
            older.send_json({"type": "invite", "target_id": 999999})
            assert _next(older)["type"] == "error"
            newer.send_json({"type": "start_matchmaking"})
            newer.send_json({"type": "invite", "target_id": 999999})
            assert _next(newer)["type"] == "error"
            wait_task = runtime._waiting_tasks[alice_id]
        newer.send_json({"type": "invite", "target_id": 999999})
        assert _next(newer)["type"] == "error"
        queued = [entry for queue in app.state.matchmaker._queues.values() for entry in queue
                  if entry["user_id"] == alice_id]
        assert len(queued) == 1 and queued[0]["websocket"] is not None
        assert runtime._waiting_tasks[alice_id] is wait_task and not wait_task.cancelled()
        with _ws(client, _token(client, bob)) as peer:
            peer.send_json({"type": "start_matchmaking"})
            assert _next(peer)["type"] == "match_found"
            assert _next(newer)["type"] == "match_found"


@pytest.mark.parametrize("human_level", [None, 0, 1], ids=["unplaced", "same-rung", "different-rung"])
def test_user_can_invite_idle_bot_regardless_of_placement_or_rung(client, app, human_level):
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_inviter")
    if human_level is not None:
        _place(app, alice_id, playable_rungs()[human_level].rung)
    runtime = app.state.pvp_lobby_bots
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                          "idle_targets": {str(rung): 1}}, revision=1)
    with _ws(client, _token(client, alice)) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        match = _next(ws)
    assert match["type"] == "match_found"
    assert match["game_type"] == "free"
    assert match["my_color"] in ("B", "W")
    assert {match["players"]["player_b"], match["players"]["player_w"]} == {alice_id, bot_id(rung, 1)}
    session = app.state.session_manager.get_session(match["session_id"])
    assert session.bot_game is True
    snapshot = runtime.build_snapshot()
    assert snapshot["applied_config_revision"] == 1
    assert snapshot["active_bot_games"] == 1
    assert snapshot["reported_at"]
    assert any(row["kind"] == "bot" and row["id"] == bot_id(rung, 1)
               and row["session_id"] == session.session_id for row in snapshot["participants"])
    headers = {"Authorization": f"Bearer {_token(client, alice)}"}
    change = client.post("/api/player", headers=headers,
                         json={"session_id": session.session_id, "bw": "W", "name": "hijack"})
    assert change.status_code == 403
    restart = client.post("/api/new-game", headers=headers, json={"session_id": session.session_id})
    assert restart.status_code == 403
    readable = client.get("/api/sgf/save", headers=headers, params={"session_id": session.session_id})
    assert readable.status_code == 200


def test_bot_move_rechecks_seat_and_turn_under_session_lock(client, app, monkeypatch):
    from unittest.mock import MagicMock
    from katrain.web import session as session_module
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    monkeypatch.setattr(session_module, "WebKaTrain", lambda **kwargs: MagicMock())
    rung = playable_rungs()[0].rung
    human_id, username = _make_user(app, "bot_turn")
    _place(app, human_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)
    token = _token(client, username)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        sid = _next(ws)["session_id"]
    session = app.state.session_manager.get_session(sid)
    human_color = "B" if session.player_b_id == human_id else "W"
    bot_color = "W" if human_color == "B" else "B"
    node = session.katrain.game.current_node
    node.next_player = human_color

    def stale_outside_read():
        node.next_player = bot_color
        return {"player_to_move": human_color, "awaiting_count": False}

    session.katrain.reset_mock()
    session.katrain.get_state.side_effect = stale_outside_read
    headers = {"Authorization": f"Bearer {token}"}
    stale = client.post("/api/move", headers=headers, json={"session_id": sid, "pass_move": True})
    assert stale.status_code in (403, 409), stale.text
    session.katrain.assert_not_called()

    node.next_player = human_color
    session.katrain.get_state.side_effect = None
    session.katrain.get_state.return_value = {"player_to_move": human_color, "awaiting_count": False}
    accepted = client.post("/api/move", headers=headers, json={"session_id": sid, "pass_move": True})
    assert accepted.status_code == 200, accepted.text
    session.katrain.assert_any_call("play", None, guard=True, expected_player=human_color)


def test_bot_resignation_records_human_once_and_releases_room(client, app):
    from katrain.web.core.models_db import AiLadderProfile, UserGame
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_resign")
    _place(app, alice_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)
    token = _token(client, alice)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        match = _next(ws)
    sid = match["session_id"]
    app.state.session_manager.get_session(sid).katrain.get_sgf.return_value = "(;GM[1])"
    response = client.post("/api/resign", headers={"Authorization": f"Bearer {token}"}, json={"session_id": sid})
    assert response.status_code == 200, response.text
    with pytest.raises(KeyError):
        app.state.session_manager.get_session(sid)
    assert alice_id not in app.state.matchmaker._active_users
    assert bot_id(rung, 1) not in app.state.matchmaker._active_users
    db = app.state.session_factory()
    try:
        assert db.query(UserGame).filter_by(user_id=alice_id, game_type="free", source="play_human").count() == 1
        assert db.get(AiLadderProfile, alice_id).ai_ladder_rung == rung
    finally:
        db.close()


def test_bot_accepts_human_count_request_immediately(client, app):
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_count")
    _place(app, alice_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)
    token = _token(client, alice)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        match = _next(ws)
    sid = match["session_id"]
    session = app.state.session_manager.get_session(sid)
    session.katrain.get_state.return_value = {"awaiting_count": True, "history": [], "end_result": "终局"}
    session.katrain.game.current_node.score = 2.5
    session.katrain.get_sgf.return_value = "(;GM[1])"
    response = client.post("/api/count/request", headers={"Authorization": f"Bearer {token}"},
                           json={"session_id": sid})
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "B+2.5"
    with pytest.raises(KeyError):
        app.state.session_manager.get_session(sid)


def test_bot_count_failure_stays_visible_for_retry(client, app):
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_count_retry")
    _place(app, alice_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)
    token = _token(client, alice)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        sid = _next(ws)["session_id"]
    session = app.state.session_manager.get_session(sid)
    session.katrain.get_state.return_value = {"awaiting_count": True, "history": [], "end_result": "终局"}
    session.katrain.game.current_node.score = None
    session.katrain.ensure_current_score.return_value = None
    response = client.post("/api/count/request", headers={"Authorization": f"Bearer {token}"},
                           json={"session_id": sid})
    assert response.status_code == 400
    assert session.bot_degraded is True
    assert session.game_ended is False
    assert app.state.session_manager.get_session(sid) is session


def test_bot_timeout_binds_clock_and_records_actual_winner(client, app, monkeypatch):
    from unittest.mock import MagicMock
    from katrain.web import session as session_module
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs
    from katrain.web.core.models_db import UserGame
    from katrain.web.models import EndgameConflict, GameEnd

    rung = playable_rungs()[0].rung
    monkeypatch.setattr(session_module, "WebKaTrain", lambda **kwargs: MagicMock())
    human_id, username = _make_user(app, "bot_timeout")
    _place(app, human_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)
    token = _token(client, username)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        sid = _next(ws)["session_id"]
    session = app.state.session_manager.get_session(sid)
    game = session.katrain.game
    node = game.current_node
    game.terminal = None
    human_color = "B" if session.player_b_id == human_id else "W"
    bot_color = "W" if human_color == "B" else "B"
    node.next_player = bot_color
    game.game_id = "clock-game"
    session.katrain.get_state.return_value = {"player_to_move": bot_color, "end_result": None}
    session.katrain.get_sgf.return_value = "(;GM[1])"

    def clock_not_expired(action, **kwargs):
        assert action == "timeout"
        assert kwargs == {"expected_game_id": "clock-game", "expected_node_id": id(node), "color": bot_color}
        raise EndgameConflict("clock_not_expired")

    session.katrain.side_effect = clock_not_expired
    headers = {"Authorization": f"Bearer {token}"}
    denied = client.post("/api/timeout", headers=headers, json={"session_id": sid})
    assert denied.status_code == 409, denied.text
    assert app.state.session_manager.get_session(sid) is session

    def expired(action, **kwargs):
        assert kwargs["color"] == bot_color
        game.terminal = GameEnd(game, node, f"{human_color}+T")

    session.katrain.side_effect = expired
    accepted = client.post("/api/timeout", headers=headers, json={"session_id": sid})
    assert accepted.status_code == 200, accepted.text
    db = app.state.session_factory()
    try:
        row = db.query(UserGame).filter_by(user_id=human_id, game_type="free").one()
        assert row.result == f"{human_color}+T"
    finally:
        db.close()


def test_bot_leave_marks_terminal_and_releases_reservation(client, app):
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_leave")
    _place(app, alice_id, rung)
    runtime = app.state.pvp_lobby_bots
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                          "idle_targets": {}}, revision=1)
    token = _token(client, alice)
    with _ws(client, token) as ws:
        ws.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        match = _next(ws)
    sid = match["session_id"]
    session = app.state.session_manager.get_session(sid)
    session.katrain.get_sgf.return_value = "(;GM[1])"
    response = client.post("/api/multiplayer/leave", headers={"Authorization": f"Bearer {token}"},
                           json={"session_id": sid})
    assert response.status_code == 200, response.text
    assert session.bot_finalized is True
    assert session.game_ended is True
    assert not runtime._busy


def test_waiting_human_gets_same_rung_bot_after_grace_period(client, app):
    from katrain.web.core.pvp_lobby_bots import playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "bot_wait")
    _place(app, alice_id, rung)
    runtime = app.state.pvp_lobby_bots
    runtime.human_wait_seconds = 0.01
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                          "idle_targets": {}}, revision=1)
    with _ws(client, _token(client, alice)) as ws:
        ws.send_json({"type": "start_matchmaking", "game_type": "rated"})
        match = _next(ws)
    assert match["type"] == "match_found"
    assert match["game_type"] == "free"
    assert alice_id in (match["players"]["player_b"], match["players"]["player_w"])
    assert min(match["players"]["player_b"], match["players"]["player_w"]) < 0
    assert app.state.session_manager.get_session(match["session_id"]).bot_rung == rung


def test_runtime_publishes_admin_snapshot_with_revision(client, app):
    import json
    from katrain.web.core.models_db import SystemConfigDB

    db = app.state.session_factory()
    try:
        db.add(SystemConfigDB(key="pvp_lobby_bot_config", value=json.dumps({"revision": 9, "config": {
            "version": 1, "enabled": True, "bot_game_limit": 2, "idle_targets": {"1": 3}}})))
        db.commit()
    finally:
        db.close()
    runtime = app.state.pvp_lobby_bots
    runtime._load_config()
    runtime._publish_snapshot()
    db = app.state.session_factory()
    try:
        row = db.get(SystemConfigDB, "pvp_lobby_bot_runtime")
        snapshot = json.loads(row.value)
    finally:
        db.close()
    assert snapshot["applied_config_revision"] == 9
    assert snapshot["rungs"][0]["idle_target"] == 3
    assert snapshot["rungs"][0]["idle_now"] >= 3
    assert snapshot["participants"]


def test_rotation_creates_only_capped_bot_rooms_and_preserves_idle_targets(client, app):
    from katrain.web.core.pvp_lobby_bots import playable_rungs

    runtime = app.state.pvp_lobby_bots
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 1,
                          "idle_targets": {}}, revision=1)
    client.portal.call(runtime._start_rotation_game)
    client.portal.call(runtime._start_rotation_game)
    sessions = [session for session in app.state.session_manager.list_active_multiplayer_sessions()
                if getattr(session, "bot_game", False)]
    assert len(sessions) == 1
    assert sessions[0].player_b_id < 0 and sessions[0].player_w_id < 0
    assert sessions[0].bot_rung == playable_rungs()[0].rung
    rows = [row for row in runtime.public_online_rows() if row["ladder_rung"] == sessions[0].bot_rung]
    assert sum(row["presence"] == "idle" for row in rows) >= 2


def test_duplicate_queue_request_and_stop_leave_no_bot_match(client, app):
    import time
    from katrain.web.core.pvp_lobby_bots import playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "queue_cancel")
    _place(app, alice_id, rung)
    runtime = app.state.pvp_lobby_bots
    runtime.human_wait_seconds = 0.05
    runtime.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                          "idle_targets": {}}, revision=1)
    with _ws(client, _token(client, alice)) as ws:
        ws.send_json({"type": "start_matchmaking"})
        ws.send_json({"type": "start_matchmaking", "game_type": "rated"})
        ws.send_json({"type": "stop_matchmaking"})
        ws.send_json({"type": "invite", "target_id": 999999})
        assert _next(ws)["type"] == "error"
        time.sleep(0.1)
    assert not app.state.session_manager.list_active_multiplayer_sessions()
    assert not app.state.matchmaker.has_waiters()


def test_two_human_passes_settle_nonranking_game_once(client, app):
    from katrain.web.models import GameEnd
    from katrain.web.core.models_db import UserGame

    black_id, black = _make_user(app, "pass_black")
    white_id, white = _make_user(app, "pass_white")
    session = app.state.session_manager.create_multiplayer_session(
        black_id, white_id, b_name=black, w_name=white, initial_game_type="free", skip_initial_analysis=True)
    game = session.katrain.game
    node = game.current_node
    game.terminal = None
    node.end_state = None
    node.score = 1.5
    session.katrain.analysis_allowed = True
    session.katrain.get_state.return_value = {"player_to_move": "B", "history": ["pass", "pass"],
                                               "awaiting_count": False, "end_result": "board-game-end"}
    session.katrain.get_sgf.return_value = "(;GM[1];B[];W[])"
    session.katrain.ensure_current_score.return_value = 1.5
    session.katrain._commit_end_state.return_value = GameEnd(game, node, "B+1.5")
    session.katrain.side_effect = lambda *args, **kwargs: setattr(game, "terminal", GameEnd(game, node, "board-game-end"))

    token = _token(client, black)
    response = client.post("/api/move", headers={"Authorization": f"Bearer {token}"},
                           json={"session_id": session.session_id, "pass_move": True})
    assert response.status_code == 200, response.text
    client.portal.call(app.state.session_manager.on_game_ended, session, GameEnd(game, node, "board-game-end"))
    db = app.state.session_factory()
    try:
        rows = db.query(UserGame).filter(UserGame.user_id.in_([black_id, white_id]),
                                         UserGame.game_type == "free").all()
        assert len(rows) == 2
        assert {row.result for row in rows} == {"B+1.5"}
    finally:
        db.close()


def test_two_human_passes_expose_count_retry_after_score_failure(client, app):
    from katrain.web.models import GameEnd

    black_id, black = _make_user(app, "retry_black")
    white_id, white = _make_user(app, "retry_white")
    session = app.state.session_manager.create_multiplayer_session(
        black_id, white_id, b_name=black, w_name=white, initial_game_type="free", skip_initial_analysis=True)
    game = session.katrain.game
    node = game.current_node
    game.terminal = None
    node.end_state = None
    node.score = None
    session.katrain.analysis_allowed = True
    session.katrain.get_state.side_effect = lambda: {
        "player_to_move": "B", "history": ["pass", "pass"], "end_result": "终局",
        "awaiting_count": bool(getattr(session.katrain, "pvp_lobby_awaiting_count", False)),
        "degraded": bool(getattr(session.katrain, "pvp_lobby_degraded", False)),
    }
    session.katrain.get_sgf.return_value = "(;GM[1];B[];W[])"
    session.katrain.ensure_current_score.return_value = None
    session.katrain._commit_end_state.return_value = GameEnd(game, node, "B+1.5")
    session.katrain.side_effect = lambda *args, **kwargs: setattr(game, "terminal", GameEnd(game, node, "终局"))

    black_token, white_token = _token(client, black), _token(client, white)
    move = client.post("/api/move", headers={"Authorization": f"Bearer {black_token}"},
                       json={"session_id": session.session_id, "pass_move": True})
    assert move.status_code == 200, move.text
    assert move.json()["state"]["degraded"] is True
    assert move.json()["state"]["awaiting_count"] is True
    assert session.game_ended is False

    node.score = 1.5
    first = client.post("/api/count/request", headers={"Authorization": f"Bearer {black_token}"},
                        json={"session_id": session.session_id})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "pending"
    second = client.post("/api/count/request", headers={"Authorization": f"Bearer {white_token}"},
                         json={"session_id": session.session_id})
    assert second.status_code == 200, second.text
    assert second.json()["result"] == "B+1.5"
    assert second.json()["state"]["degraded"] is False
    assert second.json()["state"]["awaiting_count"] is False


@pytest.mark.parametrize("score", [None, 1.5])
def test_central_human_double_pass_first_frame_waits_for_score(client, app, score, monkeypatch):
    from unittest.mock import MagicMock
    from katrain.core.constants import MODE_PLAY
    from katrain.web.models import GameEnd
    from katrain.web import session as session_module

    monkeypatch.setattr(session_module, "WebKaTrain", lambda **kwargs: MagicMock())

    source = Path(__file__).resolve().parents[2] / "katrain/web/interface.py"
    spec = importlib.util.spec_from_file_location("_pvp_real_interface", source)
    real_interface = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_interface)

    black_id, black = _make_user(app, "first_frame_black")
    white_id, white = _make_user(app, "first_frame_white")
    session = app.state.session_manager.create_multiplayer_session(
        black_id, white_id, b_name=black, w_name=white, initial_game_type="free", skip_initial_analysis=True)
    manager = app.state.session_manager
    reservation = app.state.matchmaker.reserve_invitation(black_id, white_id)
    assert app.state.matchmaker.bind_session(reservation, session.session_id, black_id, white_id)
    game = session.katrain.game
    node = game.current_node
    node.next_player = "B"
    node.is_pass = True
    node.parent.is_pass = True
    node.end_state = None
    node.score = score
    game.current_node = node
    game.katrain = session.katrain
    game.terminal = None
    game.end_result = "终局"
    game.ended_at.return_value = False
    session.katrain.ai_ladder_commit_lock = threading.RLock()
    session.katrain.play_analyze_mode = MODE_PLAY
    session.katrain.analysis_allowed = True
    session.katrain.pvp_lobby_awaiting_count = False
    session.katrain.pvp_lobby_degraded = False
    session.katrain.ensure_current_score.return_value = score
    session.katrain.get_sgf.return_value = "(;GM[1];B[];W[])"

    def state():
        return {"player_to_move": "B", "history": ["pass", "pass"],
                "end_result": game.end_result if game.terminal else None,
                "awaiting_count": getattr(session.katrain, "pvp_lobby_awaiting_count", False) is True,
                "degraded": getattr(session.katrain, "pvp_lobby_degraded", False) is True}

    frames = []
    owners_at_frame = []
    original_broadcast = manager._schedule_broadcast

    def capture(_session, payload):
        if payload.get("type") == "game_update":
            frames.append(dict(payload["state"]))
            owners_at_frame.append(app.state.matchmaker._active_users.get(black_id))
        return original_broadcast(_session, payload)

    manager._schedule_broadcast = capture
    session.katrain.get_state.side_effect = state
    session.katrain.update_state.side_effect = lambda: session.katrain.update_state_callback(state())
    def play(action, *args, **kwargs):
        if action == "play":
            real_interface.WebGame.record_two_pass_end(game, node)
            session.katrain.update_state()

    session.katrain.side_effect = play

    if score is not None:
        def commit(result, **kwargs):
            node.end_state = result
            game.end_result = result
            game.terminal = GameEnd(game, node, result)
            return game.terminal

        session.katrain._commit_end_state.side_effect = commit

    response = client.post("/api/move", headers={"Authorization": f"Bearer {_token(client, black)}"},
                           json={"session_id": session.session_id, "pass_move": True})
    assert response.status_code == 200, response.text
    assert frames[0]["awaiting_count"] is True
    assert frames[0]["degraded"] is False
    assert owners_at_frame[0] == session.session_id
    if score is None:
        assert frames[-1]["awaiting_count"] is True
        assert frames[-1]["degraded"] is True
        assert session.game_ended is False
        assert app.state.matchmaker._active_users[black_id] == session.session_id
    else:
        assert frames[-1]["awaiting_count"] is False
        assert frames[-1]["degraded"] is False
        assert frames[-1]["end_result"] == "B+1.5"
        assert session.game_ended is True


def test_game_ended_callback_does_not_release_pending_human_count(client, app):
    from katrain.web.models import GameEnd

    black_id, black = _make_user(app, "pending_callback_black")
    white_id, white = _make_user(app, "pending_callback_white")
    manager = app.state.session_manager
    session = manager.create_multiplayer_session(
        black_id, white_id, b_name=black, w_name=white, initial_game_type="free", skip_initial_analysis=True)
    reservation = app.state.matchmaker.reserve_invitation(black_id, white_id)
    assert app.state.matchmaker.bind_session(reservation, session.session_id, black_id, white_id)
    session.katrain.pvp_lobby_awaiting_count = True
    manager.on_game_ended = None
    end = GameEnd(session.katrain.game, session.katrain.game.current_node, "终局")

    manager._on_game_ended(session.session_id, end)
    manager._on_state(session.session_id, {"end_result": "终局", "awaiting_count": True})

    assert session.game_ended is False
    assert app.state.matchmaker._active_users[black_id] == session.session_id


def test_accept_invite_without_an_invitation_creates_no_game(client, app):
    """没人邀请过我,我 `accept_invite` 也开不出局来 —— **而且屏上会说出来**。

    🔴 2026-08-26 之前这条走的是「屏障」写法:先发一条注定回 error 的 `invite`,
    看第一条收到的是不是它。**之所以需要屏障,正是因为被拒的 accept 是静默的** ——
    服务端那个 `if` 没有 `else`,前端点完就关窗 ⇒ 用户按下「接受并开局」屏上什么都不发生。
    那是 2026-08-25 加 `consume_invite` + `INVITE_TTL_SECONDS` 那次**自己造出来的**:
    在它之前 accept 恒成功(不安全,但不会没反应)。

    补上 `else` 之后屏障就不必要了,断言也变强:**不但没建局,而且回了 `INVITE_NOT_PENDING`。**
    """
    _, alice = _make_user(app, "alice")
    _, mallory = _make_user(app, "mallory")
    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]

    before = len(app.state.session_manager._sessions)

    with _ws(client, _token(client, alice)), _ws(client, _token(client, mallory)) as m:
        # mallory 从没收到过邀请,却直接「接受」alice 的邀请。
        m.send_json({"type": "accept_invite", "target_id": alice_id})
        first = _next(m)

    assert first["type"] == "error", f"被拒的 accept 应该出声,而收到的是 {first}"
    assert first.get("code") == "INVITE_NOT_PENDING", first
    assert len(app.state.session_manager._sessions) == before, "凭空建出了一局棋"


def test_accept_invite_says_so_when_the_invitation_expired(client, app):
    """过期那一档:邀请真发过,但过了 `INVITE_TTL_SECONDS` ⇒ 开不出局,**并且说出来**。

    「没人邀请过我」和「邀请过但过期了」在用户那里是两件事,在这条通道上曾经
    **长得一模一样**(都是什么都不发生)。
    """
    _, alice = _make_user(app, "alice")
    _, bob = _make_user(app, "bob")
    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]
    bob_id = app.state.user_repo.get_user_by_username(bob)["id"]

    before = len(app.state.session_manager._sessions)
    lobby = app.state.lobby_manager
    lobby.record_invite(alice_id, bob_id)
    # 把发出时刻推到 TTL 之外 —— 不睡 120 秒。
    lobby._pending_invites[(alice_id, bob_id)] -= lobby.INVITE_TTL_SECONDS + 1

    with _ws(client, _token(client, bob)) as b:
        b.send_json({"type": "accept_invite", "target_id": alice_id})
        first = _next(b)

    assert first["type"] == "error" and first.get("code") == "INVITE_NOT_PENDING", first
    assert len(app.state.session_manager._sessions) == before, "过期的邀请也开出了局"


def test_accept_invite_after_a_real_invitation_creates_the_game(client, app):
    """正对照:真被邀请过就开得出来 —— 否则上一条的「没建局」只说明这条路整个不通。"""
    _, alice = _make_user(app, "alice")
    _, bob = _make_user(app, "bob")
    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]
    bob_id = app.state.user_repo.get_user_by_username(bob)["id"]

    before = len(app.state.session_manager._sessions)

    with _ws(client, _token(client, alice)) as a, _ws(client, _token(client, bob)) as b:
        a.send_json({"type": "invite", "target_id": bob_id})
        assert _next(b)["type"] == "invitation"
        assert _next(a)["type"] == "info"

        b.send_json({"type": "accept_invite", "target_id": alice_id})
        assert _next(b)["type"] == "match_found"

    assert len(app.state.session_manager._sessions) == before + 1


def test_an_invitation_can_only_open_one_game(client, app):
    """`consume_invite` 是一次性的 —— 同一封邀请开不出第二局。"""
    _, alice = _make_user(app, "alice")
    _, bob = _make_user(app, "bob")
    alice_id = app.state.user_repo.get_user_by_username(alice)["id"]
    bob_id = app.state.user_repo.get_user_by_username(bob)["id"]

    with _ws(client, _token(client, alice)) as a, _ws(client, _token(client, bob)) as b:
        a.send_json({"type": "invite", "target_id": bob_id})
        assert _next(b)["type"] == "invitation"
        assert _next(a)["type"] == "info"

        b.send_json({"type": "accept_invite", "target_id": alice_id})
        assert _next(b)["type"] == "match_found"
        after_first = len(app.state.session_manager._sessions)

        # 同一封邀请再用一次。
        b.send_json({"type": "accept_invite", "target_id": alice_id})
        b.send_json({"type": "invite", "target_id": 999_999})   # 屏障
        assert _next(b)["type"] == "error"

    assert len(app.state.session_manager._sessions) == after_first, "同一封邀请开出了第二局"


def test_removing_old_human_room_does_not_release_new_room_reservation(client, app):
    alice_id, alice = _make_user(app, "room_owner")
    bob_id, bob = _make_user(app, "room_old")
    carol_id, carol = _make_user(app, "room_new")
    dave_id, dave = _make_user(app, "room_third")

    with _ws(client, _token(client, alice)) as a, _ws(client, _token(client, bob)) as b, \
            _ws(client, _token(client, carol)) as c, _ws(client, _token(client, dave)) as d:
        a.send_json({"type": "invite", "target_id": bob_id})
        assert _next(b)["type"] == "invitation"
        assert _next(a)["type"] == "info"
        b.send_json({"type": "accept_invite", "target_id": alice_id})
        old_room = _next(b)
        assert old_room["type"] == "match_found"
        assert _next(a)["type"] == "match_found"

        old_session = app.state.session_manager.get_session(old_room["session_id"])
        old_session.game_ended = True
        app.state.session_manager.on_session_state(old_session.session_id)

        a.send_json({"type": "invite", "target_id": carol_id})
        assert _next(c)["type"] == "invitation"
        assert _next(a)["type"] == "info"
        c.send_json({"type": "accept_invite", "target_id": alice_id})
        new_room = _next(c)
        assert new_room["type"] == "match_found"
        assert _next(a)["type"] == "match_found"

        app.state.session_manager.remove_session(old_session.session_id)
        assert app.state.session_manager.get_session(new_room["session_id"]).session_id == new_room["session_id"]
        a.send_json({"type": "invite", "target_id": dave_id})
        assert _next(d)["type"] == "invitation"
        assert _next(a)["type"] == "info"
        d.send_json({"type": "accept_invite", "target_id": alice_id})
        blocked = _next(d)
        assert blocked["type"] == "error" and blocked["code"] == "ALREADY_PLAYING"


def test_removing_old_human_room_keeps_new_bot_room_reserved(client, app):
    from katrain.web.core.pvp_lobby_bots import bot_id, playable_rungs

    rung = playable_rungs()[0].rung
    alice_id, alice = _make_user(app, "room_to_bot")
    bob_id, bob = _make_user(app, "room_to_bot_peer")
    _place(app, alice_id, rung)
    app.state.pvp_lobby_bots.apply_config({"version": 1, "enabled": True, "bot_game_limit": 0,
                                           "idle_targets": {}}, revision=1)

    with _ws(client, _token(client, alice)) as a, _ws(client, _token(client, bob)) as b:
        a.send_json({"type": "invite", "target_id": bob_id})
        assert _next(b)["type"] == "invitation"
        assert _next(a)["type"] == "info"
        b.send_json({"type": "accept_invite", "target_id": alice_id})
        old_room = _next(b)
        assert old_room["type"] == "match_found"
        assert _next(a)["type"] == "match_found"
        old_session = app.state.session_manager.get_session(old_room["session_id"])
        old_session.game_ended = True
        app.state.session_manager.on_session_state(old_session.session_id)

        a.send_json({"type": "invite", "target_id": bot_id(rung, 1)})
        bot_room = _next(a)
        assert bot_room["type"] == "match_found"
        app.state.session_manager.remove_session(old_session.session_id)
        assert app.state.matchmaker._active_users[alice_id] == bot_room["session_id"]
        assert app.state.matchmaker.reserve_invitation(alice_id, bob_id) is None
