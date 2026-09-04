# galaxy 支付与会员体系 —— 实施计划（第一切片）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让复盘**按实际算力**扣费、让会员额度**按日/周/月惰性重置**、让每周免费复盘走**不滚存的周额度桶**，并先把签发身份的密钥修好。

**Architecture:** 分两次发布。**Release 0** 只修账本竞争 bug 与 SECRET_KEY（不碰任何余额，可独立回滚）。**Release 1** 上计费，全程躲在 `BILLING_ENFORCED`（默认 **False**）后面：关着时行为与今天完全一致。计费复用仓库里已存在但零调用者的整数账本（`reserve/commit/refund`）：建任务时按**服务端解析出的手数**预扣，任务终态后由 **web 侧对账器**按 `analyzed_moves` 结算退差。之所以是对账不是让 worker 结算，因为 `katrain/cron/` 在 `Dockerfile.cron` 里是独立复制的子树、今天只 import `katrain.cron.*`。额度桶是**计数器不是货币**（惰性周期键，无重置任务），每周免费复盘用**不滚存的周桶**而不是永久积分赠额。

**Review:** 本计划第 1 稿经 codex adversarial-review 判 **NO-SHIP**（7 findings / 4 critical）。第 2 稿逐条处置，其中两条事实指控我已独立复核**属实**：
- `UserGameCreate.move_count: int = 0` 是**客户端提交**的、原样入库 ⇒ 上传 300 手 SGF 声明 0 手即可预扣 0 而拿到完整分析（`user_games.py:32,132`）。
- `reconcile_stale_reservations` **无差别退还所有超过 `BILLING_RESERVATION_TTL_SEC=120` 秒的 reserved 行**、不看归属（`billing.py:273-299`，`server.py:226`）⇒ 复盘动辄数分钟，每次 web 重启都会把在跑的预扣全额退掉，随后结算再补一笔"估多退款" ⇒ 白嫖 + 凭空生钱。
第 2 稿另补一条 codex 未发现的：**cron 有自己的 SGF 解析器**（`katrain/cron/sgf.py:200 parse_game`），与 web 侧 `katrain/core/sgf_parser.py` 是两套实现 ⇒ 只在 web 侧解析并不能保证 `actual <= reserved`，必须让**手数有唯一权威**（见 Task 4）。

**Review（第 2 轮）:** 第 2 稿再次被判 **NO-SHIP**（9 findings）。我独立复核后确认两条新的事实指控**属实**，且其中一条比 SECRET_KEY 更严重：
- `server.py:197-199` 在空库启动时创建 **`admin` / 密码 `admin`**，`:209-214` 随后把任何名为 `admin` 的账号**无条件**提权成 `is_admin`。**不需要伪造任何 token**，登录表单就能拿到管理员赠额与兑换码接口。→ 提升为 **Task 0**，与 SECRET_KEY 同属 Release 0。
- `reports.py:283 /retry` 把 failed 任务直接改回 `pending` 且不重新授权；结算器若先跑并清掉 `charge_ref`，用户就能**免费续跑**剩余部分。`cron/jobs/requeue_reports.py` 对 completed 任务同理。→ Task 6 增加"可重试的失败不终结授权"。

第 3 稿处置了 9 条中的 7 条。**明确延后的 2 条**（写在文末「已知限制」，不是遗漏）：
- 「把 billing/quota 改成调用方管理事务」——那是重写一个正在工作的账本 API，与本切片的风险不相称。改用**确定性 ref + 孤儿回收器**达到可恢复性，残余风险已具体写明。
- 「POST 的客户端幂等键」——本稿先用 `authorizing` 纳入去重集合 + 活跃任务唯一索引覆盖绝大多数，幂等键排进后续。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL（生产）/ SQLite（开发与单测）；迁移走 `katrain/web/core/migrations.py` 手写 ADD COLUMN / CREATE INDEX；pytest。

**Spec:** `superpowers/tracks/galaxy-payment/requirements.md`（与本计划同目录，必须一起读）

## Global Constraints

- **不要跑 `alembic revision`**。仓里装着 `alembic>=1.13.0` 但**没有 env.py / 版本链**。迁移只走 `katrain/web/core/migrations.py`。
- **迁移必须 SQLite + PG 双兼容**。唯一约束走独立 `CREATE UNIQUE INDEX`，**不得**用 `ADD COLUMN ... UNIQUE`（SQLite 直接报错）。
- **单进程**：`uvicorn.run(app, ...)` 无 `workers` 参数。进程内状态今天可用，但任何依赖它的地方要留注释写明"加 workers 即静默失效"。
- **没有 Redis**。
- **不要 `git stash`**：本仓 13 个 worktree 共用一条 stash 栈。
- **`katrain/cron/` 是自足子树**：`Dockerfile.cron` 只 `COPY katrain/cron/`，且现有代码只 import `katrain.cron.*`。**不得**从 `katrain/cron/` import `katrain.web.*`。
- **状态诚实**：加载/错误/空态/重试不得伪装成成功。额度不足要说清差多少，不许静默降级成"成功但没分析"。
- **测试分层**：跑 SQLite 的单测证明不了 PG 的行锁/时区行为。这类断言 `pytest.skip` 并写明"只能在 PG 上证"，**不许改绿**。
- **账本表受保护**：`migrations.py:33` `PROTECTED_TABLES = {"credit_transactions", "redeem_codes", "recharge_orders"} | AI_LADDER_TABLES | {...}`。新增的 `quota_buckets` **要加进去**——它记录已消费的额度，重建即等于给所有人重置额度。
- **单位约定（全局唯一）**：`1 credit = 1 AU = 1000 visits @ cost_factor 1.0`。**不引入第二种货币**（2026-06-07 裁决）。
- **金额一律整数**，不用浮点。取整一律 `math.ceil`，最小 1。
- 提交信息用中文，风格跟随 `git log`（`feat(scope): ...` / `fix(scope): ...`）。
- **发布闸**：计费全程躲在 `settings.BILLING_ENFORCED`（默认 **False**）后面。关着时 `POST /reports` 的行为必须与今天**逐字节一致**（不扣费、不消费额度、不返 402）。打开的前置：P3 手机绑定 + 注册限流已上线（裁决 D3 的条件）、P5 合规页脚已上线、U4 经营资质已定性。**任何任务都不得把默认值改成 True。**
- **不许在 rollback 之后做补偿写**。`billing.reserve`/`grant` 当年就是栽在这里（Task 1）；`quota._ensure_bucket` 同款分支已按此写。
- **环境**：这个 worktree 的 venv 要用 `uv sync --extra web` 装（web 依赖在 `pyproject.toml` 的 `[project.optional-dependencies].web` 里）。**光跑 `uv sync` 装不上 fastapi**，所有 web 测试会以 `ModuleNotFoundError` 全红——那不是代码问题。已在本 worktree 装好。

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `katrain/web/core/billing.py` | 整数账本：reserve/commit/refund/grant | 改（修竞争补偿 bug） |
| `katrain/web/core/analysis_cost.py` | **新**：算力→credits 的纯函数，无 IO、无 ORM | 建 |
| `katrain/web/core/quota.py` | **新**：额度桶的惰性开桶与原子消费 | 建 |
| `katrain/web/core/config.py` | 计价参数、免费额度、SECRET_KEY fail-fast | 改 |
| `katrain/web/core/models_db.py` | `QuotaBucket` 表；`ReportTask.charge_ref`；去掉 `credits` 列默认值 | 改 |
| `katrain/web/core/migrations.py` | 新列 / 新索引 / `PROTECTED_TABLES` | 改 |
| `katrain/web/models.py` | pydantic `User.credits` 的硬编码默认值 | 改 |
| `katrain/web/core/report_settlement.py` | **新**：终态复盘任务的对账结算（web 侧，不碰 cron） | 建 |
| `katrain/web/api/v1/endpoints/reports.py` | 建任务时查额度 + 预扣 | 改 |
| `katrain/web/api/v1/endpoints/billing.py` | 余额 + 额度看板端点 | 改 |
| `katrain/web/server.py` | 启动时的 SECRET_KEY 闸；对账器挂载 | 改 |
| `tests/web_ui/test_billing_race.py` | **新**：账本竞争补偿的回归测试 | 建 |
| `tests/web_ui/test_analysis_cost.py` | **新**：算力计价纯函数 | 建 |
| `tests/web_ui/test_quota.py` | **新**：额度桶 | 建 |
| `tests/web_ui/test_report_charging.py` | **新**：建任务→预扣→结算全链路 | 建 |
| `tests/web_ui/test_secret_key_gate.py` | **新**：生产启动闸 | 建 |

---

## Task 0: 拆掉 admin/admin 默认凭据（Release 0，排在最前）

`server.py:197-199`：空库启动时 `repo.create_user("admin", get_password_hash("admin"))`。
`server.py:209-214`：随后**无条件**把任何名为 `admin` 的账号置 `is_admin=True`。
合起来 = 一个公开已知的管理员口令。它绕过 JWT，直接命中 `/billing/admin/grant` 与 `/billing/admin/codes`。
**修 SECRET_KEY 而不修这条，等于换了门锁却把钥匙留在门垫下。**

**Files:**
- Modify: `katrain/web/server.py:196-214`
- Modify: `katrain/web/core/config.py`
- Test: `tests/web_ui/test_admin_bootstrap.py`（新建）

**Interfaces:**
- Produces: `settings.ADMIN_BOOTSTRAP_PASSWORD: str = ""`；server 模式下为空则**不创建**任何默认账号

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_admin_bootstrap.py
"""server 模式不得创建公开已知口令的管理员账号。"""
import inspect

from katrain.web import server


def test_no_hardcoded_admin_password_in_bootstrap():
    src = inspect.getsource(server)
    assert 'get_password_hash("admin")' not in src, (
        "空库启动时创建 admin/admin —— 那是一个公开已知的管理员口令，"
        "不需要伪造 token 就能拿到赠额和兑换码接口"
    )


def test_admin_flag_is_not_granted_by_username():
    src = inspect.getsource(server)
    assert 'User.username == "admin"' not in src, (
        "按用户名无条件提权 ⇒ 任何人注册叫 admin 的账号都可能被提权"
    )


def test_bootstrap_password_setting_exists_and_defaults_empty():
    from katrain.web.core.config import settings
    assert settings.ADMIN_BOOTSTRAP_PASSWORD == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_admin_bootstrap.py -v`
Expected: 前两条 FAIL

- [ ] **Step 3: 实现**

`config.py`：

```python
    # 空库首次启动时创建管理员账号用的口令。**默认空 = 不创建任何账号**。
    # 从环境注入（KATRAIN_ADMIN_BOOTSTRAP_PASSWORD），用完即应清掉。
    ADMIN_BOOTSTRAP_PASSWORD: str = ""
```
并在 `Settings` 的 env 装配处加 `data.setdefault("ADMIN_BOOTSTRAP_PASSWORD", os.getenv("KATRAIN_ADMIN_BOOTSTRAP_PASSWORD", ""))`。

`server.py:196-214` 整段替换为：

```python
    # 首个管理员账号只在显式注入口令时创建。
    # 曾经这里是 create_user("admin", get_password_hash("admin")) —— 一个公开已知的
    # 管理员口令，配合下方"按用户名提权"等于把管理接口敞开。两者一起拆掉。
    if not repo.list_users():
        pwd = settings.ADMIN_BOOTSTRAP_PASSWORD
        if pwd:
            try:
                repo.create_user("admin", get_password_hash(pwd))
                _s = session_factory()
                try:
                    row = _s.query(models_db.User).filter(models_db.User.username == "admin").one()
                    row.is_admin = True
                    _s.commit()
                finally:
                    _s.close()
                log.info("已按 ADMIN_BOOTSTRAP_PASSWORD 创建初始管理员")
            except ValueError:
                pass
        else:
            log.warning(
                "数据库为空且未设置 KATRAIN_ADMIN_BOOTSTRAP_PASSWORD —— 未创建任何账号。"
                "设置该环境变量后重启即可创建初始管理员。"
            )
```

> 注意：**不要**保留"把名为 admin 的账号提权"那段独立逻辑。提权只发生在这一次创建里。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_admin_bootstrap.py -v && uv run pytest tests/web_ui -q`
Expected: 新测试 PASS；既有 web_ui 测试与基线比无新增失败（很多测试依赖 admin 账号存在 —— 它们的 fixture 要改成显式建号，**不要**为了让它们绿而把默认口令留着）

- [ ] **Step 5: 写存量处置说明**

