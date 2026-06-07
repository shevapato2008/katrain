# 对弈付费分析 + 积分充值 · 实现计划(plan v2)

> Track: `sbc-pure-play-remote-analysis` · 分支 `feature/rk3588-ui`
> 需求见同目录 `requirements.md`。本文件是**可执行实现计划(HOW)**,按阶段可独立交付与验证。
> 执行约定:每阶段先写测试(TDD),再实现,跑通自动化 + 人工验证后进入下一阶段;每阶段末有 review checkpoint。
> **v2 变更**:吸收 Codex / Gemini 对抗式评审(见 `review-feedback-codex.md`、`review-feedback-gemini.md`),
> 修正了 R1 代码定位、补强了「云端权威 / 排位服务端封口 / 扣费幂等与崩溃退款 / 管理员权限 / 整数账本」等资产安全要点。

## 评审取舍(v1 → v2)

| 评审发现 | 严重度 | 处置 | 落点 |
|---|---|---|---|
| `ref_id` 带前端 nonce → 连点多扣 | Blocker(双方) | **改**:服务端派生幂等键,已购返回旧结果/409,显式 `force_recompute` | 阶段 4 |
| 先扣分→分析→失败退款,崩溃吞积分 | Blocker(双方) | **改**:`reserved→committed/refunded` 持久态 + 启动 reconcile + try/finally | 阶段 2/4 |
| board 积分可能落本地 SQLite,非云端权威 | Blocker(Codex,已验证) | **改**:board 模式 billing 全部代理 `REMOTE_API_URL`,离线 `need_online`,本地不扣 | 阶段 2 |
| 排位禁分析的服务端门控不完整(旧接口可绕) | Blocker(Codex,已验证) | **改**:`WebSession.game_type` 统一 + `assert_analysis_allowed` 守所有分析接口 | 阶段 4 |
| Admin 角色不存在 | High(双方) | **改**:`User.is_admin` 列 + `get_current_admin_user` 依赖 | 阶段 2 |
| 兑换码可爆破/并发双发 | High(双方) | **改**:128bit 高熵码 + 单条条件 UPDATE + 频控 | 阶段 2 |
| Float 表示积分/人民币 | High(Codex) | **改**:整数账本(积分 INTEGER,人民币 `*_fen` INTEGER) | 阶段 2 |
| 无 Alembic 直接上账本 | High(Codex) | **改**:轻量迁移(inspector 补列/索引,billing 表禁 drop-all) | 阶段 2 |
| R1 代码定位错误(`_do_new_game` 不调 `analyze_all_nodes`;465 在 `_do_edit_game`) | High(Codex,已验证) | **改**:统一 `should_suppress_auto_eval()` helper,覆盖初始/编辑/载入/配置重启 | 阶段 1 |
| 阶段 3 先把 analyze_extra 路由远程会开免费入口 | High(Codex) | **改**:阶段 3 只接复盘/研究;play 实时分析只走阶段 4 付费 + 守卫 | 阶段 3/4 |
| 付费分析 KataGo priority 未定 | Medium(Gemini) | **改**:显式高优先级(紧贴 genmove) | 阶段 4 |
| 一次性结果字段未定义,会和 `cn.analysis` 缓存冲突 | Medium(Codex) | **改**:`paid_analysis` 状态模型 + entitlement | 阶段 4/5 |
| API 路径不一致(`/billing` vs `/api/v1/billing`) | Medium(Codex) | **改**:billing 统一 `/api/v1/billing/*` | 阶段 2 |
| `engine/remote_url` 落点不明,Settings 不读 | Medium(Codex) | **改**:明确配置来源与映射 | 阶段 3 |
| ManualConfirm 订单缺所有权/审计/包价约束 | Medium(Codex) | **改**:套餐服务端定 + proof 鉴权 + confirmed_by/at/note | 阶段 6 |
| webhook 需预留 raw body / 验签 / 防重放 | Medium(双方) | **改**:base 接口签名定为 `verify_callback(raw_body, headers)` | 阶段 6 |
| board 离线不能只看 `analysis_engine.available` | Medium(Codex) | **改**:billing 与 engine 分别探测,错误码细分 | 阶段 4/5 |
| ScoreGraph 显隐靠模式状态精准控制 | Medium(Gemini) | **改**:显式 `is_review_mode`/state 互斥 | 阶段 5 |
| WeChat/Alipay 空壳类 + webhook 路由可后移 | Low(Codex) | **砍**:本期只留接口契约,不实现类/路由 | 阶段 6 |
| `RechargeOrder.expired` 自动过期 cron 过度设计 | Low(双方) | **砍**:本期只 `pending/proof_submitted/paid/cancelled`,无定时过期 | 阶段 2/6 |
| 管理员订单核对前台页 | Low(Codex) | **降级**:本期最简受保护 API + CLI,前台页 → Phase 6b | 阶段 6 |

