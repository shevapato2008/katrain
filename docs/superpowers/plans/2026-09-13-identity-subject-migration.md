# P1 身份主体换轨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 JWT 的鉴权主体从 `users.username` 换成 `users.uuid`，并引入 `token_epoch` 让改密码即刻失效所有已签发的 access/refresh token。

**Architecture:** token 载荷从 `{"sub": <用户名>}` 变成 `{"sub": <32 位 uuid>, "epoch": <int>}`。7 个铸造点与 2 个解析点一起换轨（不能分开落，否则中间态所有鉴权全断）。`users` 表加一列 `token_epoch`，`set_password_hash` 在写密码的同一条 UPDATE 里 `+1`。不动 `username` 的唯一索引、不动任何 wire 字段 ⇒ 零跨仓改动。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · python-jose(JWT) · pytest · SQLite(测试/盒子) + PostgreSQL(生产)

**Spec:** `docs/superpowers/specs/2026-09-13-identity-subject-migration-design.md`

## Global Constraints

- 仓库 `/Users/fan/Repositories/katrain-phone-login`，分支 `feature/phone-login`，基线 `bbeb5af3`。python 用 `./.venv/bin/python`。
- **所有鉴权失败一律返 401**，detail 用该函数已有的 `credentials_exception`。**不许**让「epoch 不匹配」与「uuid 查不到」返回可区分的结果（状态码、detail、响应时间）——判据与 `katrain/web/core/auth.py:16-21` 的 docstring 同源。
- **读 `token_epoch` 一律写成 `(user_dict.get("token_epoch") or 0)`**。`migrations.add_missing_columns`（`katrain/web/core/migrations.py:341`）拼的 `ADD COLUMN` 不带 NOT NULL ⇒ 新建库是 NOT NULL、迁移旧库是 nullable。不许假设非空。
- **不动**：`users.username` 的唯一索引、`/auth/login` 的请求体、`/box-sso/bootstrap` 的 wire 字段、`_get_or_create_shadow_user` 的去重键、任何前端文件。这些属 P2/P3/P4。
- 本仓 i18n 铁律：默认中文，不用日语。本计划不新增任何用户可见文案。
- 提交信息结尾附：
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
  ```
- **`.gitignore` 有 `log*` 且 macOS 大小写不敏感**：新建测试文件后用 `git add -f <路径>` 并用 `git status --porcelain` 回读确认，不要只看 `git status`。

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `katrain/web/core/models_db.py` | `User` 加 `token_epoch` 列 | 改（1 行 + 注释） |
| `katrain/web/core/auth.py` | `_to_dict` 暴露 `token_epoch`；新增 `get_user_by_uuid`（抽象 + 实现）；`set_password_hash` bump epoch | 改（3 处） |
| `katrain/web/api/v1/endpoints/auth.py` | 7 个铸造点、2 个解析点换轨 | 改（9 处） |
| `tests/web_ui/test_token_epoch_migration.py` | 新列在「新建库」与「迁移旧库」两条路上的形状 | 新建 |
| `tests/web_ui/test_identity_subject.py` | 闸 1（改密码即刻失效）、闸 2（sub 形状）、闸 3（nullable 分叉） | 新建 |
| `tests/web_ui/conftest.py` | `token_for()` 助手 | 改（新增函数） |
| 5 个既有测试文件 | 15 处自造 token 改用 `token_for()` | 改 |
| `superpowers/tracks/phone-login/identity-freeze-change-request.md` | 交 Fan 转达身份 track 的变更请求 | 新建 |

---

### Task 1: `token_epoch` 列与它的迁移形状

**Files:**
- Modify: `katrain/web/core/models_db.py:99`（`phone_verified_at` 那行之后）
- Modify: `katrain/web/core/auth.py:437-452`（`_to_dict`）
- Test: `tests/web_ui/test_token_epoch_migration.py`（新建）

**Interfaces:**
- Produces: `models_db.User.token_epoch`（`Integer`，新建库 NOT NULL 默认 0，迁移库 nullable）；`_to_dict` 返回的字典新增键 `"token_epoch"`。Task 2–5 都读这个键。

- [ ] **Step 1: 写失败测试**

新建 `tests/web_ui/test_token_epoch_migration.py`：

```python
"""`token_epoch` 列在两条路上的形状：全新建库 与 迁移旧库。

只测 `create_all` 证明不了生产 —— 线上库早就存在，跑的是
`migrations.add_missing_columns()`（`SQLAlchemyUserRepository.init_db()` 里那一串）。
这个文件照 `tests/web_ui/test_phone_migration.py` 的夹具写法。
"""
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

from katrain.web.core import migrations, models_db


