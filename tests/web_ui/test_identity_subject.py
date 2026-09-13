"""鉴权主体换轨：JWT 的 sub 装 users.uuid，并用 token_epoch 让改密码即刻失效会话。

三条闸：
  闸 1 改密码后旧 access 与旧 refresh 双双 401（P1 的核心价值，此前无人守）
  闸 2 token 的 sub 是 32 位十六进制且不等于用户名（防有人改回去）
  闸 3 token_epoch 为 NULL 的行（迁移旧库的形状）仍能正常鉴权
"""
import re

import pytest
from sqlalchemy import create_engine, text
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


async def test_a_user_row_with_null_token_epoch_still_authenticates(phone_app, phone_auth_client):
    """迁移旧库上 token_epoch 可空（见 test_token_epoch_migration.py）。

    把该用户的 epoch 直接置 NULL，再用他的 token 打 /auth/me —— 必须仍然 200。
    读取侧一旦把 `or 0` 删掉，这条变成 401。

    仓储上**没有** `.engine` 属性，拿 engine 的方法是 `repo._bind()`
    （core/auth.py:143，它自己的 docstring 解释了为什么不能抓模块级全局 engine）。
    同时请求 `phone_app` 与 `phone_auth_client` 拿到的是同一个 app（pytest 夹具按用例缓存）。

    **为什么要先改建表语句**：`phone_app`(conftest.py:152) 建库走的是
    `Base.metadata.create_all`，也就是「全新建库」那条分叉，`token_epoch` 上带
    NOT NULL —— 直接置 NULL 会 IntegrityError。而本闸要断言的行为属于「迁移旧库」
    那一半（`migrations.add_missing_columns` 拼的 ADD COLUMN 不带 NOT NULL，
    migrations.py:341）。所以先把这张表改成迁移库的形状，再置 NULL：造的是**输入**，
    结论（/auth/me 仍 200）仍由真实 HTTP 路径量出来。
    """
    resp = await phone_auth_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"}
    )
    token = resp.json()["access_token"]

    repo = phone_app.state.user_repo
    engine = repo._bind()
    with engine.begin() as conn:
        ddl = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")).scalar()
    patched = re.sub(r"(token_epoch\s+INTEGER[^,\n]*?)\s+NOT NULL", r"\1", ddl)
    assert patched != ddl, "users 上 token_epoch 没有 NOT NULL —— 这条正则过期了，本闸在假装造了迁移库"
    with engine.begin() as conn:
        conn.execute(text("PRAGMA writable_schema=ON"))
        conn.execute(text("UPDATE sqlite_master SET sql=:s WHERE type='table' AND name='users'"), {"s": patched})
        conn.execute(text("PRAGMA writable_schema=OFF"))
    engine.dispose()  # 让 SQLite 重新解析 schema；conftest 收尾本来也 dispose，提前一次无害
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET token_epoch = NULL WHERE username = 'alice'"))
    assert repo.get_user_by_username("alice")["token_epoch"] is None, "没造出 NULL，本闸下面那句是空跑"

    me = await phone_auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200, f"token_epoch 为 NULL 的行鉴权失败了：{me.status_code} {me.text}"