---

## 0. 总体架构

```
┌──────────────── 前端(kiosk + galaxy 共享 billing 逻辑)────────────────┐
│ CreditContext / useCredits ── 余额、单价、billingOnline、刷新           │
│ 控件徽标(⌊余额/单价⌋) → 点击 → 够则 POST 付费分析 / 不够弹 RechargeDialog │
│ RechargePage(套餐 / 兑换码 / 个人码+凭证)                              │
└───────────────────────────────────────────────────────────────────────┘
                │ REST (/api/v1/billing/*, /api/analysis/paid)
┌───────────────▼───────────── 后端(FastAPI)──────────────────────────┐
│ billing.py 服务:get_balance / reserve / commit / refund / grant / settle│
│   ├─ server 模式:直接读写云端 DB(账本权威)                            │
│   └─ board   模式:全部代理 REMOTE_API_URL;离线 need_online,本地不扣   │
│ 分析门控:assert_analysis_allowed(session) 守所有分析接口(反作弊封口)  │
│ 付费分析 handler:门控 → reserve → 跑一次(高优先级)→ commit/超时 refund │
│ 引擎编排:play_engine(本地 genmove)| analysis_engine(remote_url)     │
│ R1:should_suppress_auto_eval() 时 MODE_PLAY 抑制自动 eval               │
│ 启动 reconcile:扫描超时 reserved → 自动 refund / 标记人工               │
└───────────────────────────────────────────────────────────────────────┘
```

**已验证的既有事实**(代码核对):
- 积分=stub:`models_db.py:39 credits = Column(Float, default=10000.00)`,零业务逻辑;`User` 无 `is_admin/role`。
- 无 alembic;`Base.metadata.create_all`(`auth.py`)自动建新表,但**不能**补列 / 改类型 / 补唯一索引。
- `KATRAIN_MODE ∈ {server, board}`(`config.py:33`);**`REMOTE_API_URL` 已存在**(`config.py:34`,board 模式远程地址)——复用为 billing 代理目标。
- `WebSession`(`session.py:14`)**无** `rated/game_type` 字段——需新增。
- rated 目前仅前端 URL param(`galaxy/pages/GamePage.tsx:27`),后端不知情。
- R1 真实入口(已核对):
  - 初始分析在 `Game.__init__`(`core/game.py:463-465`)`skip_initial_analysis=False` 时起后台线程跑 `analyze_all_nodes`。
  - 走子分析在 `core/game.py:553-560 play()`(`played_node.analyze(...)`,含教学 557/558 与普通 560)。
  - `_do_new_game`(`interface.py:382`)**本身已带 `skip_initial_analysis` 参**,**不直接**调 `analyze_all_nodes`。
  - `analyze_all_nodes` 的直接调用点:`_do_edit_game`(`interface.py:465`)、配置重启(`interface.py:1030`)。
  - ponder 在 `_do_update_state`(`interface.py:549`);教学 undo 在 `interface.py:526`;`_do_load_sgf`(`interface.py:654`)透传 `skip_initial_analysis`。
- HTTP 引擎客户端 `KataGoHttpEngine`(`engine.py:539-787`)完整(ownership/policy、`overrideSettings.humanSLProfile`、`/health`)。

---

## 阶段 1 · R1 抑制 kiosk 自动 eval(性能修复,独立可交付)

