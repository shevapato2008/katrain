# Galaxy 对局记录统一入口 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将统一“对局记录”入口放到 Galaxy 对局首页并直达现有复盘模块，同时删除升降级子模块内的错误入口并锁定统一棋局写入契约。

**Architecture:** 不新建历史页面或数据库表。`PlayMenu` 只增加一个页面级次要导航动作；`AiLadderRatedSetup` 删除模块专用入口；现有 `user_games` 和 `/galaxy/report` 保持权威，升降级后端只补回归断言。

**Tech Stack:** React 19、React Router、MUI、Vitest/Testing Library、pytest、Playwright

---

## Chunk 1: 统一入口与数据契约

### Task 1: 移动 Galaxy 对局记录入口

**Files:**
- Create: `katrain/web/ui/src/galaxy/pages/PlayMenu.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/PlayMenu.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.tsx`

- [ ] **Step 1: 写失败测试**

为 `PlayMenu` 断言页头右侧存在次要按钮“对局记录”，点击后导航到 `/galaxy/report`；分别点击三张模式卡并断言仍导航到 `/galaxy/play/ai?mode=free`、`/galaxy/play/ai?mode=rated`、`/galaxy/play/human`。修改 `AiLadderRatedSetup` 测试，断言不再出现“查看正式对局记录”。

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd katrain/web/ui && npm test -- --run src/galaxy/pages/PlayMenu.test.tsx src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`

Expected: `PlayMenu` 因缺少“对局记录”按钮失败，升降级组件因旧按钮仍存在失败。

- [ ] **Step 3: 最小实现**

在 `PlayMenu` 标题行使用现有 MUI `Box` 横向布局，右侧增加 `variant="outlined"` 的“对局记录”按钮并导航 `/galaxy/report`；小屏允许标题行换行但按钮仍可访问。删除 `AiLadderRatedSetup` 中的 `HistoryRoundedIcon` 导入和记录按钮。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `cd katrain/web/ui && npm test -- --run src/galaxy/pages/PlayMenu.test.tsx src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`

Expected: 两个测试文件全部通过。

### Task 2: 锁定统一棋局表写入契约

**Files:**
- Modify: `tests/web_ui/test_ai_ladder_api.py`

- [ ] **Step 1: 加强现有成功路径断言**

在 `test_ranked_natural_result_saves_once_then_settles_once` 中同时断言唯一 `UserGame` 的
`id == game_id`、`source == "play_ai"`、`game_type == "ai_ladder_ranked"`，并断言唯一 ledger 行复用相同 `game_id`。

- [ ] **Step 2: 运行聚焦后端测试**

Run: `.venv/bin/python -m pytest tests/web_ui/test_ai_ladder_api.py -k 'ranked_natural_result_saves_once_then_settles_once' -q`

Expected: PASS；若失败，只修复实际缺失的现有写入字段，不建立新表。

这是对既有成功路径的 characterization 断言，预期直接通过。若失败，停止执行并先把实际缺失定位到
`katrain/web/server.py` 或 `katrain/web/core/user_game_repo.py`，再为该缺失另写明确的 RED→GREEN 步骤；
不得依据本计划中的泛化描述直接修改生产代码。

### Task 3: 构建与目标尺寸视觉确认

**Files:**
- Create: `katrain/web/ui/playwright.visual.config.ts`
- Create: `katrain/web/ui/tests/galaxy-play-record-entry-visual.spec.ts`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/play-record-entry/1440x900/implementation.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/play-record-entry/430x880/implementation.png`

- [ ] **Step 1: 新增隔离视觉用例**

新增最小 `playwright.visual.config.ts`，以 `npm run dev -- --host 127.0.0.1` 启动 Vite、使用
`http://127.0.0.1:5173`，不启动依赖 PostgreSQL 的完整后端。复用 Galaxy 真实外壳和翻译 Fixture，分别在
1440×900 和 430×880 打开 `/galaxy/play`，断言“对局记录”位于页头区域、可见且可点击，三张模式卡
数量不变、页面无横向溢出，并截图两个实现态。

- [ ] **Step 2: 运行聚焦验证**

Run: `cd katrain/web/ui && npm test -- --run src/galaxy/pages/PlayMenu.test.tsx src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`

Run: `cd katrain/web/ui && npm test -- --run src/galaxy/pages/report/ReportsPage.test.tsx`

Run: `cd katrain/web/ui && npm run build`

Run: `cd katrain/web/ui && npx playwright test tests/galaxy-play-record-entry-visual.spec.ts --project=chromium --config=playwright.visual.config.ts`

Expected: 全部 PASS，并生成 1440×900 截图。

- [ ] **Step 3: 停止等待视觉确认**

向用户展示实现截图。用户确认前不提交本实现切片，也不开始跨设备生命周期。

- [ ] **Step 4: 用户确认后提交**

Run: `git add katrain/web/ui/playwright.visual.config.ts katrain/web/ui/src/galaxy/pages/PlayMenu.tsx katrain/web/ui/src/galaxy/pages/PlayMenu.test.tsx katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.tsx katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx katrain/web/ui/tests/galaxy-play-record-entry-visual.spec.ts tests/web_ui/test_ai_ladder_api.py superpowers/tracks/galaxy-ai-ladder-journey/visual/play-record-entry`

Run: `git commit -m "统一 galaxy 对局记录入口"`
