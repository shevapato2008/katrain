# 验收发现：galaxy free play 仍免费提供强模型实时分析（R3/R4 未落地）

**日期：** 2026-06-09
**来源：** 在 http-engine-remove-spawn 任务的本地手动验收中，跑 galaxy 服务器版（PostgreSQL，`:8001`，连本地 KataGo `:8000`）测 "Play vs AI (free)" 时发现。
**状态：** 待办，归入本 track 的 pending 阶段（4b/5/6）。本次 http-engine 任务**不处理**（用户决定）。

---

## 现象

galaxy "Play vs AI (free)" 模式下，右侧胜率图表（Graph）**默认打开**，每手自动显示形势判断（实测：`Black Winrate 99.6% / Black Lead +14.7 pts`）。这块强模型实时分析是**免费**提供的，与 R3/R4 的付费/移除设计冲突。

## 证据

- 每手落子后，后端日志稳定出现一条 `priority: 1002, maxVisits: 500` 的自动局面分析查询（区别于 AI 应手的 `humanSLProfile` 查询）。
- 该查询打到本地 `:8000` 的 **KataGo 完整模型 `b28c512`**（强模型），用来算右侧胜率/形势——不是 human-like 应手模型。
- 前端 Graph 面板默认处于打开态。

## 根因（已查实）

- `katrain/web/interface.py` `WebGame.play(move, analyze=True)`：每手默认 `analyze=True` 触发 per-node 自动 eval。
- 仅有两道闸拦截分析，galaxy free play 两道都不命中：
  - `should_suppress_auto_eval()`（R1）：只在 `KATRAIN_MODE == "board"`（kiosk）+ `MODE_PLAY` 时抑制。galaxy 非 board 模式 → 不抑制。
  - `analysis_allowed()`（R3/R5 防作弊）：只对 `game_type in (rated, ranked)` 禁分析。free 局 → 允许。
- 因此 galaxy free play = 非 board + `game_type="free"` → 自动 eval 开 + 分析允许 → 每手免费跑 500-visit 完整模型分析并默认显示胜率图。

## 对应需求（尚未在 galaxy free play 落地）

- **R3 对弈页付费分析改造（kiosk + galaxy 共享逻辑）**：领地/支招/变化图默认关；按次扣分触发；排位局置灰。当前 galaxy free play 的「胜率/形势自动分析」未纳入此付费门控。
- **R4 对弈页移除胜率图表**：图表应只在复盘报告显示，对弈页不留持续 loading / 死控件。当前 galaxy 对弈页 Graph 默认开且持续更新。

## 待办（归入 4b/5/6）

1. galaxy free play 默认**不**自动跑 per-node 500-visit 分析（对弈页 Graph 默认收起 / 移除，按 R4）。
2. 胜率/形势/领地/支招/变化图改为 R3 的「默认关 + 按次扣分触发 + 余额不足弹充值」逻辑，galaxy 走自身引擎、kiosk 走远程。
3. 排位局沿用现有 `analysis_allowed()` 全程禁用。

## 备注

- 与本次已完成的改动无关：http-engine de-spawn（R8）正常；AI 应手已修为 `humanSLProfile + maxVisits=1`（弱/像人/快），不受影响。
- 这里描述的 500-visit 自动分析是「强模型形势判断」，与 AI 应手是两个独立查询、两个用途。