def _fresh_engine(tmp_path, name):
    """按模型新建一个库 —— 「全新部署」那条路。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    models_db.Base.metadata.create_all(eng)
    return eng


def _legacy_users_db(tmp_path, name):
    """没有 token_epoch 的 users 表 —— 线上库在这次改动之前的形状。"""
    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    md = MetaData()
    Table(
        "users",
        md,
        Column("id", Integer, primary_key=True),
        Column("username", String, unique=True, index=True),
        Column("hashed_password", String),
    )
    md.create_all(eng)
    return eng


def test_fresh_db_has_token_epoch_not_null_defaulting_to_zero(tmp_path):
    insp = inspect(_fresh_engine(tmp_path, "fresh"))
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert "token_epoch" in cols, "新建库缺 token_epoch 列"
    assert cols["token_epoch"]["nullable"] is False


def test_migration_adds_token_epoch_to_an_existing_users_table(tmp_path):
    eng = _legacy_users_db(tmp_path, "legacy")
    migrations.add_missing_columns(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("users")}
    assert "token_epoch" in cols, "迁移路径没把 token_epoch 加上"


def test_migrated_column_is_nullable_and_that_is_why_readers_must_coalesce(tmp_path):
    """**这条是刻意断言一个缺陷，不是断言一个期望。**

    `migrations.add_missing_columns`（migrations.py:341）拼的 DDL 只带 DEFAULT、
    不带 NOT NULL ⇒ 迁移库上这一列可空，而新建库上不可空。两条路结构不一致。

    本轮不修那个函数（它影响所有列、不属 P1 范围），改为在**读取侧**兜住：
    所有读 token_epoch 的地方都写 `(user_dict.get("token_epoch") or 0)`。
    这条测试把这个分叉钉住，免得有人日后看到「新建库是 NOT NULL」就把 `or 0` 删掉。
    配套的行为闸在 tests/web_ui/test_identity_subject.py 的闸 3。
    """
    eng = _legacy_users_db(tmp_path, "legacy2")
    migrations.add_missing_columns(eng)
    col = {c["name"]: c for c in inspect(eng).get_columns("users")}["token_epoch"]
    assert col["nullable"] is True, (
        "迁移库上 token_epoch 竟然是 NOT NULL —— 说明 add_missing_columns 改过了，"
        "此时读取侧的 `or 0` 可以评估是否还需要，但要连同闸 3 一起重裁"
    )


def test_to_dict_exposes_token_epoch(tmp_path):
    """解析侧要从仓储返回的字典里读它 —— `_to_dict` 是显式白名单，不加就永远读不到。"""
    from sqlalchemy.orm import sessionmaker

    from katrain.web.core.auth import SQLAlchemyUserRepository

    # SQLAlchemyUserRepository.__init__ 收的是 **session_factory**，不是 URL 字符串
    # （core/auth.py:140）。仓里既有写法见 tests/web_ui/test_lobby_sso_websocket.py:29。
    eng = create_engine(f"sqlite:///{tmp_path}/d.db")
    repo = SQLAlchemyUserRepository(sessionmaker(bind=eng))
    repo.init_db()
    created = repo.create_user(username="epoch-user", hashed_password="x")
    assert "token_epoch" in created
    assert created["token_epoch"] == 0
```

- [ ] **Step 2: 跑它，确认红，且红的原因对**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_token_epoch_migration.py -q`
Expected: **5 条里 4 条红**。红因必须是「缺 token_epoch 列 / 字典里没有这个键」，
**不是** import 错误或夹具炸。`test_migrated_column_is_nullable...` 这条在列不存在时会
`KeyError: 'token_epoch'` —— 也算正确的红。

- [ ] **Step 3: 加列**

`katrain/web/core/models_db.py`，在 `phone_verified_at = Column(...)`（第 99 行）之后插入：

```python
    # 凭据世代。改密码时 +1 ⇒ 之前签发的 access/refresh token 全部立即失效。
    # 少了它，`/auth/refresh` 只验签名 + 主体存在，改完密码的人仍能连续换发
    # 最长 REFRESH_TOKEN_EXPIRE_DAYS = 90 天（config.py:114）。
    # ⚠️ **读的时候一律 `(d.get("token_epoch") or 0)`**：migrations.add_missing_columns
    # 拼的 ADD COLUMN 不带 NOT NULL ⇒ 迁移旧库上这一列可空，与新建库结构不同。
    # 那条分叉由 tests/web_ui/test_token_epoch_migration.py 钉着。
    token_epoch = Column(Integer, nullable=False, default=0, server_default="0")
```

- [ ] **Step 4: `_to_dict` 暴露它**

`katrain/web/core/auth.py` 的 `_to_dict`（第 437 行起），在 `"phone_bound": ...` 那一行**之前**插入：

```python
            # 解析侧要拿它和 token 里的 epoch 比。pydantic `User`(models.py:181) 没有
            # 这个字段，v2 默认 extra='ignore' 会静默丢掉它 —— 那是对的，前端不需要。
            "token_epoch": user_obj.token_epoch,
```

- [ ] **Step 5: 跑测试，确认全绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_token_epoch_migration.py -q`
Expected: **5 passed**。

- [ ] **Step 6: 确认没有连带打红别人**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_migration.py tests/web_ui/test_auth_persistence.py tests/web_ui/test_auth_api.py -q`
Expected: 与改动前一致（`test_phone_migration.py` 里比较唯一列集合的那条不受影响 —— 新列不唯一）。

- [ ] **Step 7: 提交**

```bash
cd /Users/fan/Repositories/katrain-phone-login
git add -f tests/web_ui/test_token_epoch_migration.py
git add katrain/web/core/models_db.py katrain/web/core/auth.py
git status --porcelain
git commit -m "$(cat <<'EOF'
feat(identity): users 加 token_epoch 列，并钉住它的迁移分叉

改密码即刻失效会话要靠这一列。它的两条路结构不同:新建库 NOT NULL、
迁移旧库 nullable —— 因为 migrations.add_missing_columns 拼的 ADD COLUMN
不带 NOT NULL。本轮不修那个函数(它影响所有列),改在读取侧一律 `or 0`,
并用一条刻意断言该缺陷的测试钉住,免得有人日后看到新建库是 NOT NULL 就把兜底删掉。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 2: `get_user_by_uuid`

**Files:**
- Modify: `katrain/web/core/auth.py:99`（抽象基类，`get_user_by_id` 声明之后）
- Modify: `katrain/web/core/auth.py:341`（`SQLAlchemyUserRepository.get_user_by_id` 之后）
- Test: `tests/web_ui/test_identity_subject.py`（新建，本 Task 只写前两条）

**Interfaces:**
- Consumes: Task 1 的 `_to_dict`（返回的字典含 `uuid` 与 `token_epoch`）
- Produces: `UserRepository.get_user_by_uuid(user_uuid: str) -> Optional[Dict[str, Any]]`。Task 3 的两个解析点调它。

- [ ] **Step 1: 写失败测试**

新建 `tests/web_ui/test_identity_subject.py`：

```python
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
```

- [ ] **Step 2: 跑它，确认红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q`
Expected: **3 条全红**，红因是 `AttributeError: 'SQLAlchemyUserRepository' object has no attribute 'get_user_by_uuid'`。

- [ ] **Step 3: 抽象基类加声明**

`katrain/web/core/auth.py`，在 `get_user_by_id` 的 `@abstractmethod` 块（第 98-100 行）之后插入：

```python
    @abstractmethod
    def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        pass
```

- [ ] **Step 4: 实现**

`katrain/web/core/auth.py`，在 `SQLAlchemyUserRepository.get_user_by_id`（第 333-341 行）之后插入：

```python
    def get_user_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        """按 account_subject 查行。**用 `.one_or_none()` 不用 `.first()`。**

        `users.uuid` 有唯一索引（models_db.py:70-71），所以结果集基数 ≤ 1。
        用 `.one_or_none()` 的理由是：万一哪天那条唯一索引没了（迁移漏删、
        有人改了模型），它会**抛** MultipleResultsFound 而不是静默取一行 ——
        而静默取一行在鉴权路径上就是跨账号串号。
        同文件的 `get_user_by_username`(:258) 用的是 `.first()`，那是既有行为，
        本轮不动它（P3 去掉用户名唯一性时必须一起重裁）。
        """
        session = self.session_factory()
        try:
            user = session.query(models_db.User).filter(models_db.User.uuid == user_uuid).one_or_none()
            if user:
                return self._to_dict(user)
            return None
        finally:
            session.close()
```

- [ ] **Step 5: 跑测试，确认绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q`
Expected: **3 passed**。

- [ ] **Step 6: 提交**

```bash
cd /Users/fan/Repositories/katrain-phone-login
git add -f tests/web_ui/test_identity_subject.py
git add katrain/web/core/auth.py
git status --porcelain
git commit -m "$(cat <<'EOF'
feat(identity): 仓储新增 get_user_by_uuid,用 one_or_none 不用 first

users.uuid 有唯一索引,结果集基数 ≤ 1。用 one_or_none 是为了万一那条索引
哪天没了能**抛**而不是静默取一行 —— 静默取一行在鉴权路径上就是跨账号串号。
同文件的 get_user_by_username 仍是 first,那是既有行为,P3 去掉用户名唯一性时
必须一起重裁。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 3: 铸造与解析一起换轨

**⚠️ 铸造与解析必须在同一个提交里落。** 只改一半会让所有鉴权当场全断，且中间态无法测试。

**Files:**
- Modify: `katrain/web/api/v1/endpoints/auth.py` —— 铸造 7 处（`:115`、`:299`、`:350`、`:351`、`:364`、`:365`、`:402`）、解析 2 处（`:189-208` `get_user_from_token`、`:380-403` `refresh`）
- Test: `tests/web_ui/test_identity_subject.py`（追加闸 2 与闸 3）

**Interfaces:**
- Consumes: Task 2 的 `repo.get_user_by_uuid`；Task 1 的 `_to_dict["token_epoch"]`
- Produces: token 载荷 `{"sub": <32-hex>, "epoch": <int>, "exp": ..., "type": "access"|"refresh", ["box_generation": n]}`。Task 4 的 `token_for()` 按这个形状造。

- [ ] **Step 1: 追加闸 2 与闸 3 的测试**

在 `tests/web_ui/test_identity_subject.py` 末尾追加：

```python
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
    """
    resp = await phone_auth_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "oldpw123456"}
    )
    token = resp.json()["access_token"]

    repo = phone_app.state.user_repo
    with repo._bind().begin() as conn:
        conn.execute(text("UPDATE users SET token_epoch = NULL WHERE username = 'alice'"))

    me = await phone_auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200, f"token_epoch 为 NULL 的行鉴权失败了：{me.status_code} {me.text}"
