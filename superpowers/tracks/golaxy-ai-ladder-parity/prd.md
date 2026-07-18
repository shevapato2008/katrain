# PRD — Golaxy AI Ladder Parity（对标星阵 39 级 + 最强档）

| | |
|---|---|
| **Branch** | `feature/golaxy-ai-ladder-parity` |
| **Worktree** | `/Users/fan/Repositories/katrain-golaxy-ai-ladder-parity` |
| **Track dir** | `superpowers/tracks/golaxy-ai-ladder-parity/` |
| **Status** | Spec draft (brainstorm complete, research complete, awaiting user review) |
| **Date** | 2026-07-19 |

---

## 1. 背景与动机 (Background & Motivation)

KaTrain 目前的对弈 AI 是**风格化 / 拟人 AI**（`ai:human` / `ai:pro` = `HumanStyleStrategy`，`ai:p:rank` = `RankStrategy`），强度以 `kyu_rank` / `human_kyu_rank` 表示，最高标称到 9D（业余 9 段）。实测发现：**拟人 9D 甚至赢不了星阵围棋的 8D**。根因（研究确认）：`HumanStyleStrategy` 是对 KataGo HumanSL 网络的**纯策略采样（1 visit，无搜索）**——KataGo 官方文档明确指出，HumanSL 原始策略在**中高段以上不代表真实棋力**，因为它"只是顶尖棋手不读棋时的第一感"。要在中高段以上有真实棋力，**必须加搜索（visits）**。

目标：改用**正经的 KataGo 对弈网络**（b18，甚至更小的网络）+ **调整计算参数（visits、humanSLProfile、搜索偏置）**，全面对标星阵围棋的 39 个等级。已具备的条件：

- 跨平台对弈模块已接通星阵（`katrain/web/platforms/golaxy/`），可用其**无状态 genmove 隧道**（`engine_client.py:219-290`）作为对手引擎，用于实测校准。
- 生产 KataGo 引擎（`katago-gpu0` @ `:8000`，TensorRT/GPU）**已带 human model**（`/health` 返回 `has_human_model:true`），即 humanSLProfile 在服务端可直接用。
- 磁盘上有 `kata1-b18c384nbt-s9996604416-d4316597426.bin.gz`（b18）；`b28c512` 已部署于分析引擎（`katago-gpu1` @ `:8002`）用于复盘。

**范围原则**：先对齐星阵的 39 个等级（共 40 档，见 §5），再视情况决定是否增加新等级（**本轨道不做**）。

---

## 2. 关键发现：星阵"双尺度"更正 (The Two-Scale Correction) ⚠️

原始需求认为"跨平台对弈调研出的 `elo_score` 220–3300 是错的，应改成官网的 4000..−600"。**研究 + 代码核对证明这是两个真实且不同的尺度，代码值并非笔误。**

- 代码 `GOLAXY_AI_LEVELS.elo_score`（`engine_client.py:519-559`，3300→220）= **API `level` 参数**，2026-07-02 从客户端 Vuex `aiLevelList` 实测抓取，是打星阵对局时真正发送的强度参数（`1级=1100` 已验证）。
- 官网表的 "Elo分"（4000→−600）= 星阵**展示用的强度/排名 Elo**（营销 / 升降级用）。

逐值对照：

| 区段 | 官网 "Elo分" | 代码 API `level` | 关系 |
|---|---|---|---|
| 中段（5级 ~ 准9段） | 700 … 2900 | **完全相同** | ✅ 一致 |
| 底部（6级→18级） | 600 → **−600**（−100/档） | 620 → **220**（压缩，约停在 220） | API **饱和** |
| 顶部（9段→星阵3星） | 3100 → **4000**（+300/档） | 3000 → **3300**（压缩） | API **饱和** |

**含义**：星阵引擎的强度旋钮（`level`）有效范围约 220–3300；超出后**展示 Elo 继续涨但真实棋力几乎不变**。因此：

