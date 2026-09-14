"""绑定手机号。**已绑号的账号不许再绑第二个号** —— 那是一条自助换绑路径。

夹具形状照抄 tests/web_ui/test_billing_api.py:20-50：独立 sqlite +
`AsyncClient(ASGITransport(app))`。**刻意不用 TestClient**：它会跑 lifespan，
而 `_lifespan_server` 无条件用全局 `SessionLocal` 重建六个 repo 再覆盖
`app.state`（tests/conftest.py 顶部那段长注释记了完整链路）—— 注入在前、覆盖在后，
那样写下去的行会落进开发机真库并被 conftest 的写闸拦住。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core.config import settings
from katrain.web.core.db import Base, get_db

SEND = "/api/v1/auth/phone/send-code"
BIND = "/api/v1/auth/phone/bind"
PHONE_LOGIN = "/api/v1/auth/phone/login"


class _Capture:
    """记下发出去的码的假供应商。`ConsoleProvider` 只 print，测试读不到。"""

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

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path / 'phone_bind.db'}")
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    # 手机功能总开关默认关（`PHONE_LOGIN_ENABLED`，等阿里云短信签名报备）。
    # 本文件测的是手机功能**本身**，不是那个开关 ⇒ 在这里打开，继续测「功能开着」那条路。
    # 「关着」那条路由 tests/web_ui/test_phone_feature_flag.py 单独守着。
    monkeypatch.setattr(settings, "PHONE_LOGIN_ENABLED", True)

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


async def _auth(client, username, password="pw123456"):
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _cid(client, phone, purpose):
    r = await client.post(SEND, json={"phone": phone, "purpose": purpose})
    assert r.status_code == 200, r.text
    return r.json()["challenge_id"]


async def test_bind_requires_auth(client):
    r = await client.post(BIND, json={"challenge_id": "x", "code": "000000"})
    assert r.status_code == 401


async def test_bind_sets_phone_and_returns_masked(app, client, sms):
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["phone_masked"] == "+86 138****8000"
    assert "13800138000" not in r.text, "原始号不许整串回给前端"
    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["phone_bound"] is True


async def test_bind_consumes_the_challenge_before_checking_uniqueness(app, client, sms):
    """**核销在前、查唯一性在后。** 反过来这个端点就是号码枚举器：
    任何登录用户可逐个探测「这个号有没有账号」。核销在前意味着
    你必须先控制这个号，才配知道它被占了。"""
    _make_user(app, "owner", phone="+8613800138000")
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "phone_taken"

    r2 = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r2.status_code == 400
    assert r2.json()["detail"]["code"] == "challenge_consumed", "失败那次也必须把码核销掉"


async def test_bind_rejects_a_login_purpose_challenge(app, client, sms):
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "login")
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_rebinding_a_different_number_is_refused(app, client, sms, monkeypatch):
    """已绑号的账号再绑一个新号 = **自助换绑**，必须拒。

    换绑就是旧号的解绑：3 张卡可以轮流释放号码给新账号，免费复盘份数不受卡数限制；
    而 Task 11 那条「未绑号不建桶」的短路，正确性也建在「没有解绑路径」上。
    """
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)  # 一条用例里要给两个号各发两次码
    _make_user(app, "binder")
    h = await _auth(client, "binder")

    cid1 = await _cid(client, "13800138000", "bind")
    first = await client.post(BIND, json={"challenge_id": cid1, "code": sms.codes[-1]}, headers=h)
    assert first.status_code == 200, first.text

    cid2 = await _cid(client, "13900139000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid2, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "already_bound"

    # 库里那一列一个字节都没动：旧号仍然登得进这个账号，新号仍然没有账号。
    # 断在这里而不是断 `phone_bound is True` —— 后者在换绑成功时也是 True，量不出东西。
    old = await _cid(client, "13800138000", "login")
    r_old = await client.post(PHONE_LOGIN, json={"challenge_id": old, "code": sms.codes[-1]})
    assert r_old.status_code == 200, r_old.text
    new = await _cid(client, "13900139000", "login")
    r_new = await client.post(PHONE_LOGIN, json={"challenge_id": new, "code": sms.codes[-1]})
    assert r_new.status_code == 404
    assert r_new.json()["detail"]["code"] == "phone_not_bound"


async def test_rebinding_the_same_number_is_idempotent(app, client, sms, monkeypatch):
    """同号重复绑定返 200 —— 刷新页面/网络重试不该看到一个红色的 409。"""
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)
    _make_user(app, "binder")
    h = await _auth(client, "binder")

    cid1 = await _cid(client, "13800138000", "bind")
    assert (await client.post(BIND, json={"challenge_id": cid1, "code": sms.codes[-1]}, headers=h)).status_code == 200

    cid2 = await _cid(client, "13800138000", "bind")
    r = await client.post(BIND, json={"challenge_id": cid2, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["phone_masked"] == "+86 138****8000"


async def test_bind_is_unreachable_on_a_strict_box(app, client, sms, monkeypatch):
    """strict 盒子上这条路不通，而且**什么都没发生**。

    **注意断的是 401 不是 403。** strict 模式下 `resolve_http_token`
    只认 `sb_go_token` cookie、Bearer 头被忽略（core/box_sso.py:72-75），
    于是 `Depends(get_current_user)` 在函数体之前就把请求挡了，
    `_guard_phone_endpoint` 的 403 根本轮不到。把断言写成 403，
    断的是一件不会发生的事 —— 那条用例红了也说明不了任何问题。
    真正守住 `_guard_phone_endpoint` 被调用的是下一条（board 503）。
    """
    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    assert r.status_code == 401

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.json()["phone_bound"] is False, "盒子上那次请求不许留下任何绑定"


async def test_bind_503_on_board_and_does_not_forward(app, client, sms, monkeypatch):
    """非 strict 盒子：503 `need_online_phone`，**且一个远端方法都不调**。

    这一条是唯一守着 `_guard_phone_endpoint(request)` 真被调用的断言 ——
    把那行删掉，它当场变红。
    """
    from unittest.mock import MagicMock

    _make_user(app, "binder")
    h = await _auth(client, "binder")
    cid = await _cid(client, "13800138000", "bind")

    remote = MagicMock()
    app.state.remote_client = remote
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    try:
        r = await client.post(BIND, json={"challenge_id": cid, "code": sms.codes[-1]}, headers=h)
    finally:
        app.state.remote_client = None
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote.method_calls == [], "盒子上这条路不转发，一个远端方法都不许调"