**目标**:`KATRAIN_MODE=="board"` 且 `MODE_PLAY` 时,本地引擎每步只收 genmove,无 priority-1002 自动 eval。
**注意**:不能漏掉初始 / 编辑 / 载入 / 配置重启等隐藏入口(v1 此处定位有误,已修正)。

### 实现
1. `interface.py` `WebKaTrain.__init__`:加 `self.suppress_auto_eval = (settings.KATRAIN_MODE == "board")`(读 `web.core.config.settings`)。
2. **统一 helper** `should_suppress_auto_eval(self) -> bool`:返回 `self.suppress_auto_eval and self.play_analyze_mode == MODE_PLAY`(复盘 / 研究模式恒为 False,不误伤合法分析)。
3. 走子分析:`WebBaseGame.play`(`interface.py:85`)→ `super().play(..., analyze=analyze and not should_suppress_auto_eval())`;`core/game.py:553-560` 的 `play(analyze=...)` 已透传,无需改 core。显式付费分析走阶段 4 独立路径,不受此影响。
4. 初始分析:创建 `WebGame` 时传 `skip_initial_analysis = skip_initial_analysis or should_suppress_auto_eval()`(覆盖 `_do_new_game:416`、`_do_load_sgf:658`)。
5. ponder:`_do_update_state`(`interface.py:549`)在 suppress 时跳过 `analyze_extra("ponder")` 并 `stop_pondering()`,`self.pondering=False`。
6. 教学 undo:`_do_update_state`(`interface.py:526`)`analyze_undo` 在 suppress 时跳过(纯下棋 kiosk 不开教学)。
7. 编辑局 / 配置重启:`_do_edit_game`(`interface.py:465`)与配置重启(`interface.py:1030`)的 `analyze_all_nodes` 在 suppress 时跳过(或仅 play 模式跳过,research 保留)。

### 测试(先写)`tests/web_ui/test_suppress_auto_eval.py`
- mock 引擎记录所有 `request_analysis`。`KATRAIN_MODE=board` 下分别覆盖:**新局、走一步、悔棋、编辑局、载入 SGF、配置重启**,断言只有 `PRIORITY_EXTRA_AI_QUERY`(genmove)查询,无 `PRIORITY_DEFAULT`/`PRIORITY_GAME_ANALYSIS` eval。
- `KATRAIN_MODE=server`(galaxy)下断言自动 eval **仍发出**(回归保护)。
- research / 复盘模式下断言分析**不被误抑制**(即使 board)。

### 人工验证(板上)
```
journalctl -u smartbox-katrain -f | grep "Sending KataGo HTTP analysis query"
# 对弈走子/新局/悔棋:只应出现含 humanSLProfile 的 genmove;无 priority-1002 + includeOwnership 的 eval
```
AI 落子 wall-clock 应降到 ≤ ~2s(验收 §1、§2)。

### Checkpoint:阶段 1 可单独提交并部署到板子,先解决最痛的卡顿。

---

## 阶段 2 · 积分账本 + 服务 + 基础 API(后端基石,云端权威)

**目标**:服务端权威的单池**整数**积分:reserve/commit/refund + 原子幂等扣分、加分、查余额、兑换码、管理员加分;**board 模式全部代理云端**。

### 2.1 数据模型 `katrain/web/core/models_db.py`(整数账本)
- `User` 增列:`is_admin = Column(Boolean, default=False, nullable=False)`;新账本统一用整数(见迁移)。
- `CreditTransaction`:`id, user_id(FK, index), delta(Integer 有符号), reason(String), ref_id(String **unique**), status(String: committed/reserved/refunded), balance_after(Integer), created_at, updated_at`。`ref_id` 是幂等键。
- `RechargeOrder`:`id, user_id(FK), package_id(String), amount_fen(Integer), credits(Integer), provider(String), status(String: pending/proof_submitted/paid/cancelled), out_trade_no(String unique), proof_url(Text null), proof_hash(String null), confirmed_by(int null), confirmed_at(null), confirm_note(Text null), created_at, settled_at(null)`。**无 expired/自动过期**(本期砍)。
- `RedeemCode`:`code(String unique, 高熵 ≥128bit), credits(Integer), used_by(int null), used_at(null), expires_at(null), created_at`。
- `RedeemAttempt`(频控审计,或用内存/Redis 计数):`user_id/ip, ts, success`。

