# 围棋 track · Phase 3 身份迁移前置

> 状态：**草案** · 2026-08-10 · 归属：围棋 track（本仓自有文档，非共享副本）
> 上位契约：`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md`（v1，**副本不可直接编辑**）
> 对应条目：冻结件 §7-3、§7-4；统一架构 `ranked-play-unified-architecture-2026-08-09.md` §13-ter
> 实测基准：本仓 `feature/golaxy-ai-ladder-parity` @ `34276464`，交叉核对 `develop@73ba868f`（冻结件所据 pin）

本文只做两件事：把冻结件派给围棋的两条前置**写成可执行的要求**，并记录实测中发现的、
需要回写正本的偏差。**本阶段不改任何运行时代码。**

---

## §A 前置一（冻结件 §7-3）：「保 id」

### A.1 冻结件的原文，以及它错在哪

> 三张表 FK `users.id`（`models_db.py:105`、`:133`、`:170`），身份服务的副本必须**保 id 值**，
> 否则三张表全成孤儿。

**结论（必须保 id）成立。给出的理由范围低估了 5 倍，并且指错了风险主体。**

实测（`scripts/count_user_fk.py`，可在任意 ref 上复现）：

```
pin 73ba868f : FK -> users.id  = 16 列 / 14 表
HEAD 34276464: FK -> users.id  = 16 列 / 14 表   （表名逐个一致）
```

| 表 | 列 | @73ba868f | @34276464 |
|---|---|---|---|
| `relationships` | `follower_id` / `following_id` | :77 / :78 | :76 / :77 |
| `rating_history` | `user_id` | :89 | :88 |
| `ai_ladder_profiles` | `user_id` | :105 | :104 |
| `ai_ladder_pending_games` | `user_id` | :133 | :132 |
| `ai_ladder_game_ledger` | `user_id` | :170 | :169 |
| `live_comments` | `user_id` | :450 | :291 |
| `user_tsumego_progress` | `user_id` | :548 | :389 |
| `user_tutorial_progress` | `user_id` | :568 | :409 |
| `user_games` | `user_id` | :750 | :591 |
| `report_tasks` | `user_id` | :823 | :664 |
| `platform_games` | `user_id` | :941 | :782 |
| **`credit_transactions`** | `user_id` | :977 | :818 |
| **`redeem_codes`** | `used_by` | :996 | :837 |
| **`recharge_orders`** | `user_id` / `confirmed_by` | :1013 / :1021 | :854 / :862 |

**风险主体不是围棋。** 冻结件自己的 §13-ter ⚪ 行已经证明围棋 ranked 今天零局可计分
（`katrain/core/ladder.py:483` `_CERTIFIED_RUNGS: FrozenSet[int] = frozenset()`，`:495` 处
`certified = recipe is not None and rung in _CERTIFIED_RUNGS`）——**那三张 ranked 表没有存量数据**。
真正有存量、且 id 一旦漂移就直接坏账的是加粗那三张**计费表**。

⇒ 「保 id」的性质应从「围棋表会成孤儿」改写为「**账目完整性**」。按原写法，读者会以为这条前置的
风险随围棋标定进度而变；实际上它与围棋无关，且**现在就已经是硬约束**。

### A.2 「保 id」的正确读法：迁移期约束，不是 schema 约束

国象 track 提出的规则——**`users.id` 只做单库内部 FK、永不导出，对外一律用 `account_subject`**——
消解了本条的歧义。据此，「保 id」应当被读成：

> **复制账号行时不得重铸 `users.id`。** 仅此而已。

而**不是**「`users.id` 要跨服务可比」——后者恰恰是冻结件 §2 明令禁止的
（`account_row_ref`「跨服务不可比」）。原文「身份服务的副本必须保 id 值」单独读容易滑向后者。

这个读法的好处：要求落在**迁移步骤**上，而不是落在表结构上。只要行引用不出网，
收敛到 `account_subject` 就**不需要动这 14 张表的任何存量**。