在 `superpowers/tracks/galaxy-payment/deploy-secret-key.md` 里加一节：**上线前必须检查两台机器上是否存在用户名为 `admin` 且口令仍是 `admin` 的账号**，有就当场改掉或禁用。代码改动挡的是"以后不再产生"，挡不住"已经产生的那个"。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/server.py katrain/web/core/config.py tests/web_ui/test_admin_bootstrap.py superpowers/tracks/galaxy-payment/deploy-secret-key.md
git commit -m "fix(auth): 拆掉 admin/admin 默认凭据与按用户名无条件提权"
```

---

## Task 1: 修账本竞争补偿（钱的 bug，必须最先）

`reserve` 与 `grant` 在丢失幂等竞争时，`db.rollback()` **已经撤销了那次余额变动**，代码随后又做了一次"补偿"UPDATE，于是净效果多一份。已实测：`reserve` 让用户**白得** amount，`grant` 让用户**倒扣** amount。现有幂等测试走的是 `_existing_tx` 早退路径，从未覆盖这条分支。

**Files:**
- Modify: `katrain/web/core/billing.py:104-117`（reserve 的 except 分支）、`katrain/web/core/billing.py` 中 grant 的同构分支
- Test: `tests/web_ui/test_billing_race.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces: `billing.reserve` / `billing.grant` 在竞争分支下**净变化为 0**，返回赢家的 `balance_after`。签名不变。

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_billing_race.py
"""账本幂等竞争分支：丢失竞争时余额净变化必须为 0。

现有 test_billing.py 的幂等用例走的是 `_existing_tx` 早退路径，
碰不到 db.commit() 抛 IntegrityError 的那条分支。这里用「预置同 ref_id 行
+ 让 _existing_tx 第一次谎报 None」把执行强行赶进那条分支。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mkuser(db, credits=100):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _force_lost_race(monkeypatch, db, fn, user_id, amount, ref_id):
    """预置赢家行，并让第一次 _existing_tx 返回 None。"""
    db.add(
        models_db.CreditTransaction(
            user_id=user_id, delta=-1, reason="winner",
            ref_id=ref_id, status="reserved", balance_after=99,
        )
    )
    db.commit()
    real = billing._existing_tx
    calls = {"n": 0}

    def fake(session, rid):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(session, rid)

    monkeypatch.setattr(billing, "_existing_tx", fake)
    return fn(db, user_id, amount, "probe", ref_id)


def test_reserve_lost_race_does_not_gift_credits(monkeypatch, db):
    u = _mkuser(db, credits=100)
    before = billing.get_balance(db, u.id)
    _force_lost_race(monkeypatch, db, billing.reserve, u.id, 30, "race-r")
    assert billing.get_balance(db, u.id) == before, "丢失竞争不得改变余额"


def test_grant_lost_race_does_not_debit(monkeypatch, db):
    u = _mkuser(db, credits=100)
    before = billing.get_balance(db, u.id)
    _force_lost_race(monkeypatch, db, billing.grant, u.id, 30, "race-g")
    assert billing.get_balance(db, u.id) == before, "丢失竞争不得改变余额"


def test_reserve_lost_race_returns_winner_balance(monkeypatch, db):
    u = _mkuser(db, credits=100)
    got = _force_lost_race(monkeypatch, db, billing.reserve, u.id, 30, "race-r2")
    assert got == 99, "应返回赢家那一行记录的 balance_after"
```

- [ ] **Step 2: 跑测试确认它失败**

Run: `cd /Users/fan/Repositories/katrain-galaxy-payment && uv run pytest tests/web_ui/test_billing_race.py -v`
Expected: `test_reserve_lost_race_does_not_gift_credits` 与 `test_grant_lost_race_does_not_debit` FAIL（余额分别是 130 和 70）

- [ ] **Step 3: 删掉两处补偿 UPDATE**

`reserve` 的 except 分支改成（删掉 re-credit 那三行）：

```python
    try:
        db.commit()
    except IntegrityError:
        # 丢失幂等竞争。db.rollback() 会把本事务里的扣款一并撤销，
        # 所以**不要**再做补偿 UPDATE —— 那会凭空多给一份。
        # （实测：补偿版让用户白得 amount；grant 的同构分支让用户倒扣 amount。）
        db.rollback()
        winner = _existing_tx(db, ref_id)
        return int(winner.balance_after) if winner else get_balance(db, user_id)
    return balance_after
```

`grant` 的 except 分支同样处理：只保留 `db.rollback()` + 读赢家，删掉那次 `credits - :amt`。

- [ ] **Step 4: 跑测试确认通过，并跑既有账本测试确认没回归**

Run: `uv run pytest tests/web_ui/test_billing_race.py tests/web_ui/test_billing.py -v`
Expected: 全部 PASS（既有 17 条 + 新 3 条）

- [ ] **Step 5: 提交**

```bash
git add tests/web_ui/test_billing_race.py katrain/web/core/billing.py
git commit -m "fix(billing): 幂等竞争分支不再重复补偿 —— reserve 白送、grant 倒扣的两处"
```

---

## Task 2: 生产必须显式注入 SECRET_KEY，拿不到就拒绝启动

今天 `docker-compose.yml` 没传 `KATRAIN_SECRET_KEY`，生产跑的是仓库里的字面量 —— 任何人都能自签 `{"sub": "admin"}`。

**Files:**
- Modify: `katrain/web/core/config.py:38, 115`
- Modify: `katrain/web/server.py`（启动闸）
- Modify: `docker-compose.yml`（第 70 行附近 katrain-web 的 environment）
- Test: `tests/web_ui/test_secret_key_gate.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces: `config.INSECURE_DEFAULT_SECRET_KEY`（模块级常量，字面量真源）；`config.assert_secret_key_is_safe(mode: str) -> None`，`mode == "server"` 且密钥等于默认值时抛 `RuntimeError`。

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_secret_key_gate.py
"""生产模式下拿不到显式 SECRET_KEY 必须拒绝启动，不得静默回退到仓库字面量。"""
import pytest

from katrain.web.core import config


def test_default_key_is_a_named_constant():
    # 字面量必须只有一处真源，否则改一处漏一处。
    assert config.INSECURE_DEFAULT_SECRET_KEY == "katrain-secret-key-change-this-in-production"


def test_server_mode_rejects_default_key():
    with pytest.raises(RuntimeError, match="KATRAIN_SECRET_KEY"):
        config.assert_secret_key_is_safe("server", config.INSECURE_DEFAULT_SECRET_KEY)


def test_server_mode_accepts_injected_key():
    config.assert_secret_key_is_safe("server", "a-real-32-byte-random-value-xxxxx")


def test_board_mode_tolerates_default_key():
    # 盒子上本地库不签发跨机身份，闸只管服务端。
    config.assert_secret_key_is_safe("board", config.INSECURE_DEFAULT_SECRET_KEY)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n", "x", "short-key-123"])
def test_server_mode_rejects_empty_and_short_keys(bad):
    """compose 的 :? 只保护 compose 一条入口；直接 python/systemd 启动照样能传空串。"""
    with pytest.raises(RuntimeError):
        config.assert_secret_key_is_safe("server", bad)


def test_minimum_length_is_a_named_constant():
    assert config.MIN_SECRET_KEY_CHARS >= 32
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_secret_key_gate.py -v`
Expected: FAIL — `AttributeError: module 'katrain.web.core.config' has no attribute 'INSECURE_DEFAULT_SECRET_KEY'`

- [ ] **Step 3: 实现**

在 `katrain/web/core/config.py` 顶部加常量，并把 `:38` 与 `:115` 两处字面量都换成它：

```python
INSECURE_DEFAULT_SECRET_KEY = "katrain-secret-key-change-this-in-production"


MIN_SECRET_KEY_CHARS = 32


def assert_secret_key_is_safe(mode: str, secret_key: str) -> None:
    """服务端模式下必须显式注入一个**足够长**的密钥。

    盒子（board）跑本地库、不对外签发身份，放行。

    为什么不只挡默认字面量：compose 的 `:?` 只保护 compose 这一条入口。
    直接 `python -m katrain`、systemd、或别的部署路径传进来的空串、空白、
    单字符都会通过，而 HS256 的短密钥可以离线穷举 —— 拿到任意一个 token
    就能反推密钥并伪造管理员。
    """
    if mode != "server":
        return
    if not secret_key or not secret_key.strip():
        raise RuntimeError("拒绝以空 SECRET_KEY 启动服务端：设置 KATRAIN_SECRET_KEY。")
    if len(secret_key.strip()) < MIN_SECRET_KEY_CHARS:
        raise RuntimeError(
            f"SECRET_KEY 太短（{len(secret_key.strip())} 字符，至少 {MIN_SECRET_KEY_CHARS}）："
            "HS256 短密钥可离线穷举。用 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` 生成。"
        )
    if secret_key == INSECURE_DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "拒绝以内置默认 SECRET_KEY 启动服务端：任何人都能用仓库里的字面量伪造任意用户的 token。"
            "请设置环境变量 KATRAIN_SECRET_KEY（建议 `python -c \"import secrets;print(secrets.token_urlsafe(48))\"`）。"
        )
```

在 `katrain/web/server.py` 的 `create_app` 里，**engine 启动之前**调用：

```python
    from katrain.web.core.config import assert_secret_key_is_safe
    assert_secret_key_is_safe(settings.KATRAIN_MODE, settings.SECRET_KEY)
```

`docker-compose.yml` 的 `katrain-web` 与 `katrain-cron` 两处 `environment` 各加一行：

```yaml
      - KATRAIN_SECRET_KEY=${KATRAIN_SECRET_KEY:?KATRAIN_SECRET_KEY 必须在 .env 里设置}
```

（`:?` 让 compose 在变量缺失时**直接失败**，而不是传一个空串进去。）

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_secret_key_gate.py -v && uv run pytest tests/web_ui -x -q`
Expected: 新测试 PASS；既有 web_ui 测试无新增失败（**先记基线**：改动前先跑一次存下失败集合，用 `comm` 比名字集合，不比条数）

- [ ] **Step 5: 写发布顺序说明**

在 `superpowers/tracks/galaxy-payment/deploy-secret-key.md` 写清：换密钥 = **全站登出一次**（access 7 天 / refresh 90 天的 token 全部失效）。发布顺序：先在 home-ubuntu 的 `.env` 设置并重启验证，再上 ucloud-v100；公告或选低峰。**不要**为了避免登出而保留旧密钥双验——那等于洞还开着。

- [ ] **Step 6: 提交**

```bash
git add tests/web_ui/test_secret_key_gate.py katrain/web/core/config.py katrain/web/server.py docker-compose.yml superpowers/tracks/galaxy-payment/deploy-secret-key.md
git commit -m "feat(auth): 服务端拒绝以内置默认 SECRET_KEY 启动"
```

---

## Task 3: 算力计价的纯函数

**Files:**
- Create: `katrain/web/core/analysis_cost.py`
- Modify: `katrain/web/core/config.py`
- Test: `tests/web_ui/test_analysis_cost.py`（新建）

**Interfaces:**
- Consumes: 无（纯函数，不碰 DB）
- Produces:
  - `VISITS_PER_CREDIT: int = 1000`
  - `MODEL_COST_FACTOR: dict[str, float]`，`default_factor(model: str | None) -> float`
  - `report_cost(moves: int, visits_per_move: int, model: str | None = None) -> int` —— 返回 credits，`ceil`，下界 1（`moves == 0` 时返回 0）

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_analysis_cost.py
"""算力计价：按 moves × visits 算，不按盘算。"""
import pytest

from katrain.web.core import analysis_cost as ac


def test_cost_scales_with_move_count():
    """100 手认输的棋不应该和 300 手收一样的钱 —— 这是本功能存在的理由。"""
    short = ac.report_cost(100, 500)
    long = ac.report_cost(300, 500)
    assert long == pytest.approx(short * 3, rel=0.01)
    assert short < long


def test_cost_scales_with_visits():
    assert ac.report_cost(200, 2000) == 4 * ac.report_cost(200, 500)


def test_standard_250_move_report():
    # 250 手 × 500 visits = 125_000 visits = 125 credits
    assert ac.report_cost(250, 500) == 125


def test_zero_moves_costs_nothing():
    assert ac.report_cost(0, 500) == 0


def test_tiny_game_still_costs_at_least_one():
    assert ac.report_cost(1, 1) == 1


def test_model_factor_applied():
    assert ac.report_cost(250, 500, "b18") < ac.report_cost(250, 500, "b28")


def test_unknown_model_falls_back_to_one():
    assert ac.report_cost(250, 500, "no-such-net") == ac.report_cost(250, 500, "b28")


def test_negative_moves_rejected():
    with pytest.raises(ValueError):
        ac.report_cost(-1, 500)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_analysis_cost.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'katrain.web.core.analysis_cost'`

- [ ] **Step 3: 实现**

```python
# katrain/web/core/analysis_cost.py
"""算力 → credits 的换算。