```

**夹具事实（2026-09-13 已核，不用再确认）**：`phone_auth_client` 在
`tests/web_ui/conftest.py:191` 定义，是 **async 夹具**，yield 一个已经带好
Authorization 头的 `httpx.AsyncClient`，**不返回元组**；它建的账号写死是
`alice` / `oldpw123456`。所以用它的测试必须是 `async def`，且全部 `await`。
拿 engine 用 `repo._bind()`（`core/auth.py:143`），仓储上没有 `.engine` 属性。
**不要改那个夹具**——它有别的消费者（`test_phone_endpoints.py` 等）。

- [ ] **Step 2: 跑这两条，确认红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q -k "subject_is_the_account_uuid or null_token_epoch"`
Expected: 闸 2 红（`sub` 是用户名，不匹配 32-hex）；闸 3 此时**可能是绿的**（因为解析还按用户名走，epoch 根本没被读）——
**如实记录它此刻为绿**，它要到 Step 4 之后才真正生效。这属于「闸的绿分支要靠真实树、红分支要靠变异」，
闸 3 的红分支由 Task 6 的 M5 提供。

- [ ] **Step 3: 7 个铸造点换轨**

`katrain/web/api/v1/endpoints/auth.py`，逐处替换（行号为改动前）：

```python
# :115  /phone/login —— get_by_phone 已经拿到整行，直接用它的 uuid
"access_token": create_access_token(
    data={"sub": user["uuid"], "epoch": user.get("token_epoch") or 0}
),

# :299  /box-sso/bootstrap
local_access = create_access_token(
    data={"sub": shadow_user["uuid"], "epoch": shadow_user.get("token_epoch") or 0},
    box_generation=body.generation,
)

# :350-351  board login
local_access = create_access_token(
    data={"sub": shadow_user["uuid"], "epoch": shadow_user.get("token_epoch") or 0}
)
local_refresh = create_refresh_token(
    data={"sub": shadow_user["uuid"], "epoch": shadow_user.get("token_epoch") or 0}
)

# :364-365  server login
access_token = create_access_token(
    data={"sub": user_dict["uuid"], "epoch": user_dict.get("token_epoch") or 0}
)
refresh_token = create_refresh_token(
    data={"sub": user_dict["uuid"], "epoch": user_dict.get("token_epoch") or 0}
)

# :402  refresh 换发 —— 用**当前** epoch，不是 token 里那个
new_access_token = create_access_token(
    data={"sub": subject, "epoch": (user_dict.get("token_epoch") or 0)}
)
```

