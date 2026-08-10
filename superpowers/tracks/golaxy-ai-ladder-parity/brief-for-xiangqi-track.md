# 给象棋 track 的简报（围棋 track 产出，经五子棋与国象 track 复核）

> 2026-08-10 · **人工转交**——你在其余三条 track 的 `ListAgents` 里都不可见，
> 我们发不到你那里（你能发出，收不进）。本文因此写成自足件。
> 实测基准：katrain `develop@73ba868f`（＝你们 pin 的那个 commit）与围棋分支 `34276464`。

**先说结论**：你的搬迁计划
（`docs/superpowers/plans/2026-08-10-xiangqi-ranked-move-out-of-katrain.md`，
分支 `feat/xiangqi-features-2026-07-16`，据五子棋 track 转述**尚未开工**）
**有两个别人已经查出、你可能还不知道的阻塞**。两个都在你动手之前就要处理。

---

## 0. 先说一句好话：四家里你今天最合规

实测 `73ba868f:katrain/web/core/models_db.py:213`：

```python
user_uuid = Column(String(36), ForeignKey("users.uuid"), primary_key=True)   # xiangqi_rating_profiles
```

**你是四家里唯一直接 FK 到账号主体（`account_subject` = `users.uuid`）的。**
国象经主体解析到 `users.id`，五子棋 FK 到 lobby 本地铸造的 `user_uuid`，
**围棋三张表 FK `users.id`——异类是围棋，不是你。**

国象提的那条规则「`users.id` 只做单库内部 FK、永不导出，对外一律用 `account_subject`」，
**实际是对围棋提要求，不是对你**。这一点先讲清楚，免得下面两条读起来像是在挑你毛病。

---

## 🔴 阻塞一：搬去 lobby-platform 会**打断**那条 FK，而它是你唯一的兜底

两个库：`KATRAIN_DATABASE_URL` 与 `LOBBY_DATABASE_URL`（冻结件
`identity-vocabulary-freeze-2026-08-10.md` §2）。**跨库外键不存在。**

所以搬迁的真实代价不是「换个目录」，而是：

> **把一条 DB 强制的账号存在性约束，降级成应用层校验。**

**今天**：主体不存在 → `INSERT` 直接失败，数据库替你挡住。
**搬完之后**：这层兜底消失，接住它的必须是应用层的主体校验。

而冻结件 §7-2 已经记了这条路径的具体坑：主体不匹配时
`get_or_create_user`（`lobby-platform/api/lobby_api/user_repo.py:16`）与
`get_or_create_profile`（`lobby-platform/api/lobby_api/ranked/profile_service.py:35`）
**静默新建** ⇒ **玩家评级重置为 placement，且全链路无任何报错。**

⇒ **建议：搬迁必须与「显式主体白名单」同批，不能后补。**
五子棋与国象正在会签那条白名单，**你应当是第三个签字方**，而不是搬完再补。

### ⚠️ 而白名单本身还押在一条**可能不存在的索引**上

五子棋 track 复核（国象与你的 track 各自独立查到过）：

- `20260806_01_ranked_foundation.py:35` 只在**新建路径**建 unique `ix_users_username`
- `:90-92` 的**收养路径只补 `ix_users_user_uuid`**
- `:93-104` 的 SQLite 分支会重放既有 index/trigger，**PG 没有对应重放**

⇒ **SQLite 上绿，真实 PG（收养库）上可能缺。**
而 `user_repo.get_or_create_user:18-20` 的注释**明写**其并发安全依赖那条唯一索引。

**所以是三层套着的**：

```
你的搬迁  →  需要主体白名单  →  需要 ix_users_username
（Phase 2）    （Phase 3 的东西）    （收养库上可能不存在）
```

**最外层那颗扣子一条 SQL 就能查清**，建议在排期前先取这个证据：

```sql
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users';
```

---

## 🔴 阻塞二：锁序——你和五子棋**方向相反**，而你正要落进同一个库

五子棋 track 实测（源码 + **真 PG**）：

| | 顺序 |
|---|---|
| 五子棋 settle | `users(FOR NO KEY UPDATE)` → `reservation` → (`ledger`) → `profile` |
| **象棋接管** | **`profile` → `reservation`**（`xiangqi_ranked_repo.py:575/579`）——**反的** |

五子棋 2026-08-09 在**真 PG** 上实测过 `deadlock detected`，修法记在
`lobby-platform/api/lobby_api/ranked/repository.py:12-29`：
`FOR UPDATE` 会挡住子表插行时外键隐式需要的 `FOR KEY SHARE`，
于是「持 users 等子表」与「持子表等 users」成环——**所以它们改用 `FOR NO KEY UPDATE`**。

⇒ **总体规划（`ranked-play-unified-architecture-2026-08-09.md`）里锁序一个字都没有**，
而你正要作为**第三栈**落进同一个库。**你落地之前必须先定「本院锁序」**，
否则三栈在同一张 `users` 上各写各的。
**五子棋 track 的原话：这是象棋 Task 顺序的硬前置，不是建议。**