单位约定（全局唯一）：1 credit = 1 AU = 1000 visits @ cost_factor 1.0。
不引入第二种货币 —— 额度桶是计数器，账本是单池积分。

这里是纯函数：不碰 DB、不读 settings 之外的任何东西，便于单测和在
预扣（用估算手数）与结算（用实际手数）两端复用同一条式子。
"""
import math
from typing import Optional

VISITS_PER_CREDIT = 1000

# 取自 KataGo 官方 docs/NetworkArchitectures.md 的 cost/eval 一列。
# 该文档自称 "extremely approximate"，所以这些值只用于**相对**计价，
# 换模型时必须在生产 GPU 上实测 `katago benchmark` 再调（裁决 D8）。
MODEL_COST_FACTOR = {
    "b28": 1.0,
    "b18": 0.45,
    "b40": 3.0,
    "tf3-b11c768": 1.1,
}
DEFAULT_MODEL = "b28"


def default_factor(model: Optional[str]) -> float:
    """未知模型一律按 1.0 计 —— 宁可少收，不可因为字符串拼错就多收。"""
    if not model:
        return MODEL_COST_FACTOR[DEFAULT_MODEL]
    return MODEL_COST_FACTOR.get(model, MODEL_COST_FACTOR[DEFAULT_MODEL])


def report_cost(moves: int, visits_per_move: int, model: Optional[str] = None) -> int:
    """一份复盘的 credits 成本。

    moves 为 0 时返回 0（还没分析过任何一手，不该收钱）；
    其余情况向上取整且下界为 1（分析发生了就不能免费）。
    """
    if moves < 0 or visits_per_move < 0:
        raise ValueError("moves 与 visits_per_move 必须 >= 0")
    if moves == 0 or visits_per_move == 0:
        return 0
    visits = moves * visits_per_move * default_factor(model)
    return max(1, math.ceil(visits / VISITS_PER_CREDIT))
```

在 `config.py` 的 `BILLING_PRICES` 旁边加一行注释指向它（**不要**在 `BILLING_PRICES` 里加 `report: N`——那正是按盘计价，与裁决 D6 相反）。**本任务不加任何免费额度常量**：免费复盘是不滚存的周桶（Task 9），不是积分。

```python
    # 复盘不在这张表里：它按算力计价，见 katrain/web/core/analysis_cost.py。
    # 往这里加 "report": N 等于回到按盘计价（裁决 D6 明确否掉）。
    BILLING_PRICES: dict = {"territory": 10, "hints": 10, "variations": 10}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_analysis_cost.py -v`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add katrain/web/core/analysis_cost.py katrain/web/core/config.py tests/web_ui/test_analysis_cost.py
git commit -m "feat(billing): 复盘按算力计价的纯函数 —— moves × visits，不按盘"
```

---

## Task 4: 手数的唯一权威（堵住 move_count=0 的白嫖路）

`UserGameCreate.move_count: int = 0` 是**客户端提交**的、`user_games.py:132` 原样入库。而 cron 在 `report_analyze.py:197` 用**自己那套**解析器（`katrain/cron/sgf.py:200 parse_game`）重新数手数并覆盖 `task.total_moves`。两件事合起来：声明 0 手 ⇒ 预扣 0 ⇒ cron 照样跑满全盘。

**光在 web 侧解析一次不够**——两套解析器可能数出不同的值，`actual > reserved` 依然可能发生。所以把手数做成**任务上的契约**：web 在建任务时解析并写死 `total_moves`，cron **不再覆盖已有值**，且只分析这个前缀。

**Files:**
- Modify: `katrain/web/api/v1/endpoints/reports.py`
- Modify: `katrain/cron/jobs/report_analyze.py:197-198`
- Test: `tests/web_ui/test_report_move_authority.py`（新建）
- Test: `tests/test_cron_report_moves.py`（新建）

**Interfaces:**
- Consumes: `katrain.core.sgf_parser.SGF`（`katrain/core/` 是 web 与 cron 都能用的共享层，但 cron 容器里**没有**它——所以只有 web 侧用）
- Produces: `reports.count_moves(sgf_content: str) -> int`；不变式 **`ReportTask.total_moves` 一经写入即不可变**

- [ ] **Step 1: 写失败测试（web 侧）**

```python
# tests/web_ui/test_report_move_authority.py
"""手数必须由服务端解析，客户端声明的 move_count 不作数。

回归的是一条实打实的白嫖路：UserGameCreate.move_count 由客户端提交
（user_games.py:32），声明 0 就会让预扣算出 0，而 cron 仍会跑满全盘。
"""
import pytest

from katrain.web.api.v1.endpoints import reports


SGF_3_MOVES = "(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pp])"
SGF_0_MOVES = "(;GM[1]FF[4]SZ[19])"


def test_counts_moves_from_sgf_not_from_client_claim():
    assert reports.count_moves(SGF_3_MOVES) == 3


def test_empty_game_counts_zero():
    assert reports.count_moves(SGF_0_MOVES) == 0


def test_malformed_sgf_raises_not_returns_zero():
    """解析不了必须报错。返回 0 等于把「读不懂」伪装成「不要钱」。"""
    with pytest.raises(ValueError):
        reports.count_moves("this is not sgf")


def test_none_or_blank_raises():
    with pytest.raises(ValueError):
        reports.count_moves("")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_move_authority.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'count_moves'`

- [ ] **Step 3: 实现 web 侧解析**

在 `katrain/web/api/v1/endpoints/reports.py` 顶部加：

```python
def count_moves(sgf_content: str) -> int:
    """从 SGF 数出实际手数。

    **不要**信任 `UserGame.move_count`：那是 `UserGameCreate` 里客户端提交的字段
    （`user_games.py:32` 默认 0），拿它计价等于让付款方自己填金额。

    解析失败抛 ValueError —— 返回 0 会把「读不懂这份棋谱」伪装成「这份复盘不要钱」。
    """
    from katrain.core.sgf_parser import SGF, ParseError

    if not sgf_content or not sgf_content.strip():
        raise ValueError("空 SGF")
    try:
        root = SGF.parse_sgf(sgf_content)
    except (ParseError, Exception) as exc:
        raise ValueError(f"SGF 解析失败: {exc}") from exc
    n, node = 0, root
    while node.children:
        node = node.children[0]
        if node.move is not None:
            n += 1
    return n
```

> 这段已对着真实 API 实跑验证过（`katrain/core/sgf_parser.py:417 SGF.parse_sgf`、`:289 SGFNode.move`、`:311 nodes_in_tree`）：3 手 SGF 数出 3、空 SGF 数出 0、乱码抛 `ParseError`。注意 `SGF.parse_sgf` 抛的是 `ParseError`，所以 `except` 里要把它列上。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_move_authority.py -v`
Expected: 4 passed

- [ ] **Step 5: 让 cron 不再覆盖手数**

`katrain/cron/jobs/report_analyze.py:197-198` 改为：

```python
            # total_moves 由 web 在建任务时解析并写死（那是计价的操作数）。
            # 这里只在它缺失时兜底 —— 覆盖它会让「已付费的手数」与「实际分析的手数」
            # 脱钩，客户端就能靠少报手数白嫖算力。
            if not task.total_moves:
                task.total_moves = len(moves)
            paid_moves = task.total_moves
            moves = moves[:paid_moves]
            task.analyzed_moves = min(task.analyzed_moves or 0, len(moves))
```

- [ ] **Step 6: 写 cron 侧回归测试**

```python
# tests/test_cron_report_moves.py
"""cron 不得覆盖 web 写死的 total_moves —— 那是计价操作数。"""
import inspect

from katrain.cron.jobs import report_analyze


def test_cron_does_not_unconditionally_overwrite_total_moves():
    src = inspect.getsource(report_analyze)
    # 无条件赋值这一行必须消失；判据落在源码上是因为跑通整个 job 需要
    # KataGo 与数据库，而这里要守的恰恰是「那一行别回来」。
    assert "task.total_moves = len(moves)\n" not in src.replace(
        "                task.total_moves = len(moves)\n", "", 1
    ) or True
    # 更强的判据：赋值必须处在 `if not task.total_moves:` 之下
    assert "if not task.total_moves:" in src, "缺少「只在缺失时兜底」的守卫"
    assert "moves = moves[:paid_moves]" in src, "缺少「只分析已付费前缀」的截断"
```

**变异验证**（必做）：临时把 `if not task.total_moves:` 这一行删掉，跑该测试确认 FAIL，再恢复。把这次变异写进测试 docstring。

- [ ] **Step 7: 提交**

```bash
git add katrain/web/api/v1/endpoints/reports.py katrain/cron/jobs/report_analyze.py tests/web_ui/test_report_move_authority.py tests/test_cron_report_moves.py
git commit -m "fix(billing): 手数由服务端解析并成为任务契约 —— 堵住 move_count=0 白嫖全盘算力"
```

---

## Task 5: 建任务即计费，且不留「已跑未计费」的窗口

cron 按 `status == "pending"` 认领（`report_analyze.py:147`）。若先把任务落成 pending 再计费，两次 commit 之间 cron 就可能已经把它领走——崩溃即留下**已运行但没扣钱**的任务。做法：先落成 **`authorizing`**（cron 不认的状态），计费成功后再原子翻成 `pending`。

**Files:**
- Modify: `katrain/web/core/models_db.py`（`ReportTask.charge_ref`）
- Modify: `katrain/web/core/migrations.py`
- Modify: `katrain/web/core/config.py`（`BILLING_ENFORCED`）
- Modify: `katrain/web/api/v1/endpoints/reports.py`
- Test: `tests/web_ui/test_report_charging.py`（新建）

**Interfaces:**
- Consumes: `analysis_cost.report_cost`、`reports.count_moves`、`billing.reserve`、`quota.try_consume`
- Produces: `ReportTask.charge_ref: str | None`；`ReportTask.status` 新增 `authorizing`；`POST /api/v1/reports/` 余额不足返 **402** `{"code":"insufficient_credits","need":N,"have":M}`

- [ ] **Step 1: 写失败测试（穿过真实端点，不是直接调 billing）**

```python
# tests/web_ui/test_report_charging.py
"""建复盘任务的计费闭环 —— 断言打在 POST /api/v1/reports/ 上。

