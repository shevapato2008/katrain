# galaxy 支付与会员体系 —— 实施计划（第一切片）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让复盘**按实际算力**扣费、让会员额度**按日/周/月惰性重置**、让每周免费额度**走账本发放**，并先把签发身份的密钥修好。

**Architecture:** 复用仓库里已经存在但**零调用者**的整数账本（`core/billing.py` 的 `reserve/commit/refund`）：建复盘任务时按 `UserGame.move_count × requested_visits` **预扣**，任务终态后由 **web 侧对账器**按 `ReportTask.analyzed_moves` **结算并退差**。之所以是对账而不是让 worker 直接结算，是因为 `katrain/cron/` 在 `Dockerfile.cron` 里是**独立复制的子树**、且今天只 import `katrain.cron.*`——跨目录 import 只会在容器里炸。额度桶是**计数器不是货币**（惰性周期键，无 cron 重置任务），账本仍是单池、只记真金白银。

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_secret_key_gate.py -v`
Expected: FAIL — `AttributeError: module 'katrain.web.core.config' has no attribute 'INSECURE_DEFAULT_SECRET_KEY'`

- [ ] **Step 3: 实现**

在 `katrain/web/core/config.py` 顶部加常量，并把 `:38` 与 `:115` 两处字面量都换成它：

```python
INSECURE_DEFAULT_SECRET_KEY = "katrain-secret-key-change-this-in-production"


def assert_secret_key_is_safe(mode: str, secret_key: str) -> None:
    """服务端模式下必须显式注入密钥。

    盒子（board）跑本地库、不对外签发身份，放行。
    这里故意不做「长度/熵」检查 —— 唯一要挡的是「忘了配」，
    多加判据只会在部署时制造假红。
    """
    if mode == "server" and secret_key == INSECURE_DEFAULT_SECRET_KEY:
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

在 `config.py` 的 `BILLING_PRICES` 旁边加一行注释指向它（**不要**在 `BILLING_PRICES` 里加 `report: N`——那正是按盘计价，与裁决 D6 相反）：

```python
    # 复盘不在这张表里：它按算力计价，见 katrain/web/core/analysis_cost.py。
    # 往这里加 "report": N 等于回到按盘计价（裁决 D6 明确否掉）。
    BILLING_PRICES: dict = {"territory": 10, "hints": 10, "variations": 10}
    FREE_WEEKLY_CREDITS: int = 150  # 约等于一份 300 手的标准复盘
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

## Task 4: 建复盘任务时预扣

**Files:**
- Modify: `katrain/web/core/models_db.py`（`ReportTask` 加 `charge_ref` 列）
- Modify: `katrain/web/core/migrations.py`（新列）
- Modify: `katrain/web/api/v1/endpoints/reports.py:186-230`
- Test: `tests/web_ui/test_report_charging.py`（新建）

**Interfaces:**
- Consumes: `analysis_cost.report_cost`、`billing.reserve`、`billing.InsufficientCredits`
- Produces: `ReportTask.charge_ref: str | None`（账本幂等键，形如 `report:{task_id}`）；`POST /api/v1/reports/` 在余额不足时返 **402** + `{"code": "insufficient_credits", "need": N, "have": M}`

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_report_charging.py
"""建复盘任务 → 按估算手数预扣 → 终态按实际手数结算。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db
from katrain.web.core import analysis_cost as ac


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _user(db, credits):
    u = models_db.User(username="u1", hashed_password="x", credits=credits)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _game(db, user_id, move_count):
    g = models_db.UserGame(user_id=user_id, source="import", move_count=move_count)
    db.add(g); db.commit(); db.refresh(g)
    return g


def test_report_task_carries_a_charge_ref():
    assert hasattr(models_db.ReportTask, "charge_ref")


def test_reserve_uses_estimated_move_count(db):
    u = _user(db, credits=1000)
    g = _game(db, u.id, move_count=250)
    need = ac.report_cost(g.move_count, 500)
    assert need == 125
    billing.reserve(db, u.id, need, "report", "report:1")
    assert billing.get_balance(db, u.id) == 875


def test_short_game_reserves_less_than_long_game(db):
    """裁决 D6 的直接断言。"""
    u = _user(db, credits=10_000)
    short = ac.report_cost(100, 500)
    long = ac.report_cost(300, 500)
    assert short * 3 == long


def test_insufficient_credits_raises(db):
    u = _user(db, credits=10)
    with pytest.raises(billing.InsufficientCredits):
        billing.reserve(db, u.id, 125, "report", "report:2")
    assert billing.get_balance(db, u.id) == 10, "失败不得扣款"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_charging.py -v`
