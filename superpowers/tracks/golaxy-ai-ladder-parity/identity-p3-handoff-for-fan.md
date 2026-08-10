# 交接件：需要人工转达的事项（围棋 track → Fan）

> 2026-08-10 · 围棋 track 产出 · **本文自足**，可直接整篇转发，不需要额外上下文
> 实测基准：katrain 仓 `feature/golaxy-ai-ladder-parity` @ `34276464`，交叉核对 `develop@73ba868f`

## 为什么需要你人工转

两件事叠加：

1. **冻结件正本没有任何 track 能编辑。** `superpowers/shared/identity-vocabulary-freeze-2026-08-10.md`
   由身份 track 单线程维护，围棋、国象、五子棋**三家都被明确要求不得编辑**，只能提变更请求。
   下面 4 条变更请求因此全部悬空。
2. **象棋 track 三家都联系不上。** 它能发出，但围棋、国象、五子棋的 `ListAgents` 里都看不到它，
   回复一律 `No agent named ... is reachable`。**它是只出不进的。**
   而冻结件里恰好有一条「⚠️ 象棋 Phase 2 提交进 katrain 子模块，bump pin 前先协调」——
   **这条协调从任何一侧都执行不了。**

---

## A. 给冻结件正本的 4 条变更请求

### A-1 🔴 §7-3 与架构 §13-ter：「三张表」实测是 **14 张表 / 16 个 FK 列**，且含计费表

原文：「三张表 FK `users.id`（`models_db.py:105/133/170`），身份服务的副本必须保 id 值，
否则**三张表**全成孤儿」。

**结论（必须保 id）成立；范围低估 5 倍，且指错了风险主体。**
实测 `katrain/web/core/models_db.py` 中 `ForeignKey("users.id")` = **16 列 / 14 表**，
除三张 ranked 表外还含 **`credit_transactions` / `redeem_codes` / `recharge_orders` 三张计费表**。

关键反转：冻结件自己的 §13-ter 已证明围棋 ranked **今天零局可计分**
（`katrain/core/ladder.py:483` `_CERTIFIED_RUNGS = frozenset()`）⇒ 那三张 ranked 表**没有存量**。
真正有存量、且 id 一旦漂移就直接坏账的是三张计费表。

⇒ **「保 id」的理由应从「围棋表成孤儿」改为「账目完整性」**，与围棋标定进度无关，现在就是硬约束。

- **五子棋 track 已在 pin `73ba868f` 上独立复核，逐表一致，投票支持进正本。**
- 可复现：`python3 superpowers/tracks/golaxy-ai-ladder-parity/scripts/count_user_fk.py 73ba868f HEAD`

### A-2 🔴 §7 新增独立条目：搬 `users` 会**静默**拿走结算路径的串行化锚

围棋 `settle_game` 在 PostgreSQL 下**唯一**的 per-user 串行化手段，是对 `users` 行加的行锁
（`katrain/web/core/ai_ladder_ranked.py:322`）。三条证据：

1. 同文件 `_begin_write_transaction`（`:397-406`）文档字符串明写「**PostgreSQL uses the row locks
   below.** SQLite ignores `FOR UPDATE`…」，实现只有 sqlite 一个分支 ⇒ PG 下无其他串行化手段；
2. profile 侧的 `.with_for_update()`（`:332-337`）在 profile 尚不存在时**锁不到任何行**
   （紧接 `if profile is None:` 才创建）；
3. 幂等检查（账本 `one_or_none`，`:315-320`）在锁之后读，靠的正是这把锁。

⇒ `users` 搬出本库 = 锁消失 = 首次结算并发绕过幂等，**不报错，只是窗口重新打开**。

**建议写成正面判据**（国象 track 提出，围棋采纳——只扫用法只能找病灶、对未写的代码无约束力）：

> **每条结算路径的幂等/串行化锚点，必须落在本模块自己的表上（唯一约束），不得依赖账号行锁。**
> 自查：假设 `users` 明天变成另一个库里的只读副本，这条路径还成立吗？