1. **星阵 1星≈2星≈3星 很可能真实棋力接近**；**12级≈…≈18级 亦然**——尽管展示 Elo 相差数百。
2. 对标必须以**实测强度**为准（打锚点对局测得），展示 Elo + 段位桥接仅作先验。
3. 代码**缺**的是：展示强度 Elo 列 + 野狐/现实段位参考列。

**决策（用户确认）**：**双尺度共存 + 先实测重验。** 保留 `elo_score`（API `level`）作为打星阵的真实参数；新增 `display_elo` + `ref_rank` 列；实现时先用 token 在**多个 level**（不只 1级）上重验真实 API 编码，确认压缩行为。

---

## 3. 目标 / 非目标 (Goals / Non-Goals)

### 目标

- G1. 定义一个 **40 档强度阶梯**：第 1–39 档 1:1 对标星阵 39 个等级（按 `level_name`），第 40 档 = 最强 KataGo @ 500 visits。
- G2. 每档由**显式的 rung→config 配置**驱动（网络 / 机制 / humanSLProfile / visits / humanSL 搜索偏置 / 后端路由提示），可复现、可调。
- G3. 提供**两阶段校准**：离线临时阶梯生成 + 实测锚点校准（打星阵 genmove API），产出经验证的配置表。
- G4. 服务端 Web（galaxy `AiSetupPage`）落地 40 档"对标星阵"选择器，标注星阵级/段名 + 展示强度 Elo。
- G5. 架构预留 **SBC 拆分路由**接缝（弱档→SBC 本地 CPU、强档→服务器 GPU），v1 全部走服务器。
- G6. 修正星阵数据模型（双尺度共存），并实测重验 `level` 编码。

### 非目标

- N1. **不**增加超出星阵 39 级的新档位（顶端 40 档除外）。
- N2. **不**追求拟人棋风优先——**强度对齐优先**（用户确认）。人类风格仅在"免费即像人"处保留（kyu/低段用 humanSL）。
- N3. **不**动复盘 / 分析引擎（`:8002` b28）路径。
- N4. v1 **不**在 SBC 上部署（只留接缝）。
- N5. **不**用 b28 于第 1–39 档（除非校准证明 b18 在合理 visit 预算内到不了星阵3星）。

---

## 4. 研究结论与决策 (Research-Backed Decisions)

| # | 问题 | 结论 |
|---|---|---|
| R1 | 纯公开 Elo 映射（不打真实对局）可行吗？ | **部分可行。** 仅中 kyu 段（星阵 ~7级–准1段）可靠到 ±1 段；深 kyu 尾、业余段过渡、职业/超职业顶端**必须实测锚定**。四套 Elo 尺度（星阵内部 / KataGo 自对弈 / EGF / GoRatings）无公开换算，单一偏移不能全程通用。→ **用 Elo 锚定 + 锚点实测的回退方案。** |
| R2 | 顶端用 b28 还是 b18 省算力？ | **第 1–39 档全用 b18**；b28 仅第 40 档。b18 每 node FLOPs ~2.5–3× 更省，b28 的优势是"等时更强"（只在最大化强度时有意义，对固定目标无意义）。顶 3 档默认 b18 递增 visits，**实测验证**，仅当 b18 到顶不足才换 b28。 |
| — | 首要目标 | **强度对齐优先**（非拟人优先）。 |
| — | 校准预算 | **~7 锚点 × ~50 局 + 分带修正**，再抽查 3–4 非锚点档。 |
| — | UI 首版位置 | **服务端 Web galaxy `AiSetupPage`**。 |
| — | 星阵尺度 | **双尺度共存 + 先实测重验**。 |

**KataGo HumanSL 事实（研究，均有一手来源）**：