- [ ] **Step 4: 2 个解析点换轨**

`get_user_from_token`（第 189 行起）整体替换成：

```python
async def get_user_from_token(token: str, repo: Any, box_sso: Any = None) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject: str = payload.get("sub")
        if subject is None:
            raise credentials_exception
        if strict_box_sso_enabled() and (box_sso is None or not box_sso.validates(payload.get("box_generation"))):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_dict = repo.get_user_by_uuid(subject)
    if user_dict is None:
        raise credentials_exception
    # 改密码会把 token_epoch +1 ⇒ 之前签发的每一张票立刻对不上。
    # `or 0`：迁移旧库上这一列可空（migrations.py:341 的 ADD COLUMN 不带 NOT NULL）。
    # `int(...)` 包 try：伪造的 token 里 epoch 可以是任意 JSON 值，不能炸成 500。
    try:
        token_epoch = int(payload.get("epoch", 0))
    except (TypeError, ValueError):
        raise credentials_exception
    if token_epoch != (user_dict.get("token_epoch") or 0):
        raise credentials_exception
    return User(**user_dict)
```

`refresh`（第 380 行起的 try 块到第 403 行）替换成：

```python
    try:
        payload = jwt.decode(body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type: str = payload.get("type")
        subject: str = payload.get("sub")
        if token_type != "refresh" or subject is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    repo = request.app.state.user_repo
    user_dict = repo.get_user_by_uuid(subject)
    if user_dict is None:
        raise credentials_exception
    try:
        token_epoch = int(payload.get("epoch", 0))
    except (TypeError, ValueError):
        raise credentials_exception
    if token_epoch != (user_dict.get("token_epoch") or 0):
        raise credentials_exception

    # Board mode: also refresh remote tokens (best-effort, design 5.1)
    remote_client = getattr(request.app.state, "remote_client", None)
    if remote_client is not None:
        try:
            await remote_client._refresh_access_token()
        except Exception:
            logger.debug("Remote token refresh failed (best-effort), local refresh continues")

    new_access_token = create_access_token(
        data={"sub": subject, "epoch": (user_dict.get("token_epoch") or 0)}
    )
    return {"access_token": new_access_token, "token_type": "bearer"}
```

- [ ] **Step 5: 跑闸 2 与闸 3，确认绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q`
Expected: **5 passed**（Task 2 的 3 条 + 闸 2 + 闸 3）。

- [ ] **Step 6: 跑全量，产出「预期红」清单**

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest tests -q 2>&1 | tee /tmp/p1-after-switch.log | tail -3
grep -E '^(FAILED|ERROR) tests/' /tmp/p1-after-switch.log \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | LC_ALL=C sort -u > /tmp/p1-now.txt
LC_ALL=C sort -u superpowers/tracks/phone-login/test-baseline.txt > /tmp/p1-base.txt
comm -23 /tmp/p1-now.txt /tmp/p1-base.txt | tee /tmp/p1-expected-red.txt
wc -l /tmp/p1-expected-red.txt
```

Expected: `/tmp/p1-expected-red.txt` **非空**，且里面每一条都应落在这 5 个文件里：
`test_ai_ladder_api.py` / `test_board_auth.py` / `test_lobby_sso_websocket.py` /
`test_tutorial_db_api.py` / `test_box_sso.py`。

- [ ] **Step 7: 逐条确认红因是「token 形状变了」而不是别的**

对清单里的每个文件各挑一条，用 `-q --tb=short` 单独跑，确认错误是 401 / 拿不到身份，
**不是** 500、不是 import 错误、不是断言逻辑错。

```bash
./.venv/bin/python -m pytest "$(head -1 /tmp/p1-expected-red.txt)" -q --tb=short
```

出现任何一条红因不属于「token 形状变了」的，**停下来先查它**，不要带着往下走。

- [ ] **Step 8: 提交（此时测试是红的，刻意如此）**

