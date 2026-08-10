<!-- 由围棋 track 生成：36 个 agent 的并行取证 + 对抗式复核（27 条确认 / 3 条被推翻）。
     本文所有关键断言已由围棋 track 逐条回读源码复核，见文末「复核记录」。 -->

# `users.rank` 归属裁定简报

**日期**：2026-08-10 · **分支**：`feature/golaxy-ai-ladder-parity` @ `34276464` · **对应**：冻结件 §7-4 / §8-1（`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md:199,207`），前置件 §B（`superpowers/tracks/golaxy-ai-ladder-parity/identity-p3-preconditions.md:109-118`）

## 建议：**不跟账号走（选项 B）**

**唯一驱动事实**：`users.rank`（`katrain/web/core/models_db.py:56`，`Column(String, default="20k")`）在**全仓零写入**——注册时由列默认值落一次（`katrain/web/core/auth.py:161` 只传 username+hashed_password），此后没有任何 Python 写它（旧写入方 `katrain/web/core/ranking.py` 已在 `75e551f5` 删除，原因写在 `katrain/web/core/game_repo.py:5-10`：「两套段位系统写同一列」）。它今天只有两个读者：账号序列化（`katrain/web/core/auth.py:296`）和围棋的**非权威**定级开窗种子（`katrain/web/api/v1/endpoints/ai_ladder.py:119`、`katrain/web/core/ai_ladder_ranked.py:339`）。唯一能解释这个字符串的代码是围棋侧的 `_legacy_rank_to_rung`（`katrain/web/core/ai_ladder_ranked.py:85-96`，kyu/dan → rung）。**platform_core 若接手，将持有一个它写不了、读不懂、校验不了的字段。**

真正的段位权威早已不在这一行：`AiLadderProfile.ai_ladder_rung`（`katrain/web/core/models_db.py:99-112`，「Authoritative ranked-AI state, independent from the legacy human ladder」），且只有 `RANK_MOVING_GAME_TYPES = ("ai_ladder_ranked",)` 能动它（`katrain/web/interface.py:253-256`）。

---

## 选项 A：跟账号走

- **含义**：platform_core 的 `users` 表保留 `rank` 列，围棋通过账号服务读取。
- **会坏什么**：① 跨节点分歧变成静默事故——盒内影子用户（`katrain/web/api/v1/endpoints/auth.py:185`）与云端 users 行各算一次窗口，不一致即 `opponent_rung_mismatch`（`katrain/web/core/ai_ladder_ranked.py:342`），而 profile 只在匹配分支创建（:344-353），账号会**永久卡在定级**。② 立下「棋类段位可放共享账号行」的先例，与统一架构里三家各自建表的现状相反（`superpowers/shared/ranked-play-unified-architecture-2026-08-09.md:96-98`：`ranked_glicko_profiles` / `ranked_elo_profiles` / `ranked_ladder_profiles`）。
- **成本**：短期最低（改数据来源即可）；但 platform_core 边界扩大不可逆，冻结件 §2 把它限定为 account·auth·db·config·migrations（`identity-p3-preconditions.md:113-114`）。
- **影响谁**：四家共用边界，象棋/国象/五子棋会照此索要各自段位列。

## 选项 B：留在围棋（推荐）

- **含义**：platform_core 的 `users` **不含** `rank`。围棋侧二选一：直接丢弃（种子缺失时本就回落全窗，见 `ai_ladder_ranked.py:57-58` 与 :85-96 的 `None` 分支），或迁移时一次性 backfill 进 `ai_ladder_profiles`。
- **会坏什么**：几乎没有真实行为变化。`/me`、`/register`（`katrain/web/api/v1/endpoints/auth.py:362,321`）与 `/users/{followers,following,online}`（`katrain/web/api/v1/endpoints/users.py:37,44,51`）少一个字段，但 `katrain/web/models.py:180` 有默认值 `"20k"`，**不会抛错、会静默填默认**；前端 `katrain/web/ui/src/context/AuthContext.tsx:8` 是未校验 cast，也不编译失败。唯一自身读者 `GalaxySidebar.tsx:167,172` 今天本来就永远显示 `?`/`No Rank`，`FriendsPanel.tsx:103` 今天本来就永远打印 `20k`。
- **成本**：低—中：删列/迁移 + 清 1 个 Pydantic 字段 + 清前端 3 处，顺带修掉上述既有显示 bug。
- **影响谁**：只影响围棋，且给另外三家立的是正确先例。

---

## 紧急度

- **rank 本身可安全推迟**：write-dead，任一选择今天都不改变运行时行为。
- **但同一行上有一条必须先决的硬阻塞（与 rank 无关）**：`settle_game` 对 `users` 行加 `SELECT … FOR UPDATE`（`katrain/web/core/ai_ladder_ranked.py:322`）。PostgreSQL 下这是结算路径**唯一**的 per-user 串行化锚——`_begin_write_transaction` 只对 SQLite 发 BEGIN IMMEDIATE（:397-406），profile 的 FOR UPDATE 在 profile 尚不存在时锁不到任何行（:332-337）。`users` 一旦搬出本库，这把锁消失，必须先补 profile 侧 upsert/advisory lock。**Phase 3 动代码前必须处理，不要等 rank 裁定。**

## 未验证 / 不知道

- 生产库 `users.rank` 的真实取值分布**未核**：`docs/database-info/schema.md` 是约半年前快照（缺全部 `ai_ladder_*` 表），不可作依据。
- 未读象棋/五子棋/国象仓（不在本仓），跨棋类判断仅据共享文档。
- 冻结件 §7-4 引用的是 vendor pin 的 `models_db.py:57` / `ai_ladder.py:118`，本仓实际为 `:56` / `:119`（各差一行），说明正本盯的是另一个 submodule pin；不影响结论，但回写正本时应对齐。
- platform_core 是否已有 schema 草案、`rating_history`（`models_db.py:84-91`，全仓零读零写）是否随账号迁移，均未见于本仓任何文件。

---

## 复核记录（围棋 track 逐条回读源码，2026-08-10）

上文关键断言全部经人工回读确认，非仅凭 agent 报告：

| 断言 | 复核结果 |
|---|---|
| `users.rank` 全仓零写入，仅注册时列默认值落一次 | ✅ `katrain/web/core/auth.py:161` 只传 username+hashed_password；`models_db.py:56` `default="20k"` |
| 旧写入方已删除 | ✅ `katrain/web/core/ranking.py` 不存在；理由逐字见 `katrain/web/core/game_repo.py:5-11`（「两套段位系统写同一列」） |
| 唯一解释该字符串的代码在围棋侧 | ✅ `_legacy_rank_to_rung`（`ai_ladder_ranked.py:85-96`）解析 kyu/dan：`21-value` / `min(20+2*value, 38)` |
| 真正权威是 `AiLadderProfile.ai_ladder_rung` | ✅ `models_db.py:99` 类注释「Authoritative ranked-AI state, independent from the legacy human ladder」 |
| 🔴 结算路径对 `users` 行加 FOR UPDATE | ✅ `ai_ladder_ranked.py:322` `.with_for_update()`；`_begin_write_transaction` 文档字符串明写「PostgreSQL uses the row locks below」，BEGIN IMMEDIATE 仅 SQLite 分支 |
| 🔴 profile 锁在 profile 不存在时锁不到东西 | ✅ 同文件 `:332-337` `.with_for_update().one_or_none()`，紧接 `if profile is None:` 才创建 |