- humanSLProfile 家族：`rank_20k..rank_9d`、`preaz_20k..preaz_9d`、`rank_{BR}_{WR}` / `preaz_{BR}_{WR}`（非对称）、`proyear_1800..proyear_2023`；均由 `b18c384nbt-humanv0.bin.gz`（v1.15.0）提供。
- 纯 1-visit 采样最匹配到**中高段**；再高需加搜索。
- humanSL **可与搜索结合**（`humanSLCpuctPermanent`、`humanSLRootExploreProbWeightless/Weightful`、`humanSLOppExploreProbWeightful`、`humanSLChosenMoveProp`、`humanSLChosenMovePiklLambda`），官方 `gtp_human9d_search_example.cfg` 用 400 visits + `preaz_9d` 达到"9d 或更强"；**注意：加搜索"大幅降低拟人度以换强度"**。
- **无**已发表的 rank_Nk 对真实段位的量化标定；低 kyu（18-20k）因训练数据集中在 ~5k 而表现不稳/偏离标称。→ 深 kyu 段容差放宽、必须实测。

---

## 5. 40 档阶梯定义 (The 40-Rung Ladder)

- **Rung 1–39**：按星阵 `GOLAXY_AI_LEVELS` 的 `level_name` 1:1 对应（18级 … 1级 … 准1段 … 9段 … 星阵1星 … 星阵3星）。每档目标 = 对应星阵档位的**实测强度**（~50% 胜率 ± 容差）。
- **Rung 40**：最强 KataGo = **b28c512 @ maxVisits=500**，无 humanSL 偏置。按构造保证 rung 40 ≥ rung 39（单调）。
- 每档带一份 `LadderRung` 配置（见 §8.1）。展示：`{星阵级/段名} · 对标星阵 · {display_elo}`（如"5段 · 对标星阵 · Elo2100"）。

---

## 6. 分带 → 机制映射 (Band → Mechanism Recipe)

第 1–39 档全部基于 **b18**（+ human model）。

| 带 | 星阵档位 | 机制 | 容差/备注 |
|---|---|---|---|
| 深 kyu（真 ~20k–15k） | 18级–7级 | humanSL `rank_20k…rank_15k`，**visits=1**，full temperature | ±1.5 段，训练稀疏、易不稳，必须实测 |
| **中 kyu（真 ~14k–5k）** | 6级–2级 | humanSL `rank_14k…rank_5k`，**visits=1** | 甜区，纯映射 ±1 段可靠，**勿加 visits** |
| 低 kyu/SDK（真 ~4k–1d） | 1级–1段 | humanSL `rank_4k…rank_1d`，visits=1 | 段/级边界，开始关注服务器段位膨胀 |
| 业余段（真 ~2d–6d） | 2段–9段 | 低段：humanSL `rank_2d…rank_5d`，visits=1；高段：humanSL `rank_6d…rank_9d` + **轻搜索**（visits 5–25）+ humanSL 偏置。备选：纯低-visits b18（若不要求棋风） | **过渡/交接带**，段位膨胀最严重，**必锚定** |
| 职业 | 星阵1星/2星 | b18 + 搜索 + humanSL `preaz_9d` 偏置，visits ~100–300（**强度优先则可去偏置用纯 b18 搜索，更省更强**） | 人类段位已饱和（都映到野狐9D），**必锚定** |
| 超职业 | 星阵3星（rung 39） | b18 高 visits ~400–500（到顶不足才换 b28） | 离人类尺度，无外部锚，**必锚定**；保 rung39 < rung40 |
| 天花板 | rung 40 | **b28c512 @ 500 visits**，满强 | 固定构造，非目标 |

> **强度优先取舍（用户确认）**：职业+ 档位用纯 b18 搜索（更强、更省算力）；humanSL 偏置仅在"免费即像人"的 kyu/低段保留。业余高段两法皆可，由校准择优。

---

## 7. 校准方法论 (Calibration Methodology) — 两阶段

### 阶段 A：离线临时阶梯（offline provisional）

1. 按 §6 给每档指定机制。
2. kyu ~ 低段（约 rung 1–24）：按官网段位桥接插值出 humanSL profile（18级→`rank_20k`，7级→`rank_15k`，1级→`rank_4k`，准1段→`rank_3k`，1段→`rank_1d`，…至 ~`rank_5d`），visits=1。近零成本、rank-native。
3. 高段/职业/超职业（约 rung 25–39）：用**单一平滑旋钮 = b18 上的 maxVisits**（Elo-vs-visits 低区约 log-linear ~100 Elo/倍增），humanSL 偏置参数固定；选 visits 使各档 Elo 单调递增，直到 rung40 的 b28@500 天花板。
4. **校验严格单调**（顺序即使绝对值未锚也可靠）。

