import sys
from pathlib import Path
from unittest.mock import MagicMock

# Force pytest to import the current workspace before similarly named sibling repos.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Define a list of kivy modules to mock
kivy_modules = [
    "kivy",
    "kivy.config",
    "kivy.storage",
    "kivy.storage.jsonstore",
    "kivy.utils",
    "kivy.clock",
    "kivy.properties",
    "kivy.uix",
    "kivy.uix.boxlayout",
    "kivy.uix.widget",
    "kivy.core",
    "kivy.core.window",
    "kivy.metrics",
    "kivy._event",
    "kivy.lang",
    "kivy.resources",
    "kivy.app",
    "kivy.core.clipboard",
    "kivymd",
    "kivymd.app",
    "kivymd.uix",
    "kivymd.uix.floatlayout",
]

for mod in kivy_modules:
    sys.modules[mod] = MagicMock()

# Specific mocks for values and classes
sys.modules["kivy.utils"].platform = "linux"


class MockObservable:
    pass


sys.modules["kivy._event"].Observable = MockObservable

# Mock JsonStore to behave like a dict for simple tests
import json
import os


class MockJsonStore(dict):
    def __init__(self, filename, **kwargs):
        super().__init__()
        self.filename = filename
        # Initialize with some default values to avoid KeyError in KaTrainBase
        self["general"] = {"version": "0.0.0", "debug_level": 0}
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f:
                    self.update(json.load(f))
            except Exception:
                pass

    def put(self, key, **kwargs):
        self[key] = kwargs

    def get(self, key):
        return self[key]


sys.modules["kivy.storage.jsonstore"].JsonStore = MockJsonStore

# Mock Config
sys.modules["kivy"].Config = MagicMock()
sys.modules["kivy.config"].Config = MagicMock()

# Mock katrain.web.interface to prevent kivy/lang import chain triggered
# by katrain/web/__init__.py → katrain/web/interface.py → katrain.core...
#
# sys.modules is process-global and conftest runs at collection, so this stub
# leaks into every other test collected in the same run. It has to be an
# unconditional assignment: tests in this directory poke at it as a MagicMock
# (WebKaTrain.return_value), so a setdefault that lost the race to a real import
# breaks them. Tests elsewhere that need the REAL WebKaTrain must therefore not
# import it by name -- see tests/web/test_game_types.py, which loads the module
# from disk under its own name so it cannot be handed the stub.
sys.modules["katrain.web.interface"] = MagicMock()


# P3 手机绑定/验证码登录（superpowers/tracks/phone-login）共用夹具。
# Task 7/8/9/10 的 HTTP 用例全部从这里取，不要在各自的测试文件里再造一份。
import contextlib

import pytest


class SmsOutbox(list):
    """发出去的码。**必须打这个桩**：`sms.get_provider()` 在默认配置
    （`SMS_PROVIDER=""`）下直接抛 `SmsProviderError`，不打桩的话每一次
    send-code 都走 502 分支，断言 200/429 的用例一条也不可能绿。
    """

    fail_with = None          # 置上一个异常实例，下一次 send 就抛它

    @property
    def last_code(self) -> str:
        assert self, "还没有发出过任何一条码"
        return self[-1]["code"]


@pytest.fixture
def sms_outbox(monkeypatch):
    from katrain.web.core import sms as sms_module

    box = SmsOutbox()

    class _RecordingProvider(sms_module.SmsProvider):
        async def send(self, phone_e164, code, is_intl):
            if box.fail_with is not None:
                raise box.fail_with
            box.append({"phone": phone_e164, "code": code, "is_intl": is_intl})

    monkeypatch.setattr(sms_module, "get_provider", lambda: _RecordingProvider())
    return box