### 2.2 轻量迁移 `katrain/web/core/migrations.py`(新建,在 `init_db` 后调用)
- 用 SQLAlchemy `inspect()` 检查并**只做可审计 ALTER**:补 `users.is_admin` 列(默认 False)、补账本表唯一索引(`credit_transactions.ref_id`、`recharge_orders.out_trade_no`、`redeem_codes.code`)与 `user_id` 索引。
- **绝不对含 billing 表的 DB 执行 drop-all**(现有 SQLite schema-drift drop 逻辑要排除 billing 表)。
- `User.credits` Float→Integer:提供一次性回填(`round(credits)`),或保留 Float 显示列 + 新增整数余额列由服务层权威(二选一,优先整数权威 + 回填)。
- 测试:在「已有旧 schema」的 SQLite / Postgres fixture 上启动,断言列 / 索引 / 默认值正确,且旧数据不被 drop。

### 2.3 服务 `katrain/web/core/billing.py`(server 模式:直接读写云端 DB)
- `get_balance(db, user_id) -> int`。
- `reserve(db, user_id, amount, reason, ref_id) -> ReservationResult`:
  - 幂等:`ref_id` 已存在 → 按其 status 返回(reserved/committed 直接复用,refunded 视策略)。
  - 原子:`UPDATE users SET credits = credits - :amt WHERE id=:uid AND credits >= :amt`;rowcount==0 → raise `InsufficientCredits`。同事务写 `status='reserved'` 的 ledger 行(扣减立即生效,资金已冻结)。
- `commit(db, ref_id) -> int`:`reserved → committed`(幂等;已 committed 直接返回)。
- `refund(db, ref_id) -> int`:`reserved → refunded` 并原子加回余额(幂等;reason=`refund:{原reason}`)。
- `grant(db, user_id, amount, reason, ref_id) -> int`:原子加 + 写 committed ledger(ref_id 幂等)。
- `redeem(db, user_id, code) -> int`:**单条条件 UPDATE** `UPDATE redeem_codes SET used_by=:uid, used_at=now WHERE code=:code AND used_by IS NULL AND (expires_at IS NULL OR expires_at>now)`;检查 rowcount==1 后同事务 `grant(ref_id=f"redeem:{code}")`。错误响应**不区分**无效/已用/过期。
- `settle_order(db, out_trade_no) -> None`:幂等,pending/proof_submitted → paid + `grant(ref_id=f"order:{out_trade_no}")`。
- `reconcile_stale_reservations(db, ttl)`:启动时(`server.py` lifespan)扫描超时 `reserved` → `refund`(或标记人工)。
- 异常:`InsufficientCredits`, `InvalidRedeemCode`, `NeedOnline`。

### 2.4 board 模式代理 `katrain/web/core/billing_proxy.py`(云端权威关键)
- board 模式下,`billing.py` 的 `get_balance/reserve/commit/refund/redeem/recharge/orders` **全部转发 `REMOTE_API_URL`**(带用户 token),**不读写本地 SQLite 余额**。
- 离线(远程不可达 / token 失效)→ raise `NeedOnline`,付费分析禁用;本地只允许**短期只读余额缓存**用于显示,不参与扣减。
- 依赖注入:`get_billing_service()` 按 `settings.KATRAIN_MODE` 返回本地实现或代理实现。

### 2.5 配置 `katrain/web/core/config.py`
- `BILLING_PRICES = {"territory": N, "hints": N, "variations": N}`(整数,可被 config.json `billing/prices` 覆盖)。
- `BILLING_FREE_GRANT`(初始赠送整数,沿用默认 10000)。
- `BILLING_RESERVATION_TTL_SEC`(reserved 超时退款阈值)。
- `REDEEM_RATE_LIMIT`(每用户/IP 每分钟错误尝试上限)。