Expected: `test_report_task_carries_a_charge_ref` FAIL

- [ ] **Step 3: 加列与迁移**

`models_db.py` 的 `ReportTask` 里，`retry_count` 之后加：

```python
    # 账本幂等键。None = 这份复盘没走计费（免费额度桶已覆盖，或历史数据）。
    charge_ref = Column(String(160), nullable=True, index=True)
```

`migrations.py` 里现有 `_add_missing_columns` 会自动带上（可空、无默认值 ⇒ 纯 ADD COLUMN，两库都成立）。**确认**它被列进了迁移遍历的表集合；若不是，按该文件既有写法补一条。

- [ ] **Step 4: 在建任务处预扣**

`reports.py` 的 `create_report_task`，在 `report_task = models_db.ReportTask(...)` **之前**插入：

```python
    from katrain.web.core import analysis_cost, billing

    visits = REPORT_VISITS[task.report_type]
    estimated = analysis_cost.report_cost(game.move_count or 0, visits)
```

在 `db.add(report_task)` / `db.commit()` **之后**（需要 `task_id` 做幂等键）：

```python
    charge_ref = f"report:{report_task.id}"
    try:
        billing.reserve(db, current_user.id, estimated, "report", charge_ref)
    except billing.InsufficientCredits:
        db.delete(report_task)
        db.commit()
        raise HTTPException(
            status_code=402,
            detail={
                "code": "insufficient_credits",
                "need": estimated,
                "have": billing.get_balance(db, current_user.id),
            },
        )
    report_task.charge_ref = charge_ref
    db.commit()
```

> 顺序说明：先落任务行拿到 id 再预扣。预扣失败就把任务行删掉——**不要**留一个 pending 任务再靠别处清理，那会让 worker 白跑一次算力。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_charging.py tests/web_ui/test_billing.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/core/migrations.py katrain/web/api/v1/endpoints/reports.py tests/web_ui/test_report_charging.py
git commit -m "feat(billing): 建复盘任务时按估算手数预扣，余额不足返 402"
```

---

## Task 5: 终态结算（web 侧对账，不碰 cron）

`katrain/cron/` 是 `Dockerfile.cron` 独立复制的自足子树，今天只 import `katrain.cron.*`。让 worker 直接调 `katrain.web.core.billing` 会**只在容器里** `ModuleNotFoundError`。所以结算做成 web 侧对账器：扫终态且仍持 `reserved` 的任务，按 `analyzed_moves` 结算。

**Files:**
- Create: `katrain/web/core/report_settlement.py`
- Modify: `katrain/web/server.py`（挂到既有的 `reconcile_stale_reservations` 旁边）
- Test: `tests/web_ui/test_report_charging.py`（追加）

**Interfaces:**
- Consumes: `ReportTask.charge_ref/status/analyzed_moves/requested_visits`、`billing.commit/refund/reserve`
- Produces: `settle_finished_reports(db: Session) -> int` —— 返回本次结算的任务数；幂等，可重复调用
- Produces（在 `billing.py` 上）: `reserved_amount(db, ref_id) -> int`、`has_transaction(db, ref_id) -> bool` —— 两个公开只读助手，供结算与免费额度判定使用，避免调用方伸手取 `_existing_tx`

- [ ] **Step 1: 写失败测试（追加到 test_report_charging.py）**

```python
def test_settlement_refunds_the_unused_estimate(db):
    """250 手预扣、实际只分析了 100 手 ⇒ 退回差额。"""
    from katrain.web.core.report_settlement import settle_finished_reports

    u = _user(db, credits=1000)
    g = _game(db, u.id, move_count=250)
    t = models_db.ReportTask(
        user_id=u.id, user_game_id=g.id, report_type="normal",
        requested_visits=500, status="pending", total_moves=250, analyzed_moves=0,
    )
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    db.commit()
    assert billing.get_balance(db, u.id) == 875

    t.status = "completed"
    t.analyzed_moves = 100          # 对手第 100 手认输
    db.commit()

    assert settle_finished_reports(db) == 1
    # 实际成本 100×500 = 50 credits ⇒ 退回 125-50 = 75
    assert billing.get_balance(db, u.id) == 950