第 1 稿的测试直接调 billing.reserve，那只证明「从我这层往里通」，
证明不了端点本身会不会扣费、会不会返 402、会不会留下未计费的任务。
"""
import pytest


@pytest.mark.anyio
async def test_disabled_flag_keeps_todays_behaviour(app_with_game, monkeypatch):
    """BILLING_ENFORCED=False 时不得扣费、不得返 402、不得消费额度。"""
    client, token, game_id, user = app_with_game
    from katrain.web.core.config import settings
    monkeypatch.setattr(settings, "BILLING_ENFORCED", False)
    before = _balance(user)
    r = await client.post("/api/v1/reports/", json={"user_game_id": game_id},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert _balance(user) == before


@pytest.mark.anyio
async def test_charges_by_parsed_move_count(app_with_game, monkeypatch):
    client, token, game_id, user = app_with_game       # fixture 的 SGF 是 3 手
    from katrain.web.core.config import settings
    from katrain.web.core import analysis_cost
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    before = _balance(user)
    r = await client.post("/api/v1/reports/", json={"user_game_id": game_id},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    expected = analysis_cost.report_cost(3, 500)
    assert before - _balance(user) == expected


@pytest.mark.anyio
async def test_lying_move_count_does_not_reduce_the_charge(app, monkeypatch):
    """回归白嫖路：客户端声明 move_count=0，仍按 SGF 真实手数扣。"""
    client, token, user = app
    from katrain.web.core.config import settings
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    sgf = "(;GM[1]FF[4]SZ[19]" + "".join(f";B[aa];W[bb]" for _ in range(50)) + ")"
    g = await client.post("/api/v1/user-games/", json={
        "sgf_content": sgf, "source": "import", "move_count": 0,     # ← 谎报
    }, headers={"Authorization": f"Bearer {token}"})
    gid = g.json()["id"]
    before = _balance(user)
    await client.post("/api/v1/reports/", json={"user_game_id": gid},
                      headers={"Authorization": f"Bearer {token}"})
    assert before - _balance(user) > 0, "谎报手数不得导致零扣费"


@pytest.mark.anyio
async def test_insufficient_credits_returns_402_and_leaves_no_task(app_with_game, monkeypatch, db):
    client, token, game_id, user = app_with_game
    from katrain.web.core.config import settings
    from katrain.web.core import models_db
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    _set_balance(user, 0)
    r = await client.post("/api/v1/reports/", json={"user_game_id": game_id},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "insufficient_credits"
    assert db.query(models_db.ReportTask).count() == 0, "计费失败不得留下任务行"


@pytest.mark.anyio
async def test_no_task_is_left_claimable_without_a_charge(app_with_game, monkeypatch, db):
    """任何时刻，status=pending 的任务必须已经有 charge_ref 或已用免费额度。"""
    client, token, game_id, user = app_with_game
    from katrain.web.core.config import settings
    from katrain.web.core import models_db
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    await client.post("/api/v1/reports/", json={"user_game_id": game_id},
                      headers={"Authorization": f"Bearer {token}"})
    for t in db.query(models_db.ReportTask).filter_by(status="pending").all():
        assert t.charge_ref is not None or t.free_grant_period is not None
```

> fixture `app_with_game` / `_balance` / `_set_balance` 按 `tests/web_ui/test_billing_api.py` 里既有 `app` fixture 的写法扩展（**先读那个文件**）。`db` 是同一个会话，用于直接查表。

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_charging.py -v`
Expected: 全 FAIL（`BILLING_ENFORCED` 不存在 / 无 402 / 无 charge_ref）

- [ ] **Step 3: 加列、加状态、加开关**

`models_db.py` 的 `ReportTask`：

```python
    # 账本幂等键。None = 没走积分扣费（用了免费周额度，或 BILLING_ENFORCED 关着，或历史数据）。
    charge_ref = Column(String(160), nullable=True, index=True)
    # 用掉的免费周额度的周期键（如 "W:2026-W36"）。与 charge_ref 互斥。
    free_grant_period = Column(String(32), nullable=True)
```

同时把 `status` 的注释改成 `# authorizing / pending / running / completed / failed`。

`config.py`：

```python
    # 计费总闸。默认关 —— 打开的前置见 plan.md 的 Global Constraints。
    BILLING_ENFORCED: bool = False
```

`migrations.py` 走既有 `_add_missing_columns`（两列都可空无默认值 ⇒ 纯 ADD COLUMN）。

- [ ] **Step 4: 实现端点里的计费顺序**

`reports.py` 的 `create_report_task`。

**插入位置是这个任务最容易做错的一步，先看清函数现有的结构：**

```
1. if task.report_type not in REPORT_VISITS:  -> 400
2. dispatcher = getattr(request.app.state, "repository_dispatcher", None)
   if dispatcher is not None:
       return await _dispatch_remote_only(...)      # ← 盒子模式在这里就走了
3. game = db.query(UserGame)...                     # 拿到棋谱
4. if not task.force:  <去重查询>
5. report_task = models_db.ReportTask(...)          # ← 你要改的是这一段
```

**计费代码必须放在第 3 步之后**（要用 `game.sgf_content`），**绝不能放在第 2 步之前**：
盒子模式会把整个请求转发到云端、由云端扣费（`requirements.md §1.3` 已写明账本权威在云端）。
在盒子上再扣一次 = 同一份复盘收两次钱。

另外**第 4 步的去重查询要改**：现有状态集合是 `["pending", "running", "completed"]`，
必须把 `"authorizing"` 加进去，否则第二个并发请求会在第一个还在授权时穿过去重。

把第 5 步那段改成：

```python
    from katrain.web.core import analysis_cost, billing, quota
    from katrain.web.core.config import settings

    visits = REPORT_VISITS[task.report_type]

    if not settings.BILLING_ENFORCED:
        # 闸关着：行为与今天完全一致，一个字节都不改。
        report_task = models_db.ReportTask(
            user_id=current_user.id, user_game_id=task.user_game_id,
            report_type=task.report_type, requested_visits=visits, status="pending",
        )
        db.add(report_task); db.commit(); db.refresh(report_task)
        return _task_to_dict(report_task)

    try:
        moves = count_moves(game.sgf_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unparsable_sgf", "message": str(exc)})

    cost = analysis_cost.report_cost(moves, visits)

    # 0) 去重集合必须**包含 authorizing** —— 否则第二个并发请求会在第一个
    #    还在授权时穿过去重，造成两次真实扣费 + 两份 GPU 工作。
    #    （`reports.py:211` 现有的去重只查 pending/running/completed。）
    #    完整的客户端幂等键排在后续，见文末「已知限制」。

    # 1) 先落成 authorizing —— cron 只认 pending，这个状态它不会领走。
    report_task = models_db.ReportTask(
        user_id=current_user.id, user_game_id=task.user_game_id,
        report_type=task.report_type, requested_visits=visits,
        status="authorizing", total_moves=moves,
    )
    db.add(report_task); db.commit(); db.refresh(report_task)

    # 2) 先试免费周额度（不滚存，用掉就没）；不够再扣积分。
    period = quota.period_key("week")
    if task.report_type == "normal" and quota.try_consume(
        db, current_user.id, "free_report:week", allowance=settings.FREE_WEEKLY_REPORTS
    ):
        report_task.free_grant_period = period
    else:
        charge_ref = f"report:{report_task.id}"
        try:
            billing.reserve(db, current_user.id, cost, "report", charge_ref)
        except billing.InsufficientCredits:
            db.delete(report_task); db.commit()
            raise HTTPException(status_code=402, detail={
                "code": "insufficient_credits", "need": cost,
                "have": billing.get_balance(db, current_user.id),
            })
        report_task.charge_ref = charge_ref

    # 3) 计费落定之后才放给 cron。
    report_task.status = "pending"
    db.commit()
```

`config.py` 再加 `FREE_WEEKLY_REPORTS: int = 1`（裁决 D2：每周免费一次）。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_charging.py tests/web_ui/test_billing.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/core/migrations.py katrain/web/core/config.py katrain/web/api/v1/endpoints/reports.py tests/web_ui/test_report_charging.py
git commit -m "feat(billing): 建任务即计费 —— authorizing 状态挡住未计费的认领窗口，总闸默认关"
```

---

## Task 6: 结算，并把复盘预扣从通用 TTL 回收器手里救出来

`reconcile_stale_reservations(db, 120)` 在 web 启动时**无差别退还所有超过 120 秒的 reserved 行**（`billing.py:273-299`），不看归属。复盘动辄数分钟 ⇒ 每次 web 重启都会把在跑的复盘预扣全额退掉；之后结算再 `commit` 一个已 `refunded` 的行（无效）并补一笔"估多退款" ⇒ **白嫖 + 凭空生钱**。必须先隔离，再结算。

**Files:**
- Modify: `katrain/web/core/billing.py`（`reconcile_stale_reservations` 加 `exclude_reasons`；补两个公开只读助手）
- Modify: `katrain/web/server.py`
- Create: `katrain/web/core/report_settlement.py`
- Test: `tests/web_ui/test_report_settlement.py`（新建）

**Interfaces:**
- Consumes: `ReportTask.charge_ref/status/analyzed_moves/requested_visits`
- Produces: `settle_finished_reports(db) -> int`；`billing.reserved_amount(db, ref_id) -> int`；`billing.has_transaction(db, ref_id) -> bool`；`billing.transaction_status(db, ref_id) -> str | None`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_report_settlement.py
"""终态结算 + 通用 TTL 回收器不得碰复盘预扣。"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _user(db, credits=1000):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _task(db, user, *, status, total, analyzed, reserve):
    g = models_db.UserGame(user_id=user.id, source="import", move_count=total)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=user.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status=status,
                             total_moves=total, analyzed_moves=analyzed)
    db.add(t); db.commit(); db.refresh(t)
    ref = f"report:{t.id}"
    billing.reserve(db, user.id, reserve, "report", ref)
    t.charge_ref = ref
    db.commit()
    return t


def test_ttl_reaper_leaves_a_running_report_reservation_alone(db):
    """回归最要命的一条：web 重启不得把在跑的复盘退款。"""
    u = _user(db)
    t = _task(db, u, status="running", total=250, analyzed=40, reserve=125)
    # 把预扣时间推到 TTL 之外
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id=t.charge_ref).one()
    tx.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    n = billing.reconcile_stale_reservations(db, 120)
    assert n == 0, "复盘预扣不属于通用 TTL 回收器的管辖范围"
    assert billing.get_balance(db, u.id) == 875
    assert billing.transaction_status(db, t.charge_ref) == "reserved"


def test_ttl_reaper_still_reaps_other_stale_reservations(db):
    """隔离不能把回收器整个废掉 —— 别的预扣照收。"""
    u = _user(db)
    billing.reserve(db, u.id, 10, "analysis_territory", "hint:1")
    tx = db.query(models_db.CreditTransaction).filter_by(ref_id="hint:1").one()
    tx.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()
    assert billing.reconcile_stale_reservations(db, 120) == 1
    assert billing.get_balance(db, u.id) == 1000


def test_settlement_refunds_the_unused_estimate(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="pending", total=250, analyzed=0, reserve=125)
    t.status, t.analyzed_moves = "completed", 100      # 100 手认输
    db.commit()
    assert settle_finished_reports(db) == 1
    assert billing.get_balance(db, u.id) == 950       # 125 预扣，实收 50


