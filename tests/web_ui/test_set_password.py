"""改密码：要验证码、不要当前密码。

「忘了密码的人给不出当前密码」是个死结，验证码解开它；而且比只验当前密码更强 ——
会话被劫持的攻击者拿不到手机，改不了密码。

夹具形状与 tests/web_ui/test_phone_bind.py 一致（都照抄 test_billing_api.py:20-50）：
独立 sqlite + `AsyncClient(ASGITransport(app))`，不跑 lifespan。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

SEND = "/api/v1/auth/phone/send-code"
SET = "/api/v1/auth/set-password"


class _Capture:
    def __init__(self):
        self.codes = []

    async def send(self, phone_e164, code, is_intl):
        self.codes.append(code)


@pytest.fixture
def sms(monkeypatch):
    from katrain.web.core import sms as sms_module

    cap = _Capture()
    monkeypatch.setattr(sms_module, "get_provider", lambda: cap)
    return cap


@pytest.fixture
def app(tmp_path, monkeypatch, sms):
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'set_password.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    application = create_app(enable_engine=False)
    application.state.session_factory = TestSessionLocal
    application.state.user_repo = SQLAlchemyUserRepository(TestSessionLocal)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _override_get_db
    try:
        yield application
    finally:
        engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _make_user(app, username, password="pw123456", phone=None):
    from passlib.context import CryptContext
    from katrain.web.core import models_db

    app.state.user_repo.create_user(username, CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password))
    session = app.state.user_repo.session_factory()
    try:
        u = session.query(models_db.User).filter_by(username=username).one()
        if phone is not None:
            u.phone_e164 = phone
            session.commit()
        return u.id
    finally:
        session.close()


async def _login(client, username, password):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def _auth(client, username, password="pw123456"):
    r = await _login(client, username, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _cid(client, phone, purpose):
    r = await client.post(SEND, json={"phone": phone, "purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()["challenge_id"]


async def test_set_password_requires_auth(client):
    r = await client.post(SET, json={"challenge_id": "x", "code": "000000", "new_password": "pw87654321"})
    assert r.status_code == 401


async def test_sets_password_and_the_old_one_stops_working(app, client, sms):
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 200, r.text
    assert (await _login(client, "pwuser", "newpw123456")).status_code == 200
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 401


async def test_challenge_phone_must_match_the_current_users_phone(app, client, sms):
    """少了这一步，一个人可以拿**自己号上的码**去改**别人的**密码。

    这里的 challenge 是给受害者的号发的（现实里攻击者拿不到那个码；
    测试里假供应商看得见，所以能把这条防线单独量出来）。
    """
    _make_user(app, "victim", password="vpw123456", phone="+8613900139000")
    _make_user(app, "attacker", password="apw123456", phone="+8613800138000")
    h = await _auth(client, "attacker", "apw123456")
    cid = await _cid(client, "13900139000", "set_password")  # 受害者的号

    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "hax12345678"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "challenge_phone_mismatch"
    assert (await _login(client, "victim", "vpw123456")).status_code == 200, "受害者的密码不许被改动"


async def test_unbound_user_gets_phone_unbound_not_a_generic_error(app, client, sms):
    _make_user(app, "nophone", password="pw123456")
    h = await _auth(client, "nophone")
    cid = await _cid(client, "13800138000", "set_password")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "phone_unbound"


async def test_rejects_a_login_purpose_challenge(app, client, sms):
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "login")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_old_access_and_refresh_tokens_are_rejected_after_the_password_change(app, client, sms):
    """改密码**立刻**作废此前签发的 access 与 refresh（P1，2026-09-13 换轨）。

    **这条原来钉的是反面**：那时 JWT 载荷只有 sub/exp/type、没有密码版本位，
    `/auth/refresh` 只验签名 + 用户名存在，而 `REFRESH_TOKEN_EXPIRE_DAYS = 90`
    ⇒ 持票人改完密码还能连续换发三个月。P1 把主体换成 `users.uuid` 并加了
    `token_epoch`：`set_password_hash` 在写密码的同一条 UPDATE 里 +1，两个解析点
    都拿票里的 epoch 跟库里比。所以断言整个翻过来了 —— **不是功能坏了，是被断言的
    那个限制不存在了**。原样 skip 掉等于这条路以后再没人量。

    与 `test_identity_subject.py` 那条同名闸**不重叠**：那条直接调
    `repo.set_password_hash`，量的是仓储；这条走真的 `/auth/set-password`
    （验证码那一路），量的是**端点确实调到了它** —— 哪天有人把那句改成别的写法，
    仓储那条仍绿、这条会红。

    最后两句是反向断言：新口令必须登得进来、新签的票必须 200。少了它，一个把所有
    票都打成 401 的实现（epoch 比较写反之类）也能让上面两句全绿，而那是把登录打死。
    """
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    login = await _login(client, "pwuser", "oldpw123456")
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]
    h = {"Authorization": f"Bearer {old_access}"}

    cid = await _cid(client, "13800138000", "set_password")
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 200, r.text

    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.status_code == 401, f"改密码后旧 access token 仍然有效：{me.status_code}"
    again = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert again.status_code == 401, f"改密码后旧 refresh token 仍能换发：{again.status_code} {again.text}"

    fresh = await _auth(client, "pwuser", "newpw123456")
    assert (await client.get("/api/v1/auth/me", headers=fresh)).status_code == 200, (
        "新口令签出来的票也被拒了 ⇒ 拒的是所有票不是旧票"
    )


async def test_set_password_is_unreachable_on_a_strict_box(app, client, sms, monkeypatch):
    """strict 盒子上这条路不通，而且**什么都没发生**。

    断的是 401 不是 403：strict 模式下 Bearer 头被忽略、只认 `sb_go_token` cookie
    （core/box_sso.py:72-75），`Depends(get_current_user)` 在函数体之前就挡了。
    守着 `_guard_phone_endpoint` 真被调用的是下一条（board 503）。
    """
    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    assert r.status_code == 401

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 200, "盒子上那次请求不许改到密码"


async def test_set_password_503_on_board_and_does_not_forward(app, client, sms, monkeypatch):
    """非 strict 盒子：503 `need_online_phone`，**且一个远端方法都不调**。

    Task 7/8/9 三个端点各有这一条，Task 10 原来没有 ——
    于是代码里 `_guard_phone_endpoint(request)` 虽然调了，却没有任何断言守着它：
    哪天有人把它挪到 `verify_and_consume` 之后或删掉，全套仍绿。
    """
    from unittest.mock import MagicMock

    _make_user(app, "pwuser", password="oldpw123456", phone="+8613800138000")
    h = await _auth(client, "pwuser", "oldpw123456")
    cid = await _cid(client, "13800138000", "set_password")

    remote = MagicMock()
    app.state.remote_client = remote
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    try:
        r = await client.post(SET, json={"challenge_id": cid, "code": sms.codes[-1], "new_password": "newpw123456"}, headers=h)
    finally:
        app.state.remote_client = None
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote.method_calls == []
    assert (await _login(client, "pwuser", "oldpw123456")).status_code == 200, "被闸挡住时密码不许被改"