def test_settlement_is_idempotent(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db, credits=1000)
    g = _game(db, u.id, move_count=100)
    t = models_db.ReportTask(
        user_id=u.id, user_game_id=g.id, report_type="normal",
        requested_visits=500, status="completed", total_moves=100, analyzed_moves=100,
    )
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 50, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    db.commit()

    settle_finished_reports(db)
    after_first = billing.get_balance(db, u.id)
    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == after_first


def test_failed_task_is_fully_refunded(db):
    from katrain.web.core.report_settlement import settle_finished_reports
    u = _user(db, credits=1000)
    g = _game(db, u.id, move_count=250)
    t = models_db.ReportTask(
        user_id=u.id, user_game_id=g.id, report_type="normal",
        requested_visits=500, status="failed", total_moves=250, analyzed_moves=0,
    )
    db.add(t); db.commit(); db.refresh(t)
    billing.reserve(db, u.id, 125, "report", f"report:{t.id}")
    t.charge_ref = f"report:{t.id}"
    db.commit()

    settle_finished_reports(db)
    assert billing.get_balance(db, u.id) == 1000, "跑失败了不能收钱"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_report_charging.py -v -k settlement or refund`
Expected: FAIL — `ModuleNotFoundError: katrain.web.core.report_settlement`

- [ ] **Step 3: 实现**

```python
# katrain/web/core/report_settlement.py
"""终态复盘任务的对账结算。

**为什么是对账而不是让 worker 结算**：跑复盘的是 `katrain/cron/jobs/report_analyze.py`，
而 `Dockerfile.cron` 只 `COPY katrain/cron/`、该子树今天只 import `katrain.cron.*`。
从那里 import `katrain.web.core.billing` 在本机能跑、**在容器里必炸**。
所以由 web 侧扫「终态 + 仍持 reserved」的任务来收口。

幂等：`billing.commit`/`refund` 本身对 ref_id 幂等，且结算后 charge_ref 置空，
重复调用不会二次扣退。
"""
import logging

from sqlalchemy.orm import Session

from katrain.web.core import analysis_cost, billing, models_db

logger = logging.getLogger("katrain_web")

TERMINAL_STATUSES = ("completed", "failed")


def settle_finished_reports(db: Session, limit: int = 200) -> int:
    """结算终态但仍持预扣的复盘任务。返回结算条数。"""
    rows = (
        db.query(models_db.ReportTask)
        .filter(
            models_db.ReportTask.status.in_(TERMINAL_STATUSES),
            models_db.ReportTask.charge_ref.isnot(None),
        )
        .limit(limit)
        .all()
    )
    settled = 0
    for task in rows:
        ref = task.charge_ref
        actual = analysis_cost.report_cost(task.analyzed_moves or 0, task.requested_visits or 0)
        try:
            if actual <= 0:
                # 一手都没分析成（跑挂了/排队中被取消）—— 全额退回。
                billing.refund(db, ref)
            else:
                # 先把预扣落定，再把「估多了」的部分作为一笔独立入账退回。
                # 不用「先退全额再重扣」：那样中途崩溃会留下用户白得一份的窗口。
                reserved = billing.reserved_amount(db, ref)
                billing.commit(db, ref)
                if reserved > actual:
                    billing.grant(
                        db, task.user_id, reserved - actual,
                        reason="report_overestimate_refund", ref_id=f"{ref}:refund",
                    )
            task.charge_ref = None
            db.commit()
            settled += 1
        except billing.BillingError:
            logger.exception("结算复盘任务 %s 失败，留待下一轮", task.id)
            db.rollback()
    return settled