### 阶段 B：实测锚点修正（empirical anchoring）

5. 在 **7 个锚点档**各打 **~50 局**（N≥40–60 → ~±60 Elo CI）：**我方 AI（该档配置） vs 星阵（该档 `level`=eloScore）**。
   - **锚点**：7级(540) / 1级(1100) / 1段(1300) / 5段(2100) / 9段(3000) / 星阵1星(3100) / 星阵3星(3300)（括号为 API `level`=eloScore，取自 `GOLAXY_AI_LEVELS`，非展示 Elo）。
   - ⚠️ **对局发送 `level`=eloScore（220–3300），绝不发送展示 Elo（4000..−600 或负数）**——后者是从未观测过的参数，会打断对局。
6. 由胜率算我方配置 vs 星阵档位的 Elo 差。
7. **分带拟合修正**：中 kyu 用全局偏移+斜率；业余段/职业/超职业用**分带局部修正**（**勿**强套单一线性）。
8. 用修正后的拟合重导非锚点档（kyu 调 profile 选择，段+调 visits）。
9. 抽查 3–4 个非锚点档短对局，迭代 visits（平滑旋钮，重调便宜）。

**先把内部阶梯做平滑单调，再用锚点整体平移/校正到星阵尺度上。**

### 校准工具（harness）

- 复用 `engine_client.engine_genmove`（纯函数，`httpx.MockTransport` 可测）作星阵对手；我方走本地/服务器 KataGo 引擎。
- 一个脚本编排：交替 genmove（我方色 ↔ 星阵色），互喂着法，终局判胜负，按 (rung_config, golaxy_level) 累计胜率 → Elo 差。
- 结果落 `superpowers/tracks/golaxy-ai-ladder-parity/calibration/*.json`（配置表 + 对局日志）。

---

## 8. 架构与集成 (Architecture & Integration)

### 8.1 Rung→config 数据模型

新增 40 条 `LadderRung`（建议 `katrain/core/ai_ladder.py` 或 `katrain/web/core/`）：

```
LadderRung = {
  rung: int,               # 1..40
  golaxy_level_name: str,  # '5段' / '星阵3星' / None(rung40)
  golaxy_api_level: int,   # eloScore，打星阵校准时发送；rung40=None
  display_elo: int,        # 星阵展示强度 Elo（4000..-600）；rung40=特殊
  ref_rank: str,           # 现实段位参考（'业余4段'等），UI 用
  net: 'b18'|'b28',
  mechanism: 'humansl'|'humansl_search'|'net_search',
  human_sl_profile: str|None,   # 'rank_5d' 等
  max_visits: int,
  human_sl_params: dict|None,   # {humanSLCpuctPermanent, humanSLRootExploreProbWeightless, ...}
  backend_hint: 'server'|'sbc', # SBC 拆分接缝；v1 恒 'server'
}
```

配置表来源：阶段 A 生成 → 阶段 B 修正后固化（校验入库，带版本号）。

### 8.2 每档引擎覆盖（per-rung engine overrides）

- 现状：强度只经 `kyu_rank`/`human_kyu_rank` 表达，引擎是**单一全局配置**（`server.py:816-841` 把 0–28 slider 映射到 config）。本地 AI 走 `/api/ai-move`（`server.py:935-948`，注意对 engine-play 会话 403）→ strategy → `engine.request_analysis`。
- 新增：一个**"ladder"对手**在建局时携带自己的 `max_visits` + `humanSLProfile` + humanSL 偏置参数，经现成的 `overrideSettings` / `extra_settings` 合并点注入（`engine.py:188`），**不依赖**全局 strategy config。
- 复用 `HumanStyleStrategy` 的 profile 注入路径（`ai.py:1637-1655` 已发送 `humanSLProfile`）；扩展它接受**外部指定的 profile + visits + humanSL 搜索参数**，或新建一个 `AI_LADDER` strategy。（设计倾向：新建 `LadderStrategy`，从 `LadderRung` 读参数，避免污染现有 human/rank 语义。）