```bash
cd /Users/fan/Repositories/katrain-phone-login
cp /tmp/p1-expected-red.txt superpowers/tracks/phone-login/p1-expected-red.txt
git add katrain/web/api/v1/endpoints/auth.py tests/web_ui/test_identity_subject.py
git add -f superpowers/tracks/phone-login/p1-expected-red.txt
git status --porcelain
git commit -m "$(cat <<'EOF'
feat(identity)!: JWT sub 换成 users.uuid,并加 epoch 比较

7 个铸造点与 2 个解析点必须同一个提交落 —— 只改一半所有鉴权当场全断,
且中间态无法测试。

顺带修掉一条今天就悬着的:/auth/phone/login 按手机号查行却用该行的 username
签 token,签发时选中的行与解析时 .first() 选中的行可以是不同的两行。
它今天不触发只因为 username 还唯一。

**本提交测试是红的,刻意如此。** 15 处测试自己造 token,形状变了必然红。
预期红清单已存进 superpowers/tracks/phone-login/p1-expected-red.txt,
下一个提交把它归零。逐条确认过红因都是「拿不到身份 → 401」,没有 500、
没有 import 错误。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 4: 测试助手与 15 处批量改造

**Files:**
- Modify: `tests/web_ui/conftest.py`（新增 `token_for` / `refresh_token_for`）
- Modify: `tests/web_ui/test_ai_ladder_api.py`（8 处）、`test_board_auth.py`（4 处）、
  `test_lobby_sso_websocket.py`（1 处）、`test_tutorial_db_api.py`（1 处）、`test_box_sso.py`（1 处）

**Interfaces:**
- Consumes: Task 3 的 token 形状
- Produces: `token_for(repo, username) -> str` 与 `refresh_token_for(repo, username) -> str`

- [ ] **Step 1: 在 conftest 里加助手**

`tests/web_ui/conftest.py` 末尾追加：

```python
def token_for(repo, username: str, *, box_generation: int | None = None) -> str:
    """按用户名找到那一行，用它的 **uuid + 当前 epoch** 签一张 access token。

    测试里不许再手写 `create_access_token({"sub": <用户名>})` —— 主体换轨之后
    那种 token 解不出用户，表现是 401，而错误信息会指向业务逻辑不是 token 形状，
    极易误诊。
    """
    from katrain.web.core.auth import create_access_token

    user = repo.get_user_by_username(username)
    assert user is not None, f"token_for: 库里没有用户 {username!r}"
    return create_access_token(
        data={"sub": user["uuid"], "epoch": user.get("token_epoch") or 0},
        box_generation=box_generation,
    )


def refresh_token_for(repo, username: str) -> str:
    """同上，签 refresh token。"""
    from katrain.web.core.auth import create_refresh_token

    user = repo.get_user_by_username(username)
    assert user is not None, f"refresh_token_for: 库里没有用户 {username!r}"
    return create_refresh_token(
        data={"sub": user["uuid"], "epoch": user.get("token_epoch") or 0}
    )
```

- [ ] **Step 2: 改 5 个文件里的 15 处**

逐处把 `create_access_token({"sub": <名字>})` 换成 `token_for(<该文件拿 repo 的表达式>, <名字>)`，
`create_refresh_token(data={"sub": <名字>})` 换成 `refresh_token_for(...)`。
每个文件里 repo 的取法不同（有的是 `app.state.user_repo`，有的是夹具），
**改之前先在该文件里搜一次 `user_repo` 看它怎么拿的**，不要假设。

⚠️ **其中 7 处是越权闸的「攻击者」token**（`test_ai_ladder_api.py` 的
`'receipt-attacker'` / `'state-other'` / `'analysis-other'` / `'vision-other'` /
`'resign-other'` / `'other-lifecycle-user'` / `'game-id-attacker'`）。
它们各自在紧邻几行用 `models_db.User(username=...)` 建了对应的行。
**必须用那一行的 uuid 重签，让它们继续验 403/404。**
**不许**把断言改成 401 迁就 —— 那等于把一批越权闸悄悄退役。

- [ ] **Step 3: 跑那 5 个文件**

```bash
./.venv/bin/python -m pytest tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_board_auth.py \
  tests/web_ui/test_lobby_sso_websocket.py tests/web_ui/test_tutorial_db_api.py \
  tests/web_ui/test_box_sso.py -q 2>&1 | tail -5
```
Expected: 全绿，或只剩基线里本来就有的那几条。

- [ ] **Step 4: 预期红归零**

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest tests -q 2>&1 | tee /tmp/p1-after-tests.log | tail -3
grep -E '^(FAILED|ERROR) tests/' /tmp/p1-after-tests.log \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | LC_ALL=C sort -u > /tmp/p1-now2.txt
echo "--- 仍红的预期红（必须为空）---"
comm -12 /tmp/p1-now2.txt <(LC_ALL=C sort -u superpowers/tracks/phone-login/p1-expected-red.txt)
echo "--- 新增失败（必须为空）---"
comm -23 /tmp/p1-now2.txt /tmp/p1-base.txt
```
Expected: **两个 `comm` 都输出为空。**

- [ ] **Step 5: 提交**