```

`billing.py` 需要补一个只读小函数（结算要知道当初扣了多少）：

```python
def reserved_amount(db: Session, ref_id: str) -> int:
    """某笔预扣的金额（正数）。找不到抛 BillingError。"""
    tx = _existing_tx(db, ref_id)
    if tx is None:
        raise BillingError(f"no transaction for ref_id {ref_id}")
    return abs(int(tx.delta))


def has_transaction(db: Session, ref_id: str) -> bool:
    """该 ref_id 是否已经落过账。调用方据此判断「发过没有」，
    不必伸手用 _existing_tx。"""
    return _existing_tx(db, ref_id) is not None
```

`server.py` 里，在既有 `reconcile_stale_reservations` 调用旁边加上启动结算与周期结算（跟随该文件既有的调度写法）。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_report_charging.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 加一条守住 cron 边界的闸**

```python
# tests/web_ui/test_cron_boundary.py
"""katrain/cron 是 Dockerfile.cron 独立复制的子树，不得反向依赖 katrain.web。"""
import pathlib
import re

CRON = pathlib.Path(__file__).resolve().parents[2] / "katrain" / "cron"


def test_cron_never_imports_katrain_web():
    offenders = []
    for py in CRON.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # 去掉注释行再看，避免文档里提一句就误报
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        if re.search(r"^\s*(from|import)\s+katrain\.web", code, re.M):
            offenders.append(str(py))
    assert offenders == [], (
        f"Dockerfile.cron 只 COPY katrain/cron/，这些跨目录 import 只会在容器里炸：{offenders}"
    )
```

**变异验证**（必须做一次，证明这条闸真的会红）：临时在 `katrain/cron/jobs/report_analyze.py` 顶部加 `from katrain.web.core import billing`，跑这条测试确认 FAIL，然后撤掉。把这次变异记录写进测试的 docstring。

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/report_settlement.py katrain/web/core/billing.py katrain/web/server.py tests/web_ui/test_report_charging.py tests/web_ui/test_cron_boundary.py
git commit -m "feat(billing): 复盘终态按实际手数对账结算，并加 cron 子树边界闸"
```

---

## Task 6: `quota_buckets` 表与迁移

**Files:**
- Modify: `katrain/web/core/models_db.py`（新表 `QuotaBucket`）
- Modify: `katrain/web/core/migrations.py`（加进 `PROTECTED_TABLES`）
- Test: `tests/web_ui/test_quota.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces: `models_db.QuotaBucket`，字段 `id / user_id / kind / period_key / allowance / used / created_at`，`UNIQUE(user_id, kind, period_key)`

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


def test_quota_bucket_table_exists():
    assert hasattr(models_db, "QuotaBucket")


def test_bucket_is_unique_per_user_kind_period(db):
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    mk = lambda: models_db.QuotaBucket(
        user_id=u.id, kind="report_standard", period_key="W:2026-W36", allowance=8, used=0
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

`models_db.py` 加：

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

（确认 `UniqueConstraint` 已在该文件的 import 列表里；没有就加。）

`migrations.py` 把 `quota_buckets` 加进保护：

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

## Task 7: 惰性开桶与原子消费

**Files:**
- Create: `katrain/web/core/quota.py`
- Test: `tests/web_ui/test_quota.py`（追加）

**Interfaces:**
- Consumes: `models_db.QuotaBucket`
- Produces:
  - `period_key(kind_period: str, now: datetime | None = None) -> str`
  - `peek(db, user_id, kind, allowance, now=None) -> tuple[int, int]` —— `(used, allowance)`
  - `try_consume(db, user_id, kind, allowance, n=1, now=None) -> bool` —— 原子；额度不足返回 `False` 且不改任何行

- [ ] **Step 1: 写失败测试（追加）**

```python
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def test_period_keys_shape():
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert quota.period_key("day", t) == "D:2026-09-05"
    assert quota.period_key("week", t) == "W:2026-W36"
    assert quota.period_key("month", t) == "M:2026-09"