@pytest.fixture
def phone_app(tmp_path, monkeypatch, sms_outbox):
    """server 模式 + 独立 SQLite。照 tests/web_ui/test_billing_api.py:22 那个形状。

    用 httpx.ASGITransport 驱动（见 phone_client）⇒ **不跑 lifespan**，
    所以 `_lifespan_server` 不会覆盖 app.state.user_repo，也不会有
    `app.state.remote_client`（server 模式本来就该没有）。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from katrain.web.core import models_db
    from katrain.web.core.auth import SQLAlchemyUserRepository
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'phone.db'}", connect_args={"check_same_thread": False}
    )
    models_db.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = create_app(enable_engine=False)
    app.state.user_repo = SQLAlchemyUserRepository(SessionLocal)

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.state.phone_test_session_factory = SessionLocal
    yield app
    engine.dispose()


@pytest.fixture
def phone_db(phone_app):
    """用例直接查库用的 session —— 与端点走的是**同一个 engine**。"""
    session = phone_app.state.phone_test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def phone_client(phone_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def phone_auth_client(phone_app):
    """已登录的普通账号 alice / oldpw123456，**没有绑手机号**。"""
    from httpx import ASGITransport, AsyncClient

    from katrain.web.core.auth import get_password_hash

    phone_app.state.user_repo.create_user(
        username="alice", hashed_password=get_password_hash("oldpw123456")
    )
    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"})
        assert r.status_code == 200, r.text
        ac.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield ac


@pytest.fixture
def phone_board_app(phone_app, monkeypatch):
    """非 strict 的盒子：有 remote_client，KATRAIN_BOX_SSO 关。"""
    from unittest.mock import AsyncMock, MagicMock

    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    remote = MagicMock()
    remote.register = AsyncMock(return_value={"id": 1, "username": "u0"})
    phone_app.state.remote_client = remote
    return phone_app


@pytest.fixture
def remote_spy(phone_board_app):
    return phone_board_app.state.remote_client


@pytest.fixture
async def phone_board_client(phone_board_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=phone_board_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def phone_strict_client(phone_app, monkeypatch):
    """strict 盒子：strict_box_sso_enabled() == True（mode=board 且 KATRAIN_BOX_SSO=1）。"""
    from httpx import ASGITransport, AsyncClient

    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", True)
    async with AsyncClient(transport=ASGITransport(app=phone_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def send_code():
    """发一条码并返回 challenge_id。**Task 8/9/10 用的就是这一个**
    （旧计划里那个没有定义体的 `_send_and_get_cid` 已作废）。"""

    async def _send(client, phone: str, purpose: str, **kwargs) -> str:
        r = await client.post(
            "/api/v1/auth/phone/send-code", json={"phone": phone, "purpose": purpose}, **kwargs
        )
        assert r.status_code == 200, r.text
        return r.json()["challenge_id"]

    return _send


@pytest.fixture
def bound_user(phone_app):
    """一个**已绑手机号**的账号。绑定直接写库 —— Task 9 才有 bind 端点，
    Task 8 不该依赖它。"""
    from katrain.web.core import models_db
    from katrain.web.core.auth import get_password_hash

    phone_app.state.user_repo.create_user(
        username="bound", hashed_password=get_password_hash("pw123456")
    )
    session = phone_app.state.phone_test_session_factory()
    try:
        u = session.query(models_db.User).filter_by(username="bound").one()
        u.phone_e164 = "+8613800138000"
        session.commit()
    finally:
        session.close()
    return {
        "username": "bound",
        "password": "pw123456",
        "phone": "13800138000",
        "phone_e164": "+8613800138000",
    }


@contextlib.contextmanager
def isolated_core_db(database_url):
    """把 `core.config/db/auth` 临时重绑到 `database_url`，退出时**原样还原**。

    为什么需要它：这几个模块在 import 时就建好了 `settings` / `engine` / `SessionLocal`
    / `get_db`，想换库只能 `importlib.reload`。而 reload 是**就地重执行模块体**——
    模块对象不变，被换掉的是里面的那些属性。凡是 `from X import Y` 的模块
    （`endpoints/auth.py` 的 `get_db`、`box_sso.py` 的 `settings`，等等）攥的仍是旧对象，
    于是：

      * 别的测试 `app.dependency_overrides[get_db] = ...` 拿到的是**新** get_db，
        与端点 `Depends(get_db)` 里的旧对象按身份匹配不上 ⇒ 覆盖静默失效、端点打到真库；
      * `monkeypatch.setattr(settings, ...)` 打的是新 settings，读它的模块看不见。

    两种失效都**不报错**，只表现为「另一个文件里几条不相干的用例红了」。
    2026-09-10 实测：不还原时 `test_sms_provider.py` 与 `test_phone_endpoints.py`
    共 10 条会红，而它们各自单独跑全绿。

    还原必须还原**属性字典**，不是把模块对象放回 `sys.modules`（模块对象从来没变过，
    那样等于什么都没做 —— 这个错我先犯了一次，是靠探针量 `a is b` 才发现的）。
    """
    import importlib
    import os
    import sys

    mods = ("katrain.web.core.config", "katrain.web.core.db", "katrain.web.core.auth")
    saved_attrs = {name: dict(vars(sys.modules[name])) for name in mods if name in sys.modules}
    saved_url = os.environ.get("KATRAIN_DATABASE_URL")
    os.environ["KATRAIN_DATABASE_URL"] = database_url
    try:
        for name in mods:
            importlib.reload(sys.modules[name])
        yield
    finally:
        for name, attrs in saved_attrs.items():
            mod = sys.modules[name]
            mod.__dict__.clear()
            mod.__dict__.update(attrs)
        if saved_url is None:
            os.environ.pop("KATRAIN_DATABASE_URL", None)
        else:
            os.environ["KATRAIN_DATABASE_URL"] = saved_url