### 8.3 humanSL 依赖

- 生产引擎 `:8000` 已 `has_human_model:true`（见部署 `server-deploy` SKILL，`/health` 期望 `has_human_model:true`）。
- **本地 dev** 需下载 `b18c384nbt-humanv0.bin.gz` 并配 `engine.humanlike_model`（`engine.py:234-250` 走 `-human-model`）或指向带 human model 的 HTTP 引擎，才能测 kyu/段带。（dev `config.json` 默认 `humanlike_model:""`、`http_has_human_model:false`。）

### 8.4 星阵数据模型改动（双尺度）

- `GOLAXY_AI_LEVELS`：保留 `elo_score`（=API `level`）；**新增** `display_elo`、`ref_rank`（野狐/现实段位）。数据来自官网表（§2），并**实测重验** API 编码。
- `/engine/levels` 端点 & 前端 `EngineLevel`（`api.ts:99-105`）随之扩列。
- 实测重验：小脚本用 token 在多个 level（如 18级/12级/1级/9段/星阵3星）genmove 一手，确认发送/接受的 `level` 值与压缩行为，落记录。

### 8.5 SBC 拆分路由接缝

- `backend_hint` 字段即接缝。v1：所有档 → 服务器 GPU。
- 未来：弱档（kyu/低段，humanSL visits=1，SBC CPU 可承受）→ SBC 本地；强档（段+搜索、职业+）→ 服务器。路由决策集中一处，便于后续接。

---

## 9. UX

- 位置：服务端 Web galaxy `AiSetupPage`（`katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`，现写 `human_kyu_rank`）。
- 新增"对标星阵"40 档选择器（离散阶梯，非连续 slider）。每档显示：星阵级/段名 + `对标星阵` + `display_elo`（+ 可选 `ref_rank`）。
- 与现有拟人 AI 并存（独立入口），不改现有 rank slider 语义（N2）。
- 建局：选中档 → 前端提交 rung 号 → 后端据 `LadderRung` 配置建局并注入引擎覆盖。

---

## 10. 分期 / v1 范围 (Phasing)

| Phase | 内容 | 交付 |
|---|---|---|
| P0 | 星阵双尺度重验 + 数据模型扩列（`elo_score` + `display_elo` + `ref_rank`）；实测重验脚本 | 正确的双尺度级别表；`/engine/levels` 扩列 |
| P1 | `LadderRung` 数据模型 + `LadderStrategy`/引擎覆盖注入 + humanSL 本地 dev 打通 | 可用 40 档骨架（临时离线配置） |
| P2 | 阶段 A 离线临时阶梯生成器（分带机制 + 插值 + 单调校验） | 单调的临时配置表 |
| P3 | 阶段 B 实测校准 harness（打星阵 API、胜率→Elo、分带修正、抽查、迭代） | 校准后固化的 40 档配置表 + 对局日志 |
| P4 | UX：galaxy `AiSetupPage` 40 档选择器 | 服务端可选可玩 |
| P5（未来，非本轨道） | SBC 拆分路由；是否加新等级 | — |

---

## 11. 风险与缓解 (Risks & Mitigations)