def test_period_key_uses_shanghai_not_utc():
    """UTC 的 2026-09-05 23:00 在上海已经是 09-06。按 UTC 算会让用户在晚上 8 点提前换桶。"""
    from katrain.web.core import quota
    t = datetime(2026, 9, 5, 23, 0, tzinfo=timezone.utc)
    assert quota.period_key("day", t) == "D:2026-09-06"


def test_consume_within_allowance(db):
    from katrain.web.core import quota
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 1


def test_consume_stops_at_allowance(db):
    from katrain.web.core import quota
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    for _ in range(3):
        assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is True
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3) is False
    assert quota.peek(db, u.id, "report_standard:week", allowance=3)[0] == 3, "失败不得计数"


def test_new_period_gets_a_fresh_bucket(db):
    from katrain.web.core import quota
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    t2 = datetime(2026, 9, 12, 10, 0, tzinfo=CST)   # 下一周
    for _ in range(3):
        quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1)
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t1) is False
    assert quota.try_consume(db, u.id, "report_standard:week", allowance=3, now=t2) is True


def test_allowance_snapshot_survives_plan_change(db):
    """开桶时的限额是快照 —— 中途降级套餐不该把已用额度变成超额。"""
    from katrain.web.core import quota
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    quota.try_consume(db, u.id, "report_standard:week", allowance=25)
    used, allowance = quota.peek(db, u.id, "report_standard:week", allowance=8)
    assert allowance == 25, "读的是桶上的快照，不是当前套餐"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 新增 6 条 FAIL

- [ ] **Step 3: 实现**

```python
# katrain/web/core/quota.py
"""额度桶：惰性周期键 + 原子消费。

**为什么没有重置任务**：周期到点会自然生成一个新的 period_key，
旧桶原地不动、新桶从 0 开始。任何"到点把 used 清零"的定时任务都是多余的，
而且一旦漏跑就会静默地让用户少领一轮。
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
    raise ValueError(f"未知周期 {kind_period!r}")


def _split(kind: str) -> Tuple[str, str]:
    """'report_standard:week' -> ('report_standard', 'week')"""
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
        # **不要做任何补偿**——billing.reserve 当年就是在这里多补了一次
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
        text(
            "UPDATE quota_buckets SET used = used + :n "
            "WHERE id = :bid AND used + :n <= allowance"
        ),
        {"n": n, "bid": row.id},
    )
    db.commit()
    return result.rowcount == 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_quota.py -v`
Expected: 9 passed

- [ ] **Step 5: 记一条只能在 PG 上证的事**

在 `test_quota.py` 末尾加：

```python
@pytest.mark.skip(reason="并发行锁只能在 PG 上证；SQLite 是库级锁，跑绿了也不说明问题")
def test_concurrent_consume_never_exceeds_allowance_on_postgres():
    """两个连接同时 try_consume 到最后一份，必须恰好一个成功。

    条件 UPDATE 的原子性依赖 PG 的行锁。SQLite 会把并发串行化，
    在这里跑绿属于「保证在本机不存在而不会红」，不构成证据。
    要证它：起两个真连接打同一行，或在 home-ubuntu 上对着 PG 跑。
    """
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/quota.py tests/web_ui/test_quota.py
git commit -m "feat(quota): 惰性周期键与原子消费 —— 无需任何重置任务"
```

