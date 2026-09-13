"""鉴权主体换轨：JWT 的 sub 装 users.uuid，并用 token_epoch 让改密码即刻失效会话。

四条闸：
  闸 1 改密码后旧 access 与旧 refresh 双双 401、而新签的票仍 200（P1 的核心价值，此前无人守）
        —— 外加一条：`token_epoch` 为 NULL 的迁移库行也必须 bump 得动
  闸 2 token 的 sub 是 32 位十六进制且不等于用户名（防有人改回去）
  闸 3 token_epoch 为 NULL 的行（迁移旧库的形状）仍能正常鉴权
  闸 4 epoch 已经**离开 0** 的账号（改过密码、再用新密码登录）续期照常 200，
        且换发回来的 access 带的是当前 epoch —— 这条守的是「0 == 0 恒成立」的反面：
        闸 1 只证了旧票被拒，没有任何用例证过本人重新登录之后续期还走得通

变异验证（2026-09-13，逐条实跑：改坏 → 跑 → 还原 → grep 回读）：

口径是**恰好**不是至少 —— 既确认该红的红了，也确认没有别的红。
基线（未改动、同一条命令）：**54 passed / 0 failed**，所以下面每一条红都是新增的。
命令：`./.venv/bin/python -m pytest tests/web_ui/{test_identity_subject,test_set_password,
test_auth_api,test_phone_endpoints}.py -q -p no:randomly`

  M1 get_user_from_token 删掉 epoch 比较 → **2 红**（预期 1）
     本文件 test_old_access_and_refresh_tokens_both_stop_working_after_a_password_change
     + test_set_password.py::test_old_access_and_refresh_tokens_are_rejected_after_the_password_change。
     两条都停在 **access** 那句断言。多出来的那条不是作用域失控：同一件事
     test_set_password.py 也守着一份，只跑本文件时看不见它。

  M2 refresh 端点删掉 epoch 比较 → **同样那 2 条**，但停在 **refresh** 那句断言
     ⇒ 闸 1 的两半确实分得开，不是一句断言兼管两件事。

  M3 set_password_hash 删掉整个 "token_epoch" 键 → **4 红**（预期 2）
     闸 1 的两条 repo 级 + 上面两条 e2e。多出的两条是同一缺陷在 HTTP 层的样子。

  M3b（窄变异，复核 Task 5）coalesce 退回裸 `User.token_epoch + 1` → **恰好 1 红**：
     test_changing_the_password_bumps_epoch_even_when_the_column_is_null。
     与 Task 5 的结论一致（本轮自己重跑，未转述）。M3 是「完全不 bump」，
     M3b 才是「只有 NULL 行 bump 不动」—— 后者是那个 coalesce 真正守的东西。

  M4 /auth/login 的 **access** 铸造改回 username → **15 红**（预期 1）
     闸 2 是唯一**点名病因**的那条（"sub 不是 32 位十六进制：'alice'"）；
     其余 14 条只报 401 —— sub='alice' 时 get_user_by_uuid 查不到行，
     整个已登录面当场塌掉。闸 2 在这里的价值是**诊断**，不是发现。

  M5 读取侧 `(user_dict.get("token_epoch") or 0)` → `user_dict["token_epoch"]`
     → **恰好 1 红**：闸 3。矩阵里唯一一条严格「恰好」的。

  M6 get_user_by_uuid 改回 .first() → **休眠，本轮未执行**。
     实测（非转述）：`ix_users_uuid` 今天是 UNIQUE 索引，把第二行 uuid 改成重复
     会被 `UNIQUE constraint failed: users.uuid` 挡回 ⇒ 正常写入路径构造不出重复行。
     **一个要留痕的判断**：闸 1/3 用 `PRAGMA writable_schema` 摘 NOT NULL 是允许的，
     因为「迁移旧库上 token_epoch 可空」这个形状**线上真实存在**；同样的手法也能摘掉
     uuid 的唯一索引把 M6 跑起来，但那造出来的是**今天任何真实库都没有的形状**。
     差别就在这儿 —— 所以这一格记休眠，不硬凑。硬凑的闸比没有更坏。

  M7（brief 之外，专为探覆盖缺口而加，允许它什么都不红）
     /auth/login 的 **refresh** 铸造改回 username → **一条都没红，54 全绿**。
     ⇒ 这个铸造点今天**无人守**。7 个铸造点里只有登录那张 access 被闸 2 盯着。
     而且比「没闸」更糟：临时探针实测，改坏之后**没改过密码的正常换发也返 401**
     （同一探针在干净代码上是 200）⇒ 全体用户的 token 续期永久失效，
     而闸 1 那两条仍然绿 —— 它们断言的正是 401，只是这次 401 来自另一个病因。

     **已补（Task 6b，2026-09-13）**：两条断言并入闸 2 —— 不新开一条闸，理由是
     闸 2 已经在同一个函数里问过「这次登录签出来的 access token 的 sub 对不对」，
     refresh 是同一次登录的另一张票，问法相同。补法：decode 登录响应里的
     `refresh_token`，重复闸 2 对 access 做的两条形状断言（32 位十六进制、不等于
     用户名），再拿它去打一次 `/auth/refresh` 断言 200 —— 前两句认形状，最后一句
     认行为（全仓另两处 refresh-200 断言喂的都是 `refresh_token_for` 自己签的票，
     量的不是这个操作数）。重跑同一条全量命令验证：**恰好 1 红**——
     `test_minted_subject_is_the_account_uuid_not_the_username`，停在新加的
     `refresh 的 sub 不是 32 位十六进制：'alice'` 那句，其余 53 条不受影响；
     还原 `auth.py` 后回到 54 passed。

  M8 见闸 4 自己的 docstring（新加的那条 refresh 往返闸）。

  M9 / M10（2026-09-13，终审 must_fix 的可选项：把两个解析点的
     `int(payload.get("epoch", 0))` 收紧成「缺 epoch 键即 401」）——
     这一对是**同一个变异跑两遍**，一遍在收紧前、一遍在收紧后，量的是收紧本身值多少：

       M10b 收紧**前**：`/auth/register` 的铸造点整个删掉 `epoch` 键
            → **68 passed / 0 failed，一条都没红**。缺键被读成 0，而所有测试账号的
            `token_epoch` 也是 0 ⇒ `0 == 0` 恒成立，这一整类「铸造点漏写 epoch」
            的缺陷对 CI 完全不可见。
       M10a 收紧**后**：同一个变异 → **1 红**
            （test_phone_endpoints.py::test_phone_login_issues_a_token_for_a_bound_user）。

       M9b / M9a 是同一对跑在 `/auth/login` 的 access 铸造点上：收紧前 3 红、
            收紧后 15 红。那个点本来就有闸（闸 2 的 `"epoch" in payload` 与闸 4），
            所以它证不了「不可见」，只证了射程 —— 真正「不可见」的那一格是 M10b。

     命令：`./.venv/bin/python -m pytest tests/web_ui/{test_identity_subject,
     test_set_password,test_auth_api,test_board_auth,test_phone_endpoints}.py
     -q -p no:randomly`（基线 68 passed / 0 failed）。
     收紧的射程实测只碰到**一个**测试铸造点：test_box_sso.py 那张刻意签坏的票
     （它在 strict 的 403 之前就返回了，走不到解析侧；给它补 epoch 只为让
     「全仓每个铸造点都写 epoch」不留例外）。
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

    # M7（2026-09-13 变异实测）：refresh 的铸造点原本无人守 —— 把它的 sub 改回用户名，
    # 全量 54 条一条不红，而真实后果是所有人的续期永久 401。闸 1 那条 e2e 挡不住它：
    # 它断言的正是 refresh 返回 401，换个病因照样绿。
    refresh_payload = jwt.decode(
        resp.json()["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert _HEX32.match(refresh_payload["sub"]), f"refresh 的 sub 不是 32 位十六进制：{refresh_payload['sub']!r}"
    assert refresh_payload["sub"] != "alice"

    # 上面两句认的是形状，这句认的是行为。全仓另外两处 refresh 的 200 断言，
    # 喂进去的 token 都是 `refresh_token_for` 自己签的 ⇒ 它们量的不是这个操作数。
    # 这是唯一一条「登录签出来的 refresh 票真的换得出新票」。
    renewed = await phone_auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": resp.json()["refresh_token"]}
    )
    assert renewed.status_code == 200, f"登录签出来的 refresh token 换不出新票：{renewed.status_code} {renewed.text}"


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


async def test_refresh_round_trip_still_works_after_the_epoch_left_zero(phone_app, phone_auth_client):
    """改完密码、用**新密码**重新登录之后，续期这条路必须照常走得通。

    这是 P1 核心承诺的后半句（前半句「旧票立刻失效」由上面闸 1 那条守）。它此前零覆盖：
    全仓断言 `/auth/refresh` 返 200 的三条用例，账号 `token_epoch` 全是 0，而
    **`0 == 0` 恒成立** ⇒ 把 auth.py 里换发那一处、或 /auth/login 铸造那一处的
    epoch 参数写坏，全量测试与基线 comm 依旧「新增失败为空」。真实后果是**只有用过
    改密码功能的人**（也就是这个特性的全部用户）在票过期后续期永久 401；盒子上更隐蔽
    —— remote_client.py 在 refresh 返 200 时主动把 `_auth_required` 清成 False，
    `is_authenticated` 因此恒为 True，用户看到的是「功能静默不工作」而不是「请重新登录」。

    **两句 `!= 0` 是这条闸的全部价值所在** —— 少了它们，这条用例在 epoch 恒为 0 的
    世界里照样绿，等于白写。所以断言写成「等于库里那个值**并且**不是 0」，两半都要：
    只比库值会被「两边一起是 0」蒙混，只比 0 又不认换发有没有跟上当前 epoch。

    改密码必须写真的 `get_password_hash(<新密码>)`：闸 1 那条 e2e 传的
    `"whatever-new-hash"` 是个假 hash，`verify_password` 过不了 —— 照抄它，第 2 步就登不进去。

    变异验证（2026-09-13，实跑：改坏 → 跑 → 还原 → grep 回读）：

      M8 /auth/refresh 换发那一处（auth.py 的 `create_access_token(data={"sub": subject,
         "epoch": ...})`）把 epoch 写死 `0` → **恰好 1 红**，就是本条，停在
         `换发的 access epoch 与库里对不上：0 vs 1`。
         命令：`./.venv/bin/python -m pytest tests/web_ui/{test_identity_subject,
         test_set_password,test_auth_api,test_board_auth}.py -q -p no:randomly`
         —— 基线（未改动、同一条命令）**44 passed / 0 failed**，改坏后
         **1 failed / 43 passed**，所以那一条红是新增的。同一条命令下另外两处断言
         refresh 返 200 的用例（本文件闸 2、test_board_auth.py 的 charlie/dave）全绿
         ⇒ 它们量的确实不是这个操作数，那三个账号的 epoch 都还是 0。
    """
    from jose import jwt

    from katrain.web.core.auth import get_password_hash
    from katrain.web.core.config import settings

    repo = phone_app.state.user_repo
    user = repo.get_user_by_username("alice")
    repo.set_password_hash(user["id"], get_password_hash("newpw654321"))

    db_epoch = repo.get_user_by_username("alice")["token_epoch"]
    assert db_epoch != 0, f"改密码没把 epoch 抬离 0（拿到 {db_epoch!r}）⇒ 下面两句 != 0 全是空跑"

    resp = await phone_auth_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "newpw654321"}
    )
    assert resp.status_code == 200, f"改完密码用新密码登不进去：{resp.status_code} {resp.text}"
    login = resp.json()

    minted = jwt.decode(login["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert (
        minted.get("epoch") == db_epoch
    ), f"登录铸出来的 access epoch 与库里对不上：{minted.get('epoch')!r} vs {db_epoch!r}"
    assert minted.get("epoch") != 0, "铸出来的 epoch 是 0 ⇒ 这条闸退化成 0 == 0，什么都没量"

    renewed = await phone_auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert (
        renewed.status_code == 200
    ), f"epoch≥1 的账号换不出新票 ⇒ 改过密码的人续期永久 401：{renewed.status_code} {renewed.text}"

    rotated = jwt.decode(
        renewed.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert (
        rotated.get("epoch") == db_epoch
    ), f"换发的 access epoch 与库里对不上：{rotated.get('epoch')!r} vs {db_epoch!r}"
    assert rotated.get("epoch") != 0, "换发出来的 epoch 是 0 ⇒ 拿它打任何接口都会被 epoch 闸拒掉"

    me = await phone_auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {renewed.json()['access_token']}"},
    )
    assert me.status_code == 200, f"换发回来的 access token 用不了：{me.status_code} {me.text}"