```bash
git add tests/
git rm --cached superpowers/tracks/phone-login/p1-expected-red.txt
rm superpowers/tracks/phone-login/p1-expected-red.txt
git status --porcelain
git commit -m "$(cat <<'EOF'
test(identity): 抽 token_for 助手,15 处自造 token 改用 uuid 重签

其中 7 处是越权闸的攻击者 token。换轨后它们会变成 401(token 解不出用户),
红因从「越权被拒」退化成「身份无效」—— 用对应 User 行的 uuid 重签让它们
继续验 403/404,没有改断言迁就 401。

预期红清单已归零并删除。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 5: 改密码即刻失效

**Files:**
- Modify: `katrain/web/core/auth.py:324-331`（`set_password_hash`）
- Test: `tests/web_ui/test_identity_subject.py`（追加闸 1）

**Interfaces:**
- Consumes: Task 1 的列、Task 3 的解析
- Produces: 改密码后 `users.token_epoch` +1

- [ ] **Step 1: 写闸 1**

在 `tests/web_ui/test_identity_subject.py` 末尾追加：

```python
# ---------- 闸 1：改密码即刻失效（P1 的核心价值） ----------


def test_changing_the_password_invalidates_previously_issued_access_tokens(repo):
    """`set_password_hash` 必须与密码写入落在同一条 UPDATE 里把 epoch +1。

    分两条 UPDATE 在并发下会丢 bump（读-改-写竞争），所以实现里用的是
    SQL 表达式 `token_epoch + 1` 而不是先读出来再加。
    """
    created = repo.create_user(username="pw-user", hashed_password="old")
    assert (created.get("token_epoch") or 0) == 0
    repo.set_password_hash(created["id"], "new")
    after = repo.get_user_by_uuid(created["uuid"])
    assert (after.get("token_epoch") or 0) == 1, "改密码没有 bump epoch ⇒ 旧票仍然有效"


