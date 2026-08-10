# Galaxy 升降级未完成对局前端预览 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在真实 Galaxy 升降级设置页中，用隔离网络 Fixture 展示并操作“本设备继续/结束、另一设备等待/结束、结算中刷新”三种状态，产出桌面与手机预览供用户确认。

**Architecture:** 扩展共享 TypeScript 状态契约，但本计划不新增生产后端；`AiLadderRatedSetup` 只负责状态面板和确认框，`AiSetupPage` 负责导航、刷新和结束请求。Playwright 在网络层注入确定性状态，生产组件中不放模拟数据。视觉确认是进入后端计划的硬检查点。

**Tech Stack:** React 18、TypeScript、MUI、Vitest/Testing Library、Playwright

**Spec:** `docs/superpowers/specs/2026-08-06-galaxy-ai-ladder-active-game-lifecycle-design.md`

---

## Chunk 1: Galaxy 前端状态与视觉预览

### Task 1: 冻结前端状态和结束命令类型

**Files:**
- Modify: `katrain/web/ui/src/features/aiLadder/types.ts`
- Modify: `katrain/web/ui/src/features/aiLadder/api.ts`
- Test: `katrain/web/ui/src/features/aiLadder/api.test.ts`

- [ ] **Step 1: 写结束请求和返回联合的失败测试**

在 `api.test.ts` 断言 `endAiLadderGame('game-1')` 向编码后的
`/api/v1/ai-ladder/games/game-1/end` POST `{"reason":"user_resigned"}`，并能解析：

```ts
{ state: 'pending_settlement', game_id: 'game-1' }
```

再覆盖 200 `settled + receipt` 和 409 `settled + receipt`；409 必须作为已生效终局返回，不能转换成普通错误。

- [ ] **Step 2: 运行聚焦测试并确认失败**

Run: `npm test -- --run src/features/aiLadder/api.test.ts`
Expected: FAIL，`endAiLadderGame` 尚未导出。

- [ ] **Step 3: 添加最小判别联合**

在 `types.ts` 添加：

```ts
export type AiLadderBlockingGame = {
  game_id: string;
  state: 'active' | 'pending_settlement';
  ownership: 'current_device' | 'other_device';
  session_id?: string;
  user_color: 'B' | 'W';
  opponent_rank_name: string;
};

export type AiLadderGameLifecycle =
  | { state: 'active'; game_id: string }
  | { state: 'pending_settlement'; game_id: string }
  | { state: 'settled'; game_id: string; receipt: { counted: boolean; reason: AiLadderCountingReason | null } };
```

给 `AiLadderReadyStatus` 添加 `blocking_game?: AiLadderBlockingGame | null`。在 `api.ts` 添加
`endAiLadderGame(gameId, token)`，复用认证头；2xx 正常解析，409 单独解析为同一个
`AiLadderGameLifecycle`，其他非 2xx 继续走现有错误映射。

- [ ] **Step 4: 运行测试并确认通过**

Run: `npm test -- --run src/features/aiLadder/api.test.ts`
Expected: PASS。

### Task 2: 实现右侧未完成对局面板

**Files:**
- Modify: `katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.tsx`
- Modify: `katrain/web/ui/src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`

- [ ] **Step 1: 写四种状态的失败测试**

覆盖：

- 无 `blocking_game` 显示“开始正式对局”；
- `active/current_device` 且有 session 显示“继续对局”“结束该对局”；
- `active/current_device` 且无 session 显示“刷新状态”“结束该对局”；
- `active/other_device` 显示“等待结算”“结束该对局”，且不显示/使用 session；
- `pending_settlement` 显示“刷新状态”，不显示“结束该对局”。
- `lifecycleReceipt` 存在时优先于 `blocking_game` 和普通挑战状态显示结算反馈；随后 status 刷新使
  `blocking_game` 消失也不能覆盖该反馈。

再断言结束按钮打开确认框，文案为“结束后将按你认输处理，并计为本局负。此操作不可撤销。”，默认危险动作不是自动执行。

- [ ] **Step 2: 运行组件测试并确认失败**

Run: `npm test -- --run src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`
Expected: FAIL，组件尚不支持占用状态 props 和动作。

- [ ] **Step 3: 添加最小 props 和条件渲染**

新增 props：

```ts
lifecyclePending: boolean;
lifecycleError?: string;
lifecycleReceipt?: { counted: boolean; reason: AiLadderCountingReason | null };
onContinue: (sessionId: string) => void;
onEndGame: (gameId: string) => void;
```