### A.3 围棋 track 的验收要求（提交给 Phase 3 执行方）

1. 账号行复制必须**保留 `users.id` 原值**（禁用自增重排、禁用 `INSERT ... RETURNING id` 重铸）。
2. 迁移后校验：上表 16 个 FK 列的孤儿行数必须为 **0**。计费三张表的孤儿检查**必须单独出报告**。
3. `users.uuid` 的生成方式（`katrain/web/core/models_db.py:51`，`uuid4().hex`，32 位小写无横杠）
   **不得改动**。冻结件 §4 已说明：改成 36 位带横杠会让所有 bootstrap 400。围棋是该值的**铸造方**，
   认领此约束；若将来需要变更，须同时改 lobby 的 `ACCOUNT_SUBJECT_PATTERN` 与
   `lobby-platform/api/tests/test_auth.py:198-216`。
4. **迁移后必须跑主体格式全量校验**：`users.uuid` 无一行不匹配 `^[0-9a-f]{32}$`。
   可执行形状见 `tests/web_ui/test_account_subject_contract.py::test_all_stored_subjects_conform`。

### A.4 权威侧无约束（本轮新发现，已部分落地）

由国象 track 指出、围棋 track 实测确认的一处**结构性缺口**，性质比 §C-3 原先记录的「列宽 36」更严重：

**`account_subject` 的 32 位约束在 katrain 里没有任何 schema 级保障。**

- 权威列 `katrain/web/core/models_db.py:51-53` 是**无长度的 `String`**；
- 全仓**只有一个铸造点**：`katrain/web/core/auth.py:161`
  `models_db.User(username=..., hashed_password=...)`——连 uuid 都不传，完全依赖模型默认值
  （源码原注释即 “Defaults are handled by SQLAlchemy model”）；
- 出网点：`katrain/web/core/auth.py:293` 的 `"uuid": user_obj.uuid`。

⇒ 保障链是「**一个 default lambda → 没了**」。任何绕过默认值直接写 `users.uuid` 的路径
（迁移脚本、admin 操作，**尤其是 Phase 3 身份服务复制账号行**）都能落进一个 36 位带横杠的值，
schema 不拦；后果是 lobby 侧全部 bootstrap 400，**国象与五子棋一起断**，且断点离写入点很远。

**已落地**（不改运行时、不需要迁移）：`tests/web_ui/test_account_subject_contract.py`，
lobby `test_auth.py:198-216` 的铸造侧对应物。`4 passed, 1 xfailed`，其中

```
test_schema_rejects_a_dashed_subject   XFAIL(strict=True)
```

是该缺口的**可执行证据**：它断言 schema 应当拒绝 36 位带横杠主体，而今天数据库照单全收。
等约束真正落地，这条会 **XPASS** 并让构建失败，提示摘掉 `xfail` 标记。

**未落地（列为 Phase 3 前置）**：给 `users.uuid` 加列宽或 CHECK 约束。这是 schema 变更 + 迁移，
冻结件 §6-3 明令 Phase 1 不动列，故本阶段不做。

---

## §A-bis 前置三（**冻结件漏列**，围棋 track 本轮发现）：结算路径的行锁会随 `users` 一起消失

🔴 **这条冻结件 §7 完全没有，但它比 `rank` 归属紧急，且与 `rank` 无关。**

围棋结算 `settle_game` 在 PostgreSQL 下**唯一**的 per-user 串行化锚，是对 `users` 行加的行锁：

```python
# katrain/web/core/ai_ladder_ranked.py:322
user = session.query(models_db.User).filter(models_db.User.id == user_id).with_for_update().one_or_none()
```

三条证据说明它确实是唯一锚点：

1. `_begin_write_transaction`（同文件 `:397-406`）的文档字符串明写
   「**PostgreSQL uses the row locks below.** SQLite ignores `FOR UPDATE`, so BEGIN IMMEDIATE …」，
   且实现只有 `if session.get_bind().dialect.name == "sqlite":` 一个分支 ⇒ **PG 下没有别的串行化手段**。