async def test_old_access_and_refresh_tokens_both_stop_working_after_a_password_change(
    phone_app, phone_auth_client
):
    """端到端：改密码前签的 access 与 refresh **双双** 401。

    refresh 那一半单独重要 —— REFRESH_TOKEN_EXPIRE_DAYS = 90（config.py:114），
    少了 epoch 比较，持有 refresh token 的人改完密码仍能连续换发长达 90 天。

    显式传 Authorization 头会覆盖 `phone_auth_client` 夹具设的默认头（httpx 的
    per-request 头优先）—— 两张票都是改密码之前签的，所以都该 401。
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
```

- [ ] **Step 2: 跑，确认红**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q -k "password"`
Expected: 两条全红。第一条红在 `epoch == 1` 断言；第二条红在 `me.status_code == 401`（此时是 200）。

- [ ] **Step 3: 实现 bump**

`katrain/web/core/auth.py` 的 `set_password_hash`（第 324 行起）整体替换：

```python
    def set_password_hash(self, user_id: int, hashed: str) -> None:
        """`create_user` 之外的**第二个** `hashed_password` 写入点。

        **必须与密码写入同一条 UPDATE**：`token_epoch` 用 SQL 表达式 `+ 1`，
        不是先读出来再加。分两条或读-改-写在并发下会丢 bump，而丢一次 bump
        的表现是「改完密码，别人手里那张票还能用最长 90 天」—— 不报错、不可见。
        """
        session = self.session_factory()
        try:
            session.query(models_db.User).filter_by(id=user_id).update(
                {
                    "hashed_password": hashed,
                    "token_epoch": models_db.User.token_epoch + 1,
                },
                synchronize_session=False,
            )
            session.commit()
        finally:
            session.close()
```

- [ ] **Step 4: 跑，确认绿**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q`
Expected: **7 passed**。

- [ ] **Step 5: 跑改密码相关的既有测试**

Run: `./.venv/bin/python -m pytest tests/web_ui/test_phone_endpoints.py tests/web_ui/test_auth_api.py -q 2>&1 | tail -3`
Expected: 与 Task 4 之后一致，无新增失败。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/auth.py tests/web_ui/test_identity_subject.py
git commit -m "$(cat <<'EOF'
feat(identity): 改密码即刻失效已签发的 access 与 refresh token

set_password_hash 在写密码的**同一条 UPDATE** 里 token_epoch + 1,用 SQL 表达式
不是读-改-写 —— 丢一次 bump 的表现是「改完密码别人手里那张票还能用最长 90 天」,
不报错不可见。

refresh 那一半单独重要:REFRESH_TOKEN_EXPIRE_DAYS = 90,少了 epoch 比较,
持票人改完密码仍能连续换发三个月。这是 USENIX Security '22 五类账号预劫持里的
Unexpired Session,论文实测 74 家潜在脆弱、19 家坐实,是命中最多的一类。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 6: 变异验证

**Files:** 无产出文件；改坏 → 跑 → 还原 → grep 回读

**Interfaces:** Consumes Task 1–5 的全部实现与三条闸

- [ ] **Step 1: 逐条跑变异矩阵**

每条按同一套动作：改坏 → 跑指定测试 → 确认**恰好**是期待的那几条红 → `git checkout -- <文件>` → `grep` 回读确认还原。

| # | 改什么 | 期待变红 |
|---|---|---|
| M1 | `get_user_from_token` 里删掉 `if token_epoch != (...)` 那两行 | `test_old_access_and_refresh_tokens_both_stop_working_after_a_password_change` 的 access 那半 |
| M2 | `refresh` 里删掉同样的 epoch 比较 | 同一条的 refresh 那半 |
| M3 | `set_password_hash` 的 update 字典里删掉 `"token_epoch": ...` | 闸 1 两条同红 |
| M4 | 把 `:364` 的铸造改回 `data={"sub": user_dict["username"]}` | 闸 2 |
| M5 | `get_user_from_token` 里把 `(user_dict.get("token_epoch") or 0)` 改成 `user_dict["token_epoch"]` | 闸 3 |

```bash
cd /Users/fan/Repositories/katrain-phone-login
# 每条变异之后都要跑这句，并确认红的是且只是上表那几条
./.venv/bin/python -m pytest tests/web_ui/test_identity_subject.py -q
# 还原并回读
git checkout -- katrain/web/api/v1/endpoints/auth.py katrain/web/core/auth.py
grep -n "token_epoch" katrain/web/api/v1/endpoints/auth.py katrain/web/core/auth.py
```

- [ ] **Step 2: M6 如实记为休眠，不许硬凑**

M6 是「`get_user_by_uuid` 改回 `.first()`」。`users.uuid` 的唯一索引今天真实存在，
**构造不出重复行** ⇒ 这一格没有可执行的变异。
按「闸的每条分支都要被执行过一次」的口径，它属于**休眠闸**：守的是「约束失效那天」。
**在 `get_user_by_uuid` 的 docstring 里写明这一点**（Task 2 的 Step 4 已经写了），
并在下一步的提交信息里如实说「M6 无法执行，原因是…」。不许为了凑满矩阵编一个假变异。

- [ ] **Step 3: 确认工作树干净**

```bash
git status --porcelain -- katrain/
```
Expected: **空**。变异只临时改坏又还原，不进任何提交。

- [ ] **Step 4: 把变异记录写进测试文件的模块 docstring**

在 `tests/web_ui/test_identity_subject.py` 的模块 docstring 末尾追加实跑结果：

```python
变异验证（<填实跑日期>，逐条实跑）：
  M1 解析去掉 epoch 比较        → 闸 1 access 那半红 ✓
  M2 refresh 去掉 epoch 比较    → 闸 1 refresh 那半红 ✓
  M3 set_password_hash 不 bump  → 闸 1 两条同红 ✓
  M4 铸造改回 username          → 闸 2 红 ✓
  M5 读取去掉 `or 0`            → 闸 3 红 ✓
  M6 get_user_by_uuid 改回 .first() → **无法执行**：uuid 有唯一索引，
     构造不出重复行。属休眠闸，守的是「那条索引哪天没了」。不许硬凑。
```

- [ ] **Step 5: 提交**

```bash
git add tests/web_ui/test_identity_subject.py
git commit -m "$(cat <<'EOF'
test(identity): 变异矩阵 M1-M5 逐条实跑,M6 如实记为休眠

五条各红且只红该红的那几条,全部还原、grep 回读确认。
M6(get_user_by_uuid 改回 .first())**无法执行**:users.uuid 有唯一索引,
构造不出重复行 —— 属休眠闸,守的是那条索引哪天没了。没有硬凑一个假变异,
硬凑的闸比没有更坏。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 7: 基线比对与构建

**Files:** 无源码改动

- [ ] **Step 1: 全量 pytest 与基线比对**

```bash
cd /Users/fan/Repositories/katrain-phone-login
./.venv/bin/python -m pytest tests -q 2>&1 | tee /tmp/p1-final.log | tail -3
grep -E '^(FAILED|ERROR) tests/' /tmp/p1-final.log \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | LC_ALL=C sort -u > /tmp/p1-final.txt
LC_ALL=C sort -u superpowers/tracks/phone-login/test-baseline.txt > /tmp/p1-base.txt
echo "--- 新增失败（必须为空）---"; comm -23 /tmp/p1-final.txt /tmp/p1-base.txt
echo "--- 基线文件必须零改动 ---"; git diff --stat -- superpowers/tracks/phone-login/test-baseline.txt
```
Expected: 第一个 `comm` **输出为空**；`git diff --stat` **为空**。

两边都 `LC_ALL=C sort` 再 `comm`：基线文件当初按 `en_US` collation 排的，
直接拿它当第二个操作数会吐出**假的**新增失败。比的是**失败名字集合**不是条数。

- [ ] **Step 2: 三个前端构建**

```bash
cd /Users/fan/Repositories/katrain-phone-login/katrain/web/ui
npm run build > /tmp/b1.log 2>&1; echo "build=$?"
npm run build:kiosk-2d > /tmp/b2.log 2>&1; echo "build:kiosk-2d=$?"
npm run build:smartbox-kiosk-2d > /tmp/b3.log 2>&1; echo "build:smartbox-kiosk-2d=$?"
```
Expected: 三个都是 `0`。

三个都要跑：`build:smartbox-kiosk-2d` 是唯一跑 `verify-kiosk.sh` 严格 localStorage-token
dist 扫描的那一档。**不要用 `${PIPESTATUS[0]}` 取退出码 —— zsh 下它恒为空，不是证据。**

- [ ] **Step 3: 全量 vitest**

```bash
cd /Users/fan/Repositories/katrain-phone-login/katrain/web/ui && npx vitest run 2>&1 | tail -8
```
Expected: `0 failed`。P1 不碰任何前端文件，理应与基线一致（上次是 1775 passed / 7 skipped）。

- [ ] **Step 4: 盒端旧票路径实测（spec §10 要求，不能只读代码）**

```bash
cd /Users/fan/Repositories/katrain-phone-login
grep -n "_refresh_access_token" -B 4 -A 6 katrain/web/api/v1/endpoints/auth.py
grep -n "def _refresh_access_token" -A 20 katrain/web/core/remote_client.py
```

确认：云端换轨后盒子拿旧 refresh token 去打 `/auth/refresh` 得到 401 时，
这条路是**向上报错让用户重新登录**，还是被 `except Exception` 吞掉后静默继续。
把读到的事实写进下一步的提交信息。若确认是静默吞掉，**不要在本 Task 里修**——
记进 `superpowers/tracks/phone-login/plan.md` 的收尾清单，交 P4 处理。

- [ ] **Step 5: 提交（如有文档改动）**

```bash
git status --porcelain
# 若 Step 4 产出了要记的事实，改 plan.md 收尾清单后再 add
git commit -m "$(cat <<'EOF'
chore(identity): P1 基线比对零新增失败,三个构建与 vitest 全绿

比的是失败名字集合不是条数,两边都 LC_ALL=C sort 再 comm ——
test-baseline.txt 当初按 en_US collation 排的,直接比会吐假的新增失败。
基线文件一个字节没改。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

---

### Task 8: 冻结件变更请求（合并前置）

**Files:**
- Create: `superpowers/tracks/phone-login/identity-freeze-change-request.md`

**Interfaces:** 无代码依赖。**这是合并前置**：没有转达记录不许合。

- [ ] **Step 1: 写变更请求**

新建 `superpowers/tracks/phone-login/identity-freeze-change-request.md`：

```markdown
# 变更请求：结掉冻结件 §8-2（JWT sub 改装 account_subject）

> 提出方：围棋 track（katrain `feature/phone-login`）· <填日期>
> 目标文件：`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md`（正本在 smartbox-software 仓）
> **本 track 不得编辑正本，本文是变更请求，需 Fan 人工转达给身份 track。**

## 请求内容

1. **§8-2 从「未决」改为「已决：改」。** 决策人 Fan，2026-09-13。
2. **§6-2 第 2 条删除**（「不改 JWT `sub` 的语义」）。它推迟这件事的唯一理由是
   「改成装 uuid 会让所有存量 token 失效」——项目处于测试阶段，无真实存量 token，
   该代价已实际为零，且随上线只会变贵。
3. **§5 改写**：katrain 的 access/refresh token，`sub` 装 `users.uuid`（= `account_subject`），
   并新增 `epoch` claim（`users.token_epoch`）。验证侧按 uuid 反查并比对 epoch。
   §5 原文点名的矛盾（「用只用于显示、不参与任何判定的那个值当唯一鉴权主体」）由此消除。
4. **§2 的 `display_name` 行加一句**：katrain `users.username` 在 P1 之后**不再**是鉴权主体；
   它仍唯一（唯一索引未动），P3 会去掉唯一性并使其可改。

## 不请求变更的部分（明确划清）

- **§4 的 32-hex 冻结不动。** 本轮不改 `users.uuid` 的生成方式。
  但要提醒：sub 改装 uuid 把这个值从「只在 bootstrap 出网」提升到**每一次鉴权的热路径**，
  而 `tests/web_ui/test_account_subject_contract.py` 那条 `xfail(strict=True)` 正记着
  「铸造侧 `users.uuid` 仍是无长度的 `String`，32 位只由一个 Python default lambda 保证」。
  该缺口的优先级因此上升，但仍属身份服务 Phase 3，本轮不动。
- **§3 的四标识符表不动。** 数字公开号是第 5 个标识符，属 P2，届时另提。
- **所有 wire 字段不动。** `/box-sso/bootstrap` 仍收 `username` ⇒ setup-wizard 侧零改动。

## 实施状态

katrain `feature/phone-login` 上已实现（Task 1–7），**尚未合并**。
合并前置就是本请求被转达并有记录。
```

- [ ] **Step 2: 提交并报告**

```bash
cd /Users/fan/Repositories/katrain-phone-login
git add -f superpowers/tracks/phone-login/identity-freeze-change-request.md
git status --porcelain
git commit -m "$(cat <<'EOF'
docs(identity): 冻结件 §8-2 变更请求(合并前置)

正本在 smartbox-software 仓,四条 track 一律不得编辑只能提请求;
而维护它的象棋 track 对其余三家只出不进 ⇒ 要 Fan 人工转达。
没有转达记录不许合。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0155BRwjEx56JRrQ2U7w7grB
EOF
)"
```

- [ ] **Step 3: 向 Fan 报告未推提交与合并前置**

按本会话既定规矩：提交后**不自动 push**，如实报告未推的提交数与合并前置状态。

---

## 自检结果

**Spec 覆盖**：spec §5 列 → Task 1；§6 铸造 + §7 解析 → Task 3；§7 仓储 → Task 2；
§8 bump → Task 5；§9 错误处理 → Task 3 Step 4 的 `int()` try 与统一 401；
§10 盒端旧票实测 → Task 7 Step 4；§11 三条闸 → Task 1/3/5，批量改造 → Task 4，
变异矩阵 → Task 6，两步基线 → Task 3 Step 6 + Task 4 Step 4 + Task 7 Step 1；
§12 交付顺序 → Task 1–8 一一对应；§3 变更请求 → Task 8。**无缺口。**

**占位符扫描**：无 TBD / TODO / 「类似 Task N」/ 无代码的代码步骤。

**类型一致性**：`get_user_by_uuid(user_uuid: str) -> Optional[Dict[str, Any]]` 在
Task 2 定义、Task 3 消费，名字与签名一致；`token_for(repo, username, *, box_generation=None) -> str`
在 Task 4 定义并在同 Task 消费；token 载荷键 `sub` / `epoch` 在 Task 3 定义，
Task 4、5、6 一致引用。