### 2.6 权限 `katrain/web/core/auth.py`
- 新增 `get_current_admin_user` 依赖:校验 `User.is_admin`(非 `username=="admin"`)。
- 首次初始化把默认 admin 标记 `is_admin=True`,但**强制改密 / 禁用弱口令**;board shadow-user **不得**获得本地 admin。

### 2.7 API `katrain/web/api/v1/endpoints/billing.py`(统一 `/api/v1/billing/*`)
- `GET /api/v1/billing/balance` → `{credits, billing_online}`。
- `GET /api/v1/billing/prices` → `{territory, hints, variations, packages[]}`。
- `POST /api/v1/billing/redeem {code}` → `{credits}`(频控)。
- 管理员(`get_current_admin_user`):`POST /api/v1/billing/admin/grant {username, amount}`、`POST /api/v1/billing/admin/codes {count, credits}`。

### 测试(先写)`tests/web_ui/test_billing.py`
- reserve 正常冻结 + ledger(status=reserved);余额不足 raise;commit/refund 幂等;refund 后余额精确复原。
- **整数精确性**:0、刚好够、连续扣减后余额精确(无浮点误差)。
- **并发**:两 session 同 ref_id / 余额恰好够一次 → 只成功一次(两个独立 DB session)。
- redeem:有效、已用、过期、并发同码只一次成功、错误响应不可区分、超频 429。
- grant / admin grant;非 admin / shadow-user 调 admin 接口 403,admin 成功。
- **board 代理**:board 模式改本地 `users.credits` 不影响余额;`REMOTE_API_URL` 断开 → `spend`/`reserve` 不落本地账,返回 `need_online`。
- reconcile:制造超时 reserved,启动后被 refund。

### Checkpoint:积分后端(含云端权威 / 整数账本 / reserve-commit-refund / 迁移)可独立测,无 UI 依赖。

---

## 阶段 3 · 远程引擎编排(R6,不计费,只接复盘/研究)

**目标**:可配置第二引擎;**仅复盘/研究**走 `remote_url`;play 模式实时分析**不在本阶段开放**(留给阶段 4 付费 + 守卫)。galaxy 复用自身;未配置回退本地。

### 实现
1. **配置落点明确**:`engine/remote_url`(+ `remote_analyze_path/remote_health_path/remote_has_human_model`)由 `WebKaTrain.config("engine/remote_url")` 读取(`~/.katrain/config.json` 的 `engine` 段),构造 `remote_cfg = {**engine_cfg, "backend": "http", "http_url": remote_url, ...}`;或新增 env `KATRAIN_ANALYSIS_KATAGO_URL` 进 `Settings`。明确二选一,避免「以为配了实际没读到」。
2. `interface.py` 引擎初始化:`self.engine`=现有(本地 genmove / galaxy 自身);配 `remote_url` → `self.analysis_engine = KataGoHttpEngine(self, remote_cfg)`,否则 `= self.engine`。helper `analysis_engine()`。
3. **只改复盘 / 研究路径**用 `analysis_engine()`:`_do_analyze_extra("game")`(报告)、研究模式分析。**play 模式的 `/api/analysis/extra` 不在此改造为远程免费**(否则开后门)。
4. 健康探测:`/health` 失败 → `analysis_engine` 标记不可用(供阶段 4 离线判断);**不静默 fallback 到本地做付费分析**。
5. 编排可复用 `web/core/router.py` 骨架或直接在 interface(优先简单)。

### 测试(先写)`tests/web_ui/test_engine_routing.py`
- 配 `remote_url` → 复盘/研究分析发往 remote client;genmove 仍走本地(mock 双 client)。
- 不配 → 回退 `self.engine`。
- galaxy(server,无 remote_url)→ 分析=自身引擎,回归不变。
- play 模式 `/api/analysis/extra` **不**被本阶段路由到远程免费分析(防后门回归)。

### 人工验证
- 临时把 `remote_url` 指本地 :8000,触发一次复盘,日志确认查询发往该 URL。

### Checkpoint:引擎编排可测,b28 未部署不阻塞(本地/mock URL)。

---

## 阶段 4 · rated 服务端封口 + 付费分析后端(R3 核心,资产安全重点)