2. profile 侧虽然也有 `.with_for_update()`（`:332-337`），但紧接着就是 `if profile is None:` 才创建 ⇒
   **首次结算时 profile 行还不存在，锁不到任何行**。
3. 幂等检查（账本 `one_or_none`，`:315-320`）在锁之后读，靠的正是这把锁。

⇒ **`users` 表一旦搬出本库，这把锁就没了**，首次结算并发会绕过幂等检查。
**Phase 3 动代码之前必须先补 profile 侧 upsert 或 advisory lock，不能等 `rank` 裁定。**

### 通则（经三家会签后改写为**正面判据**）

围棋最初提的是「搬账号前全仓扫 `with_for_update()` 打在 `users` 上的用法」。国象 track 指出
**只扫用法只能找到病灶、给不出药方，且对还没写的代码没有约束力**，建议改写为正面判据，围棋采纳：

> **每条结算路径的幂等/串行化锚点，必须落在本模块自己的表上（唯一约束），不得依赖账号行锁。**
> **自查方式：假设 `users` 明天变成另一个库里的只读副本，这条路径还成立吗？**

三家自查结果（各自实测，非推测）：

| track | 锚点 | 是否受影响 |
|---|---|---|
| 国象 | **约束式幂等**：`rated_ledgers` 唯一键 `(user_id, game_type, rated_game_id)`，`rated_settlement.py:281-287` 接 `IntegrityError` 回读赢家回执 | ❌ 不受影响——锚点在自己表上。这也解释了它零 `with_for_update` 却无并发缺口 |
| 五子棋 | `profile_service.get_or_create_profile:36-41` 文档字符串逐字：「lock its **immutable account parent** to serialize concurrent first reservations」 | ✅ **同构受影响**，已写进其计划 S6-附 2 |
| 围棋 | `ai_ladder_ranked.py:322` 对 `users` 行 `FOR UPDATE` | ✅ **受影响**（本节） |

⇒ 国象是唯一免疫的，**而且不是运气**：它用约束式幂等而非锁式串行化。**这是四家应当收敛到的形状。**

### 🔴 附带发现（围棋自身的潜在缺陷，非仅迁移前置）

`:322` 用的是 `FOR UPDATE`，但 **`settle_game` 从不写 `users` 行**——只读 `user.rank`（`:341`）。
实测：`sed -n '300,392p'` 范围内无任何 `user.<attr> =` 赋值。⇒ **锁级别强于所需。**

五子棋 track 在**真 PG 上**（2026-08-09）实测过这个模式会 `deadlock detected`
（`ranked/repository.py:12-29` 有记录）：`FOR UPDATE` 会挡住子表插行时外键隐式需要的 `FOR KEY SHARE`，
于是「持 users 等子表」与「持子表等 users」成环。它们因此改用 `FOR NO KEY UPDATE`（`key_share=True`）。

围棋的暴露面**比五子棋大**：`users.id` 上挂着 **14 张表**的 FK（见 §A.1），所以 `settle_game`
持锁期间，任何并发插入这 14 张表（含三张**计费表**）的事务都要等这把锁。

**建议改法**：`.with_for_update()` → `.with_for_update(key_share=True)`。
**未落地，因为无法在本机验证**——SQLite 上 `FOR UPDATE` 被忽略，**这个问题在 SQLite 上永远看不见**，
必须在真 PG 上跑。列为待验证项，不擅自改并发语义。

---

## §B 前置二（冻结件 §7-4 / §8-1）：`users.rank` 的归属

**状态：✅ 已由 Fan 裁定 —— 选项 B「留在围棋」，2026-08-10。**
决策简报见 `identity-p3-rank-ownership-brief.md`（同目录，36 agent 取证 + 对抗式复核 + 人工回读复核）。