---

## Task 8: 每周免费额度走账本

**Files:**
- Create: `katrain/web/core/free_grant.py`
- Modify: `katrain/web/api/v1/endpoints/reports.py`
- Test: `tests/web_ui/test_free_weekly.py`（新建）

**Interfaces:**
- Consumes: `quota.period_key`、`billing.grant`、`billing.has_transaction`(Task 5)、`config.FREE_WEEKLY_CREDITS`
- Produces: `ensure_free_weekly(db, user) -> int` —— 返回本次发放额（已发过返 0）

⚠️ **未决事项 U1 在这里落地**：`credit_transactions.ref_id` 是**全局**唯一。若用手机号做键而用户没有手机号，`weekly:None:2026-W36` 会让**第一个用户领到、其余全部 IntegrityError 静默不发**。本切片手机绑定尚未上线 ⇒ **本任务一律按 `user_id` 分桶**，并在代码里写死注释说明手机绑定上线后要迁移，且迁移必须处理"同一个人多个账号"的合并。

- [ ] **Step 1: 写失败测试**

```python
# tests/web_ui/test_free_weekly.py
"""每周免费额度：一人一周一次，幂等，走账本。"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import billing, models_db

CST = timezone(timedelta(hours=8))


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _user(db, name="u1"):
    u = models_db.User(username=name, hashed_password="x", credits=0)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_grants_once_per_week(db):
    from katrain.web.core.free_grant import ensure_free_weekly
    from katrain.web.core.config import settings
    u = _user(db)
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert ensure_free_weekly(db, u, now=t) == settings.FREE_WEEKLY_CREDITS
    assert ensure_free_weekly(db, u, now=t) == 0, "同一周不得重复发放"
    assert billing.get_balance(db, u.id) == settings.FREE_WEEKLY_CREDITS


def test_next_week_grants_again(db):
    from katrain.web.core.free_grant import ensure_free_weekly
    from katrain.web.core.config import settings
    u = _user(db)
    ensure_free_weekly(db, u, now=datetime(2026, 9, 5, 10, 0, tzinfo=CST))
    ensure_free_weekly(db, u, now=datetime(2026, 9, 12, 10, 0, tzinfo=CST))
    assert billing.get_balance(db, u.id) == 2 * settings.FREE_WEEKLY_CREDITS


def test_two_users_both_get_it(db):
    """回归：ref_id 是全局唯一的，键选错会让第二个人静默领不到。"""
    from katrain.web.core.free_grant import ensure_free_weekly
    from katrain.web.core.config import settings
    a, b = _user(db, "a"), _user(db, "b")
    t = datetime(2026, 9, 5, 10, 0, tzinfo=CST)
    assert ensure_free_weekly(db, a, now=t) == settings.FREE_WEEKLY_CREDITS
    assert ensure_free_weekly(db, b, now=t) == settings.FREE_WEEKLY_CREDITS
    assert billing.get_balance(db, b.id) == settings.FREE_WEEKLY_CREDITS


def test_grant_is_recorded_in_the_ledger(db):
    from katrain.web.core.free_grant import ensure_free_weekly
    u = _user(db)
    ensure_free_weekly(db, u, now=datetime(2026, 9, 5, 10, 0, tzinfo=CST))
    rows = db.query(models_db.CreditTransaction).filter_by(user_id=u.id).all()
    assert len(rows) == 1
    assert rows[0].reason == "free_weekly"
    assert rows[0].ref_id == f"free_weekly:{u.id}:W:2026-W36"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_free_weekly.py -v`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现**