**目标**:统一 game_type 服务端门控(封死所有分析接口);付费分析 reserve→跑一次→commit/refund,服务端幂等键,持久 pending。

### 4.1 rated / 分析门控(服务端统一封口)
1. `WebSession`(`session.py`)增 `game_type: str`(`free|ranked|rated|research`)或等价 `analysis_allowed: bool`。
2. 所有会话创建入口写入:`create_session`、`new-game`(`_do_new_game` 增参 `rated/game_type`)、kiosk `/api/game/setup`(`mode='ranked'`)、matchmaker(`game_type='rated'`)。
3. `WebKaTrain.get_state()` 暴露 `game_type`/`analysis_allowed`。
4. **新增 `assert_analysis_allowed(session)`**,统一守卫所有分析接口(不止新付费接口):
   - `/api/ui/toggle`(`show_hints/show_ownership/show_policy/show_dots`)
   - `/api/analysis/extra`、`/api/analysis/continuous`、`/api/analysis/show-pv`
   - 新 `/api/analysis/paid`
   - rated/ranked 会话 → 全部 403,不触发引擎、不扣费(前端置灰为双保险)。

### 4.2 付费分析 handler `interface.py` + 路由
- 新 `_do_paid_analysis(kind)`,`kind ∈ {territory, hints, variations}`:
  1. 守卫:`assert_analysis_allowed`(rated 拒);board 离线判断**分两条**——`billing_online`(云端余额可读)与 `analysis_engine` 可用,任一不满足返回对应错误码。
  2. **服务端派生幂等键**:`ref_id = f"analysis:{session_id}:{node_id}:{kind}"`(**无前端 nonce**)。已成功(committed)→ 直接返回既有结果 / 409 `already_purchased`,不再扣费。需重算:显式 `force_recompute=true` → 服务端生成 `:{attempt}` 后缀并要求 UI 二次确认。
  3. `reserve(prices[kind], reason=f"analysis_{kind}", ref_id)` → `InsufficientCredits` 时返回 `insufficient`(前端弹窗)。
  4. `try`: 用 `analysis_engine()` 对当前节点跑**一次**(territory→`ownership=True`;hints→top moves;variations→PV 单发),**显式高优先级**(紧贴 `PRIORITY_EXTRA_AI_QUERY`,保证付费即时体验,但不高于 genmove 抢落子);成功 → `commit(ref_id)` + 把结果写 `paid_analysis` 一次性字段 + 返回新余额。
  5. `except / timeout / finally`: `refund(ref_id)`(reason=`refund_{kind}`)。崩溃由阶段 2 启动 reconcile 兜底。
- 结果状态模型(与 `cn.analysis` 缓存解耦):`get_state().paid_analysis = {node_id, kind, payload, entitlement}`;entitlement 按 `session_id+node_id+kind` 记录。已购节点再次打开**免费查看**已有结果,不自动重算;离开节点隐藏但保留 entitlement。
- REST:`POST /api/analysis/paid {kind, force_recompute?}`(session token;`server.py` → `katrain("paid_analysis", ...)`)。billing 调用经 `get_billing_service()`(board 走代理)。

### 测试(先写)`tests/web_ui/test_paid_analysis.py` + `test_rated_gating.py`
- 余额够:扣对应单价(reserve→commit)、跑一次、返回结果+新余额。
- 余额不足:不扣、返回 `insufficient`。
- **rated 反作弊**:rated/ranked 会话直接 POST `/api/analysis/paid`、`/api/analysis/extra`、`/api/analysis/continuous`、`/api/analysis/show-pv`、`/api/ui/toggle` 全部 403,不触发引擎、不扣费。
- 分析失败 / 超时:**refund**,余额复原。
- **幂等 / 防连点**:同节点同 kind 连点 → 只扣一次,第二次返回既有结果 / 409。
- **崩溃**:reserve 后引擎抛异常 / 进程重启 → reconcile 退款,无吞分。
- board:`billing` 不可达 → `need_online_billing`;引擎不可达 → `analysis_engine_unavailable`;均不扣。
- 优先级:断言付费分析查询 priority 高于普通 eval、不高于 genmove。