**裁定结果**：`platform_core` 的 `users` **不含 `rank`**。围棋侧二选一：直接丢弃
（种子缺失本就回落全窗，`ai_ladder_ranked.py:57-58` 与 `:85-96` 的 `None` 分支），
或迁移时一次性 backfill 进 `ai_ladder_profiles`。**尚未实施**——属 Phase 3 迁移动作，此刻不动列。

对其他 track 的意义：`platform_core` 边界**不因围棋而扩大**，五子棋/国象正在会签的主体白名单
与本条**不碰同一批 `users` 行变更**，两条可解耦并行排期（已同步给两家）。

**裁定依据（围棋 track 建议，获采纳）：选项 B（留在围棋）。** 驱动事实：`users.rank` **全仓零写入**——注册时列默认值
（`katrain/web/core/auth.py:161` + `models_db.py:56` `default="20k"`）落一次，此后无人再写；
旧写入方 `katrain/web/core/ranking.py` 已被围棋 track 自己删除，理由逐字见
`katrain/web/core/game_repo.py:5-11`（「keeping it would have meant two rank systems writing the
same `users.rank` column」）。真正的段位权威早已是 `AiLadderProfile.ai_ladder_rung`
（`models_db.py:99`「Authoritative ranked-AI state」）。唯一能解释这个字符串的代码是围棋侧的
`_legacy_rank_to_rung`（`ai_ladder_ranked.py:85-96`，kyu/dan → rung）。

⇒ **platform_core 若接手，将持有一个它写不了、读不懂、校验不了的字段。**

要点：`rank`（`katrain/web/core/models_db.py:56`，`Column(String, default="20k")`）是**围棋域语义**的
字段，却坐在将要被移走的共享 `users` 行上。冻结件 §2 把 `platform_core` 限定为
account·auth·db·config·migrations，**对它沉默**。

此项会扩大或收窄 `platform_core` 的边界，而该边界四家共用，故围棋 track **不自行拍板**。

---

## §C 回写正本的请求（围棋 track 提出，已发出）

副本按规矩不可直接编辑，以下均以变更请求形式发给了共享文档持有方。

| # | 目标 | 内容 | 状态 |
|---|---|---|---|
| 1 | 冻结件 §7-3 / 架构 §13-ter | 「三张表」→「14 张表 16 个 FK 列，含三张计费表」；「保 id」理由改为账目完整性 | 已发；五子棋 track 在 pin 上**独立复核成立**并投票支持进正本 |
| 2 | 冻结件 §1 | `identity-contract-matrix.py` 未被 `sync-shared-doc.sh` 同步进本仓，§1 的复现命令在下游跑不了 | 已发 |
| 3 | 冻结件 §4 | 漂移清单应写成「lobby 三处（已统一到 32）**＋ katrain 侧一处性质不同的结构性缺口**」：权威列 `users.uuid`（`models_db.py:51-53`）是无长度 `String`，32 位仅由 Python default 保证，schema 零约束；象棋三张表以 `String(36)` 引用它（`:213`/`:236`/`:283`），恰好装得下被禁止的格式。**风险不在引用侧的宽度，在权威侧的无约束。** | 已发（措辞由国象 track 修正后采纳） |

| 4 | 冻结件 §7（**新增独立条目**） | 🔴 **搬 `users` 会静默拿走结算路径的串行化锚**（本文 §A-bis）。应写成正面判据：「每条结算路径的幂等/串行化锚点必须落在本模块自己的表上，不得依赖账号行锁」 | 已发；五子棋 track 投票**该进 §7 做独立条目、不附在某一家名下**，理由：前三条改的是描述精度，**这条改的是搬迁前必须做的动作** |
| 5 | 围棋自身（非正本） | 🔴 `ai_ladder_ranked.py:322` 的 `FOR UPDATE` 强于所需（`settle_game` 从不写 users 行），在真 PG 上有死锁环风险，且会阻塞 14 张表的并发插入 | 待在真 PG 上验证后改为 `key_share=True`；**SQLite 上永远看不见** |