右侧渲染优先级固定为 `lifecycleReceipt → blocking_game → 普通挑战`；左侧段位/进度保持不变。当前设备且有
session 的唯一实底主行动为“继续对局”；另一设备为“等待结算”；结算中为“刷新状态”。使用 MUI `Dialog`
二次确认，取消按钮先获得焦点，结束按钮为危险色且请求期间禁用。

- [ ] **Step 4: 运行组件测试并确认通过**

Run: `npm test -- --run src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx`
Expected: PASS。

### Task 3: 连接设置页动作但保持后端可替换

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`

- [ ] **Step 1: 写页面动作失败测试**

断言“继续对局”导航到现有 rated game route；“等待结算/刷新状态”调用 hook 的 `retry`；确认结束后调用
`endAiLadderGame`。返回 `pending_settlement` 时刷新 status；返回 `settled`（包括 409 重放）时先保存并展示
receipt，再刷新 status；普通失败保留面板并显示错误。

- [ ] **Step 2: 运行页面测试并确认失败**

Run: `npm test -- --run src/galaxy/pages/AiSetupPage.test.tsx`
Expected: FAIL，页面尚未传入生命周期动作。

- [ ] **Step 3: 实现页面级状态和处理器**

添加独立的 `lifecyclePending`、`lifecycleError`、`lifecycleReceipt`；继续动作只接受组件已经校验过的 session；
结束动作调用 API，`pending_settlement` 刷新 status，`settled` 先把 receipt 传给右侧面板的既有结算反馈样式
再刷新，失败时不清理 status。不要添加 query Fixture、轮询或后端兼容猜测。

- [ ] **Step 4: 运行页面测试并确认通过**

Run: `npm test -- --run src/galaxy/pages/AiSetupPage.test.tsx`
Expected: PASS。

### Task 4: 产出目标 viewport 真实运行时预览

**Files:**
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/reference.html`
- Create: `katrain/web/ui/tests/galaxy-ai-ladder-active-game-visual.spec.ts`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/1440x900/reference.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/1440x900/implementation.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/1440x900/comparison.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/1440x900/overlay.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/430x880/reference.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/430x880/implementation.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/430x880/comparison.png`
- Create: `superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game/430x880/overlay.png`

- [ ] **Step 1: 制作最小视觉参考**

用单文件 HTML 复刻已确认 Galaxy 设置页构图，并以明确参数输出两个状态：1440×900 为
`active/other_device`，430×880 为 `active/current_device`。复用现有颜色、字体层级、按钮尺寸和容器，不重画
logo、图标或棋盘资产；分别截取与实现同状态的 `reference.png`。

- [ ] **Step 2: 添加隔离网络 Fixture 的 Playwright 用例**

拦截认证、翻译、真实 logo、`GET /api/v1/ai-ladder/status` 和结束命令；桌面展示
`active/other_device`，手机展示 `active/current_device`。另增加无需截图的 `pending_settlement` 场景，断言只有
“刷新状态”且没有结束按钮。共同断言标题、返回按钮、正确动作、确认框和无横向溢出。

- [ ] **Step 3: 运行最小前端验证**

Run: `npm test -- --run src/features/aiLadder/api.test.ts src/galaxy/components/aiLadder/AiLadderRatedSetup.test.tsx src/galaxy/pages/AiSetupPage.test.tsx`
Expected: PASS。

Run: `npx tsc --noEmit`
Expected: PASS。

- [ ] **Step 4: 运行两个视觉 viewport 并保存截图**

Run: `/Users/fan/.codex/skills/playwright/scripts/playwright_cli.sh test tests/galaxy-ai-ladder-active-game-visual.spec.ts`
Expected: 1440×900、430×880 用例通过并生成两张截图。

- [ ] **Step 5: 生成同尺寸对比证据并交给用户确认**

为两个 viewport 各生成参考/实现并排图和 50% 透明叠加图。核对构图与几何间距、组件层级、字体色彩材质、
真实图标/品牌资产、文案和状态语义，以及 430×880 纵向滚动和按钮可达性。向用户展示参考、实现、并排和
叠加证据；在用户明确确认前停止，不进入后端契约、数据库或跨设备集成。

- [ ] **Step 6: 提交前端预览切片**

```bash
git add katrain/web/ui/src/features/aiLadder katrain/web/ui/src/galaxy katrain/web/ui/tests/galaxy-ai-ladder-active-game-visual.spec.ts superpowers/tracks/galaxy-ai-ladder-journey/visual/active-game
git commit -m "预览升降级未完成对局状态"
```

## 后续检查点（本计划不执行）

用户确认视觉后，另写后端集成计划，覆盖账号级占用、`active → terminal` CAS、按局状态接口、共享
`user_games` 单行写入和原设备终局感知。本计划不以本地 `AiLadderPendingGame` 冒充跨设备权威，也不提前修改数据库。