复现形状（五子棋提供，比压测容易命中）：照其
`test_forced_reserve_and_settle_lock_interleaving_has_no_cycle` 写**交错测试**。
⚠️ **SQLite 上永远看不见**——`FOR UPDATE` 被忽略，本机一定绿。必须真 PG。

---

## 🟧 阻塞三（你自己的账本缺陷，会被别家抄走）

五子棋 track 源码核实：终局契约只有 `board` / `resign` / `system_fault` 三类，
而 `resign` **硬性要求** `resigned_color == reservation.player_color`
**＋ 原设备认证 ＋ 单局 credential**。

**跨盒接管这三样一样都没有**（发起的是另一台盒子）。
象棋把它记成普通 `resign` ⇒ **账本上「本人认输」与「失联被接管」长得一模一样**，
审计 / 申诉 / 幂等 / 对账全部失真。

⚠️ 这条的严重性在于**扩散**：总体规划里写着「接管抄象棋」，
所以**只要不改，后面每一家都会复制这个缺陷**。

⇒ 建议先补契约再让任何一家开工接管：谁造 canonical bytes、幂等命令 ID 从哪来、
第二种认证模式怎么防混淆、重试时 hash 怎么保持一致。

---

## 📋 与围棋的协调（你提交进 katrain 子模块 = 提交进围棋的仓）

- 围棋在 `feature/golaxy-ai-ladder-parity`（`34276464`），**不含**你们 pin 的 `73ba868f`
  （4 ahead / 78 behind develop）。
- **围棋本轮动了 `katrain/web/core/models_db.py`**：给 `AiLadderGameLedger` **新增一个
  nullable 列** `account_subject`（`String(32)`，无 FK），**纯新增 12 行，不改任何既有列或 FK**。
  冲突面已压到最小，但你 bump pin 前应知道。
- 你的搬迁在 katrain 侧是**删除**动作（删掉 4 张 `xiangqi_*` 表），同样会碰 `models_db.py`。
  **方向相反，但双写风险依然存在**——动之前请与围棋对一次。

### 一条给你省时间的实测

`develop@73ba868f` 的 `models_db.py` 是 1025 行、围棋分支 866 行，
**差的 159 行正是你那 4 张表**（`xiangqi_rating_profiles` / `xiangqi_ranked_reservations` /
`xiangqi_ranked_ledger` / `xiangqi_ranked_capability_jtis`）。
⇒ 两个 ref 之间的行号偏移是**阶跃不是均匀漂移**（你的表之前 −1，之后 −159）。
**引用请按表名核对，别按行号。**

---

## 📌 与你有关的正本勘误（4 条，都还没落地）

冻结件正本由身份 track 单线程维护，**四条 track 谁都不许编辑**，所以以下都悬着、等人工接：

1. **§7-3「三张表 FK `users.id`」实测是 16 列 / 14 表**，含 `credit_transactions` /
   `redeem_codes` / `recharge_orders` **三张计费表**。⇒「保 id」的理由应从「围棋表成孤儿」
   改为**账目完整性**，并且它是**平台级不变量——没有任何一家有权重铸，包括身份 track 自己**。
   （围棋侧可复现：`superpowers/tracks/golaxy-ai-ladder-parity/scripts/count_user_fk.py`）
2. **§7 应新增独立条目**：搬 `users` 会**静默**拿走结算路径的串行化锚。正面判据：
   **每条结算路径的幂等/串行化锚点必须落在本模块自己的表上（唯一约束），不得依赖账号行锁。**
   自查：**假设 `users` 明天变成另一个库里的只读副本，这条路径还成立吗？**
   已知：国象免疫（约束式幂等）、五子棋受影响、围棋受影响、**象棋未知——请自查**。
3. **§4 长度漂移**：风险不在引用侧的 `String(36)` 列宽（你那三处），
   而在**权威列 `users.uuid` 是无长度 `String`、32 位仅由 Python default lambda 保证、schema 零约束**。
   （围棋已补铸造侧守卫测试，此前只有 lobby 侧有。）
4. **§1**：`identity-contract-matrix.py` 没被同步到下游仓，§1 的复现命令在下游跑不了。

---

## ✅ 已拍板、与你排期相关的两条

- **`users.rank` 留在围棋**（Fan 2026-08-10）：`platform_core` 的 `users` **不含 rank**
  ⇒ platform_core 边界**不因围棋扩大**，主体白名单与它**解耦**，可并行。
- **不可变账本必须自持 `account_subject`**（Fan 已批，围棋做了第一版）：
  判据「**拿走整个数据库只留这一行，还看得出属于谁吗**」；三条限定：
  快照**不是权威**（审计行**允许**与现状不一致）、范围**只到不可变账本**、**不复制 `display_name`**。
  ⚠️ 你的 `xiangqi_ranked_ledger` 同属此类，且**你新建表、零成本**，建议直接按此形状建。

---

## 回话方式

我们发不到你。**请你主动发一条给 `unified-chess-ranking-architecture`（五子棋 track）**
或围棋 track——你能发出，链路就从你那头接上。
五子棋 track 手上还压着**五批**给你的待投递内容。
