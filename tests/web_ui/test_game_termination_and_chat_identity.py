"""终结这局的权限,和「谁说的这句话」由谁决定。

两条都是**在这之前不存在**的守卫,不是加固:

1. `/api/resign` 与 `/api/timeout` 只要求 `get_current_user_optional`,而两者都会记录终局、
   判出胜方(`winner = 对手`)并广播 `game_end`。任何登录用户拿到一个 session_id,就能把
   一局陌生人的活棋判负、把胜利记进对手账上。session_id 也不需要猜:
   `GET /api/v1/games/active/multiplayer` 至今不带鉴权,返回的正是全部在跑的 session_id。

2. 房间聊天是 `broadcast_to_session(session_id, message)` —— 把客户端原样送来的 dict
   整包广播回房间。`sender` 是发送方自己写的,而且 payload 没有长度上限。

三棋共享侧 `lobby_api` 修过同一个聊天病(`7caab6137`),四家 wire 契约把结论钉成了字段名:
`shapes.Chat` = `{from_id, from_name, text}`,身份两项由服务端填,**叫 `from_name` 不叫
`sender`**;超长**拒绝**而不是截断(静默截断会让发出去的和收到的不是同一句话)。

每条否定用例都配了正对照。没有正对照,「403」和「这条端点本来就不通」分不开 —— 而后者
会让守卫看起来生效、实际上是端点被别的东西挡住了。
"""

import threading
import uuid

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from katrain.web.core.config import settings
from katrain.web.core.db import Base
from katrain.web.server import CHAT_MAX_LEN, create_app