| 风险 | 缓解 |
|---|---|
| `b18@N visits ≥ 星阵3星` 未经实测；星阵3星离人类尺度，星阵冠军级引擎据报与满搜索 KataGo 势均力敌 | 顶 3 档默认 b18 递增 visits，**实测**；到顶不足才换 b28（配置一改即可） |
| HumanSL rank_Nk 无量化标定；rank 标签在 KGS/OGS/野狐混合池，或整体偏 1–2 段 | 分带经验偏移修正；以**实测**为准，不信标称 |
| 深 kyu（18-20k）不稳/非单调 | 放宽容差（±1.5 段）；必要时 preaz_ 变体 / `rootPolicyTemperature` 增变化；实测校验单调 |
| 业余高段"humanSL 1-visit → +搜索/低-visits"交接处强度突变或棋风跳变 | 交接带锚定 + 平滑 visits；强度优先下可全用低-visits b18 消除跳变 |
| 星阵档位标称偏强（同名 段/级 比野狐人类强）→ 若映"标签"会继承偏差 | 映**实测强度**而非标签（正是锚点对局的目的） |
| 跨尺度非线性 → 单一全局线性拟合会漂移 ≥1 段 | 强制**分带**修正，禁单斜率全程套用 |
| 校准送错 `level`（送展示 Elo/负数）打断对局 | harness 只送 `elo_score`（220–3300）；加断言校验 |
| 星阵 API 配额 / token 过期 | 复用现成 auth 刷新重试（`adapter.py` OAuth2）；限速；~7×50 局预算 |
| b28@500（rung40）算力最贵 | 明确为固定天花板；生产 GPU 需为该档预留 |

---

## 12. 待验证 / 开放问题 (To-Verify)

- V1. **实测重验**星阵 `level` 编码（多个 level，非只 1级），确认 220–3300 压缩行为与代码一致（或发现官方已改 → 更新表）。
- V2. b18 在合理 visit 预算内能否到达星阵3星实测强度（决定顶 3 档是否需 b28）。
- V3. humanSL profile 的离散粒度（每 1 段一档）能否覆盖各 kyu 档（是否需 blend/微调旋钮）。
- V4. 星阵 genmove 隧道是否接受满范围 `level` 及 pass/resign 编码（`coords.py` 尚未捕获 pass/resign）。
- V5. 本地 dev 用哪种方式接 human model（下载 humanv0 本地跑，还是连服务端带 human model 的 HTTP 引擎）。

---

## 13. 成功标准 (Success Criteria)

- SC1. 40 档配置表存在、单调、可复现（版本化）。
- SC2. 7 个锚点档实测 vs 星阵**胜率 ∈ [40%, 60%]**（±~1 段）；抽查的非锚点档同区间。
- SC3. 服务端 Web `AiSetupPage` 可选 40 档并成功建局对弈，引擎覆盖参数正确注入（可在日志/查询里验证 visits / humanSLProfile）。
- SC4. 星阵双尺度数据模型正确（`elo_score` 不回归、`display_elo`/`ref_rank` 就位），现有星阵跨平台对弈**不回归**。
- SC5. 深 kyy 段容差记录明确（哪些档达标、哪些放宽），无静默截断。

---

## 附：关键代码坐标 (Key Code References)

- AI 策略 / 拟人：`katrain/core/ai.py` — `HumanStyleStrategy` (~1616-1808)、profile 串 (~1637-1655)、`ai_rank_estimation` (~87-114)、`RankStrategy.get_n_moves` (~1399-1442)。
- 强度常量：`katrain/core/constants.py` — `CALIBRATED_RANK_ELO` (~142-165)、`AI_OPTION_VALUES` (~102-128)、`AI_*_ELO` grids。
- 引擎：`katrain/core/engine.py` — `overrideSettings` 合并 (:188)、`create_engine` (:820-857)、human-model 接线 (:234-250)、HTTP 引擎 (:538-566)。
- Web 建局 / AI 走子：`katrain/web/server.py` — 建局 rank 映射 (:816-841)、`/api/ai-move` 403 守卫 (:935-948)、`game_setup` (:773)。
- 星阵：`katrain/web/platforms/golaxy/engine_client.py` — `GOLAXY_AI_LEVELS` (:519-559)、`engine_genmove` (:219-290)；`superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md` §4（`level`=`eloScore` 溯源）。
- 部署：`.claude/skills/server-deploy/SKILL.md` — `katago-gpu0 :8000`（has_human_model）、`katago-gpu1 :8002`（b28 复盘）。
- 前端：`katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`、`src/api.ts` (`EngineLevel` :99-105)。