**注意**：1–4 四条**没有任何一条能由现有 track 落地**——冻结件正本由身份 track 单线程维护，
围棋、国象、五子棋三家均被要求不得编辑。**需要人工接**（Fan 已确认由其人工转达，交接件见
`identity-p3-handoff-for-fan.md`）。

---

## §D 实测中发现的其他事实（供协调用）

1. **本分支不含 pin。** `git rev-list --left-right --count HEAD...develop` = **4 / 78**；
   `73ba868f` 不是 HEAD 的祖先。合 develop 时会继承 4 张象棋表。
2. **行号偏移是阶跃而非漂移。** `develop@73ba868f` 的 `models_db.py` 为 1025 行，本分支 866 行，
   差 159 行正是 4 张象棋表（`xiangqi_rating_profiles` / `xiangqi_ranked_reservations` /
   `xiangqi_ranked_ledger` / `xiangqi_ranked_capability_jtis`）。象棋表之前偏移 −1，之后 −159。
   ⇒ **带 pin 也不能假设偏移均匀**；用 `scripts/count_user_fk.py` 按表名核对，不要按行号。
3. **象棋是四家里唯一直接 FK 到账号主体的**（`models_db.py:213`
   `user_uuid = Column(String(36), ForeignKey("users.uuid"), primary_key=True)`）。
   围棋三张表 FK `users.id` 才是异类。国象那条「行引用永不导出」规则，**实际是对围棋提要求**。
4. **象棋搬迁计划有一个 DB 级阻塞**（据 `unified-chess-ranking-architecture` 转述，围棋未直接核实计划文本）：
   若把 `xiangqi_rating_profiles` 搬去 lobby-platform，上述 `ForeignKey("users.uuid")` **无法随行**
   （两个库：`KATRAIN_DATABASE_URL` / `LOBBY_DATABASE_URL`，冻结件 §2）。等于把一条 DB 强制的
   账号存在性约束降级为应用层校验，正好掉进冻结件 §7-2 那个「主体不匹配时静默新建、评级重置且无报错」的坑。
   ⇒ 已建议：象棋搬迁必须与「显式主体白名单」同批，不可后补。
5. **象棋 track 三家都联系不上**（只出不进）。冻结件那条「⚠️ 象棋 Phase 2 提交进 katrain 子模块，
   bump pin 前先协调」，**从围棋侧目前无法执行**。已上报 Fan。

---

## §E 提案：不可变账本必须自持主体（**待 Fan 拍板，围棋不自行落地**）

**来源**：国象 track 与围棋 track 在本轮独立得出同一结论。国象取证最全（账本四个载荷全查，
`facts_json` / `reservation_snapshot_json` / `receipt_json` / 表列，账号引用**仅** `user_id` 一个整数 FK）；
围棋对照 `ai_ladder_game_ledger`（`katrain/web/core/models_db.py:169`）同形，且更极端——
`opponent_config_snapshot` 装的是对手引擎配方，**连疑似账号字段都没有**。

**这不是某一家忘了，是同一个盲区。** 两种形状恰好互补：国象**有三个 JSON 快照列却一个账号字段都没有**，
围棋**连疑似字段都没有**。一个是有地方放而没放，一个是压根没想过要放——同一个盲区的两种表现。
这比逐家列举欠债更能说明问题。

### 通则（拟）

> 任何**只增不改的账本行**，都应当在行内自带 `account_subject` 快照，而不是只留一个行引用。

**判据（国象提出，可证伪）**：**拿走整个数据库，只留这一行，还看得出它属于谁吗？** 看不出即不合格。

### 三条限定（国象提出，围棋全部接受）

1. **快照不是权威。** `user_id` / 行引用 = **运行时操作键**；`account_subject` = **结算当刻冻结的
   历史事实**，写入一次、**永不更新**，不建 FK、不参与联接、不用于查询路由。
   > 审计行的价值恰恰在于**它可以和现状不一致**——它记的是当时。

   不写死这条，后来者见到两个字段就会去「修复不一致」，那才是灾难。
