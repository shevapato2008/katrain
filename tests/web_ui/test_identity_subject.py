"""鉴权主体换轨：JWT 的 sub 装 users.uuid，并用 token_epoch 让改密码即刻失效会话。

三条闸：
  闸 1 改密码后旧 access 与旧 refresh 双双 401（P1 的核心价值，此前无人守）
  闸 2 token 的 sub 是 32 位十六进制且不等于用户名（防有人改回去）
  闸 3 token_epoch 为 NULL 的行（迁移旧库的形状）仍能正常鉴权
"""
import re

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.auth import SQLAlchemyUserRepository


@pytest.fixture()
def repo(tmp_path):
    # 收 session_factory 不是 URL（core/auth.py:140）。
    eng = create_engine(f"sqlite:///{tmp_path}/identity.db")
    r = SQLAlchemyUserRepository(sessionmaker(bind=eng))
    r.init_db()
    return r


def test_get_user_by_uuid_finds_the_row(repo):
    created = repo.create_user(username="uuid-user", hashed_password="h")
    found = repo.get_user_by_uuid(created["uuid"])
    assert found is not None
    assert found["id"] == created["id"]
    assert found["username"] == "uuid-user"


def test_get_user_by_uuid_returns_none_for_unknown(repo):
    assert repo.get_user_by_uuid("0" * 32) is None


def test_get_user_by_uuid_does_not_accept_a_username(repo):
    """主体换轨之后，拿用户名去查必须查不到 —— 否则等于两种主体并存。"""
    repo.create_user(username="not-a-uuid", hashed_password="h")
    assert repo.get_user_by_uuid("not-a-uuid") is None


# ---------- 闸 2：主体形状 ----------

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


async def test_minted_subject_is_the_account_uuid_not_the_username(phone_auth_client):
    """登录后 decode 自己签的 token：sub 必须是 32 位十六进制，且**不等于**用户名。

    这条是防回退闸 —— 冻结件 §2 把 username 定义成「只用于显示、不参与任何判定」，
    而它当了很久的鉴权主体。谁把 sub 改回用户名，这条当场红。

    `phone_auth_client` 是 **async** 夹具（conftest.py:191），直接 yield 一个已带
    Authorization 头的 `httpx.AsyncClient`，**不返回元组**；它建的账号写死是
    alice / oldpw123456（conftest.py:197-202）。
    """
    from jose import jwt

    from katrain.web.core.config import settings

    resp = await phone_auth_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"}
    )
    assert resp.status_code == 200, resp.text
    payload = jwt.decode(resp.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert _HEX32.match(payload["sub"]), f"sub 不是 32 位十六进制：{payload['sub']!r}"
    assert payload["sub"] != "alice"
    assert "epoch" in payload, "token 里没有 epoch ⇒ 改密码失效闸形同虚设"


# ---------- 闸 3：迁移库那条 nullable 分叉 ----------


@pytest.fixture
async def migrated_phone_app(tmp_path, monkeypatch):
    """一个**真的走过迁移**的 app —— 不是长得像迁移结果的库。

    `phone_app`（conftest.py:152）建库走 `Base.metadata.create_all`，那是**新建库**那一半，
    `token_epoch` 上带 NOT NULL。而闸 3 要证的是「走过迁移的库还能不能鉴权」——两台线上机器
    和每一台盒子的库都是迁移库，这是 P1 里最贴近生产的一条闸，所以它必须跑真的迁移。

    做法：先按模型建全套表，再把 `users` 换成**本次改动之前**的形状（没有 token_epoch），
    然后真跑一次 `migrations.add_missing_columns` —— 那条 ADD COLUMN 不带 NOT NULL
    （migrations.py:341），于是 `token_epoch` 在这里是**可空**的，与线上一致。

    SQLite 默认不强制外键（SQLAlchemy 不开 `PRAGMA foreign_keys`），所以 `DROP TABLE users`
    不会被别的表的外键拦住。
    """
    from httpx import ASGITransport, AsyncClient

    from katrain.web.core import migrations, models_db
    from katrain.web.core.auth import get_password_hash
    from katrain.web.core.config import settings
    from katrain.web.core.db import get_db
    from katrain.web.server import create_app

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)

    engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE users"))
        conn.execute(
            text(
                "CREATE TABLE users ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " uuid VARCHAR, username VARCHAR, hashed_password VARCHAR,"
                " rank VARCHAR, net_wins INTEGER, elo_points INTEGER, credits INTEGER,"
                " is_admin BOOLEAN, avatar_url VARCHAR, signup_ip VARCHAR,"
                " phone_e164 VARCHAR(20), phone_verified_at DATETIME,"
                " created_at DATETIME, updated_at DATETIME)"
            )
        )
    migrations.add_missing_columns(engine)  # 这一步才把 token_epoch 加上，且不带 NOT NULL
    migrations.create_missing_indexes(engine)  # users.uuid / users.username / phone_e164 的唯一索引

    # 前提断言：哪天迁移路径变了、这个夹具静默退化成新建库，要当场说破，
    # 而不是让闸 3 在一个 NOT NULL 的库上跑然后报绿（那就是「闸量错了对象」）。
    col = {c["name"]: c for c in inspect(engine).get_columns("users")}["token_epoch"]
    assert col["nullable"] is True, "迁移路径没造出可空的 token_epoch —— 闸 3 在新建库上跑，量错对象了"

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
    # 这个 app 不是 phone_app，`phone_auth_client` 绑的是那一个，所以 alice 要自己建。
    app.state.user_repo.create_user(username="alice", hashed_password=get_password_hash("oldpw123456"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield app, ac
    engine.dispose()


async def test_a_user_row_with_null_token_epoch_still_authenticates(migrated_phone_app):
    """迁移旧库上 token_epoch 可空（见 test_token_epoch_migration.py）。

    把该用户的 epoch 直接置 NULL，再用他的 token 打 /auth/me —— 必须仍然 200。
    读取侧一旦把 `or 0` 删掉，这条变成 401。

    仓储上**没有** `.engine` 属性，拿 engine 的方法是 `repo._bind()`
    （core/auth.py:143，它自己的 docstring 解释了为什么不能抓模块级全局 engine）。
    """
    app, ac = migrated_phone_app

    resp = await ac.post("/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    repo = app.state.user_repo
    with repo._bind().begin() as conn:
        conn.execute(text("UPDATE users SET token_epoch = NULL WHERE username = 'alice'"))
    assert repo.get_user_by_username("alice")["token_epoch"] is None, "没造出 NULL，下面那句是空跑"

    me = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, f"token_epoch 为 NULL 的行鉴权失败了：{me.status_code} {me.text}"
