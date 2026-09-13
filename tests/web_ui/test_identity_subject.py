"""鉴权主体换轨：JWT 的 sub 装 users.uuid，并用 token_epoch 让改密码即刻失效会话。

三条闸：
  闸 1 改密码后旧 access 与旧 refresh 双双 401、而新签的票仍 200（P1 的核心价值，此前无人守）
        —— 外加一条：`token_epoch` 为 NULL 的迁移库行也必须 bump 得动
  闸 2 token 的 sub 是 32 位十六进制且不等于用户名（防有人改回去）
  闸 3 token_epoch 为 NULL 的行（迁移旧库的形状）仍能正常鉴权
"""
import re

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core.auth import SQLAlchemyUserRepository

from conftest import token_for


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


# ---------- 闸 1：改密码即刻失效（P1 的核心价值） ----------


def test_changing_the_password_invalidates_previously_issued_access_tokens(repo):
    """`set_password_hash` 必须与密码写入落在同一条 UPDATE 里把 epoch +1。

    分两条 UPDATE 在并发下会丢 bump（读-改-写竞争），所以实现里用的是
    SQL 表达式而不是先读出来再加。

    **这一条走的是全新建库那条分叉**（`token_epoch` NOT NULL、默认 0），
    所以它对「NULL + 1 = NULL」那个缺陷是绿的 —— 守那一半的是下面那条。
    """
    created = repo.create_user(username="pw-user", hashed_password="old")
    assert (created.get("token_epoch") or 0) == 0
    repo.set_password_hash(created["id"], "new")
    after = repo.get_user_by_uuid(created["uuid"])
    assert (after.get("token_epoch") or 0) == 1, "改密码没有 bump epoch ⇒ 旧票仍然有效"


def test_changing_the_password_bumps_epoch_even_when_the_column_is_null(repo):
    """迁移旧库上 `token_epoch` 可空，而 **SQL 里 `NULL + 1` 还是 `NULL`**。

    写成 `User.token_epoch + 1` 时，这些行改密码永远 bump 不动；读取侧又把 NULL
    读成 0（models_db.py:101）⇒ 旧票继续有效、不报错、不可见。所以实现里必须是
    `func.coalesce(User.token_epoch, 0) + 1`，而本闸就是守那个 coalesce 的 ——
    上面那条跑在全新建库上，永远走不到这条分支。

    造 NULL 的手法与闸 3 同源（`PRAGMA writable_schema` 摘掉 NOT NULL）：造的是
    **输入**，结论（bump 成 1）仍由真实的 `set_password_hash` 量出来。
    """
    created = repo.create_user(username="null-epoch-user", hashed_password="old")
    engine = repo._bind()
    with engine.begin() as conn:
        ddl = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")).scalar()
    patched = re.sub(r"(token_epoch\s+INTEGER[^,\n]*?)\s+NOT NULL", r"\1", ddl)
    assert patched != ddl, "users 上 token_epoch 没有 NOT NULL —— 这条正则过期了，本闸在假装造了迁移库"
    with engine.begin() as conn:
        conn.execute(text("PRAGMA writable_schema=ON"))
        conn.execute(text("UPDATE sqlite_master SET sql=:s WHERE type='table' AND name='users'"), {"s": patched})
        conn.execute(text("PRAGMA writable_schema=OFF"))
    engine.dispose()  # 让 SQLite 重新解析 schema
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET token_epoch = NULL WHERE id = :i"), {"i": created["id"]})
    assert repo.get_user_by_uuid(created["uuid"])["token_epoch"] is None, "没造出 NULL，本闸下面那句是空跑"

    repo.set_password_hash(created["id"], "new")

    after = repo.get_user_by_uuid(created["uuid"])["token_epoch"]
    assert after == 1, f"NULL 行改密码没 bump 起来（拿到 {after!r}）⇒ 迁移旧库上旧票永远有效"


async def test_old_access_and_refresh_tokens_both_stop_working_after_a_password_change(
    phone_app, phone_auth_client
):
    """端到端：改密码前签的 access 与 refresh **双双** 401，而新签的票仍 200。

    refresh 那一半单独重要 —— REFRESH_TOKEN_EXPIRE_DAYS = 90（config.py:114），
    少了 epoch 比较，持有 refresh token 的人改完密码仍能连续换发长达 90 天。

    最后那句「新票必须 200」不是凑数：**一个把所有票都打成 401 的实现**
    （bump 成 NULL、比较写反、读取侧坏掉）同样能让上面两句全绿，而那是把整个
    登录打死。少了反向断言，这条闸分不清「拒的是旧票」和「拒的是所有票」。

    显式传 Authorization 头会覆盖 `phone_auth_client` 夹具设的默认头（httpx 的
    per-request 头优先）。
    """
    resp = await phone_auth_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"}
    )
    login = resp.json()
    old_access, old_refresh = login["access_token"], login["refresh_token"]

    repo = phone_app.state.user_repo
    user = repo.get_user_by_username("alice")
    repo.set_password_hash(user["id"], "whatever-new-hash")

    me = await phone_auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"}
    )
    assert me.status_code == 401, f"改密码后旧 access token 仍然有效：{me.status_code}"

    rf = await phone_auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rf.status_code == 401, f"改密码后旧 refresh token 仍能换发：{rf.status_code} {rf.text}"

    fresh = await phone_auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_for(repo, 'alice')}"}
    )
    assert (
        fresh.status_code == 200
    ), f"改密码后新签的票也被拒了 ⇒ 拒的是所有票不是旧票：{fresh.status_code} {fresh.text}"
