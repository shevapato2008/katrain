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