### Checkpoint:后端付费分析闭环 + 服务端反作弊封口可测。

---

## 阶段 5 · 前端:徽标 / 按次消费 / 充值弹窗 / 移除图表(R3 + R4,两端)

**目标**:kiosk + galaxy 对弈页改造,共享 billing 逻辑(遵守 kiosk-2d 构建边界)。

### 共享 territory(`src/context` / `src/hooks` / `src/components`)
1. `CreditContext` + `useCredits`:拉 `/api/v1/billing/balance`(含 `billing_online`)与 `/prices`,提供 `balance/prices/billingOnline/balanceStatus/refresh`;付费成功用返回新余额即时更新;board 模式 `billing_online=false` 或刷新失败 → 禁用付费按钮并提示登录/联网。
2. `<AnalysisToolButton>`:通用按钮 + 右上角徽标 `⌊balance/price⌋`;`disabled` when rated / billing offline;点击:rated→无操作;`balance<price`→开 `RechargeDialog`;否则 `POST /api/analysis/paid` 一次性展示结果(错误码 `insufficient/need_online_billing/analysis_engine_unavailable/already_purchased` 分别提示)。
3. `<RechargeDialog>`:仿 19x19——「[道具]已用尽,当前余额 X,充值/兑换」;按钮:套餐购买、兑换码、取消;跳 `RechargePage`。单池无二级道具,「余额兑换」简化为「去充值」。
4. i18n:`src/i18n.ts` 加中英文案。

### kiosk(`src/kiosk/components/game/GameControlPanel.tsx` + `pages/GamePage.tsx`)
- 领地/建议/变化图 改用 `<AnalysisToolButton>`;移除「图表」(score)控件;数子/悔棋/停一手/认输 保持免费。
- rated 模式(kiosk 后续启用)透传 `isRated` 全禁。

### galaxy(`src/galaxy/components/game/RightSidebarPanel.tsx` + `pages/GamePage.tsx`)
- Territory/Advice/变化图 改用 `<AnalysisToolButton>`(替换现 `canShowAnalysis` 免费逻辑);保留 `isRated` 全禁(已有 line 331/340)。
- **移除对弈页 `ScoreGraph`**:用显式状态(`is_review_mode` / `game_state.is_over` + 模式)精准控制——对弈页不渲染、复盘报告渲染,避免靠模糊显隐引 bug。

### Board(`src/components/Board.tsx`,共享)
- ownership/hints/variations 改为渲染 `paid_analysis` 一次性结果(按 `node_id+kind`),不依赖持续 `show_*` 自动刷新;切节点 / 刷新后行为遵循 entitlement(已购免费回看,未购不显示)。

### 测试 Playwright(`katrain/web/ui/tests/`)
- 自由对弈:徽标显示次数;点击扣 1、出结果;再次点同节点不再扣;余额 0 弹 RechargeDialog;排位局控件置灰。
- 对弈页无图表;复盘报告有图表。
- board 模拟 billing 离线 → 付费按钮禁用提示。
- 两端各一条 happy path。

### 构建闸(必过)
```
cd katrain/web/ui && npm run build && npm run build:kiosk-2d   # 含 verify:kiosk-2d
```
确认 kiosk-2d 不引入 three/galaxy,billing 共享逻辑在 shared territory。

### Checkpoint:UI 改造完成,两端构建绿。

---

## 阶段 6 · 充值模块(R5,Provider 可插拔;本期仅 ManualConfirm + 兑换码)

**目标**:订单+流水+settle 真实生命周期;ManualConfirm + 兑换码上线;真网关**只留接口契约**(不实现类/路由)。

### Provider 抽象 `katrain/web/core/payment/`(新建包)
- `base.py` `PaymentProvider`:
  - `create_order(db, user_id, package) -> RechargeOrder`(套餐 **只接受服务端配置 package_id**,服务端定 `amount_fen/credits`,前端不可传金额)。
  - `verify_callback(raw_body: bytes, headers: Mapping[str,str]) -> PaymentEvent`(**预留 raw body + headers**,为真网关验签/防重放;含 `event_id`)。