三家自查（各自实测）：**国象免疫**（约束式幂等，锚点在自己表的唯一键上，`rated_settlement.py:281-287`）；
**五子棋同构受影响**（`profile_service.get_or_create_profile:36-41` 文档字符串逐字写着
「lock its immutable account parent to serialize concurrent first reservations」）；**围棋受影响**。

- **五子棋 track 投票：该进 §7 做独立条目、不附在某一家名下**——前三条改的是描述精度，
  **这条改的是搬迁前必须做的动作**。

### A-3 🟡 §4：长度漂移清单漏了一处，且**风险方向记反了**

§4 记的是 lobby 三处（`{1,32}/{1,64}/{1,64}`，国象本轮已统一到 `{1,32}`）。缺的那处性质不同：

> **主体的权威列 `users.uuid`（`katrain/web/core/models_db.py:51-53`）是无长度的 `String`，
> 32 位仅由 Python default lambda 保证，schema 零约束**；象棋三张表以 `String(36)` 引用它
> （`:213`/`:236`/`:283`），恰好装得下被禁止的 36 位格式。
> **风险不在引用侧的宽度，在权威侧的无约束。**

围棋实测把链收得更紧：**全仓只有一个铸造点**（`katrain/web/core/auth.py:161`，连 uuid 都不传，
完全依赖模型默认值），出网点 `auth.py:293`。保障链是「**一个 lambda → 没了**」。

（此措辞由国象 track 修正后采纳；围棋原来的写法把引用侧说成了风险源，是错的。）

### A-4 🟡 §1：`identity-contract-matrix.py` 没被同步到下游

§1 给了复现命令，但 `sync-shared-doc.sh` 只把两个 `.md` 带进 katrain 仓，脚本本身不在。
下游 track 无法复现那 11 条路由矩阵，只能抄表。要么纳入同步集，要么在 §1 注明「脚本只在正本仓」。

---

## B. 需要转给象棋 track 的（它收不到任何人的消息）

### B-1 🔴 搬迁计划有一个 DB 级阻塞，搬之前必须先答

据 `unified-chess-ranking-architecture` 转述，象棋计划把 ranked 从 `vendor/katrain` 搬进
lobby-platform（计划文件 `docs/superpowers/plans/2026-08-10-xiangqi-ranked-move-out-of-katrain.md`，
分支 `feat/xiangqi-features-2026-07-16`，**未开工**）。围棋在 pin 上实测：

```
73ba868f:katrain/web/core/models_db.py:213
    user_uuid = Column(String(36), ForeignKey("users.uuid"), primary_key=True)
```

**好消息**：象棋是四家里**唯一直接 FK 到账号主体**的（国象经主体解析到 `users.id`，
五子棋 FK 到 lobby 本地 `user_uuid`，围棋三张表 FK `users.id`）。按「行引用永不导出」的规则，
**象棋今天最合规，围棋才是异类。**

**问题**：正因如此，搬去 lobby-platform 会**打断这条 FK**——两个库
（`KATRAIN_DATABASE_URL` / `LOBBY_DATABASE_URL`，冻结件 §2），跨库 FK 不存在。
搬迁的真实代价是：**把一条 DB 强制的账号存在性约束，降级成应用层校验**。

而这正好掉进冻结件 §7-2 那个坑：主体不匹配时 `get_or_create_user` / `get_or_create_profile`
**静默新建 ⇒ 评级重置成 placement 且全链路无报错**。象棋今天有 FK 兜底，搬过去之后没有了。

⇒ **建议：搬迁必须与「显式主体白名单」同批，不能后补。** 五子棋与国象正在会签那条白名单，
象棋应当是第三个签字方，而不是搬完再说。

### B-2 围棋本轮动了 `katrain/web/core/models_db.py`（纯新增，一个 nullable 列）

见下 C-2。改动是加列，不改任何既有列或 FK，冲突面已压到最小，但 bump pin 前应知会。

---

## C. 已完成的事（不需要你做什么，供备案）

### C-1 ✅ `users.rank` 归属：你已裁定「留在围棋」