```python
# katrain/web/core/free_grant.py
"""每周免费复盘额度（裁决 D2 / D3）。"""
from typing import Optional

from sqlalchemy.orm import Session

from katrain.web.core import billing, models_db, quota
from katrain.web.core.config import settings


def ensure_free_weekly(db: Session, user: models_db.User, now=None) -> int:
    """按周发放免费额度。已发过返回 0。

    **键为什么是 user_id 而不是手机号**：`credit_transactions.ref_id` 是
    **全局**唯一。手机绑定尚未上线，此刻按手机号分桶会让所有无手机号的用户
    共用 `free_weekly:None:...` 这一个键 —— 第一个人领到，其余全部
    IntegrityError 静默不发。手机绑定上线后再迁移，届时必须一并处理
    「同一个人的多个账号」的合并（见 requirements.md U1）。
    """
    amount = int(settings.FREE_WEEKLY_CREDITS)
    if amount <= 0:
        return 0
    ref = f"free_weekly:{user.id}:{quota.period_key('week', now)}"
    if billing.has_transaction(db, ref):
        return 0
    billing.grant(db, user.id, amount, reason="free_weekly", ref_id=ref)
    return amount
```

在 `reports.py` 的 `create_report_task` 里，**预扣之前**调用一次 `ensure_free_weekly(db, current_user)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_free_weekly.py tests/web_ui/test_report_charging.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add katrain/web/core/free_grant.py katrain/web/api/v1/endpoints/reports.py tests/web_ui/test_free_weekly.py
git commit -m "feat(billing): 每周免费复盘额度走账本发放，键按 user_id"
```

---

## Task 9: 拆掉两处 `10000` 列默认值

新账号今天靠列默认值白拿 10000 且不过账本 ⇒ 账本与余额从第一天就对不上，免费额度也失去意义。**两处**都要改（漏一处等于没改）。

**Files:**
- Modify: `katrain/web/core/models_db.py:78`
- Modify: `katrain/web/models.py:183`
- Modify: `katrain/web/core/config.py`（`BILLING_FREE_GRANT`）
- Modify: `katrain/web/api/v1/endpoints/auth.py`（注册后发放）
- Test: `tests/web_ui/test_signup_grant.py`（新建）

**Interfaces:**
- Consumes: `billing.grant`
- Produces: 新账号余额 = `settings.BILLING_SIGNUP_GRANT`（默认 **0**），且该数额有一条 `reason="signup"` 的账本行

- [ ] **Step 1: 先记基线，再写失败测试**

```bash
uv run pytest tests/ -q 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/baseline.txt; wc -l /tmp/baseline.txt
```

```python
# tests/web_ui/test_signup_grant.py
"""新账号的赠额必须走账本，不能靠列默认值。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.config import settings


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_orm_default_is_zero(db):
    u = models_db.User(username="u1", hashed_password="x")
    db.add(u); db.commit(); db.refresh(u)
    assert u.credits == 0, "列默认值不得白送额度"


def test_pydantic_default_is_zero():
    from katrain.web.models import User as UserSchema
    # 第二处 10000 —— 漏改这里，API 会对着一个 0 余额的账号报 10000
    assert UserSchema.model_fields["credits"].default == 0


def test_signup_grant_default_is_zero():
    assert settings.BILLING_SIGNUP_GRANT == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_signup_grant.py -v`
Expected: 三条全 FAIL（分别报 10000 / 10000 / AttributeError）

- [ ] **Step 3: 实现**

- `models_db.py:78` → `credits = Column(Integer, default=0, nullable=False)`
- `models.py:183` → `credits: int = 0`
- `config.py`：删掉死常量 `BILLING_FREE_GRANT`，换成 `BILLING_SIGNUP_GRANT: int = 0`
- `endpoints/auth.py` 的 `register`，建号成功后：

```python
    if settings.BILLING_SIGNUP_GRANT > 0:
        billing.grant(db, user_dict["id"], settings.BILLING_SIGNUP_GRANT,
                      reason="signup", ref_id=f"signup:{user_dict['id']}")
```

- [ ] **Step 4: 修既有测试的过期断言**

`tests/web_ui/test_user_data_api.py:72`、`test_board_auth.py:203`、`test_billing_api.py:53` 断言新用户 `credits == 10000`。这三条断言的是**旧行为**，随本任务一起改成 0。**不要**为了让它们绿而保留 10000。

