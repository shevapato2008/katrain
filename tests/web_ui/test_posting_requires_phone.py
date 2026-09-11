"""未绑手机不得发言（对局聊天 + 直播评论）。

闸读 `current_user.phone_bound` —— Task 8 加进 pydantic `User` 与 `_to_dict` 的那个布尔。
**不读 `phone_e164`、不用 getattr**：WS 的 `current_user` 与 live.py 的
`Depends(get_current_user)` 是同一个 pydantic `User`（都出自 endpoints/auth.py:208
`return User(**user_dict)`），那个模型上没有 `phone_e164`，
`extra='ignore'` 会把它静默丢掉 ⇒ getattr 恒为 None ⇒ 所有人都发不了言。

**两处闸不同形，这是查证过的结果不是遗漏**：对局聊天多一条 `KATRAIN_MODE != "board"`，
直播评论没有。理由见 `test_chat_on_the_box_is_not_phone_gated` 的 docstring 与
`live.py` 里那段注释。

WS 用例必须用 `TestClient`（httpx 的 AsyncClient 不做 WebSocket），
而 TestClient **会跑 lifespan** ⇒ `app.state.session_factory` 必须在进它之前设好，
否则 `_lifespan_server` 会用全局 SessionLocal 重建六个 repo 覆盖掉注入，
写落进开发机真库并被 tests/conftest.py 的写闸拦住。整套接线照抄
tests/web_ui/test_game_termination_and_chat_identity.py:35-92。
"""
import threading
import uuid
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.server import create_app

COMMENTS = "/api/v1/live/matches/m1/comments"


@pytest.fixture
def app(tmp_path, monkeypatch):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'posting.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # live.py 的 create_comment 用的是**模块级** SessionLocal
    # （函数体内 `from katrain.web.core.db import SessionLocal`，不走 Depends）
    # ⇒ 只能在这里换掉，否则评论会写进开发机真库并被 conftest 的闸拦住。
    monkeypatch.setattr("katrain.web.core.db.SessionLocal", Session)

    application = create_app(enable_engine=False)
    application.state.session_factory = Session          # ← 这一行才是真正生效的那处
    application.state.user_repo = SQLAlchemyUserRepository(Session)
    application.state.game_repo = GameRepository(Session)
    application.state._TestSessionLocal = Session
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class _StubStatus:
    value = "live"


class _StubMatch:
    status = _StubStatus()


class _StubCache:
    async def get_match(self, match_id):
        return _StubMatch() if match_id == "m1" else None


class _StubLiveService:
    cache = _StubCache()


@pytest.fixture
def live_service(app):
    """`Depends(get_live_service)` 在函数体之前就要解析出来，没有它整条路是 503 ——
    那样「403」和「这个端点本来就不通」分不开。"""
    from katrain.web.api.v1.endpoints.live import get_live_service

    app.dependency_overrides[get_live_service] = lambda: _StubLiveService()
    yield app
    app.dependency_overrides.pop(get_live_service, None)


def _make_user(app, username, phone=None):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash("password"))
    session = app.state._TestSessionLocal()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        if phone is not None:
            u.phone_e164 = phone
            session.commit()
        return u.id
    finally:
        session.close()