`platform_core` 的 `users` **不含 `rank`**。驱动事实：该列**全仓零写入**——注册时
`default="20k"` 落一次（`auth.py:161`），此后无人再写；旧写入方 `katrain/web/core/ranking.py`
**已被围棋自己删除**，理由逐字写在 `katrain/web/core/game_repo.py:5-11`（「keeping it would have
meant two rank systems writing the same `users.rank` column」）；真正权威早已是
`AiLadderProfile.ai_ladder_rung`；唯一能解析该字符串的是围棋的 `_legacy_rank_to_rung`
（`ai_ladder_ranked.py:85-96`，kyu/dan → rung）。
⇒ platform_core 若接手，会持有一个**写不了、读不懂、校验不了**的字段。

**尚未实施**（属 Phase 3 迁移动作）。对其他 track：`platform_core` 边界不因围棋而扩大，
与主体白名单**不碰同一批 `users` 行变更**，可解耦并行。已同步国象与五子棋。

依据详见同目录 `identity-p3-rank-ownership-brief.md`（36 agent 并行取证 + 对抗式复核
27 确认/3 推翻 + 围棋逐条回读源码复核）。

### C-2 ✅ 账本自持主体：你已批准，围棋第一版已落地

通则：**任何只增不改的账本行，必须在行内自带 `account_subject` 快照，而不是只留行引用。**
判据（国象提出）：**拿走整个数据库，只留这一行，还看得出它属于谁吗？**

三条限定（国象提出，围棋全部接受）：① 快照**不是权威**，`user_id` 是运行时操作键，
`account_subject` 是结算当刻冻结的历史事实，写一次永不更新、不建 FK、不参与联接；
② 范围**只到不可变账本**，可变档案与短命预约不适用；③ **不复制 `display_name`**。

落地：`models_db.py` 加一个 nullable 列 + `ai_ladder_ranked.py` 冻结写入 +
**7 条守卫测试全绿**；存量兼容已在模拟已部署盒子上验证（自动 ADD COLUMN、旧数据保留、旧行为 NULL）；
回归 **267 passed, 1 xfailed**。

⚠️ 关于「围棋成本最低所以先做」：**围棋零存量是运气不是纪律**——原因是功能没上线
（`_CERTIFIED_RUNGS = frozenset()`），不是设计得好。通则里不应把围棋写成正面样板。
国象欠债最多（云端测试 PG 已有真实结算行），按 expand-contract 排期跟上，已如实报你。

### C-3 ✅ 主体格式守卫（katrain 侧此前完全没有）

新增 `tests/web_ui/test_account_subject_contract.py`，是 lobby `test_auth.py:198-216` 的**铸造侧对应物**。
`4 passed, 1 xfailed`，其中 `test_schema_rejects_a_dashed_subject` 为 **`xfail(strict=True)`**——
它是 A-3 那个缺口的**可执行证据**：断言 schema 应拒绝 36 位带横杠主体，而今天数据库照单全收。
将来真加上约束时它会 XPASS 并让构建失败，提示摘掉标记。**缺口从 latent 变成 tracked。**

未加 `String(32)`/CHECK 约束——那是 schema 变更 + 迁移，冻结件 §6-3 明令 Phase 1 不动列。

---

## D. 一条围棋自己的待办（不需要你决策，但需要真 PG）

`ai_ladder_ranked.py:322` 用 `FOR UPDATE`，但 `settle_game` **从不写 `users` 行**（只读 `user.rank`）
⇒ 锁级别强于所需。五子棋在**真 PG 上**实测过这个模式会 `deadlock detected`
（`FOR UPDATE` 挡住子表插行时外键隐式需要的 `FOR KEY SHARE`，两个方向成环），
它们因此用 `FOR NO KEY UPDATE`。

围棋暴露面更大：`users.id` 上挂着 **14 张表**的 FK，持锁期间并发插入这 14 张表（含计费表）全要等。

建议改 `.with_for_update(key_share=True)`，但**未落地**：SQLite 忽略 `FOR UPDATE`，
**这个问题在本机永远看不见**，必须在真 PG 上验证后再改。