- [ ] **Step 5: 跑全量并与基线比名字集合**

```bash
uv run pytest tests/ -q 2>&1 | grep -E "^(FAILED|ERROR)" | sort > /tmp/after.txt
comm -13 /tmp/baseline.txt /tmp/after.txt   # 必须为空：没有**新增**失败
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/models_db.py katrain/web/models.py katrain/web/core/config.py katrain/web/api/v1/endpoints/auth.py tests/
git commit -m "fix(billing): 新账号赠额改走账本，拆掉 ORM 与 pydantic 两处 10000 默认值"
```

---

## Task 10: 额度看板端点与诚实状态

**Files:**
- Modify: `katrain/web/api/v1/endpoints/billing.py`
- Test: `tests/web_ui/test_billing_api.py`（追加）

**Interfaces:**
- Consumes: `billing.get_balance`、`quota.peek`、`analysis_cost.report_cost`
- Produces: `GET /api/v1/billing/quota` → `{"credits": int, "estimates": {"normal_250_moves": int, "deep_250_moves": int}, "free_weekly": {"granted_this_week": bool, "amount": int}}`

- [ ] **Step 1: 写失败测试（追加到 test_billing_api.py）**

```python
@pytest.mark.anyio
async def test_quota_endpoint_reports_credits_and_estimates(app):
    client, token = app
    r = await client.get("/api/v1/billing/quota", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["credits"], int)
    # 估算必须标明是估算，且深度是标准的 4 倍（2000 vs 500 visits）
    assert body["estimates"]["deep_250_moves"] == 4 * body["estimates"]["normal_250_moves"]


@pytest.mark.anyio
async def test_quota_endpoint_requires_auth(app):
    client, _ = app
    r = await client.get("/api/v1/billing/quota")
    assert r.status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/web_ui/test_billing_api.py -v -k quota`
Expected: 404

- [ ] **Step 3: 实现**

```python
@router.get("/quota")
async def get_quota(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """余额 + 「这些钱大概够几份复盘」。

    估算就叫估算：真实成本按**实际分析到的手数**结算，认输的短棋会更便宜。
    前端不得把这里的数字显示成「你还能复盘 N 局」这种确定口径。
    """
    if _is_board():
        _need_online()
    from katrain.web.core import analysis_cost
    from katrain.web.core.config import settings

    return {
        "credits": billing.get_balance(db, current_user.id),
        "estimates": {
            "normal_250_moves": analysis_cost.report_cost(250, 500),
            "deep_250_moves": analysis_cost.report_cost(250, 2000),
        },
        "free_weekly": {"amount": int(settings.FREE_WEEKLY_CREDITS)},
        "billing_online": True,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/web_ui/test_billing_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add katrain/web/api/v1/endpoints/billing.py tests/web_ui/test_billing_api.py
git commit -m "feat(billing): 额度看板端点 —— 估算标注为估算"
```

---

## 本切片之后（不在本计划范围，各自需要单独的计划）

| 阶段 | 阻塞在什么上 |
|---|---|
| **手机绑定与验证码登录**（P3） | 短信签名/模板报备 **5–10 工作日**且尚未启动；需要企业实名认证；未决事项 U1（存量用户）、U2（Box SSO 用户无手机号）、U3（国际号通道与单价）。设计与评审产出已在 `requirements.md §2.1 P3` 摘要。 |
| **关掉密码注册的刷号路**（P4a） | 依赖 P3 落地（否则没有替代注册路径）。P4b（赠额归零）已在 Task 9 完成。 |
| **合规页脚 + 落地页**（P5） | 等 Fan 提供两个真实备案号；落地页本身是新页面，需要设计稿定稿。 |
| **会员套餐与支付接入** | 支付宝/微信商户开通；无自动续费资质 ⇒ 一次性购买 + 到期提醒。 |