def _token(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _inject_session(app):
    """把一个**无人认领**的会话直接塞进 session manager。

    三个 id 全 None ⇒ `guard_session_reader`(server.py:811) 早退，
    任何登录用户都连得上 —— 本组用例要的正是「第三方也在房间里」。
    conftest 把 `katrain.web.interface` 整个换成了 MagicMock，所以走 HTTP 真开一局
    不会执行到 WebKaTrain；沿用本目录既有做法手工构造一个够真的 session
    （tests/web_ui/test_game_termination_and_chat_identity.py:104-133）。
    """
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = None
    session.player_b_id = None
    session.player_w_id = None
    session.mode = "play"
    session.game_type = "free"
    session.lock = threading.Lock()
    session.sockets = set()
    session.last_access = 0.0
    session.last_state = {"end_result": None}
    session.pending_count_request = None
    session.pending_count_timestamp = None
    session.game_ended = False

    katrain = MagicMock()
    katrain.game_type = "free"
    katrain.get_sgf.return_value = "(;FF[4]SZ[19];B[pd])"
    katrain.get_state.return_value = {"end_result": None}
    katrain.game.end_result = None
    session.katrain = katrain

    app.state.session_manager._sessions[session.session_id] = session
    return session


def _await(ws, *wanted: str, limit: int = 20) -> dict:
    """读到第一个 type 命中 `wanted` 的帧。**`"error"` 永远隐式在等待集合里。**

    这条 socket 一连上就会推 `game_update` 与 `spectator_count`（server.py:2799/2815），
    别人进出房间时还会再来 `spectator_count`，所以「收下一帧」不等于「收我等的那一帧」。
    写死跳过前 N 帧的话，哪天多播一条无关广播，红的会是这些测试而不是被改坏的东西。

    ⚠️ **为什么强行并进 `"error"`**：`limit` 限的是**读几帧**，不是**等多久** ——
    `WebSocketTestSession.receive_json()` 底下是一个没有超时的队列 `get()`。
    只等 `"chat"` 的调用点，在「闸误伤了本该放行的人」这一类回归下**永远等不到那一帧**，
    于是整个套件挂死而不是变红。2026-09-11 实测：M1 变异（闸改读 `phone_e164`）让
    `_await(third_party, "chat")` 挂了四个半小时，CPU 只用掉 50 秒。
    **挂起的测试比红的测试更坏**：CI 上它表现为超时，读日志的人第一反应是去查基础设施。
    ⇒ 这个失败模式在**函数签名里**拆掉，不靠每个调用点记得多写一个参数；
    代价是调用方必须自己断言帧的类型，那正是它本来就该做的事。
    """
    wanted_set = set(wanted) | {"error"}
    for _ in range(limit):
        frame = ws.receive_json()
        if frame.get("type") in wanted_set:
            return frame
    raise AssertionError(f"{limit} 帧之内没等到 {sorted(wanted_set)}")


# --------------------------------------------------------------- 对局聊天（WS）


def test_chat_from_an_unbound_user_gets_an_error_not_silence(app, client):
    """照抄 server.py 里已有的口径：说一句而不是静默丢弃 ——
    静默丢弃时发言的人看不出自己没发出去。

    读的是**发送方自己那条 socket**：广播会回到发送方，所以闸没生效时这里
    收到的是一条 `chat` 帧（当场红），而不是永远等不到帧（挂住）。
    """
    _make_user(app, "nophone")
    session = _inject_session(app)
    with client.websocket_connect(f"/ws/{session.session_id}?token={_token(client, 'nophone')}") as ws:
        ws.send_json({"type": "chat", "text": "hello"})
        frame = _await(ws, "chat", "error")
    assert frame == {"type": "error", "code": "chat_requires_phone"}


def test_chat_from_a_bound_user_is_broadcast(app, client):
    """**正对照。** 没有它，「拒绝生效」和「聊天整个坏了」是同一个观测值。

    这条同时是「闸不许读 phone_e164」的检出点：换成
    `getattr(current_user, "phone_e164", None)` 它当场红。
    """
    _make_user(app, "bound", phone="+8613800138000")
    session = _inject_session(app)
    with client.websocket_connect(f"/ws/{session.session_id}?token={_token(client, 'bound')}") as ws:
        ws.send_json({"type": "chat", "text": "hello"})
        frame = _await(ws, "chat", "error")
    assert frame["type"] == "chat"
    assert frame["text"] == "hello"
    assert frame["from_name"] == "bound"


def test_an_unbound_users_message_never_reaches_a_third_party(app, client):
    """光有错误回执不够 —— 得确认它真的没广播出去。

    **不能写成 `assert not _has_pending(observer)`**：广播是 fire-and-forget
    （session.py 的 `create_task` / `run_coroutine_threadsafe`，请求处理这边从不 await 它）
    ⇒ 闸拆掉之后泄漏的那帧很可能「还没送到」就被读成「没有」= 假绿；
    反方向也坏 —— 观战者一连上就先收到 `game_update` 与 `spectator_count`
    （server.py:2799/2815），不排掉的话它恒为 True = 恒红。

    改成**带同步点的顺序断言**：先等到未绑号那句被明确拒绝（同步点，证明服务端
    已经处理完那条消息），再让一个已绑号的人发一句哨兵，然后把第三方的帧排到
    第一条 `type=="chat"` —— 那一条必须是哨兵。闸拆掉时它会是 `"leak"`，当场红；
    而且没有时序运气成分：两次广播由同一个事件循环按 `create_task` 的创建顺序跑，
    泄漏的那帧一定排在哨兵之前。
    """
    _make_user(app, "nophone")
    _make_user(app, "bound", phone="+8613800138000")
    session = _inject_session(app)
    base = f"/ws/{session.session_id}?token="

    with client.websocket_connect(base + _token(client, "bound")) as third_party:
        with client.websocket_connect(base + _token(client, "nophone")) as muted:
            muted.send_json({"type": "chat", "text": "leak"})
            refused = _await(muted, "chat", "error")
            assert refused.get("code") == "chat_requires_phone", refused   # ← 同步点
        third_party.send_json({"type": "chat", "text": "sentinel-42"})
        first_chat = _await(third_party, "chat")

    assert first_chat.get("text") == "sentinel-42", (
        "第三方收到的第一条终局帧不是哨兵 —— 要么未绑号那句漏出去了（闸没生效），"
        f"要么闸把已绑号的人也挡了（拿到 error 帧）：{first_chat}"
    )


def test_chat_on_the_box_is_not_phone_gated(app, client, monkeypatch):
    """**盒子上这个闸必须不落。** 不是「暂时不做」，是它在那里必然判错。

    两条已核实的事实合起来：
    1. 盒上的用户是 `_get_or_create_shadow_user`（endpoints/auth.py:265）建的影子用户，
       只有 username + `SHADOW_USER_NO_LOCAL_AUTH`，**根本没写手机号列**
       ⇒ `phone_bound` 在盒上结构性恒为 False；
    2. 四个手机端点被 `_guard_phone_endpoint`（endpoints/auth.py:44）在盒上一律
       403/503 ⇒ **盒上没有任何绑定入口**。

    ⇒ 在盒上照读这个布尔 = 每台 kiosk 上的每个用户被永久禁言、且无法自救，
    **包括那些在云端明明已经绑了号的人** —— 绑没绑这件事盒子本地根本不知道。
    而盒上的这条 WS 是**本机 LAN 广播**（`manager.broadcast_to_session` 只发给连着这台
    盒子这一局的 socket），发言的人就在棋盘旁边。

    先取 token 再切模式：board 模式下 `/auth/login` 会走 `remote_client` 那条转发分支。
    """
    _make_user(app, "boxuser")                      # 影子用户就是这个形状：没有手机号
    session = _inject_session(app)
    token = _token(client, "boxuser")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    with client.websocket_connect(f"/ws/{session.session_id}?token={token}") as ws:
        ws.send_json({"type": "chat", "text": "hello"})
        frame = _await(ws, "chat", "error")
    assert frame["type"] == "chat", f"盒上未绑号被闸住了 —— 每台 kiosk 都会永久禁言：{frame}"
    assert frame["text"] == "hello"


# ------------------------------------------------------------- 直播评论（REST）


def test_live_comment_from_an_unbound_user_is_403(live_service, client):
    _make_user(live_service, "nophone")
    r = client.post(
        COMMENTS,
        json={"content": "hi"},
        headers={"Authorization": f"Bearer {_token(client, 'nophone')}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "comment_requires_phone"


def test_live_comment_from_a_bound_user_succeeds(live_service, client):
    """**正对照。** 否则「403」与「这条端点本来就不通」是同一个观测值。"""
    _make_user(live_service, "bound", phone="+8613800138000")
    r = client.post(
        COMMENTS,
        json={"content": "hi"},
        headers={"Authorization": f"Bearer {_token(client, 'bound')}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "hi"
    assert r.json()["username"] == "bound"