- `manual.py` `ManualConfirmProvider`:`create_order` 建 pending 单 + 返回个人收款码引用 + 金额;无自动回调。
- WeChat/Alipay:**本期不实现类、不挂路由**,仅在包 README 标注接口契约与待办(资质后插入)。
- 工厂 `get_provider(name)`(本期只注册 manual)。

### API(扩 `billing.py`,统一 `/api/v1/billing/*`)
- `POST /api/v1/billing/recharge {package_id, provider}` → `create_order` → `{order_id, qr_url, amount_fen}`。
- `POST /api/v1/billing/recharge/{order_id}/proof {proof}` → 存凭证;**校验 `order.user_id==current_user`**;校验大小/类型;存 `proof_url/proof_hash`,状态 → `proof_submitted`。
- `POST /api/v1/billing/admin/orders/{id}/confirm {note}` → `settle_order`(`get_current_admin_user`);只允许 `pending/proof_submitted`;记录 `confirmed_by/at/note`;**重复确认幂等**返回已入账。
- `GET /api/v1/billing/orders` → 当前用户订单与状态。
- **webhook 本期不挂路由**(真网关接入时再加,届时直接用 `verify_callback(raw_body, headers)`)。

### 前端 `RechargePage`(共享,参考 19x19)
- 套餐列表 + 兑换码输入 + 选 ManualConfirm → 展示个人收款码 + 提交凭证 + 轮询订单状态。
- 管理员核对:**本期最简受保护 API + CLI 脚本**;前台管理页 → Phase 6b。

### 测试
- 后端:create_order→pending(金额来自服务端套餐,篡改前端金额无效);proof 越权提交别人订单 403;admin confirm→paid+入账(幂等,重复 confirm 不双加);非 admin confirm 403;`settle_order` 幂等。
- 前端:充值页下单→显示码→提交凭证→(模拟 admin confirm)→余额增加。

### Checkpoint:充值闭环(人工核对)可走通;真支付只差 Provider 实现 + webhook 路由激活。

---

## 阶段 7 · 集成 / 回归 / 验收

1. 全量后端测试:`CI=true uv run pytest tests`(含并发扣分、reserve-commit-refund、reconcile、rated 服务端封口、整数精确性、迁移 fixture)。
2. 前端:`npm test`(Playwright);两构建 `npm run build` + `npm run build:kiosk-2d` 绿。
3. 回归(验收 §8):`KATRAIN_MODE=server` galaxy 既有对局/复盘对照基线;关闭付费门控可回退。
4. 板上冒烟(验收 §1-2、§7):AI ≤~2s;日志只 genmove;配 `remote_url` 后付费分析/复盘发往远程;board 离线付费禁用。
5. 逐条核对 `requirements.md §6` 验收标准(尤其 §3 扣分原子幂等、§4 排位全禁、§7 远程路由)。
6. `black -l 120` 格式化;`i18n.py -todo` 补齐翻译。

### 最终 Checkpoint:对照验收清单逐项打勾,提交 PR。

---

## 风险 / 待确认(执行中可能回头问)
- **单价数值 / 初始赠送积分**:`billing/prices`(整数)与 `BILLING_FREE_GRANT` 默认需产品定;计划用占位默认,易改。
- **board billing 代理协议**:`REMOTE_API_URL` 的 `/api/v1/billing/*` 远端实现需与云端 server 模式一致(同一套代码两种部署,代理只透传 token)。
- **kiosk rated 模式**:当前 kiosk 无排位入口;服务端 game_type 门控先就位,kiosk UI 启用排位另议。
- **`User.credits` Float→Integer 迁移**:需在含真实用户数据的库上验证回填与回滚;若有小数积分需先与产品确认取整规则。
- **个人收款码合规**:ManualConfirm 为过渡;真自动化需个体户/公司商户号 + webhook(见 requirements §3.7、§7)。
- **b28 未部署**:远程链路以可配置 URL + 本地/mock 验证;部署后填 `remote_url` 即生效。
- **`force_recompute` 产品语义**:同节点同道具是否允许付费重算、是否二次确认,需产品最终拍板;计划默认「已购免费回看,重算需显式确认」。