@pytest.fixture
def app(tmp_path):
    """独立的库 + `settings.DATABASE_URL` 用完必还。

    `settings` 是**进程级单例**,而 pytest 一个进程跑完整个目录。第一版这个 fixture 把
    `DATABASE_URL` 改成自己的库却没有还回去,于是排在后面的 `test_user_data_api.py`
    连到了本模块留下的那个库,报 `ValueError: User already exists` —— 失败出现在一个
    与本次改动毫无关系的文件里。**先跑一次干净树取基线再 diff,才看得出这两条是我造的**;
    单看「26 个红」会顺理成章地判成既有噪声。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.game_repo import GameRepository

    db_path = tmp_path / "termination.db"
    previous_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite:///{db_path}"

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    # **这一行才是真正生效的那一处。** 底下两行单独存在时是装饰性的：`client` fixture
    # 的 `with TestClient(app)` 会跑 lifespan，而 `_lifespan_server` 无条件用全局
    # `SessionLocal` 重建六个 repo 再覆盖 `app.state` —— 注入在 `TestClient` 之前、
    # 覆盖在之后，于是上面这个 tmp 库从头到尾一行没写过，19 个 `alice-/bob-/mallory-`
    # 用户全落进了开发机的真实 dev 库，而测试一直是绿的（断言只看 HTTP 行为）。
    # 2026-08-23 用 SQL 层探针量出来的；`tests/conftest.py` 现在有闸守着。
    application.state.session_factory = Session
    # 下面两行留着是为了不经 lifespan 直接用 `app` fixture 的用例；经 lifespan 时
    # 它们会被覆盖成由同一个 `Session` 建出来的等价物。
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


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _token(client, username: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "password"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _inject_session(app, *, user_id=None, player_b_id=None, player_w_id=None):
    """把一个多人局(或单机局)直接塞进 session manager。

    conftest 把 `katrain.web.interface` 整个换成了 MagicMock,所以走 HTTP 真开一局不会
    执行到 WebKaTrain —— 沿用本目录既有做法(test_ranked_rules.py / test_ai_game_autosave.py),
    手工构造一个够真的 session。
    """
    session = MagicMock()
    session.session_id = uuid.uuid4().hex
    session.user_id = user_id
    session.player_b_id = player_b_id
    session.player_w_id = player_w_id
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


# ------------------------------------------------------- 终结守卫


@pytest.mark.parametrize("endpoint", ["/api/resign", "/api/timeout"])
def test_an_outsider_cannot_end_someone_elses_game(app, client, endpoint):
    """局外人终结别人的活局 → 403。

    正对照在下一条:同一个端点、同一局,换成参与者就能终结。两条一起才排除了
    「这条端点本来就不通」—— 单看 403 说明不了守卫生效。
    """
    black_id, _ = _make_user(app, "alice")
    white_id, _ = _make_user(app, "bob")
    _, mallory_name = _make_user(app, "mallory")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post(endpoint, json={"session_id": session.session_id}, headers=_login(client, mallory_name))
    assert resp.status_code == 403, resp.text
    assert "player in this game" in resp.json()["detail"]


@pytest.mark.parametrize("endpoint", ["/api/resign", "/api/timeout"])
def test_a_player_can_still_end_their_own_game(app, client, endpoint):
    """**正对照。** 参与者走同一条路必须能过 —— 否则上一条的 403 只是端点坏了。"""
    black_id, black_name = _make_user(app, "alice")
    white_id, _ = _make_user(app, "bob")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post(endpoint, json={"session_id": session.session_id}, headers=_login(client, black_name))
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("endpoint", ["/api/resign", "/api/timeout"])
def test_an_unclaimed_local_session_is_not_gated(app, client, endpoint):
    """三个 id 全是 None 的本地单机局**不设闸**。

    盒上未登录直接开的一局没有可越权的对象;对它要求登录只会打死离线玩法,换不来任何
    安全。这一条守的是**修复的边界**:它会在有人把守卫简化成「一律要求登录」时红。
    """
    session = _inject_session(app)

    resp = client.post(endpoint, json={"session_id": session.session_id})
    assert resp.status_code == 200, resp.text


def test_the_other_player_is_also_allowed(app, client):
    """白方也是参与者 —— 允许集不能只写成「开局的那个人」。

    多人局的 `session.user_id` 被 `create_multiplayer_session` 设成了黑方 id
    (`session.py`:`primary_user_id = player_b_id if ... >= 0 else ...`),只看 `user_id`
    的守卫会把白方一并挡在门外,而那正是最常认输的那一方。
    """
    black_id, _ = _make_user(app, "alice")
    white_id, white_name = _make_user(app, "bob")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    resp = client.post("/api/resign", json={"session_id": session.session_id}, headers=_login(client, white_name))
    assert resp.status_code == 200, resp.text


# ------------------------------------------------------- 告诉对面 vs 记进账本


@pytest.mark.parametrize("endpoint,reason", [("/api/resign", "resign"), ("/api/timeout", "timeout")])
def test_the_opponent_is_told_even_when_the_game_cannot_be_recorded(app, client, endpoint, reason):
    """落账失败**不许**吃掉「这局结束了」那条广播。

    两件事本来捆在同一个 `try` 里,广播排在 `record_multiplayer_game` 后面 ⇒ 记不进去
    就不广播。而盒上 `app.state.game_repo` **恒为 None**(board 模式那一段明写
    「Multiplayer game_repo not used in board mode」),所以这条路上每一次认输/超时
    都会把对面挂在「还在等你走」,日志里只留一句「Failed to record game result」——
    那句话一个字都没提广播也没了。

    这里就用 `game_repo = None` 造这个状态,不是另编一个异常:**盒上的形状就是它**。

    变异记录:把广播搬回 `try` 里(合入前的写法),这两条都红在最后那句 assert。
    数子和退出两处本来就把广播放在 try 外,所以只有这两条路有病 —— 那也说明
    「捆在一起」不是这份代码的约定,是这两处漏了。
    """
    black_id, black_name = _make_user(app, "alice")
    white_id, _ = _make_user(app, "bob")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    app.state.game_repo = None  # 盒上就是这个值

    sent = []
    manager = app.state.session_manager
    original = manager._schedule_broadcast
    manager._schedule_broadcast = lambda sess, msg: sent.append((sess, msg))
    try:
        resp = client.post(endpoint, json={"session_id": session.session_id}, headers=_login(client, black_name))
    finally:
        manager._schedule_broadcast = original

    assert resp.status_code == 200, resp.text
    ends = [m for _, m in sent if m.get("type") == "game_end"]
    assert ends, f"{endpoint} 落账失败后没有广播 game_end —— 对面不知道这局结束了"
    assert ends[0]["data"]["reason"] == reason
    assert ends[0]["data"]["winner_id"] == white_id


# ------------------------------------------------------- 聊天身份


def _chat_socket(client, session_id: str, token: str):
    return client.websocket_connect(f"/ws/{session_id}?token={token}")


def _await(ws, *wanted: str, limit: int = 8) -> dict:
    """读到第一个 type 命中 `wanted` 的帧。

    这条 socket 一连上就会推 `game_update` 和 `spectator_count`(后者还会在别人进出时
    再来),所以「收下一帧」不等于「收我等的那一帧」。写死跳过前 N 帧的话,哪天多播一条
    无关的广播,红的会是这些测试而不是被改坏的东西。
    """
    for _ in range(limit):
        frame = ws.receive_json()
        if frame.get("type") in wanted:
            return frame
    raise AssertionError(f"{limit} 帧之内没等到 {wanted}")


def test_the_client_cannot_choose_who_it_speaks_as(app, client):
    """客户端自报的 `sender` 不作数,广播出去的身份来自会话。

    这一条同时钉住**字段名**:契约要求 `from_name`,而不是 katrain 原来那个 `sender`。
    只断言「身份对」而不断言字段名的话,四家前端仍然各读各的键。
    """
    black_id, black_name = _make_user(app, "alice")
    white_id, _ = _make_user(app, "bob")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=white_id)

    with _chat_socket(client, session.session_id, _token(client, black_name)) as ws:
        ws.send_json({"type": "chat", "text": "hi", "sender": "bob", "from_name": "bob"})
        frame = _await(ws, "chat", "error")

    assert frame["from_name"] == black_name, "身份没有被服务端覆盖 —— 冒名发言仍然可行"
    assert frame["from_id"] == black_id
    assert frame["text"] == "hi"
    assert "sender" not in frame, "客户端的键被原样转发了 —— 字段白名单没生效"


def test_over_length_chat_is_rejected_not_truncated(app, client):
    """超长**拒绝**。

    截断的话,发送方看到自己发出的是一句话、房间里收到的是另一句,而发送方看不出被改过。
    共享侧 `platform_core.config.CHAT_MAX_LEN` 上方那段写的是同一个理由。
    """
    black_id, black_name = _make_user(app, "alice")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=black_id)

    with _chat_socket(client, session.session_id, _token(client, black_name)) as ws:
        ws.send_json({"type": "chat", "text": "x" * (CHAT_MAX_LEN + 1)})
        frame = _await(ws, "chat", "error")

    assert frame == {"type": "error", "code": "chat_text_too_long"}


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"type": "chat"}, "chat_text_required"),
        ({"type": "chat", "text": 42}, "chat_text_required"),
        ({"type": "chat", "text": "   "}, "chat_text_empty"),
    ],
)
def test_malformed_chat_gets_a_code_not_silence(app, client, payload, code):
    """拒收要带 code。

    契约 `_doc` 写着「前端一律按 code 出本地化文案」—— 只关掉不回话的话,中文界面上
    这几种拒绝**没有文案可出**,用户看到的是消息凭空消失。
    """
    black_id, black_name = _make_user(app, "alice")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=black_id)

    with _chat_socket(client, session.session_id, _token(client, black_name)) as ws:
        ws.send_json(payload)
        frame = _await(ws, "chat", "error")

    assert frame == {"type": "error", "code": code}


def test_a_well_formed_chat_still_goes_through(app, client):
    """**正对照。** 上面四条拒绝之后,得证明这条 socket 上聊天本来是通的 ——
    否则「拒绝生效」和「聊天整个坏了」是同一个观测值。"""
    black_id, black_name = _make_user(app, "alice")
    session = _inject_session(app, user_id=black_id, player_b_id=black_id, player_w_id=black_id)

    with _chat_socket(client, session.session_id, _token(client, black_name)) as ws:
        ws.send_json({"type": "chat", "text": " 你好 "})
        frame = _await(ws, "chat", "error")

    assert frame["text"] == "你好", "两端空白没有被 strip"


# ------------------------------------------------------- 限长必须是源码里的字面量


def test_chat_max_len_is_a_source_literal_not_an_env_lookup():
    """`CHAT_MAX_LEN` 必须是模块级的**字面量**,不许从环境变量解析出来。

    这一条守的是四家 wire 契约 `shared.limits` 的前提,而不是 200 这个数本身:
    **跨仓的闸只能看见源码。** 一道从 vendored 源码里读这个常量的闸,看得见
    `CHAT_MAX_LEN = 200`,却看不见 `int(os.getenv("...", "200"))` 在生产上解析成了什么
    —— 那行代码在 500 和 200 时逐字相同。这个值一旦变成 env,契约就再也钉不住它,
    而且**不会有任何东西红**(2026-08-18 共享侧正是这个状态,由围棋 track 查出后拿掉)。

    数值本身的一致性**不在这里守**:那需要同时拿到契约与本仓源码,而本仓没有 smartbox
    的 submodule 也没有契约副本(全仓 `.gitmodules` 不存在)。在这里读一个隔壁仓的路径,
    只会得到一条在 CI 里静默跳过、却报绿的闸 —— 正是这几轮一直在拆的那种。
    那一半由共享仓的跨仓闸守(它同时拥有契约与 `vendor/katrain`)。

    ⇒ 分工按**操作数在哪儿**划:本仓守「它是不是字面量」,共享仓守「这个字面量等不等于契约」。
    """
    import ast
    from pathlib import Path

    import katrain.web.server as server_mod

    tree = ast.parse(Path(server_mod.__file__).read_text(encoding="utf-8"))
    assignments = [
        node
        for node in tree.body  # 只看模块级:函数里再定义一个同名的不算数
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CHAT_MAX_LEN" for t in node.targets)
    ]
    assert len(assignments) == 1, f"CHAT_MAX_LEN 在模块级出现了 {len(assignments)} 次"
    value = assignments[0].value
    assert isinstance(value, ast.Constant) and isinstance(value.value, int), (
        "CHAT_MAX_LEN 不再是字面量 —— 契约 shared.limits 那条闸从此看不见它的真值。"
        "要让它可配,得先把它从 shared.limits 里拿出来,并说明为什么四家不必一致。"
    )
    assert value.value == server_mod.CHAT_MAX_LEN, "AST 读到的值与导入到的值不一致"