2. **范围只到不可变账本。** 围棋对照：`ai_ladder_game_ledger`（`:169`）适用；
   `ai_ladder_profiles`（`:104`，可变派生态）**不适用**；`ai_ladder_pending_games`（`:132`，短命预约）**不适用**。
   放宽范围会退化成「给每张表加个 uuid 列」，反而推翻刚约定的「行引用不出网」。
3. **不复制 `display_name`。** 它可变、可为中文、冻结件 §2 明说不参与判定；复制进审计行等于邀请
   后来者拿它做匹配。**只冻结 `account_subject` 一个。**

### 落地成本（三家实测）

| track | 存量 | 成本 |
|---|---|---|
| 围棋 | **零**（`katrain/core/ladder.py:483` `_CERTIFIED_RUNGS = frozenset()`，功能未上线） | 最低，直接加列 |
| 象棋 | 新建表 | 零成本，建议同批 |
| 国象 | 云端测试 PG 已有真实结算行（统一架构 §17） | 须走 expand-contract：nullable 加列 → 回填 → 水位线追尾 |

⚠️ **围棋零存量是运气不是纪律**——原因是功能没上线，不是设计得好。通则中不应把围棋写成正面样板。

### 状态：✅ Fan 已批准（2026-08-10），**围棋第一版已落地**

改动（**新增，不改任何既有列或 FK**，属 expand 段）：

| 文件 | 改动 |
|---|---|
| `katrain/web/core/models_db.py` | `AiLadderGameLedger` 新增 `account_subject = Column(String(32), nullable=True)`，附意图注释 |
| `katrain/web/core/ai_ladder_ranked.py` | `_new_ledger` 增参 `account_subject`；`settle_game` 在**已持有的** user 行上取 `user.uuid` 冻结写入 |
| `tests/web_ui/test_ledger_self_containment.py` | **7 条守卫测试，全绿** |

守卫测试逐条对应三条限定与判据：

| 测试 | 断言的性质 |
|---|---|
| `test_orphan_row_still_identifies_its_owner` | **判据本身**：删光 `users` 与 `ai_ladder_profiles`，账本行仍说得出属于谁；并断言 `row.user is None` 证明行引用确已悬空、是主体在起作用 |
| `test_account_subject_is_not_a_foreign_key` | 限定一的可执行形式——有 FK 就说明有人在拿它做联接 |
| `test_account_subject_is_frozen_and_never_follows_the_account` | 限定一：结算后改 `users.uuid`，账本仍持**旧值**（审计行**允许**与现状不一致） |
| `test_mutable_tables_do_not_carry_a_subject` | 限定二：`ai_ladder_profiles` / `ai_ladder_pending_games` **不得**有此列 |
| `test_display_name_is_not_copied_into_the_ledger` | 限定三：`display_name` / `username` 均不得出现 |
| `test_ignored_games_also_carry_the_subject` | 被忽略的结算也写账本行，同样要可识别 |
| `test_ledger_row_carries_account_subject` | 正常路径 + 格式 `^[0-9a-f]{32}$` |

**存量兼容已验证**：模拟一台已部署盒子（无该列、且有一行真实结算数据），
`migrations.add_missing_columns` 自动 `ALTER TABLE ADD COLUMN`，**旧数据完整保留、旧行 `account_subject` 为 NULL**。
无需手写迁移脚本。

**回归**：`test_ai_ladder_ranked.py` / `test_ai_ladder_api.py` / `test_migrations.py` /
两个新守卫文件合计 **267 passed, 1 xfailed**。

⚠️ 仍需协调：本次动了 `katrain/web/core/models_db.py`，即与象棋 track 双写风险最高的文件。
改动是**纯新增**（一个 nullable 列），不改既有列/FK，冲突面已压到最小，但象棋 bump pin 前仍应知会。