def test_settlement_ignores_unfinished_tasks(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    _task(db, u, status="running", total=250, analyzed=40, reserve=125)
    assert settle_finished_reports(db) == 0
    assert billing.get_balance(db, u.id) == 875


def test_settlement_is_idempotent(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=100, analyzed=100, reserve=50)
    settle_finished_reports(db)
    once = billing.get_balance(db, u.id)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == once


def test_failed_with_zero_analysis_is_fully_refunded(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="failed", total=250, analyzed=0, reserve=125)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 1000


def test_failed_after_partial_analysis_charges_only_what_ran(db):
    """跑挂了但已经烧了算力 —— 收已发生的那部分，不是全免也不是全收。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="failed", total=250, analyzed=60, reserve=125)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 1000 - 30   # 60×500 = 30 credits


def test_settlement_resumes_a_half_done_commit(db):
    """回归：上一轮在 commit 与 grant 之间崩了，差额必须补退，不能永久按预估收。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    billing.commit(db, t.charge_ref)          # 模拟"只做了一半"
    assert billing.get_balance(db, u.id) == 875
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 950, "125 预扣、实收 50，差额 75 必须退回"


def test_resume_does_not_double_refund(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    settle_finished_reports(db)
    once = billing.get_balance(db, u.id)
    t.charge_ref = f"report:{t.id}"            # 人为把引用放回去，模拟重复扫描
    db.commit()
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == once, "退款行已存在就不能再退一次"


def test_settlement_skips_a_reservation_someone_else_already_refunded(db):
    """防御：万一预扣已被别处退掉，结算必须原地跳过、不得再补一笔赠额。"""
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=100, reserve=125)
    billing.refund(db, t.charge_ref)
    before = billing.get_balance(db, u.id)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == before, "已退款的预扣不得再生出一笔钱"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_settlement.py -v`
Expected: 前两条与结算相关的全部 FAIL

- [ ] **Step 3: 隔离 TTL 回收器**

`billing.py`：

```python
# 这些 reason 的预扣有自己的生命周期管理者，通用 TTL 回收器一律不碰。
# 复盘要跑几分钟到几十分钟，远超 BILLING_RESERVATION_TTL_SEC(120)；
# 让通用回收器碰它 = 每次 web 重启把在跑的复盘全额退掉。
LONG_RUNNING_REASONS = frozenset({"report"})


def reconcile_stale_reservations(db: Session, ttl_seconds: int) -> int:
    ...
    stale = (
        db.query(models_db.CreditTransaction)
        .filter(
            models_db.CreditTransaction.status == "reserved",
            models_db.CreditTransaction.created_at < cutoff,
            ~models_db.CreditTransaction.reason.in_(LONG_RUNNING_REASONS),
        )
        .all()
    )
```

并补两个只读助手：

```python
def reserved_amount(db: Session, ref_id: str) -> int:
    """某笔预扣的金额（正数）。找不到抛 BillingError。"""
    tx = _existing_tx(db, ref_id)
    if tx is None:
        raise BillingError(f"no transaction for ref_id {ref_id}")
    return abs(int(tx.delta))


def has_transaction(db: Session, ref_id: str) -> bool:
    return _existing_tx(db, ref_id) is not None


def transaction_status(db: Session, ref_id: str) -> Optional[str]:
    tx = _existing_tx(db, ref_id)
    return None if tx is None else str(tx.status)
```

- [ ] **Step 4: 实现结算器**

```python
# katrain/web/core/report_settlement.py
"""终态复盘任务的对账结算。

**为什么是对账不是让 worker 结算**：跑复盘的是 `katrain/cron/jobs/report_analyze.py`，
而 `Dockerfile.cron` 只 `COPY katrain/cron/`、该子树只 import `katrain.cron.*`。
从那里 import `katrain.web.core.billing` 本机能跑、**容器里必炸**。

**时延语义（诚实性）**：从任务终态到余额准确之间有一个对账周期的窗口。
所以 `/billing/quota` 必须在返回余额前先跑一次本用户的结算（见 Task 11），
用户看到的数才是准的；后台周期跑只是兜底。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from katrain.web.core import analysis_cost, billing, models_db

logger = logging.getLogger("katrain_web")

# 只有 completed 是「可以立刻结算」的终态。
# failed 不在这里 —— 它可能被 /retry 复活，立刻终结授权会让用户免费续跑
# （见本任务 Step 7）。failed 走 _settleable_failed() 的宽限期分支。
TERMINAL_STATUSES = ("completed",)


def settle_finished_reports(db: Session, limit: int = 200, user_id: int | None = None) -> int:
    """结算终态但仍持预扣的复盘任务。返回结算条数。幂等。"""
    from sqlalchemy import or_
    from katrain.web.core.config import settings

    grace_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.REPORT_RETRY_GRACE_SEC
    )
    q = db.query(models_db.ReportTask).filter(
        models_db.ReportTask.charge_ref.isnot(None),
        models_db.ReportTask.billing_exempt_reason.is_(None),
        or_(
            models_db.ReportTask.status.in_(TERMINAL_STATUSES),
            # failed 过了宽限期才结算：宽限期内 /retry 可以复用原预扣。
            (models_db.ReportTask.status == "failed")
            & (models_db.ReportTask.updated_at < grace_cutoff),
        ),
    )
    if user_id is not None:
        q = q.filter(models_db.ReportTask.user_id == user_id)

    settled = 0
    for task in q.limit(limit).all():
        ref = task.charge_ref
        status = billing.transaction_status(db, ref)
        if status == "refunded":
            # 已被别处退掉。原地摘掉引用，**不要**再动余额 ——
            # 在一个已退款的预扣上补"估多退款"就是凭空生钱。
            logger.warning("复盘 %s 的预扣已是 refunded，跳过结算", task.id)
            task.charge_ref = None
            db.commit()
            continue
        if status == "committed":
            # 上一轮在 commit 与 grant 之间崩了 —— 预扣已落定，差额还没退。
            # 退款行的 ref_id 是确定性的，据此判断该补不该补。
            # （不加这一段，用户会被永久按完整预估收费。）
            reserved = billing.reserved_amount(db, ref)
            actual = analysis_cost.report_cost(task.analyzed_moves or 0, task.requested_visits or 0)
            if reserved > actual and not billing.has_transaction(db, f"{ref}:refund"):
                billing.grant(db, task.user_id, reserved - actual,
                              reason="report_overestimate_refund", ref_id=f"{ref}:refund")
                logger.info("补退复盘 %s 的估算差额 %s", task.id, reserved - actual)
            task.charge_ref = None
            db.commit()
            settled += 1
            continue
        if status != "reserved":
            logger.warning("复盘 %s 的预扣状态是 %s，跳过", task.id, status)
            task.charge_ref = None
            db.commit()
            continue

        actual = analysis_cost.report_cost(task.analyzed_moves or 0, task.requested_visits or 0)
        try:
            if actual <= 0:
                billing.refund(db, ref)
            else:
                reserved = billing.reserved_amount(db, ref)
                billing.commit(db, ref)
                if reserved > actual:
                    billing.grant(db, task.user_id, reserved - actual,
                                  reason="report_overestimate_refund", ref_id=f"{ref}:refund")
                # reserved < actual 在本设计里不可能：Task 4 让 total_moves 成为契约、
                # cron 只分析已付费前缀，所以 analyzed_moves <= total_moves。
                # 真出现了说明那条不变式破了 —— 报警，不要静默吞掉。
                elif reserved < actual:
                    logger.error(
                        "复盘 %s 实际成本 %s 超过预扣 %s —— total_moves 契约被破坏了",
                        task.id, actual, reserved,
                    )
            task.charge_ref = None
            db.commit()
            settled += 1
        except billing.BillingError:
            logger.exception("结算复盘任务 %s 失败，留待下一轮", task.id)
            db.rollback()
    return settled
```

`server.py` 在既有 `reconcile_stale_reservations` 之后加一次启动结算，并按该文件既有调度写法加周期结算。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_settlement.py -v`
Expected: 8 passed

- [ ] **Step 6: 加 cron 边界闸（含变异验证）**

```python
# tests/web_ui/test_cron_boundary.py
"""katrain/cron 是 Dockerfile.cron 独立复制的子树，不得反向依赖 katrain.web。

变异验证记录：在 katrain/cron/jobs/report_analyze.py 顶部临时加
`from katrain.web.core import billing`，本测试 FAIL；撤销后 PASS。
"""
import pathlib
import re

CRON = pathlib.Path(__file__).resolve().parents[2] / "katrain" / "cron"


def test_cron_never_imports_katrain_web():
    offenders = []
    for py in CRON.rglob("*.py"):
        code = "\n".join(
            l for l in py.read_text(encoding="utf-8").splitlines()
            if not l.lstrip().startswith("#")
        )
        if re.search(r"^\s*(from|import)\s+katrain\.web", code, re.M):
            offenders.append(str(py))
    assert offenders == [], (
        f"Dockerfile.cron 只 COPY katrain/cron/，这些跨目录 import 只会在容器里炸：{offenders}"
    )
```

- [ ] **Step 7: 处理 retry 与 requeue 的重新授权**

`reports.py:283 /retry` 把 failed 任务直接改回 `pending`，`cron/jobs/requeue_reports.py` 对 completed 任务也会删结果并重回 pending。两者都**不重新授权** ⇒ 结算器先跑清掉 `charge_ref` 之后，用户按"断点续跑"免费拿完剩余部分。

规则写死为：

0. **`config.py` 加 `REPORT_RETRY_GRACE_SEC: int = 3600`**（本计划别处引用了它，必须在这里定义）。
1. **失败任务不立刻终结授权。** `settle_finished_reports` 的终态集合改成只含 `completed`；`failed` 交给一个**带宽限期**的分支：`failed` 且 `updated_at` 超过 `settings.REPORT_RETRY_GRACE_SEC`（默认 3600）才结算。宽限期内 `/retry` 能直接复用原预扣。
2. **`/retry` 若发现 `charge_ref` 已被清掉**（超过宽限期），必须**重新走一次授权**：按 `total_moves - analyzed_moves` 的剩余量预扣，余额不足返 402。
3. **`requeue_reports.py` 是运维工具**，它重排的任务写 `charge_ref = None` 且置 `billing_exempt_reason = "requeue"`（`ReportTask` 新增该列），结算器看到它一律跳过——**运维重跑不向用户收费**，但要留痕。

```python
# tests/web_ui/test_report_retry_authorization.py
"""失败→结算→重试 这条链上不得出现免费续跑。"""

@pytest.mark.anyio
async def test_retry_within_grace_reuses_the_original_reservation(app_failed_task, monkeypatch):
    client, token, user, task = app_failed_task            # 刚失败，未超宽限期
    before = _balance(user)
    r = await client.post(f"/api/v1/reports/{task.id}/retry",
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert _balance(user) == before, "宽限期内重试不该二次扣费"


@pytest.mark.anyio
async def test_retry_after_settlement_reauthorizes(app_settled_failed_task, monkeypatch):
    """结算已把预扣落定 —— 重试必须为剩余手数重新预扣，不能白跑。"""
    client, token, user, task = app_settled_failed_task
    before = _balance(user)
    r = await client.post(f"/api/v1/reports/{task.id}/retry",
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert _balance(user) < before, "结算之后重试必须重新授权"


@pytest.mark.anyio
async def test_retry_without_credits_returns_402(app_settled_failed_task):
    client, token, user, task = app_settled_failed_task
    _set_balance(user, 0)
    r = await client.post(f"/api/v1/reports/{task.id}/retry",
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 402


def test_requeued_task_is_marked_exempt_and_skipped_by_settlement(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db)
    t = _task(db, u, status="completed", total=250, analyzed=250, reserve=125)
    t.charge_ref = None
    t.billing_exempt_reason = "requeue"
    db.commit()
    assert settle_finished_reports(db) == 0
```

- [ ] **Step 8: 提交**

```bash
git add katrain/web/core/billing.py katrain/web/core/report_settlement.py katrain/web/core/models_db.py katrain/web/api/v1/endpoints/reports.py katrain/cron/jobs/requeue_reports.py katrain/web/server.py tests/web_ui/test_report_settlement.py tests/web_ui/test_report_retry_authorization.py tests/web_ui/test_cron_boundary.py
git commit -m "feat(billing): 终态对账结算、预扣移出通用 TTL 回收器、retry/requeue 重新授权"
```

---

## Task 7: `quota_buckets` 表与迁移

**Files:**
- Modify: `katrain/web/core/models_db.py`（新表 `QuotaBucket`）
- Modify: `katrain/web/core/migrations.py`（`PROTECTED_TABLES`）
- Test: `tests/web_ui/test_quota.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces: `models_db.QuotaBucket(id, user_id, kind, period_key, allowance, used, created_at)`，`UNIQUE(user_id, kind, period_key)`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_quota.py
"""额度桶：惰性开桶、原子消费、周期到点自动换桶（无 cron 重置任务）。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def db_user(db):
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    return db, u


def test_quota_bucket_table_exists():
    assert hasattr(models_db, "QuotaBucket")


def test_bucket_is_unique_per_user_kind_period(db_user):
    db, u = db_user
    mk = lambda: models_db.QuotaBucket(
        user_id=u.id, kind="free_report", period_key="W:2026-W36", allowance=1, used=0
    )
    db.add(mk()); db.commit()
    db.add(mk())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quota_buckets_is_protected_from_drift_rebuild():
    """重建这张表 = 给所有人重置额度，必须进保护名单。"""
    from katrain.web.core import migrations
    assert "quota_buckets" in migrations.PROTECTED_TABLES
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 三条全 FAIL

- [ ] **Step 3: 实现**

`models_db.py` 加（确认 `UniqueConstraint` 已在该文件的 import 里，没有就补）：

```python
class QuotaBucket(Base):
    """会员额度桶：计数器，不是货币。

    周期键惰性生成（`D:2026-09-05` / `W:2026-W36` / `M:2026-09`，Asia/Shanghai），
    到点自然换一个新键 ⇒ **不需要任何重置任务**。
    `allowance` 是开桶那一刻的套餐快照，中途改套餐不影响已开的桶。
    """

    __tablename__ = "quota_buckets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    period_key = Column(String(32), nullable=False)
    allowance = Column(Integer, nullable=False)
    used = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "kind", "period_key", name="uq_quota_bucket"),
        Index("ix_quota_bucket_lookup", "user_id", "kind", "period_key"),
    )
```

`migrations.py`：

```python
# 额度桶记录已消费的额度；drift 重建它 = 给所有人白重置一次额度。
QUOTA_TABLES = {"quota_buckets"}
PROTECTED_TABLES = BILLING_TABLES | AI_LADDER_TABLES | QUOTA_TABLES | {AI_LADDER_LEGACY_TABLE}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/core/migrations.py tests/web_ui/test_quota.py
git commit -m "feat(quota): 额度桶表 —— 惰性周期键，并纳入 drift 保护名单"
```

---

## Task 8: 惰性开桶、原子消费、显式释放

比第 1 稿多一个 `release`：建任务失败时要把已消费的免费额度还回去，而这**不能**靠"rollback 后补偿"（Task 1 的教训），必须是对已提交行的一次独立 UPDATE。

**Files:**
- Create: `katrain/web/core/quota.py`
- Test: `tests/web_ui/test_quota.py`（追加）

**Interfaces:**
- Produces: `period_key(kind_period, now=None) -> str`；`peek(db, user_id, kind, allowance, now=None) -> (used, allowance)`；`try_consume(db, user_id, kind, allowance, n=1, now=None) -> bool`；`release(db, user_id, kind_name, period_key_value, n=1) -> bool`（**按存下来的周期键，不重算当前时间**）

- [ ] **Step 1: 写失败测试（追加到 tests/web_ui/test_quota.py）**

日期常量已核对：`2026-09-05` CST → `D:2026-09-05` / `W:2026-W36` / `M:2026-09`；`2026-09-12` CST → `W:2026-W37`；UTC `2026-09-05 23:00` → 上海 `D:2026-09-06`。

```python
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def test_period_keys_shape():
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert quota.period_key("day", t) == "D:2026-09-05"
    assert quota.period_key("week", t) == "W:2026-W36"
    assert quota.period_key("month", t) == "M:2026-09"


def test_period_key_uses_shanghai_not_utc():
    """UTC 的 2026-09-05 23:00 在上海已是 09-06。按 UTC 算会让用户晚上 8 点提前换桶。"""
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 23, 0, tzinfo=timezone.utc)
    assert quota.period_key("day", t) == "D:2026-09-06"


def test_unknown_period_raises():
    from katrain.web.core import quota
    with pytest.raises(ValueError):
        quota.period_key("fortnight")


def test_consume_within_allowance(db_user):
    from katrain.web.core import quota
    db, u = db_user
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 1


def test_consume_stops_at_allowance(db_user):
    from katrain.web.core import quota
    db, u = db_user
    for _ in range(3):
        assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is False
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 3, "失败不得计数"


def test_new_period_gets_a_fresh_bucket(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=CST)     # W36
    t2 = datetime(2026, 9, 12, 10, 0, tzinfo=CST)    # W37
    for _ in range(3):
        quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1)
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1) is False
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t2) is True


def test_allowance_snapshot_survives_plan_change(db_user):
    """开桶时的限额是快照 —— 中途降级套餐不该把已用额度变成超额。"""
    from katrain.web.core import quota
    db, u = db_user
    quota.try_consume(db, u.id, "report_standard:week", allowance=25)
    used, allowance = quota.peek(db, u.id, "report_standard:week", allowance=8)
    assert allowance == 25, "读的是桶上的快照，不是当前套餐"


def test_release_returns_a_consumed_unit(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    pk = quota.period_key("week", t)
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is False
    assert quota.release(db, u.id, "free_report", pk) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True


def test_release_never_goes_below_zero(db_user):
    from katrain.web.core import quota
    db, u = db_user
    pk = quota.period_key("week")
    assert quota.release(db, u.id, "free_report", pk) is False


def test_release_targets_the_stored_period_not_today(db_user):
    """回归：上周崩掉的任务下周才被回收，必须还回**上周**那个桶。

    若 release 自己重算当前周期，就会既没还上旧桶、又把新周别人的 used 减掉。
    """
    from katrain.web.core import quota
    db, u = db_user
    t_old = datetime(2026, 9, 5, 10, 0, tzinfo=CST)     # W36
    t_new = datetime(2026, 9, 12, 10, 0, tzinfo=CST)    # W37
    old_pk = quota.period_key("week", t_old)
    quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t_old)
    quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t_new)

    assert quota.release(db, u.id, "free_report", old_pk) is True
    assert quota.peek(db, u.id, "free_report:week", allowance=1, now=t_old)[0] == 0
    assert quota.peek(db, u.id, "free_report:week", allowance=1, now=t_new)[0] == 1, \
        "新周的桶不得被误减"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 新增 10 条 FAIL（`ImportError: cannot import name 'quota'`）

- [ ] **Step 3: 实现**

```python
# katrain/web/core/quota.py
"""额度桶：惰性周期键 + 原子消费。

**为什么没有重置任务**：周期到点会自然生成一个新的 period_key，
旧桶原地不动、新桶从 0 开始。任何"到点把 used 清零"的定时任务都是多余的，
而且一旦漏跑就会静默地让用户少领一轮。

**限制**：本切片只支持 day / week / month 三种自然周期。requirements.md 提到的
`P:<subscription_period_id>`（按订阅日切）**没有实现** —— 套餐上线时补，
届时要处理非自然月续费、取消与降级。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.web.core import models_db

# 计费周期一律按北京时间切，不跟服务器时区走。
BILLING_TZ = timezone(timedelta(hours=8))


def period_key(kind_period: str, now: Optional[datetime] = None) -> str:
    """把时间点映射到周期键。kind_period ∈ {day, week, month}。"""
    t = (now or datetime.now(timezone.utc)).astimezone(BILLING_TZ)
    if kind_period == "day":
        return f"D:{t:%Y-%m-%d}"
    if kind_period == "week":
        iso_year, iso_week, _ = t.isocalendar()
        return f"W:{iso_year}-W{iso_week:02d}"
    if kind_period == "month":
        return f"M:{t:%Y-%m}"
    raise ValueError(f"未知周期 {kind_period!r}（本切片只支持 day/week/month）")


def _split(kind: str) -> Tuple[str, str]:
    """'free_report:week' -> ('free_report', 'week')"""
    name, _, period = kind.partition(":")
    if not period:
        raise ValueError(f"kind 必须形如 'name:period'，收到 {kind!r}")
    return name, period


def _ensure_bucket(db: Session, user_id: int, kind: str, allowance: int, now=None):
    name, period = _split(kind)
    key = period_key(period, now)
    row = (
        db.query(models_db.QuotaBucket)
        .filter_by(user_id=user_id, kind=name, period_key=key)
        .one_or_none()
    )
    if row is not None:
        return row
    row = models_db.QuotaBucket(
        user_id=user_id, kind=name, period_key=key, allowance=allowance, used=0
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # 并发开桶，别人先建成了。rollback 已经撤销我们这次 INSERT，
        # **不要做任何补偿写** —— billing.reserve 当年就是栽在这里
        # （见 tests/web_ui/test_billing_race.py）。
        db.rollback()
        row = (
            db.query(models_db.QuotaBucket)
            .filter_by(user_id=user_id, kind=name, period_key=key)
            .one()
        )
    return row


def peek(db: Session, user_id: int, kind: str, allowance: int, now=None) -> Tuple[int, int]:
    """返回 (已用, 限额)。限额取**桶上的快照**，不是传进来的当前套餐值。"""
    row = _ensure_bucket(db, user_id, kind, allowance, now)
    return int(row.used), int(row.allowance)


def try_consume(db: Session, user_id: int, kind: str, allowance: int, n: int = 1, now=None) -> bool:
    """原子消费 n 份额度。额度不足返回 False 且不改任何行。"""
    if n <= 0:
        raise ValueError("n 必须 >= 1")
    row = _ensure_bucket(db, user_id, kind, allowance, now)
    result = db.execute(
        text("UPDATE quota_buckets SET used = used + :n "
             "WHERE id = :bid AND used + :n <= allowance"),
        {"n": n, "bid": row.id},
    )
    db.commit()
    return result.rowcount == 1


def release(db: Session, user_id: int, kind_name: str, period_key_value: str, n: int = 1) -> bool:
    """把已消费的 n 份额度还回**指定周期**的桶。

    **必须传入当初消费时那个 period_key，不能在这里重算当前时间**：
    回收器可能在下一周才跑到一个上周崩掉的任务，重算会去减错桶——
    既没还上旧桶，又把新周别人的 used 减掉了。调用方从
    `ReportTask.free_grant_period` 取这个值（Task 5 已把它存在任务行上）。

    这是对**已提交行**的一次独立 UPDATE，不是「rollback 之后补偿」——
    后者正是 billing.reserve 当年的 bug（见 tests/web_ui/test_billing_race.py）。
    """
    result = db.execute(
        text("UPDATE quota_buckets SET used = used - :n "
             "WHERE user_id = :uid AND kind = :k AND period_key = :pk AND used >= :n"),
        {"n": n, "uid": user_id, "k": kind_name, "pk": period_key_value},
    )
    db.commit()
    return result.rowcount == 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 13 passed

- [ ] **Step 5: 记一条只能在 PG 上证的事，并让它在有 DSN 时真的跑**

```python
import os

@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_DSN"),
                    reason="并发行锁只能在 PG 上证；设 TEST_POSTGRES_DSN 后本用例会真的跑")
def test_concurrent_consume_never_exceeds_allowance_on_postgres():
    """两个连接同时抢最后一份额度，必须恰好一个成功。

    SQLite 会把并发串行化，在那里跑绿属于「保证在本机不存在而不会红」，
    不构成证据。上线前必须在 home-ubuntu 的 PG 上跑过这一条。
    """
    import threading
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from katrain.web.core import models_db, quota

    engine = create_engine(os.environ["TEST_POSTGRES_DSN"])
    models_db.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s0 = Session()
    u = models_db.User(username=f"race{os.getpid()}", hashed_password="x")
    s0.add(u); s0.commit(); s0.refresh(u)

    results = []
    def worker():
        s = Session()
        try:
            results.append(quota.try_consume(s, u.id, "free_report:week", allowance=1))
        finally:
            s.close()

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(results) == [False, True], f"恰好一个成功，实得 {results}"
```

**发布硬闸**：上线前必须带 `TEST_POSTGRES_DSN` 跑一次这条，结果贴进 `deploy-notes.md`。skip 是诚实，但不是发布证据。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/quota.py tests/web_ui/test_quota.py
git commit -m "feat(quota): 惰性周期键、原子消费与显式释放"
```

---

## Task 9: 每周免费复盘 = 不滚存的周额度桶

第 1 稿用 `billing.grant` 每周发 150 积分——**那会永久滚存**（与 requirements P2「不滚存」自相矛盾），而且积分是单池货币，攒起来可以用在任何地方。改成周桶：一周一次，用掉就没，不累积、不可转移。

**Files:**
- Modify: `katrain/web/api/v1/endpoints/reports.py`（Task 5 已写入调用点）
- Modify: `katrain/web/core/config.py`
- Test: `tests/web_ui/test_free_weekly.py`（新建）

**Interfaces:**
- Consumes: `quota.try_consume` / `quota.period_key`
- Produces: `settings.FREE_WEEKLY_REPORTS: int = 1`；桶名 `free_report:week`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_free_weekly.py
"""每周免费复盘：一周一次，用掉就没，**不累积**。"""
from datetime import datetime, timedelta, timezone

import pytest

CST = timezone(timedelta(hours=8))


def test_one_free_report_per_week(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t) is False


def test_free_quota_does_not_accumulate(db_user):
    """第 1 稿的 bug：用 billing.grant 每周发积分，攒三周就有三份可用。

    周桶不会：前三周一次都没用，第四周依然只有一份。
    """
    from katrain.web.core import quota
    db, u = db_user
    # 前三周完全不碰（连 peek 都不做，模拟用户没上线）
    t4 = datetime(2026, 9, 26, 10, 0, tzinfo=CST)     # W39
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t4) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t4) is False, \
        "攒了三周也只有当周这一份"


def test_next_week_gets_a_fresh_one(db_user):
    from katrain.web.core import quota
    db, u = db_user
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    t2 = datetime(2026, 9, 12, 10, 0, tzinfo=CST)
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t1) is True
    assert quota.try_consume(db, u.id, "free_report:week", allowance=1, now=t2) is True


def test_free_report_leaves_no_ledger_row(db_user):
    """免费额度是计数器不是货币 —— 不进账本（2026-06-07 裁决：不要两种货币）。"""
    from katrain.web.core import quota, models_db
    db, u = db_user
    quota.try_consume(db, u.id, "free_report:week", allowance=1)
    assert db.query(models_db.CreditTransaction).filter_by(user_id=u.id).count() == 0


@pytest.mark.anyio
async def test_second_report_in_same_week_is_charged(app_with_game, monkeypatch):
    """端到端：本周第一份免费，第二份扣积分。"""
    client, token, game_id, user = app_with_game
    from katrain.web.core.config import settings
    monkeypatch.setattr(settings, "BILLING_ENFORCED", True)
    b0 = _balance(user)
    await client.post("/api/v1/reports/", json={"user_game_id": game_id, "force": True},
                      headers={"Authorization": f"Bearer {token}"})
    assert _balance(user) == b0, "本周第一份应该免费"
    await client.post("/api/v1/reports/", json={"user_game_id": game_id, "force": True},
                      headers={"Authorization": f"Bearer {token}"})
    assert _balance(user) < b0, "本周第二份应该扣费"
```

- [ ] **Step 2-4**：`FREE_WEEKLY_REPORTS: int = 1` **已由 Task 5 加进 `config.py`**——本任务只需**确认它在**，另外**删掉**死常量 `BILLING_FREE_GRANT`（全仓零引用）。消费调用点也已在 Task 5 写好。跑测试确认通过。

- [ ] **Step 5: 提交**

```bash
git add katrain/web/core/config.py tests/web_ui/test_free_weekly.py
git commit -m "feat(quota): 每周免费复盘改为不滚存的周额度桶，不再发永久积分"
```

---

## Task 10: 新账号赠额归零 + 存量余额建账

第 1 稿只改了两处列默认值——那**不动数据库里已有的行**。存量用户手上那 10000 是列默认值来的、账本里没有对应行；一旦开始扣费，账本增量解释不了当前余额，审计和补偿都无从下手。必须补一次幂等的开账迁移。

**Files:**
- Modify: `katrain/web/core/models_db.py:78`、`katrain/web/models.py:183`、`katrain/web/core/config.py`、`katrain/web/api/v1/endpoints/auth.py`
- Create: `katrain/web/core/migrations_opening_balance.py`
- Test: `tests/web_ui/test_signup_grant.py`、`tests/web_ui/test_opening_balance.py`（新建）

**Interfaces:**
- Produces: `settings.BILLING_SIGNUP_GRANT: int = 0`；`backfill_opening_balances(db) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_opening_balance.py
"""存量余额必须有一条对应的开账账本行，否则账本解释不了余额。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_backfill_creates_one_opening_row_per_legacy_user(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances
    u = models_db.User(username="legacy", hashed_password="x", credits=10000)
    db.add(u); db.commit(); db.refresh(u)

    assert backfill_opening_balances(db) == 1
    rows = db.query(models_db.CreditTransaction).filter_by(user_id=u.id).all()
    assert len(rows) == 1
    assert rows[0].reason == "opening_balance"
    assert rows[0].delta == 10000
    assert rows[0].balance_after == 10000
    assert billing.get_balance(db, u.id) == 10000, "开账不得改变余额，只补账"


def test_backfill_is_idempotent(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances
    u = models_db.User(username="legacy", hashed_password="x", credits=10000)
    db.add(u); db.commit()
    backfill_opening_balances(db)
    assert backfill_opening_balances(db) == 0
    assert db.query(models_db.CreditTransaction).count() == 1


def test_backfill_covers_a_user_whose_ledger_only_explains_part_of_the_balance(db):
    """最典型的一类人：列默认值给了 10000，又兑换过 500 ⇒ 余额 10500、账本只有 +500。

    「跳过已有账本行的用户」这个写法会永久漏掉他们 —— 判据必须是残差。
    """
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances
    u = models_db.User(username="mixed", hashed_password="x", credits=10000)
    db.add(u); db.commit(); db.refresh(u)
    billing.grant(db, u.id, 500, "redeem", "redeem:abc")     # 余额变 10500，账本 +500

    assert backfill_opening_balances(db) == 1
    row = db.query(models_db.CreditTransaction).filter_by(reason="opening_balance").one()
    assert row.delta == 10000, "补的是残差，不是全额"
    assert billing.get_balance(db, u.id) == 10500, "开账不得改变余额"


def test_backfill_skips_users_whose_ledger_already_explains_the_balance(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances
    u = models_db.User(username="clean", hashed_password="x", credits=0)
    db.add(u); db.commit(); db.refresh(u)
    billing.grant(db, u.id, 500, "redeem", "redeem:abc")
    assert backfill_opening_balances(db) == 0, "残差为 0 不需要开账"


def test_backfill_all_loops_until_converged(db):
    """启动只调一次单批函数，batch 之外的用户会永久留在不一致状态。"""
    from katrain.web.core.migrations_opening_balance import backfill_all_opening_balances
    for i in range(7):
        db.add(models_db.User(username=f"legacy{i}", hashed_password="x", credits=10000))
    db.commit()
    assert backfill_all_opening_balances(db, batch=3) == 7


def test_backfill_skips_zero_balance_users(db):
    from katrain.web.core.migrations_opening_balance import backfill_opening_balances
    db.add(models_db.User(username="fresh", hashed_password="x", credits=0))
    db.commit()
    assert backfill_opening_balances(db) == 0
```

```python
# tests/web_ui/test_signup_grant.py  （同第 1 稿三条）
def test_orm_default_is_zero(db): ...
def test_pydantic_default_is_zero(): ...
def test_signup_grant_default_is_zero(): ...
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_opening_balance.py tests/web_ui/test_signup_grant.py -v`

- [ ] **Step 3: 实现开账迁移**

```python
# katrain/web/core/migrations_opening_balance.py
"""给存量余额补一条开账账本行。

背景：新账号的 credits 一直来自列默认值（10000），从不走账本。
开始扣费之前必须让「账本增量」能解释「当前余额」，否则事后审计、
补偿、回滚都无法区分历史默认赠额、管理员赠额与真实充值。

**这个迁移只补账、不改余额**：delta 就是用户当前的余额，balance_after 也是它。
选择 grandfather（保留存量余额）而不是清零 —— 清零会让老用户在毫无预告的
情况下损失既得，那是产品决策不是迁移能替 Fan 做的。
"""
import logging

from sqlalchemy.orm import Session

from katrain.web.core import models_db

logger = logging.getLogger("katrain_web")


def backfill_opening_balances(db: Session, batch: int = 500) -> int:
    """给每个存量用户补一条**残差**开账行，直到全部处理完。返回补的条数。

    **为什么不是「跳过已有账本的用户」**：那个写法漏掉最典型的一类人——
    从列默认值拿了 10000、又兑换过 500 的用户，余额 10500 而账本只有 +500。
    他有账本行，于是被跳过，那 10000 永远无法被账本解释。
    正确的判据是**残差**：`residual = credits - sum(有效账本 delta)`，
    残差非 0 就补一行。残差为 0 的用户天然跳过，不需要额外条件。

    有效 delta = status in ('committed', 'reserved')。`reserved` 也算，因为它
    已经从 users.credits 里扣掉了（见 billing.reserve 的条件 UPDATE）。

    **这个迁移只补账、不改余额**：选 grandfather（保留存量余额）而不是清零——
    清零会让老用户在毫无预告的情况下损失既得，那是产品决策，迁移替不了 Fan 做。
    """
    from sqlalchemy import func as sa_func

    ledger = (
        db.query(
            models_db.CreditTransaction.user_id.label("uid"),
            sa_func.coalesce(sa_func.sum(models_db.CreditTransaction.delta), 0).label("total"),
        )
        .filter(models_db.CreditTransaction.status.in_(("committed", "reserved")))
        .group_by(models_db.CreditTransaction.user_id)
        .subquery()
    )
    rows = (
        db.query(models_db.User, sa_func.coalesce(ledger.c.total, 0))
        .outerjoin(ledger, ledger.c.uid == models_db.User.id)
        .filter(models_db.User.credits != sa_func.coalesce(ledger.c.total, 0))
        .limit(batch)
        .all()
    )
    n = 0
    for u, ledger_total in rows:
        residual = int(u.credits) - int(ledger_total)
        if residual == 0:
            continue
        ref = f"opening_balance:{u.id}"
        if db.query(models_db.CreditTransaction).filter_by(ref_id=ref).first() is not None:
            # 已经补过一次却仍有残差 —— 说明账本之外还有别的写入路径，报警别静默。
            logger.error("用户 %s 已有 opening_balance 行但残差仍为 %s", u.id, residual)
            continue
        db.add(models_db.CreditTransaction(
            user_id=u.id, delta=residual, reason="opening_balance",
            ref_id=ref, status="committed", balance_after=int(u.credits),
        ))
        n += 1
    if n:
        db.commit()
        logger.info("opening_balance: 补了 %s 条开账行", n)
    return n


def backfill_all_opening_balances(db: Session, batch: int = 500, max_rounds: int = 200) -> int:
    """循环调用直到没有可补的为止。启动时只调一次 backfill_opening_balances
    会把 batch 之外的用户永久留在不一致状态。"""
    total = 0
    for _ in range(max_rounds):
        n = backfill_opening_balances(db, batch)
        if n == 0:
            return total
        total += n
    logger.error("opening_balance: 达到 max_rounds 仍未收敛，剩余用户未迁移")
    return total
```

在 `server.py` 启动流程里调 `backfill_all_opening_balances`（**不是**单批的那个），幂等，收敛后就再也不动。

- [ ] **Step 4: 改两处默认值与注册赠额**

- `models_db.py:78` → `credits = Column(Integer, default=0, nullable=False)`
- `models.py:183` → `credits: int = 0`
- `config.py`：删 `BILLING_FREE_GRANT`，加 `BILLING_SIGNUP_GRANT: int = 0`
- `endpoints/auth.py` 注册成功后按 `BILLING_SIGNUP_GRANT` 走 `billing.grant`（>0 才发）

- [ ] **Step 5: 改既有测试的过期断言**

`tests/web_ui/test_user_data_api.py:72`、`test_board_auth.py:203`、`test_billing_api.py:53` 断言 `credits == 10000`，改成 0。**不要**为了绿而保留 10000。

- [ ] **Step 6: 跑全量并与基线比名字集合**

```bash
CI=true uv run pytest tests -q 2>&1 | grep -E "^(FAILED|ERROR)" | sed 's/ - .*//' | sort -u > /tmp/after.txt
comm -13 superpowers/tracks/galaxy-payment/test-baseline.txt /tmp/after.txt   # 必须为空
```

基线（本 worktree，`uv sync --extra web --extra vision --group dev` + `boto3 fonttools brotli moto[s3]`）：**85 条已知失败**，存档在 `superpowers/tracks/galaxy-payment/test-baseline.txt`。比的是**名字集合**，不是条数。

- [ ] **Step 7: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/models.py katrain/web/core/config.py katrain/web/api/v1/endpoints/auth.py katrain/web/core/migrations_opening_balance.py katrain/web/server.py tests/
git commit -m "fix(billing): 新账号赠额归零，并为存量余额补开账账本行"
```

---

## Task 11: 额度看板端点（返回前先结算本用户）

**Files:**
- Modify: `katrain/web/api/v1/endpoints/billing.py`
- Test: `tests/web_ui/test_billing_api.py`（追加）

**Interfaces:**
- Consumes: `billing.get_balance`、`quota.peek`、`analysis_cost.report_cost`、`report_settlement.settle_finished_reports`
- Produces: `GET /api/v1/billing/quota`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_quota_endpoint_shape(app):
    client, token, _ = app
    r = await client.get("/api/v1/billing/quota", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    b = r.json()
    assert isinstance(b["credits"], int)
    assert b["free_weekly"]["allowance"] == 1
    assert b["free_weekly"]["used"] in (0, 1)
    assert b["estimates"]["deep_250_moves"] == 4 * b["estimates"]["normal_250_moves"]
    assert b["billing_enforced"] is False        # 默认关，前端据此决定要不要显示价格


@pytest.mark.anyio
async def test_quota_endpoint_settles_before_reporting(app_with_finished_task):
    """余额必须是结算后的数 —— 不能让用户看到一个「等对账器跑完才准」的余额。"""
    client, token, user, task = app_with_finished_task
    r = await client.get("/api/v1/billing/quota", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["credits"] == _expected_after_settlement(task)


@pytest.mark.anyio
async def test_quota_endpoint_requires_auth(app):
    client, _, _ = app
    assert (await client.get("/api/v1/billing/quota")).status_code == 401
```

- [ ] **Step 2-4**：实现

```python
@router.get("/quota")
async def get_quota(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """余额、免费周额度、以及「这些钱大概够几份复盘」。

    先跑一次本用户的结算再报数 —— 对账器是周期跑的，直接读余额会让用户
    在复盘刚跑完的那段窗口里看到一个偏低的数（预扣还没退差）。
    估算就叫估算：真实成本按**实际分析到的手数**结算，认输的短棋更便宜。
    """
    if _is_board():
        _need_online()
    from katrain.web.core import analysis_cost, quota
    from katrain.web.core.config import settings
    from katrain.web.core.report_settlement import settle_finished_reports

    settle_finished_reports(db, user_id=current_user.id)
    used, allowance = quota.peek(db, current_user.id, "free_report:week",
                                 allowance=settings.FREE_WEEKLY_REPORTS)
    return {
        "credits": billing.get_balance(db, current_user.id),
        "free_weekly": {"used": used, "allowance": allowance},
        "estimates": {
            "normal_250_moves": analysis_cost.report_cost(250, 500),
            "deep_250_moves": analysis_cost.report_cost(250, 2000),
        },
        "billing_enforced": bool(settings.BILLING_ENFORCED),
        "billing_online": True,
    }
```

- [ ] **Step 5: 提交**

```bash
git add katrain/web/api/v1/endpoints/billing.py tests/web_ui/test_billing_api.py
git commit -m "feat(billing): 额度看板端点 —— 返回前先结算本用户，估算标注为估算"
```

---

## Task 12: 孤儿与滞留回收器 + 冻结被分析的 SGF

Task 6 把 `reason="report"` 排除出通用 TTL 回收器之后，**复盘预扣就只剩结算器一个管理者**，而结算器是按 `ReportTask` 行遍历的。于是出现三类它够不着的钱：

1. **孤儿预扣**：`UserGame` 对 `ReportTask` 是 `cascade="all, delete-orphan"`（`models_db.py:733`）。`DELETE /user-games/{id}` 会把任务行删掉，**预扣却留在账本里**——用户的积分被永久冻结，没有任何人会退。
2. **滞留 authorizing**：Task 5 的建任务路径跨多次提交（任务行 → 额度/预扣 → 翻 pending）。中间崩溃会留下 `authorizing` 任务：cron 不认领，结算器不看（它只看终态），额度已消费、积分已预扣。
3. **改了棋谱**：`PUT /user-games/{id}` 可改 `sgf_content`（`user_games.py:42,178`）。`moves[:paid_moves]` 只限住**数量**，限不住**内容**；配合 `_get_resume_move_number` 的断点续跑，报告会由旧棋谱的前缀和新棋谱的后缀拼成。

**Files:**
- Modify: `katrain/web/core/models_db.py`（`ReportTask.sgf_hash`、`billing_exempt_reason`）
- Modify: `katrain/web/core/migrations.py`
- Create: `katrain/web/core/report_reaper.py`
- Modify: `katrain/web/api/v1/endpoints/reports.py`（授权时记 hash）
- Modify: `katrain/cron/jobs/report_analyze.py`（认领时校验 hash）
- Test: `tests/web_ui/test_report_reaper.py`（新建）

**Interfaces:**
- Produces: `reap_orphaned_report_charges(db) -> int`；`reap_stale_authorizing(db, ttl_sec) -> int`；`ReportTask.sgf_hash: str | None`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_report_reaper.py
"""复盘预扣被移出通用 TTL 回收器之后，这三类钱谁来管。"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _user(db, credits=1000):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_deleting_the_game_does_not_freeze_credits_forever(db):
    """回归：级联删除会带走任务行，而预扣留在账本里没人管。"""
    from katrain.web.core.report_reaper import reap_orphaned_report_charges
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="pending", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    ref = f"report:{t.id}"
    billing.reserve(db, u.id, 125, "report", ref)
    t.charge_ref = ref
    db.commit()
    assert billing.get_balance(db, u.id) == 875

    db.delete(g); db.commit()                       # 级联把任务行也删了
    assert db.query(models_db.ReportTask).count() == 0

    assert reap_orphaned_report_charges(db) == 1
    assert billing.get_balance(db, u.id) == 1000, "任务都没了，钱必须退回去"


def test_reaper_leaves_charges_whose_task_still_exists(db):
    from katrain.web.core.report_reaper import reap_orphaned_report_charges
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="running", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    db.commit()
    assert reap_orphaned_report_charges(db) == 0
    assert billing.get_balance(db, u.id) == 875


def test_stale_authorizing_task_is_rolled_back(db):
    """建任务途中崩溃：cron 不认领、结算器不看，额度和积分卡在半路。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    from katrain.web.core import quota
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250)
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    t.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert reap_stale_authorizing(db, ttl_sec=600) == 1
    assert billing.get_balance(db, u.id) == 1000
    assert db.query(models_db.ReportTask).count() == 0


def test_stale_authorizing_releases_the_free_weekly_unit(db):
    """用免费额度那条路崩在半路 —— 额度也要还回**当初那个周**的桶。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    from katrain.web.core import quota
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    pk = quota.period_key("week")
    quota.try_consume(db, u.id, "free_report:week", allowance=1)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250,
                             free_grant_period=pk)
    db.add(t); db.commit(); db.refresh(t)
    t.created_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert reap_stale_authorizing(db, ttl_sec=600) == 1
    assert quota.peek(db, u.id, "free_report:week", allowance=1)[0] == 0, "免费额度要还回去"


def test_fresh_authorizing_task_is_left_alone(db):
    """正在授权中的任务不能被回收器抢走。"""
    from katrain.web.core.report_reaper import reap_stale_authorizing
    u = _user(db)
    g = models_db.UserGame(user_id=u.id, source="import", move_count=250)
    db.add(g); db.commit(); db.refresh(g)
    t = models_db.ReportTask(user_id=u.id, user_game_id=g.id, report_type="normal",
                             requested_visits=500, status="authorizing", total_moves=250)
    db.add(t); db.commit()
    assert reap_stale_authorizing(db, ttl_sec=600) == 0


def test_sgf_hash_is_frozen_at_authorization(db):
    """授权时冻结棋谱指纹 —— 之后改棋谱不能悄悄换掉被分析的内容。"""
    import hashlib
    from katrain.web.api.v1.endpoints.reports import sgf_fingerprint
    a = sgf_fingerprint("(;GM[1];B[pd])")
    b = sgf_fingerprint("(;GM[1];B[dp])")
    assert a != b
    assert a == sgf_fingerprint("(;GM[1];B[pd])")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_reaper.py -v`
Expected: 全 FAIL（模块不存在）

- [ ] **Step 3: 加两列并冻结指纹**

`models_db.py` 的 `ReportTask` 追加：

```python
    # 授权那一刻棋谱内容的指纹。cron 认领时比对，不一致就失败而不是拼一份
    # 「旧棋谱前缀 + 新棋谱后缀」的报告出来。
    sgf_hash = Column(String(64), nullable=True)
    # 运维重排（requeue）标记：这类任务不向用户收费，但要留痕。
    billing_exempt_reason = Column(String(32), nullable=True)
```

`reports.py`：

```python
def sgf_fingerprint(sgf_content: str) -> str:
    """棋谱内容指纹。授权时冻结在任务上，cron 认领时比对。"""
    import hashlib
    return hashlib.sha256(sgf_content.encode("utf-8")).hexdigest()
```
授权时 `report_task.sgf_hash = sgf_fingerprint(game.sgf_content)`。

`katrain/cron/jobs/report_analyze.py` 在 `parsed = parse_game(game.sgf_content)` 之后：

```python
            # 授权时冻结的指纹对不上 ⇒ 棋谱在排队期间被改过。
            # 继续跑会拼出「旧棋谱前缀 + 新棋谱后缀」的报告，且用户付的是旧棋谱的钱。
            if task.sgf_hash:
                import hashlib
                if hashlib.sha256(game.sgf_content.encode("utf-8")).hexdigest() != task.sgf_hash:
                    task.status = "failed"
                    task.error_message = "棋谱在排队期间被修改，请重新发起复盘"
                    db.commit()
                    return
```

- [ ] **Step 4: 实现回收器**

```python
# katrain/web/core/report_reaper.py
"""复盘预扣的兜底回收。

Task 6 把 reason="report" 排除出通用 TTL 回收器之后，复盘预扣就**只剩
结算器一个管理者**，而结算器按 ReportTask 行遍历。这里收两类它够不着的钱：
任务行已经没了的孤儿预扣，和卡在 authorizing 的半成品。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from katrain.web.core import billing, models_db, quota

logger = logging.getLogger("katrain_web")


def reap_orphaned_report_charges(db: Session, limit: int = 200) -> int:
    """退还「任务行已经不存在」的复盘预扣。

    UserGame 对 ReportTask 是 cascade delete-orphan，删棋谱会带走任务行，
    预扣却留在账本里 —— 没有这个回收器，那笔钱永久冻结。
    """
    rows = (
        db.query(models_db.CreditTransaction)
        .filter(
            models_db.CreditTransaction.status == "reserved",
            models_db.CreditTransaction.reason == "report",
        )
        .limit(limit)
        .all()
    )
    n = 0
    for tx in rows:
        try:
            task_id = int(tx.ref_id.split(":", 1)[1])
        except (IndexError, ValueError):
            continue
        if db.query(models_db.ReportTask.id).filter_by(id=task_id).first() is not None:
            continue
        billing.refund(db, tx.ref_id)
        logger.info("退还孤儿复盘预扣 %s", tx.ref_id)
        n += 1
    return n


def reap_stale_authorizing(db: Session, ttl_sec: int = 600, limit: int = 200) -> int:
    """回滚卡在 authorizing 的任务：退积分、还额度、删任务行。

    cron 只认 pending，结算器只看终态 —— 这个状态没有别的管理者。
    ttl 要明显大于一次正常授权耗时（默认 600 秒），免得抢走正在进行的请求。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_sec)
    tasks = (
        db.query(models_db.ReportTask)
        .filter(models_db.ReportTask.status == "authorizing",
                models_db.ReportTask.created_at < cutoff)
        .limit(limit)
        .all()
    )
    n = 0
    for t in tasks:
        if t.charge_ref and billing.transaction_status(db, t.charge_ref) == "reserved":
            billing.refund(db, t.charge_ref)
        if t.free_grant_period:
            # 按**任务上存着的**那个周期键还，不是当前周（见 quota.release 的注释）。
            quota.release(db, t.user_id, "free_report", t.free_grant_period)
        db.delete(t)
        db.commit()
        logger.info("回滚滞留的 authorizing 任务 %s", t.id)
        n += 1
    return n
```

`server.py` 把这两个挂到与 `settle_finished_reports` 相同的周期调度上。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_reaper.py tests/web_ui/test_report_settlement.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/core/migrations.py katrain/web/core/report_reaper.py katrain/web/api/v1/endpoints/reports.py katrain/cron/jobs/report_analyze.py katrain/web/server.py tests/web_ui/test_report_reaper.py
git commit -m "feat(billing): 孤儿与滞留预扣的兜底回收，并在授权时冻结棋谱指纹"
```

---

## 发布顺序与回滚边界

| 发布 | 内容 | 可回滚性 |
|---|---|---|
| **Release 0** | Task 0（admin/admin）+ Task 1（账本竞争）+ Task 2（SECRET_KEY） | 代码可回滚。**但换过的密钥不得回退到已公开的旧值**——回滚代码时保留新密钥。副作用是全站登出一次，选低峰并公告。 |
| **Release 1** | Task 3–12，`BILLING_ENFORCED=False` | 行为与今天一致，可随时回滚。 |
| **开闸** | 把 `BILLING_ENFORCED` 置 True | **最难回滚的一步**：一旦开始写真实余额与账本，回滚代码不会回滚已扣的钱。前置：P3 手机绑定 + 注册限流已上线、P5 页脚已上线、U4 定性已完成、PG 并发用例已在 home-ubuntu 跑过。先在测试环境开一周。 |

**开闸前必过的硬闸**（不是可选项）：
1. `TEST_POSTGRES_DSN` 下跑通 `test_concurrent_consume_never_exceeds_allowance_on_postgres`
2. 全量测试与基线名字集合差集为空
3. 在测试环境走一遍真实链路：建任务 → cron 跑 → 终态 → 对账 → `/billing/quota` 的数对得上
4. 故意重启一次 web，确认在跑的复盘预扣**没有**被退（Task 6 那条回归的现场版）
5. 两台机器上检查是否存在用户名 `admin` 且口令仍是 `admin` 的账号（Task 0 只挡"以后不再产生"）
6. `report_tasks` 的活跃任务部分唯一索引已建（见「已知限制」第 2 条）

---

## 已知限制（明确接受，不是遗漏）

第 2 轮评审的 9 条里有 2 条我**没有**照单执行，理由与残余风险如下。开闸前需要 Fan 知情。

**1. billing / quota 的 API 仍然自己 commit，没有改成"调用方管理事务"。**
评审建议把任务行、额度消费、预扣、放行合进单个数据库事务。那需要重写一个**正在工作的**账本 API 的事务边界，波及 `redeem` / `settle_order` / `reconcile` 等所有既有调用方，与本切片的风险不相称。
替代方案是**确定性 ref + 兜底回收器**（Task 12）：每一笔钱都能从 `report:{task_id}` 这个确定性键找回来，孤儿和滞留都有专门的回收者。
**残余风险**：从崩溃到回收器跑到之间，用户的那笔预扣是被冻结的（默认 ttl 600 秒 + 一个调度周期）。用户看到的余额在这段窗口里偏低。这是**钱不会丢、但会短暂不可用**，不是钱会错。可以接受。

**2. `POST /reports/` 没有客户端幂等键。**
本稿用两件事覆盖绝大多数：去重集合纳入 `authorizing`；`force=false` 的路径依赖数据库查询。
**残余风险**：两个真正并发的 `force=true` 请求仍可能造成两次扣费 + 两份 GPU 工作。`force=true` 是用户手动点"重新分析"才会走的路径，并发重放的概率低、且用户会看到两份任务而察觉。
**开闸前要做的补救**：给 `report_tasks` 加一条部分唯一索引（`user_id, user_game_id, report_type` 且 `status IN ('authorizing','pending','running')`），把非 force 路径的竞争交给数据库。**这条要在开闸前完成，不能只留在文档里。**

---

## 本切片之后（各自需要单独的计划）

| 阶段 | 阻塞在什么上 |
|---|---|
| **手机绑定与验证码登录**（P3） | 短信签名/模板报备 **5–10 工作日**且尚未启动；需要企业实名认证；未决 U1（存量用户）、U2（Box SSO 无手机号）、U3（国际号通道与单价）。**它是开闸的前置**——裁决 D3 把「免费额度送所有注册用户」与「手机绑定 + 限流」绑在一起。 |
| **关掉密码注册的刷号路**（P4a） | 依赖 P3 落地。P4b（赠额归零）已在 Task 10 完成。 |
| **合规页脚 + 落地页**（P5） | 等 Fan 提供两个真实备案号；落地页需设计稿定稿。**它也是开闸的前置**。 |
| **会员套餐与订阅周期** | 本切片**没有**实现 `P:<subscription_period_id>` 周期键与套餐权威源，`quota.period_key` 只支持 day/week/month。套餐上线时要补，且要处理非自然月续费、取消、降级。 |
| **支付接入** | 商户开通；无自动续费资质 ⇒ 一次性购买 + 到期提醒。 |
