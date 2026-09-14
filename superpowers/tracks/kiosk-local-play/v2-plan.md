# 本地对局 v2 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 kiosk「对弈 → 本地对局」做到可交付：屏上说的和后端做的一致（spec P1–P20）。

**Architecture:** 前端编排、后端核验（spec D7）。终局规则集中在新模块 `katrain/web/core/game_end_rules.py`；钟的算法抽成共享纯函数 `src/utils/gameClock.ts`。行为变化以 `game_type === 'pvp_local'`（或盒上模式 `suppress_auto_eval`）为界，galaxy 非盒上模式不变。

**Tech Stack:** FastAPI + `WebKaTrain`（pytest）；React + TypeScript + Vite（vitest、Playwright）。

**Spec:** `superpowers/tracks/kiosk-local-play/v2-design.md`
**设计稿（Fan 2026-09-14 已确认）:** `superpowers/tracks/kiosk-local-play/design/*.png`（在线版 https://claude.ai/code/artifact/e4d3c7ef-82dd-4a5e-a7b0-42db6b4ad731 ，屏 01 / 04 / 05 附 A–D / 19）

---

## 相称性裁定（Fan 2026-09-14：「不要过度设计、过度审核、过度测试」）

下面这几条**覆盖**各 Task 正文里与之冲突的步骤：

1. **S0 上板基线走查整片取消**（P1–P20 已经在摸底时逐条从源码核实过）。上板只在最后做一次终验（S5-3）。
2. **视觉关卡**：设计稿已由 Fan 确认。各 Task 里的「⏸ 停下等 Fan 确认」「四图 fourup」「承重实测 spec」**一律不做、不停**；新建的 `*.fourup.spec.ts`、`localClockFixture.ts` 之类的取图 / 量高 fixture **不建**。改完界面后在 S5-2 里统一出一次真浏览器截图给 Fan 看。
3. **测试只写本改动的行为**：pytest 覆盖后端判定（认输、数子、超时、galaxy 不变、名字不回填）；vitest 覆盖纯函数和组件行为。已有测试因改动变红就改到对，不额外补覆盖率。
4. **不做计划评审**；代码写完做一次代码评审，按意见改完即结束。

## 设计稿文案表（与 Task 正文不一致时以此为准）

| 位置 | 文案 |
|---|---|
| 屏 01 首页「本地对局」卡片副标（未登录时） | `要先登录 · 下完自动存谱` |
| 屏 04「怎么落子」提示 | `实体盘只有 19 路 · 选 13 路或 9 路就在屏幕上下` |
| 屏 04「贴目」下提示 | `让子局贴 0 目 · 选了让子这一组就收起`（让子 > 0 时贴目组收起，同屏 02） |
| 屏 04「用时」提示 | `钟在玩家卡上倒数 · 读秒用完判超时负 · 不限时就只记谱` |
| 屏 04「落子提示音」提示 | `和「设置 · 声音」里的落子音是同一个开关` |
| 屏 04 底部说明 | `屏上不给提示和形势判断；双方各停一手后自动数子，死活按引擎判断。` / `这一局只留档，不动段位；中途退出不存谱。` |
| 屏 05 本地对局右栏按键 | `数子` `停一手` `认输`（只有这三个） |
| 右栏开关行右端 | 手数不够时 `数子要下满 {n} 手`；双 pass 后 `双方都停了一手` |
| 玩家卡钟 · 主时间 | 大字 `09:42`，小字 `读秒 {len}秒×{n}` |
| 玩家卡钟 · 读秒 | 大字 `00:24`（青玉色），小字 `读秒 · 剩 {n} 次` |
| 玩家卡钟 · 到点 | 大字 `00:00`，小字 `超时`，整张卡红边红字 |
| 玩家卡钟 · 不限时 | 不变：`第 {n} 手` / `不限时` |
| 右栏状态条（开关行之上）· 超时判负后 | 标题 `黑方超时负`（红），副行 `白超时胜 · 第 {n} 手 · 已存进历史对局`，右侧药丸键 `复盘本局` |
| 右栏状态条 · 自动数子中 | 标题 `正在数子…`（带转圈） |
| 右栏状态条 · 数子失败 | 标题 `数子没有完成`（红），副行 `{真实原因} · 检查网络后重试`（原因按错误码），右侧药丸键 `重试` |
| 退出确认框 | 标题 `退出这局？` 正文 `这局还没下完，退出后不会保存。` 键 `继续下` / `退出不保存`（红） |
| 认输确认框 | 标题 `哪一方认输？` 正文 `对方记中盘胜，这局会存进历史对局。` 键 `黑方认输` / `白方认输`（红，带黑白子） / `取消` |
| 屏 19 本地对局行 | 两边名字都空：`本地对局 · 未记名`，否则 `本地对局 · 两人`；行首子黑白各半（`rowDisc(null)`） |

> 状态条是**右栏里的一块**（设计稿 05 附 B / C），不是 Snackbar / 弹出 Alert。Task 正文里写成 `Alert` 的，改成右栏状态条，`data-testid` 保持 `auto-count-status`。

---

## Global Constraints

1. **范围**：右栏三键、认输选方、钟、超时判负只对 `game_type === 'pvp_local'`；自由对弈 / 升降级对局屏不变。
2. **galaxy 不变**：非盒上模式双 pass 落账行为与 `1b6c67b5` 一致，有 pytest 钉住。
3. **数子门槛**：`scaled_count_min_moves(base, n) = max(1, round(base * n * n / 361))`（19→100、13→47、9→22），后端 `get_state` 下发，全局生效。双 pass 自动数子不看门槛。
4. **贴目**：让子 > 0 时发给后端的 komi 为 0（屏 04 全部；屏 02 仅 `mode === 'free'`）。
5. **名字照抄**：附录 A 共享契约里的函数名、字段名、错误码不许换。数子 400 code ∈ `below_min_moves` / `game_over` / `analysis_pending`；超时 409 code = `time_not_expired`。
6. **提示音**：只读写 `utils/audioPrefs.ts` 的 `sfx`；`grep -rn kioskPlaySound katrain/web/ui/src` 无输出。
7. **文案**：前端 `t('ns:key', '中文默认')`；新 key 在 S5-1 补 11 种语言。
8. **后端测试**：`CI=true uv run pytest <文件> -q`；**每次跑完** `git status --short katrain/config.json`，被改了就 `git checkout -- katrain/config.json`。Python 改动 `uv run black -l 120 <文件>`。
9. **前端测试**：`cd katrain/web/ui && npx vitest run <路径>`；类型检查 `npx tsc -b`。不写断言布局的 jsdom 测试。
10. **构建**：改了共享区（`src/components` `src/hooks` `src/utils` `src/api.ts` `src/types`）的 Task 结束前 `npm run build` 与 `npm run build:kiosk-2d` 都绿。
11. **Playwright**：跑前 `npm run build`；两个配置都 `reuseExistingServer`（:8002 / :5173），端口上有别的工作树的服务时先停下，不许复用。
12. **git**：只 `git add` 本 Task 的路径；不许 `git add -A`、不许 `git stash`；commit 中文、结尾两行：
    `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
    `Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ`
13. **上板**（仅 S5-3）：只部署到 `/mnt/data/<dir>/`，不碰 `/root/smartbox-software/vendor/katrain`；一次只跑一项；去登录页不带 `?logout=1`；部署前 ⏸ Fan 确认；隧道端口先 `lsof` 查空闲（19222/18081 属于 `katrain-kiosk-debug` 会话），上板前先 SendMessage 问它板子是否空闲。

---

## 执行顺序与并行泳道

```
泳道 A（主工作树）：S2a-1…4 → S2b-1…4 → S3-1 → S3-2 → S3-4 → S3-5
泳道 B（worktree ../katrain-klp-s1，分支 feature/kiosk-local-play-s1）：S1-1 … S1-5
泳道 C（worktree ../katrain-klp-s4，分支 feature/kiosk-local-play-s4）：S4-1 … S4-5
三条都完成 → B、C 依次 merge --no-ff 回 feature/kiosk-local-play → S5-1 → S5-2 → 代码评审 → S5-3（上板，需 Fan）
```

**跨泳道共改文件（按段归属）**：

| 文件 | 泳道 A | 泳道 B（S1） | 泳道 C（S4） |
|---|---|---|---|
| `src/hooks/useGameSession.ts` | `handleAction` | `playSound` | — |
| `src/kiosk/pages/PlayPage.tsx` | — | 本地对局卡片副标 | `if (token)` 闸 |
| `katrain/web/server.py` | resign / count / play_move 钩子 / timeout | — | `_record_ai_game_locked` 名字回填 |

合并后 grep 确认双方改动都在（无冲突 ≠ 合对了），再在主工作树跑一遍三条泳道各自的测试文件。

---

## 切片 S1：开一局，按约定开始下

**目标**：开局设置屏（屏 04 本地对局、屏 02 自由对弈）按下「开始对局」后，这一局**真的**按屏上说的开始——让子局实际贴 0 目；这一局下不下实体盘在开局那一刻定下并随活动会话记住，对局路由外的守卫与对局屏读同一个值（9/13 路不再被整屏拦去标定）；提示音只剩一把开关（全局 `audioPrefs` 的 `sfx`）；屏 04 底部说明与用时副标如实；首页「本地对局」卡片在游客态直接说要登录并给出路。

**覆盖 spec 条目**：§3.5（落子方式判定）、§4.1（屏 04）、§4.2（屏 02 仅 `mode === 'free'`）、§4.3 前半（首页游客卡片提示）。问题 P3、P8、P9、P10（屏 04 文案部分）、P11。

**切片顺序（垂直切片，界面有改动）**：S1-1 纯函数/守卫（无视觉）→ S1-2 提示音统一 → S1-3 屏 04 界面 → S1-4 屏 02 界面 → S1-5 首页游客卡片界面 → S1-6 四图视觉关卡 + ⏸ Fan 确认 → S1-7 真浏览器文案/贴目用例（集成验收）。本切片**没有后端/契约改动**（`komi` 字段、`game_setup` 端点都已存在），所以 Fan 确认之后直接进集成验收。

## Task 列表

### Task S1-1: 落子方式在开局那一刻定下，守卫与对局屏读同一个值

**Files:**
- Modify: `katrain/web/ui/src/kiosk/utils/activeSession.ts`（`ActiveSession` 接口约 L4-9：加 `onBoard?: boolean`；`readActiveSession` 约 L16-33 不改校验逻辑，只补一行注释）
- Modify: `katrain/web/ui/src/kiosk/utils/playInput.ts`（文件末尾，`playInputState` 之后：新增 `readSessionPlayOnBoard`）
- Modify: `katrain/web/ui/src/kiosk/components/vision/PlayInputGuard.tsx`（整个组件体约 L21-25）
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（**只动** 约 L204-207 `const [playOnBoard] = useState(readPlayOnBoard); const physicalPlay = …` 这 4 行和 import 行里的 `readPlayOnBoard`）
- Test: `katrain/web/ui/src/kiosk/__tests__/activeSession.test.ts`（追加 1 条）
- Test: `katrain/web/ui/src/kiosk/utils/playInput.test.ts`（追加 describe 块）
- Test: `katrain/web/ui/src/kiosk/__tests__/PlayInputGuard.test.tsx`（追加 3 条）

**Interfaces:**
- Consumes: `readActiveSession('game')`（`kiosk/utils/activeSession.ts`）、`readPlayOnBoard()`（`kiosk/utils/playInput.ts`）
- Produces:
  - `ActiveSession.onBoard?: boolean`（契约名）
  - `export function readSessionPlayOnBoard(pathname: string): { onBoard: boolean; fromSession: boolean }` —— 活动会话 `route` 与 `pathname`（去掉末尾 `/` 后）相等且 `onBoard` 为 boolean 时返回 `{ onBoard: s.onBoard, fromSession: true }`；否则 `{ onBoard: readPlayOnBoard(), fromSession: false }`。**本 Task 新增的辅助名，契约里没有，已在「契约冲突」登记**
  - `PlayInputGuard`：用 `useLocation().pathname` 调 `readSessionPlayOnBoard`，`onBoard` 为真才套 `PhysicalBoardGuard`
  - `GamePage` 的 `physicalPlay`：`fromSession` 为真时 = `isVisionEnabled && onBoard`；否则保持今天的三段式 `isVisionEnabled && readPlayOnBoard() && board_size === 19`

**为什么路由比较要写对**：对局路由是 `play/pvp/local/game/:sessionId`、`play/ai/game/:sessionId` 等（`KioskApp.tsx` 约 L107、L121-123），挂在 `/kiosk` 下，所以 `useLocation().pathname` 形如 `/kiosk/play/pvp/local/game/<id>`，与开局屏写入的 `route` 逐字相同。**不能**拿 `route` 去和路由模式（带 `:sessionId`）比，也**不能**只比前缀——`/kiosk/play/pvp/room/<id>` 等别的对局路由上活动会话可能是另一局，必须回落到偏好。

- [ ] **Step 1：执行时先核实行号与名字**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "export interface ActiveSession" -A 6 src/kiosk/utils/activeSession.ts
grep -n "useState(readPlayOnBoard)" -A 3 src/kiosk/pages/GamePage.tsx
grep -n "readPlayOnBoard" src/kiosk/pages/GamePage.tsx src/kiosk/components/vision/PlayInputGuard.tsx
grep -n "PlayInputGuard>" src/kiosk/KioskApp.tsx
ls src/kiosk/utils/playInput.test.ts
```
预期：接口里有 `kind/label/route/ts` 四个字段；GamePage 里 `const [playOnBoard] = useState(readPlayOnBoard);` 后跟 `const physicalPlay = isVisionEnabled` 三行；`KioskApp.tsx` 有 4 条 `<PlayInputGuard>` 路由。若 `playInput.test.ts` 不存在，Step 2 的 describe 块改为新建该文件（顶部加 `import { describe, it, expect, beforeEach } from 'vitest';`）。

- [ ] **Step 2：写失败测试（纯函数 + 存储）**

在 `src/kiosk/utils/playInput.test.ts` 顶部 import 行把 `readSessionPlayOnBoard` 加进去，并追加：

```ts
import { writeActiveSession, clearActiveSession } from './activeSession';

describe('readSessionPlayOnBoard —— 这一局落在哪儿以开局那一刻为准', () => {
  const ROUTE = '/kiosk/play/pvp/local/game/s1';
  beforeEach(() => { localStorage.removeItem(PLAY_ON_BOARD_KEY); clearActiveSession('game'); });

  it('活动会话就是当前这一局且记了 onBoard:用它,不看偏好(9 路局偏好开着也不去标定)', () => {
    writePlayOnBoard(true);
    writeActiveSession({ kind: 'game', label: 'x', route: ROUTE, ts: 1, onBoard: false });
    expect(readSessionPlayOnBoard(ROUTE)).toEqual({ onBoard: false, fromSession: true });
    expect(readSessionPlayOnBoard(`${ROUTE}/`)).toEqual({ onBoard: false, fromSession: true });
  });

  it('活动会话是另一局:回落偏好 —— 不许按前缀认成同一局', () => {
    writePlayOnBoard(true);
    writeActiveSession({ kind: 'game', label: 'x', route: ROUTE, ts: 1, onBoard: false });
    expect(readSessionPlayOnBoard('/kiosk/play/pvp/local/game/s10')).toEqual({ onBoard: true, fromSession: false });
    expect(readSessionPlayOnBoard('/kiosk/play/pvp/room/s1')).toEqual({ onBoard: true, fromSession: false });
  });

  it('旧版本写下的活动会话没有 onBoard:回落偏好', () => {
    writePlayOnBoard(false);
    writeActiveSession({ kind: 'game', label: 'x', route: ROUTE, ts: 1 });
    expect(readSessionPlayOnBoard(ROUTE)).toEqual({ onBoard: false, fromSession: false });
  });
});
```

在 `src/kiosk/__tests__/activeSession.test.ts` 的 `describe('activeSession', …)` 里追加：

```ts
  it('onBoard 可选:带着能原样读回,缺了也不判无效', () => {
    writeActiveSession({ ...sample, onBoard: false });
    expect(readActiveSession('game')).toEqual({ ...sample, onBoard: false });
    writeActiveSession(sample);
    expect(readActiveSession('game')).toEqual(sample);
  });
```

- [ ] **Step 3：跑测试，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/utils/playInput.test.ts src/kiosk/__tests__/activeSession.test.ts
```
预期：`playInput.test.ts` 失败，报 `readSessionPlayOnBoard is not a function`（或 import 不到的 SyntaxError）；`activeSession.test.ts` 新用例在运行时可能已经绿（`JSON` 原样存取），但 `npx tsc -b` 会因 `onBoard` 不在 `ActiveSession` 上报错——测试文件被 tsconfig exclude，所以类型红只会在 Step 5 实现文件里体现，这里不强求它红。

- [ ] **Step 4：实现**

`src/kiosk/utils/activeSession.ts`，接口改为：

```ts
export interface ActiveSession {
  kind: ActiveSessionKind;
  label: string;
  route: string;
  ts: number;
  /**
   * 这一局下不下实体盘 —— 开局设置屏在按下「开始对局」那一刻用 `playInputState(...).onBoard`
   * 算出来写进来(设备能用 ∧ 偏好开着 ∧ 19 路)。对局路由外的 `PlayInputGuard` 和 `GamePage`
   * 都读它,不再各自判断(v2 §3.5 / P8)。**可选**:旧版本写下的记录没有它,读的一方回落偏好。
   */
  onBoard?: boolean;
}
```

`readActiveSession` 的 `if` 校验**不加** `onBoard` 条件（缺字段不能判无效），在 `return p as ActiveSession;` 上一行加注释：`// onBoard 可选,不参与有效性判断 —— 见接口注释。`

`src/kiosk/utils/playInput.ts` 顶部加 `import { readActiveSession } from './activeSession';`，文件末尾追加：

```ts
/**
 * 「这一局到底落在哪儿」—— **开局那一刻定下的值**,不是此刻的偏好。
 *
 * 开局设置屏把 `onBoard` 随活动会话写下;对局路由外的守卫和对局屏都从这里读。
 * 只在活动会话**就是当前这条路由**时才用它:比较的是完整路径(对局路由带 `:sessionId`,
 * 前缀相同不代表是同一局)。别的情况(旧记录没有 onBoard / 活动会话是另一局 /
 * 从房间、跨平台引擎进来的局)回落到偏好 —— 那正是今天的行为。
 */
export function readSessionPlayOnBoard(pathname: string): { onBoard: boolean; fromSession: boolean } {
  const norm = (p: string) => (p.length > 1 && p.endsWith('/') ? p.slice(0, -1) : p);
  const s = readActiveSession('game');
  if (s && typeof s.onBoard === 'boolean' && norm(s.route) === norm(pathname)) {
    return { onBoard: s.onBoard, fromSession: true };
  }
  return { onBoard: readPlayOnBoard(), fromSession: false };
}
```

`src/kiosk/components/vision/PlayInputGuard.tsx` 整个文件改为（文件头注释保留，末段 ⚠️ 那句改写如下）：

```tsx
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import PhysicalBoardGuard from './PhysicalBoardGuard';
import { readSessionPlayOnBoard } from '../../utils/playInput';

/* (保留原文件头注释的前三段,把最后一段 ⚠️ 替换为:)
 * ⚠️ 读的是**开局那一刻定下的值**(`readSessionPlayOnBoard`):活动会话就是当前这一局时,
 * 用开局屏算好的 `onBoard`(设备 ∧ 偏好 ∧ 19 路)—— 9/13 路的局偏好开着也不会被拦去标定(P8);
 * 否则回落偏好。与 `GamePage` 的 `physicalPlay` 读同一个函数,两边不许给出两个答案。
 * 只在渲染时同步读,不订阅变化:这一局落在哪儿开局后不可改。
 */
const PlayInputGuard = ({ children }: { children: ReactNode }) => {
  const { pathname } = useLocation();
  return readSessionPlayOnBoard(pathname).onBoard
    ? <PhysicalBoardGuard requireRecognition sub="在实体盘上对弈，要先让摄像头看清盘面">{children}</PhysicalBoardGuard>
    : <>{children}</>;
};

export default PlayInputGuard;
```

`src/kiosk/pages/GamePage.tsx`：import 行 `import { readPlayOnBoard } from '../utils/playInput';` 改为 `import { readSessionPlayOnBoard } from '../utils/playInput';`；`react-router-dom` 那行加上 `useLocation`（`import { useLocation, useNavigate, useParams } from 'react-router-dom';`）。约 L204-207 替换为：

```tsx
  // 开局那一刻定下的值优先(见 `readSessionPlayOnBoard`),与 `PlayInputGuard` 读同一个函数。
  // 回落分支保留今天的三段式:从房间 / 跨平台引擎进来的局没有开局屏写下的 onBoard。
  const { pathname } = useLocation();
  const [playOnBoard] = useState(() => readSessionPlayOnBoard(pathname));
  const physicalPlay = isVisionEnabled && playOnBoard.onBoard && (
    playOnBoard.fromSession || (session.gameState?.board_size?.[0] ?? 19) === 19
  );
```

执行时核实：`grep -n "readPlayOnBoard" src/kiosk/pages/GamePage.tsx` 替换后应**无输出**（若还有别处使用，保留原 import 并追加新名字，不要删）。

- [ ] **Step 5：守卫组件测试（真渲染，断言挡/不挡，不断言布局）**

`src/kiosk/__tests__/PlayInputGuard.test.tsx`：import 里加 `import { clearActiveSession, writeActiveSession } from '../utils/activeSession';`；`renderGuard` 改为接收路径：

```tsx
const renderGuard = (path = '/kiosk/play/pvp/local/game/s1') => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[path]}>
      <GeometryProvider>
        <PlayInputGuard><div>对局内容</div></PlayInputGuard>
      </GeometryProvider>
    </MemoryRouter>
  </ThemeProvider>,
);
```

`beforeEach` 里补 `clearActiveSession('game');`，并在 describe 内追加：

```tsx
  // P8:9 路局偏好开着,开局屏算出 onBoard=false —— 守卫必须认开局那一刻的值。
  it('活动会话就是这一局且 onBoard=false:偏好开着也直接进对局', async () => {
    writePlayOnBoard(true);
    writeActiveSession({ kind: 'game', label: 'x', route: '/kiosk/play/pvp/local/game/s1', ts: 1, onBoard: false });
    renderGuard('/kiosk/play/pvp/local/game/s1');
    expect(await screen.findByText('对局内容')).toBeInTheDocument();
    expect(screen.queryByTestId('calib-screen')).not.toBeInTheDocument();
  });

  it('活动会话是另一局:回落偏好,照样挡', async () => {
    writePlayOnBoard(true);
    writeActiveSession({ kind: 'game', label: 'x', route: '/kiosk/play/pvp/local/game/other', ts: 1, onBoard: false });
    renderGuard('/kiosk/play/pvp/local/game/s1');
    expect(await screen.findByTestId('calib-screen')).toBeInTheDocument();
  });

  it('活动会话就是这一局且 onBoard=true:照样挡去标定', async () => {
    writePlayOnBoard(false);
    writeActiveSession({ kind: 'game', label: 'x', route: '/kiosk/play/ai/game/s1', ts: 1, onBoard: true });
    renderGuard('/kiosk/play/ai/game/s1');
    expect(await screen.findByTestId('calib-screen')).toBeInTheDocument();
  });
```

- [ ] **Step 6：跑测试 + 类型检查，确认绿**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/utils/playInput.test.ts src/kiosk/__tests__/activeSession.test.ts src/kiosk/__tests__/PlayInputGuard.test.tsx src/kiosk/__tests__/GamePage.test.tsx src/kiosk/__tests__/GamePageLedBadge.test.tsx
npx tsc -b
```
预期：全部 passed，`PlayInputGuard.test.tsx` 共 5 条（原 2 + 新 3）；`tsc -b` 无输出、exit 0。`GamePage*.test.tsx` 是回归点（它们渲染对局屏，`useLocation` 需要 Router 包裹——这两个文件已用 `MemoryRouter`，若报 `useLocation() may be used only in the context of a <Router>`，说明某条用例没包 Router，给那条补 `MemoryRouter`，不要改实现）。

- [ ] **Step 7：变异自检（证明新用例不是瞎的）**

临时把 `readSessionPlayOnBoard` 里的 `norm(s.route) === norm(pathname)` 改成 `pathname.startsWith(norm(s.route))`，重跑 `npx vitest run src/kiosk/utils/playInput.test.ts`，预期「不许按前缀认成同一局」那条红（`/game/s10` 被认成 `/game/s1`）。确认红后**手工改回**，再跑一遍确认绿，`git diff src/kiosk/utils/playInput.ts` 里不应再出现 `startsWith`。

- [ ] **Step 8：commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/utils/activeSession.ts katrain/web/ui/src/kiosk/utils/playInput.ts \
  katrain/web/ui/src/kiosk/components/vision/PlayInputGuard.tsx katrain/web/ui/src/kiosk/pages/GamePage.tsx \
  katrain/web/ui/src/kiosk/__tests__/activeSession.test.ts katrain/web/ui/src/kiosk/utils/playInput.test.ts \
  katrain/web/ui/src/kiosk/__tests__/PlayInputGuard.test.tsx
git commit -m "$(cat <<'MSG'
fix(kiosk-local): 这一局下不下实体盘在开局那一刻定下 —— 9/13 路局不再被守卫整屏拦去标定

PlayInputGuard 只读偏好,对局屏却按「设备 ∧ 偏好 ∧ 19 路」判(P8)。
开局屏把 onBoard 随活动会话写下,守卫与 GamePage 读同一个 readSessionPlayOnBoard;
路由按完整路径比较,活动会话不是当前这一局时回落偏好。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```
预期：`git show --stat HEAD` 只列上面 7 个文件。

> 注：开局屏写入 `onBoard` 在 S1-3（屏 04）和 S1-4（屏 02）里做；本 Task 结束时守卫已能读，但还没有写入方，行为与今天一致（全部回落偏好）。

### Task S1-2: 提示音只留一把 —— 对局读 `audioPrefs` 的 `sfx`，删掉 `kioskPlaySound`

**Files:**
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`（**共享区**；**只动** `playSound` 约 L53-54 那一行判断 + 顶部 import）
- Test: `katrain/web/ui/src/hooks/useGameSession.test.ts`（追加 1 个 describe）

屏 04 上 `kioskPlaySound` 的两处读写（`PvpLocalSetupPage.tsx` 约 L83、L123）在 S1-3 里一并改掉——那两处和屏 04 的开关 UI 是同一个交付物。**本 Task 结束后全仓还剩那两处 `kioskPlaySound`，S1-3 结束后必须为 0。**

**Interfaces:**
- Consumes: `readAudioPref(kind: 'sfx' | 'voice'): boolean`（`src/utils/audioPrefs.ts`，已存在；只有字面 `'false'` 算关，读不了当开）
- Produces: `useGameSession().playSound` 在 `readAudioPref('sfx') === false` 时不播放

> 修正上面 Files 的 Test 行：`playSound` **不在** hook 的返回值里（只在 ws `sound` 帧里被调用，`useGameSession.ts` 约 L89-91），所以测试新建一个文件，照 `useGameSession.navigation.test.tsx` 的 `MockWebSocket` 写法造一条 `sound` 帧。Test: **Create** `katrain/web/ui/src/hooks/useGameSession.sound.test.tsx`（不追加到 `useGameSession.test.ts`）。

- [ ] **Step 1：执行时先核实**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "kioskPlaySound" -r src tests
grep -n "msg.type === 'sound'" -A 1 src/hooks/useGameSession.ts
git ls-files src/hooks/useGameSession.sound.test.tsx
```
预期：`kioskPlaySound` 恰 3 处（`useGameSession.ts` 约 L54、`PvpLocalSetupPage.tsx` 约 L83、L123）；`sound` 帧调 `playSound(msg.data.sound)`；`git ls-files` 无输出（文件不存在，可以新建）。

- [ ] **Step 2：写失败测试** —— Create `src/hooks/useGameSession.sound.test.tsx`：

```tsx
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameSession } from './useGameSession';
import { writeAudioPref } from '../utils/audioPrefs';

vi.mock('../api', () => ({
  API: { getState: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }) },
}));

/**
 * 提示音只留一把(v2 §4.1 / P9):对局里的落子声读 `audioPrefs` 的 `sfx` ——
 * 和设置屏「落子音效」、屏 04「落子提示音」是同一把。以前读的是另一把 `kioskPlaySound`,
 * 设置里关了、对局照样响。
 */
let lastWs: { onmessage: ((e: MessageEvent) => void) | null } | null = null;
class MockWebSocket {
  static OPEN = 1;
  readyState = 1;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor() { lastWs = this; }
}
const play = vi.fn(() => Promise.resolve());
class MockAudio { currentTime = 0; play = play; }

async function sendSoundFrame() {
  const { result } = renderHook(() => useGameSession({ token: 't' }));
  act(() => result.current.setSessionId('s1'));
  await waitFor(() => expect(lastWs?.onmessage).toBeTruthy());
  act(() => lastWs!.onmessage!({ data: JSON.stringify({ type: 'sound', data: { sound: 'stone1' } }) } as MessageEvent));
}

describe('useGameSession 落子声读全局 sfx 开关', () => {
  beforeEach(() => {
    vi.clearAllMocks(); lastWs = null;
    localStorage.removeItem('kiosk_audio_sfx'); localStorage.removeItem('kioskPlaySound');
    vi.stubGlobal('WebSocket', MockWebSocket); vi.stubGlobal('Audio', MockAudio);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('设置里把音效关了:对局不出声', async () => {
    writeAudioPref('sfx', false);
    await sendSoundFrame();
    expect(play).not.toHaveBeenCalled();
  });

  it('音效开着:旧键 kioskPlaySound=0 残留也不再静音(那把键已删)', async () => {
    writeAudioPref('sfx', true);
    localStorage.setItem('kioskPlaySound', '0');
    await sendSoundFrame();
    expect(play).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3：跑，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/hooks/useGameSession.sound.test.tsx
```
预期：2 条都红——第一条 `play` 被调用了 1 次（今天只看 `kioskPlaySound`）；第二条 `play` 被调用 0 次（旧键 `'0'` 仍在静音）。

- [ ] **Step 4：实现** —— `src/hooks/useGameSession.ts`

顶部 import 区追加（`utils/audioPrefs.ts` 在共享区，共享区互相 import 不越界）：

```ts
import { readAudioPref } from '../utils/audioPrefs';
```

`playSound` 里约 L54 这一行：

```ts
        if (typeof localStorage !== 'undefined' && localStorage.getItem('kioskPlaySound') === '0') return;
```

替换为：

```ts
        // 提示音只留一把:设置屏「落子音效」、屏 04「落子提示音」、这里读的都是 audioPrefs 的 sfx
        // (v2 §4.1)。galaxy 也走这个 hook —— 它从不写这把键,readAudioPref 缺键当开,行为不变。
        if (!readAudioPref('sfx')) return;
```

- [ ] **Step 5：跑，确认绿 + 共享区两个构建**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/hooks/useGameSession.sound.test.tsx src/hooks/useGameSession.test.ts src/hooks/useGameSession.navigation.test.tsx src/utils/audioPrefs.test.ts
npx tsc -b
npm run build
npm run build:kiosk-2d
```
预期：vitest 全部 passed（新文件 2 条）；`tsc -b` exit 0；两个构建都成功，`build:kiosk-2d` 末尾 `verify:kiosk-2d` exit 0（无 `THREE.` / `@react-three` 命中）。

- [ ] **Step 6：commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/hooks/useGameSession.sound.test.tsx
git status --short katrain/web/ui/src/hooks/useGameSession.sound.test.tsx
git commit -m "$(cat <<'MSG'
fix(kiosk-local): 对局落子声读全局音效开关 —— 设置里关了对局照样响

useGameSession.playSound 只读 kioskPlaySound,设置屏写的是 audioPrefs 的 sfx(P9)。
改读 readAudioPref('sfx');galaxy 从不写这把键,缺键当开,行为不变。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```
预期：`git status --short` 那一行在 add 之后显示 `A `（确认新文件没被 `.gitignore` 吞掉）；`git show --stat HEAD` 恰 2 个文件。

### Task S1-3: 屏 04 本地对局开局设置 —— 让子贴 0、写下 onBoard、提示音一把、用时副标与底部说明如实

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx`
  - 约 L82-83：`confirmSound` 的 state（删）
  - 约 L119-145：`handleStart`（删 `kioskPlaySound` 写入；`komi` 按让子取 0；`writeActiveSession` 带 `onBoard`）
  - 约 L343：用时轨 `meta`（改稿子原文 `tmpl:865`）
  - 约 L348-361：提示音 `OptionChips`（改读写 `audioPrefs`，改 hint）
  - 约 L367-377：`.setnote`（改如实说明）
  - 文件头注释约 L28-43 的 ①（那段理由在 S2 撤键后不再成立，改写）
- Test: `katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx`（改 `activeSession` mock、改 L167 起那条说明用例、追加 4 条）

**Interfaces:**
- Consumes: `readAudioPref('sfx')` / `writeAudioPref('sfx', v)` / `subscribeAudioPref`（`src/utils/audioPrefs.ts`）；`playInputState(...).onBoard`（`kiosk/utils/playInput.ts`）；`ActiveSession.onBoard?`（S1-1 产出）
- Produces（行为）：
  - `API.gameSetup(id, 'pvp_local', { …, komi: handicap > 0 ? 0 : komi, … })`
  - `writeActiveSession({ kind: 'game', label, route: '/kiosk/play/pvp/local/game/<id>', ts, onBoard: playInput.onBoard })`
  - 屏上提示音开关的选中态 = `readAudioPref('sfx')`，点击立即 `writeAudioPref('sfx', …)`（不再等到按「开始对局」才写）
  - 全仓 `kioskPlaySound` 出现次数 = 0
- 新增 i18n key（S5 补 11 语言）：`local:sound_hint_shared`、`local:clock_meta_shared`、`local:note2_a`…`local:note2_h`（见 Step 4）。旧 key `local:sound_hint`、`local:clock_meta`、`local:note_a`…`local:note_h` 在本文件里不再使用（po 里本来就是 0 条，P19）。

**说明文案的依据（写进步骤，不是愿望）**：新说明「不给提示、不看形势；双方各停一手后自动数子，由 AI 估算胜负」**要等 S2 合入才成立**——S2 撤掉「领地」「AI 支招」（§3.1）并做双 pass 自动数子（§3.4）。本 Task 先改文案，S1 与 S2 都合进之前**不上板演示**（登记在「本切片的依赖与并行」）。

- [ ] **Step 1：执行时先核实**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "kioskPlaySound\|confirmSound\|komi,\|local:clock_meta\|local:sound_hint\|setup-note\|local:note_" src/kiosk/pages/PvpLocalSetupPage.tsx
grep -n "vi.mock('../utils/activeSession'" src/kiosk/pages/PvpLocalSetupPage.test.tsx
grep -n "两边共用一套钟" /Users/fan/Repositories/smartbox-software/superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html
grep -n "title: '落子音效'" src/kiosk/pages/SettingsPage.tsx
```
预期：`kioskPlaySound` 2 处、`confirmSound` 若干处；测试文件 mock 行存在；稿子约 L865 有 `7 档 · <b>两边共用一套钟</b>`；设置屏那一行的标题是「落子音效」（说明文案要引用这个名字，名字不同就照实际改）。

- [ ] **Step 2：写失败测试**

`PvpLocalSetupPage.test.tsx` 顶部：mock 改为同时给出读写（S1-1 之后 `playInput.ts` 会 import `readActiveSession`）：

```tsx
const { writeActiveSession } = vi.hoisted(() => ({ writeActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession, readActiveSession: () => null, clearActiveSession: vi.fn() }));
import { readAudioPref, writeAudioPref } from '../../utils/audioPrefs';
```

`beforeEach` 里补 `localStorage.removeItem('kiosk_audio_sfx'); localStorage.removeItem('kioskPlaySound');`。

把 L167 起那条 `it('底下那段说明指的是「升降级对弈」,不是在线大厅', …)` **整条替换**为下面第 5 条，并在 describe 末尾追加 1–4：

```tsx
  // P3:屏上写「这一局不贴目」,载荷就必须是 0 —— 以前照发 6.5。
  it('让了子:送出去的 komi 是 0;调回 0 子:送出去的是那一档', async () => {
    renderPage();
    await userEvent.click(step('setup-handicap', '＋'));
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(lastSetup()[2]).toMatchObject({ handicap: 1, komi: 0 });
  });

  it('不让子:komi 仍是贴目轨上那一档(默认 6.5)', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(lastSetup()[2]).toMatchObject({ handicap: 0, komi: 6.5 });
  });

  // §3.5:这一局下不下实体盘在开局那一刻算好,随活动会话写下 —— 守卫和对局屏读它。
  it('活动会话带上开局那一刻的 onBoard:19 路标定过为 true,9 路为 false', async () => {
    vision.enabled = true;
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(writeActiveSession).toHaveBeenCalled());
    expect(writeActiveSession.mock.calls[0][0]).toMatchObject({ route: '/kiosk/play/pvp/local/game/s1', onBoard: true });

    writeActiveSession.mockClear();
    await userEvent.click(within(screen.getByTestId('setup-size')).getByRole('button', { name: '9 路' }));
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(writeActiveSession).toHaveBeenCalled());
    expect(writeActiveSession.mock.calls[0][0]).toMatchObject({ onBoard: false });
  });

  // P9:提示音只留一把 —— 屏 04 这颗和设置屏「落子音效」是同一把 audioPrefs sfx。
  it('提示音开关读写全局 sfx,点下去立即生效,不再写 kioskPlaySound', async () => {
    writeAudioPref('sfx', false);
    renderPage();
    const chips = within(screen.getByTestId('setup-sound'));
    expect(chips.getByRole('button', { name: '关' })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(chips.getByRole('button', { name: '开' }));
    expect(readAudioPref('sfx')).toBe(true);
    await userEvent.click(screen.getByRole('button', { name: /开始对局/ }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalled());
    expect(localStorage.getItem('kioskPlaySound')).toBeNull();
    expect(screen.getByTestId('setup-sound-group')).toHaveTextContent('和设置里的「落子音效」是同一个开关');
  });

  // P10/P11:说明要说实际发生的事 —— 没有死子交互,数子是 AI 估算;段位只在升降级对弈改。
  it('底下那段说明如实:自动数子由 AI 估算,不说「两人自己确认死活」,也不指去在线大厅', () => {
    renderPage();
    const note = screen.getByTestId('setup-note');
    expect(note).toHaveTextContent('双方各停一手后自动数子');
    expect(note).toHaveTextContent('由 AI 估算胜负');
    expect(note).toHaveTextContent('只留档,不动段位');
    expect(note).toHaveTextContent('升降级对弈');
    expect(note).not.toHaveTextContent('自己确认');
    expect(note).not.toHaveTextContent('在线大厅');
    // 用时副标照稿子原文(tmpl:865)
    expect(screen.getByTestId('setup-clock-group')).toHaveTextContent('两边共用一套钟');
  });
```

> `OptionChips` 的选项按钮是否带 `aria-pressed`：执行时 `grep -n "aria-pressed" src/kiosk/components/common/OptionChips.tsx`。若没有，把上面两处 `toHaveAttribute('aria-pressed', 'true')` 改成该组件实际表达选中的属性（照该文件已有测试 `src/kiosk/__tests__/OptionChips.test.tsx` 的断言写法），不要改组件。

- [ ] **Step 3：跑，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx
```
预期：新 5 条红——`komi` 为 6.5 而非 0；`writeActiveSession` 入参无 `onBoard`；提示音「关」未被选中（页面读的是 `kioskPlaySound`）；说明里没有「自动数子」、没有「两边共用一套钟」。其余原有用例绿。

（已核：`OptionChips` 内部渲染 `KioskOptSeg`，与「怎么落子」那组同一个组件，现有用例已用 `aria-pressed` 断言，上面的 caveat 执行时大概率不触发。）

- [ ] **Step 4：实现** —— `src/kiosk/pages/PvpLocalSetupPage.tsx`

① import：第 1 行改 `import { useMemo, useState, useSyncExternalStore } from 'react';`，并追加
`import { readAudioPref, subscribeAudioPref, writeAudioPref } from '../../utils/audioPrefs';`

② 约 L82-83 两行（注释 + `confirmSound` state）替换为：

```tsx
  // 提示音只留一把:读写全局 audioPrefs 的 sfx —— 和设置屏「落子音效」是同一把(v2 §4.1 / P9)。
  // 订阅而不是自存一份 state:两份状态迟早走散,走散的样子正是「屏上写着关、喇叭还在响」。
  const soundOn = useSyncExternalStore(subscribeAudioPref, () => readAudioPref('sfx'), () => true);
```

③ `handleStart` 里删掉 `localStorage.setItem('kioskPlaySound', …);` 那一行；`gameSetup` 载荷里 `komi,` 改为：

```tsx
        // 屏上写「已经让了 N 子,这一局不贴目」—— 载荷必须说同一件事(P3)。
        komi: handicap > 0 ? 0 : komi,
```

`writeActiveSession({ … ts: Date.now(), })` 里 `ts` 之后加：

```tsx
        // 这一局下不下实体盘,开局这一刻定下(v2 §3.5):守卫和对局屏都读它,不再各自判断。
        onBoard: playInput.onBoard,
```

④ 约 L343 用时轨：

```tsx
              meta={interpolate(t('local:clock_meta_shared', '{n} 档 · 两边共用一套钟'), { n: timeTrack.length })}
```

⑤ 约 L348-361 提示音组替换为：

```tsx
          <section className="setgrp" data-testid="setup-sound-group">
            <OptionChips
              label={t('local:move_sound', '落子提示音')}
              en="Sound"
              testId="setup-sound"
              value={soundOn ? 'on' : 'off'}
              onChange={(v) => writeAudioPref('sfx', v === 'on')}
              options={[
                { value: 'on', label: t('local:sound_on', '开') },
                { value: 'off', label: t('local:sound_off', '关') },
              ]}
              hint={t('local:sound_hint_shared', '落子和提子的声音,和设置里的「落子音效」是同一个开关')}
            />
          </section>
```

⑥ 约 L367-377 `.setnote` 替换为（`<b>` 的位置照原结构，便于视觉关卡上改措辞）：

```tsx
        <p className="setnote" data-testid="setup-note">
          {t('local:note2_a', '这一局')}
          <b>{t('local:note2_b', '不给提示、不看形势')}</b>
          {t('local:note2_c', ';双方各停一手后')}
          <b>{t('local:note2_d', '自动数子,由 AI 估算胜负')}</b>
          {t('local:note2_e', '。')}
          <br />
          {t('local:note2_f', '这一局')}
          <b>{t('local:note2_g', '只留档,不动段位')}</b>
          {t('local:note2_h', '——段位只由「升降级对弈」那条阶梯决定。')}
        </p>
```

⑦ 文件头注释 ① 段（约 L30-36，「前半句对、后半句不对…」）替换为：

```tsx
 * ① **`.setnote` 第一句**。稿子写「终局两人自己确认死活」—— 仓里没有死子交互,
 *    数子是 KataGo 目差估计(`server.py` 的 `/api/count/request`)。v2 §2 D1 撤掉对局屏的
 *    「领地」「AI 支招」,双 pass 后自动数子(§3.4)⇒ 说明改成「不给提示、不看形势;
 *    双方各停一手后自动数子,由 AI 估算胜负」。**这句话要等 v2 S2 合入才成立。**
```

⑧ 核实全仓已无旧键：

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -rn "kioskPlaySound" src tests --exclude='*.test.ts' --exclude='*.test.tsx'
```
预期：**无输出**（测试文件里保留的 `kioskPlaySound` 是「旧键残留不再静音」的反证用例，按设计存在，所以排除测试文件）。

- [ ] **Step 5：跑，确认绿**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/pages/PvpLocalSetupPage.test.tsx src/kiosk/__tests__/SettingsPage.test.tsx
npx tsc -b
npx eslint src/kiosk/pages/PvpLocalSetupPage.tsx
```
预期：vitest 全部 passed（`PvpLocalSetupPage.test.tsx` 原 10 条去 1 换 5 = 14 条）；`tsc -b` exit 0；eslint 无 error（`kiosk/**` import `src/utils/audioPrefs` 属共享区，合规）。

- [ ] **Step 6：commit**（四图在 S1-6 统一拍，本 Task 不提交任何 visual 目录下的图）

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.tsx katrain/web/ui/src/kiosk/pages/PvpLocalSetupPage.test.tsx
git commit -m "$(cat <<'MSG'
fix(kiosk-local): 屏 04 让子局实际贴 0、提示音只留一把、说明与用时副标如实

- 让子 > 0 时载荷发 komi: 0,与屏上「这一局不贴目」一致(P3)
- 开局那一刻算出的 onBoard 随活动会话写下(§3.5)
- 提示音开关读写 audioPrefs 的 sfx,删掉 kioskPlaySound(P9)
- 底部说明改为「双方各停一手后自动数子,由 AI 估算胜负」(P10/P11,依赖 S2 合入才成立)
- 用时副标改稿子原文「两边共用一套钟」(tmpl:865)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

### Task S1-4: 屏 02 自由对弈（仅 `mode === 'free'`）—— 让子贴 0、写下 onBoard

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx`（`handleStart` 约 L118-160 的**非 ranked 分支**：`gameSetup` 载荷 `komi` 约 L147、`writeActiveSession` 约 L153-158；**ranked 分支（约 L124-138，`startAiLadderGame`）一个字不动**）
- Test: `katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx`（追加 3 条，放在 L221 `calls API.createSession and gameSetup on start` 附近）

**Interfaces:**
- Consumes: `playInput`（`AiSetupPage.tsx` 约 L311 已有的 `useMemo(() => playInputState(isVisionEnabled, isRanked ? 19 : boardSize), …)`）；`ActiveSession.onBoard?`
- Produces（行为，仅 free）：`API.gameSetup(id, 'free', { …, komi: handicap > 0 ? 0 : komi })`；`writeActiveSession({ …, onBoard: playInput.onBoard })`

- [ ] **Step 1：执行时先核实**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "const handleStart" -A 45 src/kiosk/pages/AiSetupPage.tsx | grep -n "isRanked\|komi\|writeActiveSession\|onBoard"
grep -n "const playInput = useMemo" -A 3 src/kiosk/pages/AiSetupPage.tsx
grep -n "vi.mock('../utils/activeSession'\|vi.mock(.*activeSession\|useVision\|isVisionEnabled" src/kiosk/__tests__/AiSetupPage.test.tsx
grep -n "renderPage\|const render" src/kiosk/__tests__/AiSetupPage.test.tsx | head -5
```
预期：`handleStart` 里 `if (isRanked) { … return; }` 在前，之后是 free 的 `gameSetup`（载荷含 `komi,`）与 `writeActiveSession`；`playInput` 在 `handleStart` **之后**声明（约 L311）——`handleStart` 是箭头函数、调用发生在渲染之后，闭包里读 `playInput` 合法，不需要挪位置。记下测试文件里 activeSession 是否被 mock、vision 怎么 mock、渲染辅助函数叫什么，Step 2 照它的写法改名。

（已核：`AiSetupPage.test.tsx` **没有** mock `activeSession`，写入走真 localStorage；vision mock 固定 `isVisionEnabled: false`；渲染辅助是 `renderPage(mode = 'free')`；档位键辅助是 `step(testId, '＋' | '−')`。）

- [ ] **Step 2：写失败测试** —— `src/kiosk/__tests__/AiSetupPage.test.tsx` 顶部 import 追加 `import { readActiveSession, clearActiveSession } from '../utils/activeSession';`，在 `it('calls API.createSession and gameSetup on start', …)` 之后追加：

```tsx
  // P3 同形(屏 02):屏上写「这一局不贴目」,载荷就必须是 0。
  it('free:让了子送出去的 komi 是 0', async () => {
    const { API } = await import('../../api');
    vi.mocked(API.gameSetup).mockClear();
    renderPage('free');
    const user = userEvent.setup();
    await user.click(step('setup-handicap', '＋'));
    await user.click(step('setup-handicap', '＋'));
    await user.click(screen.getByRole('button', { name: /开始对局/i }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalledWith(
      'new-session-123', 'free', expect.objectContaining({ handicap: 2, komi: 0 }),
    ));
  });

  it('free:不让子时 komi 仍是贴目轨那一档', async () => {
    const { API } = await import('../../api');
    vi.mocked(API.gameSetup).mockClear();
    renderPage('free');
    await userEvent.setup().click(screen.getByRole('button', { name: /开始对局/i }));
    await waitFor(() => expect(API.gameSetup).toHaveBeenCalledWith(
      'new-session-123', 'free', expect.objectContaining({ handicap: 0, komi: 6.5 }),
    ));
  });

  // §3.5:开局那一刻的 onBoard 随活动会话写下。这台 mock 的机器没标定摄像头 ⇒ false。
  it('free:活动会话带上 onBoard(没标定摄像头 ⇒ false)', async () => {
    clearActiveSession('game');
    renderPage('free');
    await userEvent.setup().click(screen.getByRole('button', { name: /开始对局/i }));
    await waitFor(() => expect(readActiveSession('game')).toMatchObject({
      route: '/kiosk/play/ai/game/new-session-123', onBoard: false,
    }));
  });
```

执行时核实默认贴目：`grep -n "useState(6.5)" src/kiosk/pages/AiSetupPage.tsx` 预期 1 处（约 L87）；若默认值不同，把第二条的 `6.5` 改成实际值。

- [ ] **Step 3：跑，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx
```
预期：新 3 条里第 1 条红（`komi` 为 6.5）、第 3 条红（活动会话无 `onBoard`）；第 2 条今天就绿（它是回归钉，不要求红）。其余原有用例绿。

- [ ] **Step 4：实现** —— `src/kiosk/pages/AiSetupPage.tsx` 非 ranked 分支

`API.gameSetup(session_id, isRanked ? 'ranked' : 'free', { … })` 载荷里 `komi,` 改为：

```tsx
        // 屏上让了子就写「这一局不贴目」—— 载荷说同一件事(v2 §4.2 / P3)。ranked 走上面的
        // startAiLadderGame 分支,根本不经过这里。
        komi: handicap > 0 ? 0 : komi,
```

其后的 `writeActiveSession({ kind: 'game', label: …, route: …, ts: Date.now(), })` 在 `ts` 后加：

```tsx
        // 这一局下不下实体盘在开局这一刻定下(v2 §3.5),守卫与对局屏都读它。
        onBoard: playInput.onBoard,
```

**不改** ranked 分支的 `writeActiveSession`（约 L132-135）与 `handleContinue`（约 L192-197）：它们不带 `onBoard`，读的一方回落偏好 = 今天的行为（spec §4.2 只动 free）。

- [ ] **Step 5：跑，确认绿**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx
npx tsc -b
```
预期：全部 passed；`tsc -b` exit 0（若报 `playInput` used before declaration：说明 `handleStart` 不是箭头函数闭包，执行者把 `const playInput = useMemo(…)` 整块上移到 `handleStart` 之前，依赖数组不变）。

- [ ] **Step 6：commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/pages/AiSetupPage.tsx katrain/web/ui/src/kiosk/__tests__/AiSetupPage.test.tsx
git commit -m "$(cat <<'MSG'
fix(kiosk): 屏 02 自由对弈让子局实际贴 0,开局写下 onBoard

与屏 04 同形(P3、P8):让子 > 0 时载荷发 komi: 0;开局那一刻的 onBoard 随活动会话写下。
升降级分支一个字不动。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

## 切片 S2a：把一局下完，拿到正确结果（后端）

**目标**：盒上模式双方各停一手后，局面停在「等数子」而不是落账一条没有胜负的「终局」；数子门槛按路数缩放、全局生效；数子失败给出机器可读的原因码；数子端点补归属闸；本地对局认输由前端说清是哪一方认输。galaxy（非盒上模式）的双 pass 行为逐字不变。

**覆盖**：spec §3.2「后端契约 · 认输」、§3.4「后端」全部条目 + §3.4 末尾「待核实」、§6.3 后端 pytest 中除「超时」「不回填名字」外的各条、§7-3。问题 P4、P5（后端半边）、P6（后端半边）、P7、P18。

**执行时机**：本切片的四个 Task 在 **S2b 的「⏸ Fan 确认四图」通过之后**才执行（垂直切片：界面 → 视觉关卡 → Fan 确认 → 契约/后端）。S2b 的前端 Task 在确认前用隔离 fixture 驱动界面，不依赖本切片。

**全切片通用规矩（每个 Task 都适用，不再逐条重复）**

- 工作目录：`/Users/fan/Repositories/katrain-kiosk-local-play`（下文命令都从这里跑）。
- 后端测试命令一律 `CI=true uv run pytest <文件> -q`；**每跑完一次**执行 `git status --short katrain/config.json`，若输出非空（被测试改写了），执行 `git checkout -- katrain/config.json`（这是唯一允许的 checkout，只针对这个文件）。
- 改完的 Python 文件跑 `uv run black -l 120 <文件>`。
- 只 `git add` 本 Task「Files」里列出的路径；不许 `git add -A`、不许 `git stash`。
- 行号是 HEAD `1b6c67b5` 时的读数，会漂；以「函数名 + 锚点代码」定位，动手前先 `grep -n` 确认。

---

### Task S2a-1: 纯函数模块 `game_end_rules`（`scaled_count_min_moves` / `is_awaiting_count`）+ `get_state` 两个字段

**Files:**
- Create: `katrain/web/core/game_end_rules.py`
- Create: `tests/test_game_end_rules.py`
- Create: `tests/test_local_play_game_end.py`（本 Task 只写夹具 + 状态位 / 门槛两组用例；S2a-2/3/4 往里追加）
- Modify: `katrain/web/interface.py` —— 顶部 import 区（约 L24-27，`from katrain.gui.theme import Theme` 之后）；`get_state` 返回字典里 `"count_min_moves"` 那一行（约 L611，函数 `get_state` 起于约 L412）

**Interfaces:**
- Consumes：`WebKaTrain` 实例属性 `suppress_auto_eval`（`interface.py` 约 L169，`_settings.KATRAIN_MODE == "board"`）、`game_type`（`interface.py` 约 L177 默认 `"free"`，`_do_new_game` 约 L664 赋值）、`game.current_node.{is_pass, parent, end_state}`、`game.board_size`、`self.config("game/count_min_moves", 100)`。
- Produces：
  - `katrain.web.core.game_end_rules.AWAITING_COUNT_GAME_TYPES: frozenset[str]` = `{"free", "pvp_local"}`
  - `scaled_count_min_moves(base: int, board_size: int) -> int` = `max(1, round(int(base) * board_size * board_size / 361))`
  - `is_awaiting_count(iface) -> bool`
  - `get_state()` 新增 `"awaiting_count": bool`；`"count_min_moves"` 改为缩放值（19→100、13→47、9→22，base=100）
  - 测试夹具 `client`、`_owned_game(client, monkeypatch, *, game_type, board_mode, size=19, base=100, user_id=OWNER.id)`、`_move(client, sid, coords=None)`、`_recorded_results(client)`（供 S2a-2/3/4 复用）

> **与契约的一处偏离（已写进「契约冲突」）**：契约 §后端 `is_awaiting_count` 写了五条件，第 5 条「`game.manual_score` 为空」**不实现**。`Game.manual_score`（`katrain/core/game.py` 约 L330-340）不是「有人手工定过结果」，而是由 `current_node.score` 现算的估计串（`"B+3.0?"`）；数子恰恰要等这份分数（`_complete_count` 在 `score is None` 时 400）。把它当条件，分析一回来 `awaiting_count` 就翻成假，自动数子会被「已终局」拒掉。本 Task 用一条变异闸钉住这一点（`test_arrived_analysis_does_not_end_the_wait`）。若 integrator 裁定必须保留第 5 条，删掉该用例并把条件加回，但 S2a-4 的 `test_board_mode_double_pass_counts_without_threshold_once_analysis_arrives` 会红——那就是这条冲突的实证。

- [ ] **Step 1：执行时先核实三处前提**（只读，不改文件）

```bash
grep -n "self.suppress_auto_eval = \|self.game_type = " katrain/web/interface.py
grep -n "def manual_score" -A11 katrain/core/game.py
ls katrain/web/core/game_end_rules.py tests/test_game_end_rules.py tests/test_local_play_game_end.py 2>&1
```

预期：第一条命中 `self.suppress_auto_eval = _settings.KATRAIN_MODE == "board"` 与 `self.game_type = "free"` / `self.game_type = game_type if game_type is not None else "free"`；第二条可见 `return self.current_node.format_score(...) + "?"`；第三条三个文件都 `No such file or directory`（若已存在，先 `git log --oneline -- <文件>` 看是谁建的，停下报告，不要覆盖）。

- [ ] **Step 2：写纯函数单测（先红）** —— 新建 `tests/test_game_end_rules.py`，内容完整如下：

```python
"""`katrain/web/core/game_end_rules.py` 的纯函数。

`is_awaiting_count` 在这里用假对象测条件组合；「真 WebKaTrain + 真 HTTP」那一侧在
`tests/test_local_play_game_end.py`。
"""

from types import SimpleNamespace

import pytest

from katrain.web.core.game_end_rules import is_awaiting_count, scaled_count_min_moves


@pytest.mark.parametrize(
    "base, size, expected",
    [
        (100, 19, 100),
        (100, 13, 47),
        (100, 9, 22),
        (10, 9, 2),  # 开发机 ~/.katrain/config.json 里真有 count_min_moves=10
        (0, 19, 1),  # 配置成 0 = 不设门槛；history 含根节点，恒 ≥ 1
    ],
)
def test_scaled_count_min_moves(base, size, expected):
    assert scaled_count_min_moves(base, size) == expected


def _node(is_pass, parent=None, end_state=None):
    return SimpleNamespace(is_pass=is_pass, parent=parent, end_state=end_state)


def _iface(*, suppress=True, game_type="pvp_local", current=None, manual_score=None):
    root = _node(None)  # 根节点没有着手：GameNode.is_pass 返回 None
    if current is None:
        current = _node(True, parent=_node(True, parent=root))
    game = SimpleNamespace(current_node=current, manual_score=manual_score)
    return SimpleNamespace(suppress_auto_eval=suppress, game_type=game_type, game=game)


@pytest.mark.parametrize("game_type", ["free", "pvp_local"])
def test_double_pass_in_board_mode_awaits_count(game_type):
    assert is_awaiting_count(_iface(game_type=game_type)) is True


def test_galaxy_never_awaits_count():
    assert is_awaiting_count(_iface(suppress=False)) is False


def test_missing_suppress_flag_counts_as_galaxy():
    iface = _iface()
    del iface.suppress_auto_eval
    assert is_awaiting_count(iface) is False


@pytest.mark.parametrize("game_type", ["ai_ladder_ranked", "rated", "ranked"])
def test_scoring_game_types_are_untouched(game_type):
    assert is_awaiting_count(_iface(game_type=game_type)) is False


def test_single_pass_after_a_stone_does_not_await():
    root = _node(None)
    current = _node(True, parent=_node(False, parent=root))
    assert is_awaiting_count(_iface(current=current)) is False


def test_pass_right_after_root_does_not_await():
    current = _node(True, parent=_node(None))
    assert is_awaiting_count(_iface(current=current)) is False


def test_root_node_does_not_await():
    assert is_awaiting_count(_iface(current=_node(None))) is False


@pytest.mark.parametrize("end_state", ["W+R", "B+T", "B+3.5"])
def test_a_real_result_ends_the_wait(end_state):
    root = _node(None)
    current = _node(True, parent=_node(True, parent=root), end_state=end_state)
    assert is_awaiting_count(_iface(current=current)) is False


def test_arrived_analysis_does_not_end_the_wait():
    """变异闸：把 `game.manual_score` 加回条件，这一格必须红。

    manual_score 是由 `current_node.score` 现算的估计，分析一回来就是 "黑+3.0?" 这种串；
    而数子恰恰要等这份分析。它若是条件，自动数子永远在「分析到了」那一刻被判成已终局。
    """
    assert is_awaiting_count(_iface(manual_score="黑+3.0?")) is True


def test_no_game_does_not_await():
    iface = _iface()
    iface.game = None
    assert is_awaiting_count(iface) is False
```

- [ ] **Step 3：跑，确认红**

```bash
CI=true uv run pytest tests/test_game_end_rules.py -q
```

预期：收集阶段 `ModuleNotFoundError: No module named 'katrain.web.core.game_end_rules'`（1 error）。

- [ ] **Step 4：实现模块** —— 新建 `katrain/web/core/game_end_rules.py`，内容完整如下（不 import server / session / interface）：

```python
"""终局判定的纯函数 —— 数子门槛怎么随路数缩放、这一局是不是停在「等数子」。

不 import server / session / interface：调用方把 `WebKaTrain` 实例（`session.katrain`）传进来，
这里只读它身上的属性。这样 `get_state`、`/api/move` 的双 pass 钩子和 `/api/count/request`
三处读到的是同一个判定，而不是三份各写各的条件。
"""

#: 盒上模式里「双方各停一手之后该自动数子」的对局类型。升降级（`ai_ladder_ranked`）与
#: 两种反作弊局（`rated` / `ranked`）不在里面：它们的终局今天怎么落账，本轮不动。
AWAITING_COUNT_GAME_TYPES = frozenset({"free", "pvp_local"})


def scaled_count_min_moves(base: int, board_size: int) -> int:
    """手动数子的最少手数，按棋盘面积从 19 路的 `base` 缩放。

    base=100 时 19 路 100、13 路 47、9 路 22。`max(1, …)` 让配置成 0 的「不设门槛」
    仍然成立：比较对象 `len(state["history"])` 含根节点，恒 ≥ 1。
    n < 19 时 base·n²/361 不可能恰好落在 .5 上（361 = 19²，与 n² 互素），
    所以 Python 的银行家舍入与前端 Math.round 不会分叉。
    """
    return max(1, round(int(base) * board_size * board_size / 361))


def is_awaiting_count(iface) -> bool:
    """这一局是不是停在「双方各停一手、还没数子」。

    四条同时成立才为真：
      1. 盒上模式（`suppress_auto_eval`）—— galaxy 走不到；
      2. 对局类型是自由对弈或本地对局；
      3. 当前节点和父节点都是 pass；
      4. 当前节点没被认输 / 超时 / 数子写过 `end_state`。

    **不看 `game.manual_score`**：它不是「有人手工定过结果」，而是由 `current_node.score`
    现算的估计（`katrain/core/game.py` 的 `manual_score` 属性）。数子要的正是这份分数
    （`server.py` `_complete_count` 在 score 为 None 时 400），所以分析一回来 manual_score
    就不再为空 —— 把它当条件，数子能成功的那一刻这里恰好翻成假，自动数子会被「已终局」拒掉。
    """
    if not getattr(iface, "suppress_auto_eval", False):
        return False
    if getattr(iface, "game_type", "free") not in AWAITING_COUNT_GAME_TYPES:
        return False
    game = getattr(iface, "game", None)
    if game is None:
        return False
    node = game.current_node
    parent = node.parent
    if parent is None or not node.is_pass or not parent.is_pass:
        return False
    return not node.end_state
```

- [ ] **Step 5：跑，确认绿**

```bash
CI=true uv run pytest tests/test_game_end_rules.py -q
git status --short katrain/config.json
```

预期：`20 passed`（5 + 2 + 1 + 1 + 3 + 1 + 1 + 1 + 3 + 1 + 1）；第二条无输出。

- [ ] **Step 6：变异自检（钉住「不看 manual_score」）** —— 临时在 `is_awaiting_count` 最后一行改成 `return not node.end_state and not game.manual_score`，跑同一条命令，预期**恰好** `test_arrived_analysis_does_not_end_the_wait` 1 failed；随后把这一行改回 `return not node.end_state`，再跑一次回到全绿。用 `grep -n "return not node.end_state" katrain/web/core/game_end_rules.py` 回读确认已还原（不要用 git checkout 还原）。

- [ ] **Step 7：写 HTTP 集成测试的夹具与状态位用例（先红）** —— 新建 `tests/test_local_play_game_end.py`。夹具照 `tests/test_local_play_setup.py` 的写法（kivymd 主线程预热、`isolated_session_factory` 在进 `TestClient` 前设、`user_game_repo` 用 MagicMock 观察落账）。内容如下（S2a-2/3/4 会在文件末尾继续追加各自的分区）：

```python
"""本地对局 v2 · 终局契约（spec §3.2 认输、§3.4 双 pass 与数子）。

全部走真 `WebKaTrain` + 真 HTTP。落账由 `app.state.user_game_repo` 的 MagicMock 观察：
server 模式的 lifespan 不设 `repository_dispatcher`，`_record_ai_game` 于是走
`app.state.user_game_repo.create(user_id=..., **data)`。

**盒上模式靠 `session.katrain.suppress_auto_eval = True` 模拟**：生产里它由
`settings.KATRAIN_MODE == "board"` 在 `WebKaTrain.__init__` 设（interface.py），
这里建完会话再直接设，免得改进程级 settings。

**`save_config` 必须打桩**：`manager.create_session` 建的 `WebKaTrain` 是
`force_package_config=False`，`/api/game/setup`、`/api/new-game` 里的 `update_config`
会把 `~/.katrain/config.json` 改掉（2026-09-14 实测：跑一次 `test_guest_free_play.py`
就把开发机的 komi/rules 改了）。
"""

# Warm up the real kivy/kivymd Window singleton on the MAIN thread before any
# TestClient request runs — same reason as tests/test_local_play_setup.py: kivymd's
# first import from Starlette's background portal thread creates a real SDL2/Cocoa
# window off the main thread and aborts the process on macOS.
import kivymd.app  # noqa: F401

import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.server import create_app

OWNER = types.SimpleNamespace(id=7, username="owner", uuid="u-7")
STRANGER = types.SimpleNamespace(id=999, username="stranger", uuid="u-999")
HUMAN = {"name": "", "player_type": "player:human", "player_subtype": "player:human"}


@pytest.fixture
def client(isolated_session_factory):
    app = create_app(enable_engine=False)
    # 必须在进 `TestClient` **之前**设：lifespan 会用它建全部 repo 并跑 `init_db()`。
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        c.app.state.user_game_repo = MagicMock()
        c.app.state.repository_dispatcher = None
        c.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
        yield c
        c.app.dependency_overrides.clear()
        # 会话是进程级的，不收掉会连同引擎活到本次 pytest 结束（见 test_guest_free_play.py）。
        for session in list(c.app.state.session_manager._sessions.values()):
            c.app.state.session_manager.remove_session(session.session_id)


def _owned_game(client, monkeypatch, *, game_type, board_mode, size=19, base=100, user_id=OWNER.id):
    """建一个归 OWNER 的会话并开局。两边都坐人：有 AI 座位会起 genmove 后台线程，活得比用例长。"""
    session = client.app.state.session_manager.create_session(user_id=user_id)
    monkeypatch.setattr(session.katrain, "save_config", lambda *a, **k: None)
    session.katrain.suppress_auto_eval = board_mode
    sid = session.session_id
    if game_type == "pvp_local":
        r = client.post(
            "/api/game/setup",
            json={
                "session_id": sid,
                "mode": "pvp_local",
                "settings": {
                    "board_size": size,
                    "rules": "chinese",
                    "handicap": 0,
                    "komi": 7.5,
                    "black_name": "",
                    "white_name": "",
                    "time_enabled": False,
                },
            },
        )
    else:
        r = client.post(
            "/api/new-game",
            json={
                "session_id": sid,
                "size": size,
                "rules": "chinese",
                "komi": 7.5,
                "players": {"B": HUMAN, "W": HUMAN},
            },
        )
    assert r.status_code == 200, r.text
    # 显式钉住门槛基数：开发机 ~/.katrain/config.json 里真有 count_min_moves=10。
    session.katrain.update_config("game/count_min_moves", base)
    return session


def _move(client, sid, coords=None):
    r = client.post("/api/move", json={"session_id": sid, "coords": coords, "pass_move": coords is None})
    assert r.status_code == 200, r.text
    return r.json()["state"]


def _recorded_results(client):
    return [call.kwargs["result"] for call in client.app.state.user_game_repo.create.call_args_list]


# ------------------------------------------------------------------ 状态位与门槛下发（§3.4）


@pytest.mark.parametrize("game_type", ["pvp_local", "free"])
def test_board_mode_double_pass_sets_awaiting_count(client, monkeypatch, game_type):
    session = _owned_game(client, monkeypatch, game_type=game_type, board_mode=True)
    _move(client, session.session_id, [3, 3])
    first = _move(client, session.session_id)
    assert first["awaiting_count"] is False  # 只停了一手

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is True
    assert state["end_result"]  # 回落串「终局」照样非空 —— 前端必须以 awaiting_count 为准


def test_galaxy_double_pass_never_sets_awaiting_count(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False


@pytest.mark.parametrize("size, expected", [(19, 100), (13, 47), (9, 22)])
def test_state_count_min_moves_scales_with_board_size(client, monkeypatch, size, expected):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, size=size, base=100)

    state = session.katrain.get_state()

    assert state["board_size"] == [size, size]
    assert state["count_min_moves"] == expected


```

- [ ] **Step 8：跑，确认红**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q
git status --short katrain/config.json
```

预期：`test_board_mode_double_pass_sets_awaiting_count[*]` 与 `test_galaxy_double_pass_never_sets_awaiting_count` 以 `KeyError: 'awaiting_count'` 失败（3 failed）；`test_state_count_min_moves_scales_with_board_size[13-47]`、`[9-22]` 断言 `100 == 47` / `100 == 22` 失败（2 failed）；`[19-100]` 通过。合计 `5 failed, 1 passed`。若是 kivy / 数据库相关的收集错误而不是上面这些，先对照 `tests/test_local_play_setup.py` 的夹具找差异，不要改被测代码。

- [ ] **Step 9：改 `get_state`** —— `katrain/web/interface.py`：

在 import 区 `from katrain.gui.theme import Theme` 之后加一行：

```python
from katrain.web.core.game_end_rules import is_awaiting_count, scaled_count_min_moves
```

把 `get_state` 返回字典里这一行（约 L611）：

```python
            "count_min_moves": self.config("game/count_min_moves", 100),
```

替换为：

```python
            # 按路数缩放（19 路 100、13 路 47、9 路 22）。`/api/count/request` 的门槛用同一个函数。
            "count_min_moves": scaled_count_min_moves(
                self.config("game/count_min_moves", 100), self.game.board_size[0]
            ),
            # 盒上模式双方各停一手、还没数子。为真时 `end_result` 照样非空（"终局"，或分析到了之后
            # 的 "B+3.0?" 估计串），前端要以这一位为准去数子，而不是把 end_result 当成终局结果。
            "awaiting_count": is_awaiting_count(self),
```

执行时先核实：`grep -n "self.game.board_size\|board_size" katrain/web/interface.py | sed -n 1,8p` 预期 `get_state` 里已有 `"board_size": self.game.board_size` 之类的用法（`Game.board_size` 是 `(x, y)` 元组，`katrain/core/game.py` 约 L305-306 返回 `self.root.board_size`）。

- [ ] **Step 10：跑，确认绿 + 相邻回归**

```bash
CI=true uv run pytest tests/test_game_end_rules.py tests/test_local_play_game_end.py -q
CI=true uv run pytest tests/test_local_play_setup.py tests/test_local_play_recording.py -q
git status --short katrain/config.json
```

预期：第一条 `26 passed`（20 + 6）；第二条与改动前同样全绿（执行者在 Step 1 之后、改代码之前先跑一次第二条记下 passed 数，这里数字必须相同）；第三条无输出。

- [ ] **Step 11：格式化**

```bash
uv run black -l 120 katrain/web/core/game_end_rules.py katrain/web/interface.py tests/test_game_end_rules.py tests/test_local_play_game_end.py
```

预期：`interface.py` 若报 reformatted，`git diff katrain/web/interface.py` 只能出现本 Task 的两处改动；多出别处的改动说明 black 版本不一致，撤掉那些格式化（手工还原），只保留本 Task 的改动。

- [ ] **Step 12：提交**

```bash
git add katrain/web/core/game_end_rules.py katrain/web/interface.py tests/test_game_end_rules.py tests/test_local_play_game_end.py
git commit -m "$(cat <<'MSG'
feat(kiosk-local): 盒上双 pass 停在「等数子」—— get_state 下发 awaiting_count 与按路数缩放的数子门槛

纯函数放 katrain/web/core/game_end_rules.py：scaled_count_min_moves 按 n²/361 缩放
（19 路 100、13 路 47、9 路 22），is_awaiting_count 不看 game.manual_score——
它是由分析分数现算的估计串，当条件会让数子在分析到达那一刻被判成已终局。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

### Task S2a-2: 认输契约（`ResignRequest` / `_do_resign(color)` / `/api/resign`）

**Files:**
- Modify: `katrain/web/models.py` —— 第 1 行 typing import；`class ToggleAnalysisRequest`（约 L87-88）之后新增类
- Modify: `katrain/web/interface.py` —— `def _do_resign(self)`（约 L1464-1465）
- Modify: `katrain/web/server.py` —— `async def resign`（约 L1874-1954）：签名一行、`guard_session_terminator(session, current_user, "resign")` 之后插入校验、`session.katrain("resign")` 那个 `else:` 分支
- Test: `tests/test_local_play_game_end.py`（末尾追加「认输」分区）

**Interfaces:**
- Consumes：`session.game_type`（`server.py` `/api/game/setup` 的 pvp_local 分支约 L1235 设 `session.game_type = "pvp_local"`；`free` 分支约 L1092 设 `"free"`；未设时 `getattr(..., "free")`）；`WebKaTrain.__call__(message, *args, **kwargs)`（`interface.py` 约 L915）把 kwargs 转给 `_do_<message>`。
- Produces：
  - `class ResignRequest(BaseModel)`：`session_id: str`；`color: Optional[Literal["B", "W"]] = None`（`color` = **认输的一方**）
  - `WebKaTrain._do_resign(self, color=None) -> None`：`color` 给定 → `end_state = f"{对方}+R"`；不给 → 保持 `f"{current_node.player}+R"`
  - `POST /api/resign` 请求体改为 `ResignRequest`：`pvp_local` 不带 color → 400 `"color is required to resign a local two-player game"`；非 `pvp_local` 带 color → 400 `"color is only accepted for local two-player games"`；两种 400 都在任何状态改动之前返回。其余行为不变。（这两个 400 的 detail 保持字符串：前端 S2b 只在本地对局发 color，不需要按码分支。）

- [ ] **Step 1：执行时先核实**

```bash
grep -n "def __call__" -A30 katrain/web/interface.py | grep -n "_do_\|kwargs"
grep -n 'session.game_type = "pvp_local"\|session.game_type = "free"' katrain/web/server.py
grep -rn "ToggleAnalysisRequest" katrain/web/server.py | grep -n "resign"
```

预期：第一条可见 `getattr(self, method_name)(*args, **kwargs)`（HEAD 时约 L931，已核实会转发 kwargs 并随后 `update_state()`）；第二条两处都命中；第三条命中 `async def resign(request: ToggleAnalysisRequest`。

- [ ] **Step 2：追加认输用例（先红）** —— 在 `tests/test_local_play_game_end.py` 末尾追加：

```python
# ------------------------------------------------------------------ 认输（§3.2）


@pytest.mark.parametrize(
    "stones, color, expected",
    [
        ([], "W", "B+R"),  # 开局即认输：今天会判「落最后一手的一方」胜 = W+R
        ([[3, 3]], "B", "W+R"),  # 黑下一手后黑认输：今天会判 B+R
    ],
)
def test_local_resign_scores_the_named_side(client, monkeypatch, stones, color, expected):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True)
    for coords in stones:
        _move(client, session.session_id, coords)

    r = client.post("/api/resign", json={"session_id": session.session_id, "color": color})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["end_result"] == expected
    assert _recorded_results(client) == [expected]


def test_local_resign_without_color_is_rejected_before_mutation(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert session.katrain.game.current_node.end_state is None
    assert _recorded_results(client) == []


def test_free_resign_with_color_is_rejected(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id, "color": "B"})

    assert r.status_code == 400, r.text
    assert session.katrain.game.current_node.end_state is None


def test_free_resign_without_color_is_unchanged(client, monkeypatch):
    """正对照：其它模式不带 color，行为与今天一致（落最后一手的一方胜）。"""
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])

    r = client.post("/api/resign", json={"session_id": session.session_id})

    assert r.status_code == 200, r.text
    assert r.json()["state"]["end_result"] == "B+R"
    assert _recorded_results(client) == ["B+R"]


```

- [ ] **Step 3：跑，确认红**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q -k resign
git status --short katrain/config.json
```

预期：`test_local_resign_scores_the_named_side[stones0-W-B+R]` 得到 `W+R`、`[stones1-B-W+R]` 得到 `B+R`（2 failed：今天判负的是轮到走的一方）；`test_local_resign_without_color_is_rejected_before_mutation` 得到 200（failed）；`test_free_resign_with_color_is_rejected` 得到 200（failed，pydantic 默认忽略多余字段）；`test_free_resign_without_color_is_unchanged` passed。合计 `4 failed, 1 passed`。

- [ ] **Step 4：加请求模型** —— `katrain/web/models.py`：

第 1 行改为：

```python
from typing import Any, Dict, List, Literal, Optional, Union
```

在 `class ToggleAnalysisRequest(BaseModel):` 整个类（`session_id: str` 那一行）之后插入：

```python


class ResignRequest(BaseModel):
    """`/api/resign` 的请求体。`color` 是**认输的一方**。

    本地对局（`pvp_local`）两个人共用一块屏，「轮到谁」不等于「谁按的键」，所以必须说清是哪一方
    认输；其它模式不收它（服务端从座位推），带了就 400，免得被静默忽略。
    单独一个模型、不往共享的 `ToggleAnalysisRequest` 里加字段：那个模型被十几个端点共用。
    """

    session_id: str
    color: Optional[Literal["B", "W"]] = None
```

（`server.py` 第 34 行是 `from katrain.web.models import *`，不用改 import。）

- [ ] **Step 5：改 `_do_resign`** —— `katrain/web/interface.py`，把

```python
    def _do_resign(self):
        self.game.current_node.end_state = f"{self.game.current_node.player}+R"
```

替换为：

```python
    def _do_resign(self, color=None):
        """认输。`color` 是认输的一方；不给时保持旧行为（`current_node.player` 胜，即落最后一手的一方）。"""
        if color is None:
            self.game.current_node.end_state = f"{self.game.current_node.player}+R"
            return
        winner = "W" if color == "B" else "B"
        self.game.current_node.end_state = f"{winner}+R"
```

- [ ] **Step 6：改 `/api/resign`** —— `katrain/web/server.py` 的 `async def resign`：

签名一行 `async def resign(request: ToggleAnalysisRequest, current_user: User = Depends(get_current_user_optional)):` 把 `ToggleAnalysisRequest` 换成 `ResignRequest`。

紧跟在 `guard_session_terminator(session, current_user, "resign")` 之后（`ranked_ai = is_ai_ladder_ranked_session(session)` 之前）插入：

```python
        # 本地对局两人共用一块屏：「轮到谁」不等于「谁按的键」，认输必须说清是哪一方。
        # 其它模式由服务端从座位推，带了 color 就拒，免得被静默忽略。两个 400 都在任何状态改动之前。
        local_pvp = getattr(session, "game_type", "free") == "pvp_local"
        if local_pvp and request.color is None:
            raise HTTPException(status_code=400, detail="color is required to resign a local two-player game")
        if not local_pvp and request.color is not None:
            raise HTTPException(status_code=400, detail="color is only accepted for local two-player games")
```

把 `with session.lock:` 里的

```python
                else:
                    session.katrain("resign")
```

替换为（不带 color 时调用形式与今天逐字一致）：

```python
                elif request.color is None:
                    session.katrain("resign")
                else:
                    session.katrain("resign", color=request.color)
```

- [ ] **Step 7：跑，确认绿 + 端点回归（按名字集合比，不按条数）**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q
git status --short katrain/config.json
```

预期：`31 passed`（S2a-1 的 26 + 本 Task 5）；无 config 改动。

回归：动 `/api/resign` 的既有测试文件是下面这 5 个（HEAD 时 `grep -rln '/api/resign' tests` 核实过）。此刻本 Task 的改动还没提交，`HEAD` 是上一个 Task 的提交，所以从 `HEAD` 建的临时 worktree 就是基线（不用 stash、不用 checkout）。两边各跑一次，比失败用例的**名字集合**（worktree 里首次 `uv run` 会建自己的 venv，耗时几分钟，正常）：

```bash
S=$(mktemp -d)
git worktree add --detach "$S/base" HEAD
REG="tests/test_guest_free_play.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_endpoints.py tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_ai_game_autosave.py"
(cd "$S/base" && CI=true uv run pytest $=REG -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR) " | sort > "$S/base.txt")
CI=true uv run pytest $=REG -q -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR) " | sort > "$S/after.txt"
comm -13 "$S/base.txt" "$S/after.txt"
git worktree remove --force "$S/base"
git status --short katrain/config.json
```

预期：`comm -13` **无输出**（没有新增失败）。注意 zsh 不做词分割，所以变量展开写 `$=REG`；若用 bash 执行改成 `$REG`。worktree 里跑出的 `katrain/config.json` 改动随 worktree 一起删掉，主树的只看最后一条。有新增失败就停下，逐条读报错，不许按文件名判「看着不相关」。

- [ ] **Step 8：格式化并提交**

```bash
uv run black -l 120 katrain/web/models.py katrain/web/interface.py katrain/web/server.py tests/test_local_play_game_end.py
git diff --stat katrain/web/models.py katrain/web/interface.py katrain/web/server.py tests/test_local_play_game_end.py
git add katrain/web/models.py katrain/web/interface.py katrain/web/server.py tests/test_local_play_game_end.py
git commit -m "$(cat <<'MSG'
feat(kiosk-local): 本地对局认输要说清是哪一方 —— /api/resign 收 color

两人共用一块屏，「轮到谁」不等于「谁按的键」：今天判负的是轮到走的一方，
开局即退会记一条白中盘胜。ResignRequest 单独建模不动共享的 ToggleAnalysisRequest；
pvp_local 不带 color 400，其它模式带 color 400，不带时行为逐字不变。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

预期：`--stat` 只列这 4 个文件，且 `server.py` / `interface.py` 的增删行数与本 Task 的改动量相当（black 若顺手改了别处，手工还原那些行）。

---

### Task S2a-3: 双 pass 钩子在 `awaiting_count` 时不落账（galaxy 逐字不变）

**Files:**
- Modify: `katrain/web/server.py` —— `async def play_move`（约 L938）末尾的落账钩子 `if state.get("end_result") and not is_multiplayer and current_user and session.user_id:`（约 L1000-1001）
- Test: `tests/test_local_play_game_end.py`（末尾追加「双 pass 钩子」分区）

**Interfaces:**
- Consumes：S2a-1 产出的 `state["awaiting_count"]`；`_record_ai_game(session, app, current_user, result)`（`server.py` 约 L1864）。
- Produces：`/api/move` 行为变化 —— `state["awaiting_count"]` 为真时不调 `_record_ai_game`；为假时（含一切非盒上模式、`ai_ladder_ranked` / `rated` / `ranked`）与今天逐字一致。

- [ ] **Step 1：追加钩子用例（先红）** —— 在 `tests/test_local_play_game_end.py` 末尾追加：

```python
# ------------------------------------------------------------------ 双 pass 落账钩子（§3.4、P4、§7-3）


@pytest.mark.parametrize("game_type", ["pvp_local", "free"])
def test_board_mode_double_pass_records_nothing(client, monkeypatch, game_type):
    """P4：盒上不自动分析，end_result 此刻只是回落串「终局」；落账就是一条没有胜负的记录。"""
    session = _owned_game(client, monkeypatch, game_type=game_type, board_mode=True)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is True
    assert _recorded_results(client) == []


def test_galaxy_double_pass_records_exactly_as_today(client, monkeypatch):
    """spec §7-3：galaxy（非盒上模式）双 pass 的落账与今天逐字一致 —— 仍是没有胜负的回落串。

    这条在改动前后都必须绿：它钉的是「不变」，不是新行为。
    """
    from katrain.core.lang import i18n

    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False
    assert state["end_result"] == i18n._("board-game-end")
    assert _recorded_results(client) == [state["end_result"]]


def test_board_mode_scoring_game_type_double_pass_records_as_today(client, monkeypatch):
    """反作弊类型（rated / ranked / ai_ladder_ranked）不进 awaiting_count，盒上也照旧落账。

    这里直接改 `game_type` 模拟，不走真的 rated 开局（那条要引擎与段位配置）；
    判定本身的类型排除已由 tests/test_game_end_rules.py 逐个类型钉住。
    """
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True)
    session.katrain.game_type = "rated"
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)

    state = _move(client, session.session_id)

    assert state["awaiting_count"] is False
    assert _recorded_results(client) == [state["end_result"]]
```

- [ ] **Step 2：跑，确认红**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q -k "double_pass_records"
git status --short katrain/config.json
```

预期：`test_board_mode_double_pass_records_nothing[pvp_local]`、`[free]` 失败，实际落账 `['终局']`（或当前语言的 `board-game-end` 串）—— 这就是 P4；`test_galaxy_double_pass_records_exactly_as_today` 与 `test_board_mode_scoring_game_type_double_pass_records_as_today` 通过。合计 `2 failed, 2 passed`。

若 `..._scoring_game_type_...` 在改动前就因 `/api/move` 返回非 200 而失败（`game_type="rated"` 让某条闸拦下了落子），把它删掉，不要为了让它绿去改被测代码；类型排除仍由单测覆盖。在 commit message 里写一句「rated 模拟被 /api/move 的 X 闸拦下，改由单测覆盖」。

- [ ] **Step 3：改钩子** —— `katrain/web/server.py` 的 `play_move`，把

```python
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if state.get("end_result") and not is_multiplayer and current_user and session.user_id:
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}
```

替换为：

```python
        #
        # 盒上模式（`awaiting_count`）例外：那里不自动分析，end_result 此刻只是回落串「终局」，
        # 落账就是一条没有胜负的记录。改由前端看到 awaiting_count 后调 /api/count/request，
        # 数出结果再落账。galaxy 走不到 awaiting_count，这一处对它逐字不变。
        is_multiplayer = session.player_b_id is not None or session.player_w_id is not None
        if (
            state.get("end_result")
            and not state.get("awaiting_count")
            and not is_multiplayer
            and current_user
            and session.user_id
        ):
            await _record_ai_game(session, app, current_user, state["end_result"])
        return {"session_id": session.session_id, "state": state}
```

执行时先核实：`grep -n 'if state.get("end_result") and not is_multiplayer and current_user and session.user_id' katrain/web/server.py` 预期**恰好 1 处**且在 `play_move` 里（`resign` 里的是 `elif not is_multiplayer and current_user and session.user_id`，不是这一行，不要动）。

- [ ] **Step 4：跑，确认绿 + 回归**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q
git status --short katrain/config.json
```

预期：`35 passed`（31 + 4；若 Step 2 删掉了 rated 那条则 `34 passed`）。

回归：照 S2a-2 Step 7 的临时 worktree 做法（基线 = `HEAD` = S2a-2 的提交），`REG` 取 `tests/web_ui/test_ai_game_autosave.py tests/test_local_play_recording.py tests/test_guest_free_play.py tests/web_ui/test_endpoints.py`（`test_ai_game_autosave.py` 是既有的「对局结束自动存谱」测试，最可能钉着这个钩子）。预期 `comm -13` 无输出。

- [ ] **Step 5：格式化并提交**

```bash
uv run black -l 120 katrain/web/server.py tests/test_local_play_game_end.py
git add katrain/web/server.py tests/test_local_play_game_end.py
git commit -m "$(cat <<'MSG'
fix(kiosk-local): 盒上双 pass 不再落账一条没有胜负的「终局」

盒上模式不自动分析，end_result 回落成 board-game-end 串，play_move 钩子照单落账。
awaiting_count 为真时钩子不落账，改由前端调数子后再记；galaxy 与反作弊类型
走不到 awaiting_count，双 pass 行为逐字不变（有测试钉住）。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

### Task S2a-4: `/api/count/request` —— 归属闸 + 缩放门槛 + `awaiting_count` 绕过 + 结构化 400 detail

**Files:**
- Modify: `katrain/web/server.py` —— 顶部 `from katrain.web.core...` import 区（约 L19-21）；`def _complete_count`（约 L1956）里 `if score is None:` 的 `raise`；`async def request_count`（约 L2009-2023）开头到「Check if game is already over」为止
- Test: `tests/test_local_play_game_end.py`（末尾追加「数子」分区）

**Interfaces:**
- Consumes：S2a-1 的 `scaled_count_min_moves`、`state["awaiting_count"]`；`guard_session_terminator(session, current_user, action)`（`server.py` 约 L818，无人认领的会话直接放行；未登录 401；非参与者 403）。
- Produces：`POST /api/count/request`：
  - 顺序：`_get_session_or_404` → **`guard_session_terminator(..., "request-count")`（新增）** → `guard_ai_ladder_ranked_human_action` → `_guard_ai_ladder_cloud_active` → 门槛与已终局检查（`awaiting_count` 为真时整段跳过）→ 原逻辑
  - 门槛 = `scaled_count_min_moves(config("game/count_min_moves", 100), board_size)`（全局，含 galaxy 9/13 路）
  - 400 的 `detail` 从字符串改为对象 `{"code": str, "message": str}`：
    - `below_min_moves` / `"Cannot count before {N} moves"`
    - `game_over` / `"Game is already over"`
    - `analysis_pending` / `"Analysis not available yet. Please wait for KataGo analysis to complete."`（在 `_complete_count` 里，所以多人局的「对方接受」路径也带码）
  - `message` 与今天的字符串逐字相同。

**现有消费者与兼容（HEAD 时 grep 核实，见「核实记录」）**：前端三处调 `API.requestCount` —— `galaxy/pages/GamePage.tsx` 约 L312 与 `galaxy/pages/GameRoomPage.tsx` 约 L159 都是 `alert(e.message || ...)`，而 `e.message` 由 `api.ts` `apiPost`（约 L322-324）拼成 `Request failed 400: <原始 body 文本>`：改动前 body 是 `{"detail":"Cannot count before 100 moves"}`，改动后是 `{"detail":{"code":"below_min_moves","message":"Cannot count before 100 moves"}}`——弹窗仍是原始 JSON，英文原因仍在里面，不会抛错，**不需要改**；`kiosk/pages/GamePage.tsx` 约 L438-441 的 `catch {}` 不读错误内容，由 S2b 的 `countErrorMessage` 接管。后端测试里没有任何断言这三句字符串（`grep -rn "Cannot count\|already over\|Analysis not available" tests katrain/web/ui/tests` 零命中）。`test_ai_ladder_api.py` 约 L1541、L3552 对 `/api/count/request` 只断言状态码，不读 detail。

- [ ] **Step 1：执行时先核实**

```bash
grep -n "async def request_count" -A16 katrain/web/server.py
grep -n 'detail="Analysis not available yet' katrain/web/server.py
grep -rn "Cannot count\|already over\|Analysis not available" tests katrain/web/ui/tests katrain/web/ui/src
```

预期：第一条可见 `count_min_moves = session.katrain.config("game/count_min_moves", 100)` 与两个字符串 detail 的 `raise`；第二条恰好 1 处（在 `_complete_count` 里）；第三条只有 `katrain/web/ui/src/kiosk/pages/GamePage.tsx` 的中文兜底文案那一行（`'Cannot count yet (not enough moves, or the game is over)'`），测试零命中。若第三条多出别的消费者，停下，按「现有消费者与兼容」的判法逐个写明再继续。

- [ ] **Step 2：追加数子用例（先红）** —— 在 `tests/test_local_play_game_end.py` 末尾追加。其中 `test_free_game_ended_by_a_pass_outside_api_move_is_recordable` 是 spec §3.4「待核实」那一条的实证（结论与证据见本切片「核实记录」）：

```python
# ------------------------------------------------------------------ /api/count/request（§3.4、P6、P7、P18）


def test_count_threshold_scales_on_9x9_and_reports_codes(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=False, size=9, base=100)
    sid = session.session_id
    for i in range(10):  # 黑落子、白停一手，交替 10 轮：20 手 + 根节点 = 21；从不连续两手 pass
        _move(client, sid, [i % 9, i // 9])
        _move(client, sid)
    assert len(session.katrain.get_state()["history"]) == 21

    below = client.post("/api/count/request", json={"session_id": sid})
    assert below.status_code == 400, below.text
    assert below.json()["detail"] == {"code": "below_min_moves", "message": "Cannot count before 22 moves"}

    _move(client, sid, [1, 1])  # 第 22 个节点，过门槛；没有分析
    pending = client.post("/api/count/request", json={"session_id": sid})
    assert pending.status_code == 400, pending.text
    assert pending.json()["detail"]["code"] == "analysis_pending"


def test_count_on_a_finished_galaxy_game_reports_game_over(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False, base=1)
    _move(client, session.session_id, [3, 3])
    _move(client, session.session_id)
    _move(client, session.session_id)

    r = client.post("/api/count/request", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert r.json()["detail"] == {"code": "game_over", "message": "Game is already over"}


def test_board_mode_double_pass_counts_without_threshold_once_analysis_arrives(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=True, base=100)
    sid = session.session_id
    _move(client, sid, [3, 3])
    _move(client, sid)
    _move(client, sid)  # history = 4，远低于 100

    pending = client.post("/api/count/request", json={"session_id": sid})
    assert pending.status_code == 400, pending.text
    assert pending.json()["detail"]["code"] == "analysis_pending"  # 绕过了门槛，卡在分析上

    # 分析回来（生产里是前端 analyzeCurrent 触发的那一份）。此刻 game.manual_score 已非空，
    # end_result 变成 "黑+3.0?" 这种估计串 —— awaiting_count 必须仍为真，否则下面会被判「已终局」。
    session.katrain.game.current_node.analysis["root"] = {"scoreLead": 3.2, "winrate": 0.6, "visits": 10}
    assert session.katrain.game.manual_score is not None
    assert session.katrain.get_state()["awaiting_count"] is True

    r = client.post("/api/count/request", json={"session_id": sid})

    assert r.status_code == 200, r.text
    assert r.json()["result"] == "B+3.2"
    assert r.json()["state"]["end_result"] == "B+3.2"
    assert r.json()["state"]["awaiting_count"] is False
    assert _recorded_results(client) == ["B+3.2"]


def test_free_game_ended_by_a_pass_outside_api_move_is_recordable(client, monkeypatch):
    """spec §3.4 待核实那一条。

    AI 的着手不经 `/api/move`：`WebKaTrain._do_ai_move`（后台线程）→ `katrain/core/ai.py`
    `generate_ai_move` → `game.play(move)`，之后 `_do_ai_move_and_broadcast` 的 finally 只调
    `update_state()`。所以「人先停、AI 再停」收尾的局，`/api/move` 的钩子从来走不到，也没有别的
    落账路径。这里不真起 AI（NullEngine 下 genmove 线程会挂住并活过用例），而是照那条线程的
    做法直接 `game.play` + `update_state()`。
    """
    from katrain.core.game import Move

    session = _owned_game(client, monkeypatch, game_type="free", board_mode=True, base=100)
    sid = session.session_id
    _move(client, sid, [3, 3])
    _move(client, sid)  # 人（白）停一手
    with session.lock:  # 「AI」（黑）停一手，走的是 genmove 线程那条路
        session.katrain.game.play(Move(None, player=session.katrain.game.current_node.next_player))
    session.katrain.update_state()
    assert _recorded_results(client) == []  # 今天到这里为止就是没落账
    assert session.katrain.get_state()["awaiting_count"] is True

    session.katrain.game.current_node.analysis["root"] = {"scoreLead": -4.5, "winrate": 0.3, "visits": 10}
    r = client.post("/api/count/request", json={"session_id": sid})

    assert r.status_code == 200, r.text
    assert _recorded_results(client) == ["W+4.5"]


def test_count_is_restricted_to_the_owner(client, monkeypatch):
    session = _owned_game(client, monkeypatch, game_type="pvp_local", board_mode=False)
    sid = session.session_id

    client.app.dependency_overrides[get_current_user_optional] = lambda: STRANGER
    assert client.post("/api/count/request", json={"session_id": sid}).status_code == 403
    client.app.dependency_overrides[get_current_user_optional] = lambda: None
    assert client.post("/api/count/request", json={"session_id": sid}).status_code == 401
    assert session.katrain.game.current_node.end_state is None

    # 正对照：主人本人打得到端点本身（被门槛挡，不是被归属闸挡）。
    client.app.dependency_overrides[get_current_user_optional] = lambda: OWNER
    owner = client.post("/api/count/request", json={"session_id": sid})
    assert owner.status_code == 400, owner.text
    assert owner.json()["detail"]["code"] == "below_min_moves"


def test_count_on_an_unclaimed_session_needs_no_login(client, monkeypatch):
    """无人认领（游客开的）会话不设闸 —— 与认输、超时同一口径。"""
    session = _owned_game(client, monkeypatch, game_type="free", board_mode=False, user_id=None)
    client.app.dependency_overrides[get_current_user_optional] = lambda: None

    r = client.post("/api/count/request", json={"session_id": session.session_id})

    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "below_min_moves"
```

- [ ] **Step 3：跑，确认红**

```bash
CI=true uv run pytest tests/test_local_play_game_end.py -q -k "count"
git status --short katrain/config.json
```

预期（`-k count` 还会选中 S2a-1 的 `test_state_count_min_moves_scales_with_board_size[*]`（3）、`test_board_mode_double_pass_sets_awaiting_count[*]`（2）、`test_galaxy_double_pass_never_sets_awaiting_count`（1），它们保持绿）：本 Task 新增的 6 条全部失败——
- `test_count_threshold_scales_on_9x9_and_reports_codes`：`detail` 是字符串 `'Cannot count before 100 moves'`，不等于对象（门槛也没缩放）；
- `test_count_on_a_finished_galaxy_game_reports_game_over`：`detail` 是字符串；
- `test_board_mode_double_pass_counts_without_threshold_once_analysis_arrives`：`TypeError: string indices must be integers`（今天被门槛挡在 `'Cannot count before 100 moves'`）；
- `test_free_game_ended_by_a_pass_outside_api_move_is_recordable`：`assert 400 == 200`；
- `test_count_is_restricted_to_the_owner`：`assert 400 == 403`（P18：今天陌生人打得进端点）；
- `test_count_on_an_unclaimed_session_needs_no_login`：`TypeError: string indices must be integers`。

合计 `6 failed, 6 passed`。

- [ ] **Step 4：实现** —— `katrain/web/server.py`：

(a) import 区，在 `from katrain.web.core.config import settings` 之后加：

```python
from katrain.web.core.game_end_rules import scaled_count_min_moves
```

(b) `_complete_count` 里把

```python
            raise HTTPException(
                status_code=400, detail="Analysis not available yet. Please wait for KataGo analysis to complete."
            )
```

替换为：

```python
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "analysis_pending",
                    "message": "Analysis not available yet. Please wait for KataGo analysis to complete.",
                },
            )
```

(c) `request_count` 里把从 `session = _get_session_or_404(manager, request.session_id)` 到 `raise HTTPException(status_code=400, detail="Game is already over")` 这一段（HEAD 时约 L2011-2023）替换为：

```python
        session = _get_session_or_404(manager, request.session_id)
        # 数子会写终局结果并落账（记在调用者名下），和认输、超时同一道归属闸（P18）。
        guard_session_terminator(session, current_user, "request-count")
        guard_ai_ladder_ranked_human_action(session, current_user, "request-count")
        await _guard_ai_ladder_cloud_active(app, session, current_user)

        state = session.katrain.get_state()
        # 盒上模式双方各停一手（`awaiting_count`）：这时 end_result 只是「终局」回落串或分析估计，
        # 不是真结果；手数门槛也不适用 —— 两人都停了，就该数。
        if not state.get("awaiting_count"):
            # 400 的 detail 是 {code, message}：前端按 code 说出真实原因，message 与旧字符串逐字相同。
            board_size_val = state.get("board_size", [19, 19])
            board_size = board_size_val[0] if isinstance(board_size_val, (list, tuple)) else board_size_val
            count_min_moves = scaled_count_min_moves(
                session.katrain.config("game/count_min_moves", 100), int(board_size)
            )
            if len(state.get("history", [])) < count_min_moves:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "below_min_moves", "message": f"Cannot count before {count_min_moves} moves"},
                )
            if state.get("end_result"):
                raise HTTPException(status_code=400, detail={"code": "game_over", "message": "Game is already over"})
```

其后 `is_multiplayer = ...` 起的代码一行不动。

- [ ] **Step 5：跑，确认绿 + 变异自检**

```bash
CI=true uv run pytest tests/test_game_end_rules.py tests/test_local_play_game_end.py -q
git status --short katrain/config.json
```

预期：`61 passed`（单测 20 + 集成 41；若 S2a-3 删掉了 rated 那条则 `60 passed`）。

变异（每条改完跑上面同一条命令，看到预期的红后**立刻改回**，用 `grep -n` 回读确认还原，不许用 git checkout）：
1. 删掉新加的 `guard_session_terminator(session, current_user, "request-count")` 一行 → 预期恰好 `test_count_is_restricted_to_the_owner` 红。
2. 把 `if not state.get("awaiting_count"):` 改成 `if True:` → 预期 `test_board_mode_double_pass_counts_without_threshold_once_analysis_arrives` 与 `test_free_game_ended_by_a_pass_outside_api_move_is_recordable` 红。
3. 把 `scaled_count_min_moves(...)` 调用换回 `session.katrain.config("game/count_min_moves", 100)` → 预期 `test_count_threshold_scales_on_9x9_and_reports_codes` 红（`100` ≠ `22`）。

- [ ] **Step 6：回归（名字集合比）**

照 S2a-2 Step 7 的临时 worktree 做法（基线 = `HEAD` = S2a-3 的提交），`REG` 取：

```bash
REG="tests/web_ui/test_ai_ladder_api.py tests/web_ui/test_game_termination_and_chat_identity.py tests/web_ui/test_endpoints.py tests/web_ui/test_ai_game_autosave.py tests/test_guest_free_play.py tests/test_local_play_recording.py tests/test_local_play_setup.py"
```

预期 `comm -13` 无输出。最可能回归的是 `test_ai_ladder_api.py` 约 L1541 `test_ranked_session_allows_human_turn_terminal_actions[/api/count/request]`（期望 200）：新加的归属闸在 ranked 闸之前，若这条新增失败，先读 `session_owner_ids`（`grep -n "def session_owner_ids" -A20 katrain/web/core/ranked_session_guard.py katrain/web/server.py`）确认测试里的用户是不是会话参与者——是就说明闸的放置有问题，停下报告；不是就说明该测试原本依赖「陌生人能数子」这个缺陷，报告给 integrator 再定，不许自行放宽闸。

上一轮在沙箱副本上跑过全量 `tests/`：改动前后都是 `31 failed, 959 passed, 2 skipped, 1 xfailed, 31 errors`（`scratchpad/s2a-exp/regress2-s2a-base.txt` 与 `regress2-s2a-copy.txt`），条数一致但**没有比名字集合**，只能当参考，不能替代本步。

- [ ] **Step 7：格式化并提交**

```bash
uv run black -l 120 katrain/web/server.py tests/test_local_play_game_end.py
git add katrain/web/server.py tests/test_local_play_game_end.py
git commit -m "$(cat <<'MSG'
fix(kiosk-local): 数子端点补归属闸、门槛按路数缩放、400 带原因码

- P18：/api/count/request 会落账到调用者名下，却不看这局是不是他的；补上与认输、超时同一道 guard_session_terminator
- P7：门槛写死 100 手，9/13 路基本数不了子；改用 scaled_count_min_moves，全局生效（galaxy 同样）
- awaiting_count 为真时跳过门槛与「已终局」检查：双方都停了就该数
- P6：三种 400 的 detail 改为 {code, message}（below_min_moves / game_over / analysis_pending），message 与旧串逐字相同；galaxy 两处只 alert 原始 body，不受影响
- 自由对弈里 AI 停第二手收尾的局今天没有任何落账路径，现在能经数子落账（有测试）

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

## 切片 S2b：把一局下完，拿到正确结果（前端部分）

**目标**：本地对局（`game_type === 'pvp_local'`）的对局屏右栏收窄成「数子 · 停一手 · 认输」，门槛 N 读服务端 `count_min_moves`；「退出对局」与「认输」拆成两个出口（退出 = 删会话不存谱；认输先选黑/白）；双 pass 后按 `awaiting_count` 自动数子，分析没回来时退避约 15 s，失败说真实原因并给重试键；手动数子失败也按原因码出文案。

**覆盖 spec**：§3.1（右栏）、§3.2（两个出口，前端）、§3.4 前端（自动数子、原因码文案）、§6.1 屏 05 本地对局视觉关卡、§6.2 右栏承重实测。问题 P5（前端）、P6、P10（右栏部分）。

**Task 顺序（垂直切片）**：S2b-1 / S2b-2 纯逻辑（无界面）→ S2b-3 右栏 → S2b-4 GamePage 出口 + 自动数子接线（隔离 fixture 驱动）→ S2b-5 四图 + 确认框截图 + 承重实测 → ⏸ Fan 确认 → （S2a 后端，另一份计划）→ S2-INT 集成 + 删 fixture。

### Task S2b-1: API 层——`ApiError.detail`、`API.deleteSession`、`API.resign(color)`、`handleAction(opts)`、`countErrorMessage`

**Files:**
- Modify: `katrain/web/ui/src/api.ts`（`GameState.count_min_moves` 约 L77 之后加字段；`class ApiError` 约 L268-275；`apiPost` 约 L315-326；`API.createSession` 约 L330 之后插 `deleteSession`；`resign` 约 L389-390）
- Modify: `katrain/web/ui/src/hooks/useGameSession.ts`（**只动 `handleAction`**，约 L171 签名 + 约 L188 `resign` 分支）
- Create: `katrain/web/ui/src/kiosk/utils/countErrors.ts`
- Test: `katrain/web/ui/src/kiosk/utils/countErrors.test.ts`（新建）、`katrain/web/ui/src/api.localPlayV2.test.ts`（新建）

**Interfaces:**
- Consumes：无（本切片最底层）。后端契约只读 contract.md：数子 400 的 `detail = {code, message}`，code ∈ `below_min_moves` / `game_over` / `analysis_pending`；`/api/resign` 的 `color`。
- Produces：
  - `class ApiError { status: number; detail?: unknown; constructor(status: number, message: string, detail?: unknown) }`
  - `GameState.awaiting_count?: boolean`
  - `API.deleteSession(sessionId: string): Promise<void>`（非 2xx 抛 `ApiError`）
  - `API.resign(sessionId: string, token?: string, color?: 'B' | 'W'): Promise<SessionResponse>`
  - `handleAction(action: string, opts?: { color?: 'B' | 'W' }): Promise<void>`（`useGameSession` 返回值里那个）
  - `type CountErrorCode = 'analysis_pending' | 'below_min_moves' | 'game_over' | 'network' | 'http'`
  - `countErrorCode(err: unknown): CountErrorCode`
  - `countErrorMessage(err: unknown, t: (key: string, fallback?: string) => string): string`

- [ ] **Step 1: 执行时先核实锚点仍在**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "class ApiError\|export async function apiPost\|resign: (sessionId\|count_min_moves?: number" src/api.ts
grep -n "const handleAction = useCallback\|action === 'resign'" src/hooks/useGameSession.ts
grep -rn "deleteSession" src | grep -v test
```
预期：前两条各命中（行号可漂）；第三条**无输出**（仓里只有 `useResearchSession.ts:107` 与 galaxy `ResearchPage.tsx:188` 两处裸 `fetch(..., {method:'DELETE'})`，都吞掉失败，不是等价物）。

- [ ] **Step 2: 写失败测试 `src/kiosk/utils/countErrors.test.ts`**

```ts
import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api';
import { countErrorCode, countErrorMessage } from './countErrors';

const t = (key: string, fallback?: string) => fallback ?? key;
const api400 = (detail: unknown) => new ApiError(400, 'Request failed 400: …', detail);

// 判据落在**屏上那句话**,不只落在 code 上:code 对了而文案接错一格,用户照样被说错原因。
describe('数子失败的原因 → 文案', () => {
  it.each([
    ['新后端 · analysis_pending', api400({ code: 'analysis_pending', message: 'x' }), 'analysis_pending', '还在算这一手的形势，稍等再数'],
    ['新后端 · below_min_moves', api400({ code: 'below_min_moves', message: 'x' }), 'below_min_moves', '手数还不够，暂时不能数子'],
    ['新后端 · game_over', api400({ code: 'game_over', message: 'x' }), 'game_over', '这一局已经结束了'],
    ['老后端 · 分析没回来', api400('Analysis not available yet. Please wait for KataGo analysis to complete.'), 'analysis_pending', '还在算这一手的形势，稍等再数'],
    ['老后端 · 手数不足', api400('Cannot count before 100 moves'), 'below_min_moves', '手数还不够，暂时不能数子'],
    ['老后端 · 已终局', api400('Game is already over'), 'game_over', '这一局已经结束了'],
    ['网络层(fetch 直接抛)', new TypeError('Failed to fetch'), 'network', '分析服务连不上'],
    ['其它 HTTP 拒绝', new ApiError(403, 'Request failed 403: …', 'Not authorized'), 'http', '数子失败（403），请重试'],
    ['400 但 code 不认识', api400({ code: 'something_new' }), 'http', '数子失败（400），请重试'],
  ] as const)('%s', (_name, err, code, message) => {
    expect(countErrorCode(err)).toBe(code);
    expect(countErrorMessage(err, t)).toBe(message);
  });
});
```

- [ ] **Step 3: 写失败测试 `src/api.localPlayV2.test.ts`**（`ApiError.detail` 解析、`resign` 的 body 形状、`deleteSession`）

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError, apiPost } from './api';

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); });

const reply = (status: number, body: string) =>
  ({ ok: status >= 200 && status < 300, status, text: async () => body, json: async () => JSON.parse(body) });

describe('ApiError.detail', () => {
  it.each([
    ['对象 detail 原样挂上', '{"detail":{"code":"analysis_pending","message":"x"}}', { code: 'analysis_pending', message: 'x' }],
    ['字符串 detail 原样挂上', '{"detail":"Game is already over"}', 'Game is already over'],
    ['不是 JSON(网关页) ⇒ undefined', '<html>502</html>', undefined],
    ['JSON 是 null ⇒ undefined', 'null', undefined],
  ])('%s', async (_n, body, detail) => {
    fetchMock.mockResolvedValue(reply(400, body));
    const err = await apiPost('/api/count/request', { session_id: 's' }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toEqual(detail);
    expect(err.message).toBe(`Request failed 400: ${body}`); // message 格式不变
  });
});

describe('API.resign', () => {
  const bodyOf = () => JSON.parse(fetchMock.mock.calls[0][1].body);
  it('给了 color ⇒ body 带 color', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"session_id":"s","state":{}}'));
    await API.resign('s', undefined, 'W');
    expect(bodyOf()).toEqual({ session_id: 's', color: 'W' });
  });
  it('没给 color ⇒ body 里连这个键都没有(其它模式带了会 400)', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"session_id":"s","state":{}}'));
    await API.resign('s');
    expect(Object.keys(bodyOf())).toEqual(['session_id']);
  });
});

describe('API.deleteSession', () => {
  it('DELETE /api/session/{id}', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"status":"deleted"}'));
    await API.deleteSession('a/b');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/session/a%2Fb');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
  });
  it('失败必须抛 —— 不能装作已退出', async () => {
    fetchMock.mockResolvedValue(reply(500, 'boom'));
    await expect(API.deleteSession('s')).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 4: 跑测试，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/utils/countErrors.test.ts src/api.localPlayV2.test.ts
```
预期：`countErrors.test.ts` 报 `Failed to resolve import "./countErrors"`；`api.localPlayV2.test.ts` 里 `detail` 那 4 条 `expected undefined to deeply equal …`（字符串那条也红），`resign` 带 color 那条红，`deleteSession` 两条 `API.deleteSession is not a function`。

- [ ] **Step 5: 实现 `api.ts`**

(a) `GameState` 里 `count_min_moves?: number;` 下一行加：
```ts
  /**
   * 盒上模式、双方各停一手、这一局还没有结果 ⇒ 后端等前端来数子(v2-design §3.4)。
   * 为真时 `/api/count/request` 跳过手数门槛。老服务端不带这个字段 ⇒ undefined ⇒ 不自动数。
   */
  awaiting_count?: boolean;
```
(b) `class ApiError` 整体替换为：
```ts
export class ApiError extends Error {
  status: number;
  /**
   * 服务端 JSON body 里的 `detail`(FastAPI `HTTPException` 那一格),**原样**挂上:
   * 对象(`{ code, message }`,数子那三种 400)、字符串(绝大多数老端点),
   * body 不是 JSON 或没有这一格时是 `undefined`。按原因码出文案的一方读它,不要去 parse `message`。
   */
  detail?: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}
```
(c) `apiPost` 里 `throw new ApiError(response.status, \`Request failed ${response.status}: ${body}\`);` 替换为：
```ts
    let detail: unknown;
    try {
      detail = (JSON.parse(body) as { detail?: unknown }).detail;
    } catch {
      detail = undefined; // 不是 JSON(网关 502 页)或 JSON 是 null —— 没有 detail 可读
    }
    throw new ApiError(response.status, `Request failed ${response.status}: ${body}`, detail);
```
(d) `createSession: ...` 那一行之后插入：
```ts
  /* 本地对局「退出不保存」:删掉进程里这个会话,什么都不落账。
     研究页那两处(`useResearchSession.ts`、galaxy `ResearchPage.tsx`)是裸 fetch 且吞掉失败 ——
     那边是「离开时顺手收拾」;这里失败了**不能装作已退出**,所以抛。 */
  deleteSession: async (sessionId: string): Promise<void> => {
    const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new ApiError(response.status, `Request failed ${response.status}: ${body}`);
    }
  },
```
(e) `resign` 两行替换为：
```ts
  /* `color` 只给本地对局(pvp_local):后端对 pvp_local **必须**带、对其它模式**带了就 400**
     ⇒ 没给时 body 里绝不能出现这个键。 */
  resign: (sessionId: string, token?: string, color?: 'B' | 'W'): Promise<SessionResponse> =>
    apiPost("/api/resign", color ? { session_id: sessionId, color } : { session_id: sessionId }, token),
```

- [ ] **Step 6: 实现 `useGameSession.ts` 的 `handleAction`**（只动这两处）

```ts
    const handleAction = useCallback(async (action: string, opts?: { color?: 'B' | 'W' }) => {
```
```ts
            // 本地对局(pvp_local)的认输要说**是哪一方**认输(后端不带 color 回 400);
            // 其它模式不许带(带了同样 400)⇒ 没给 color 时调用形状与原来逐字一致。
            else if (action === 'resign') result = opts?.color
                ? await API.resign(sessionId, token, opts.color)
                : await API.resign(sessionId, token);
```

- [ ] **Step 7: 实现 `src/kiosk/utils/countErrors.ts`**

```ts
import { ApiError } from '../../api';

/**
 * 数子失败的**原因**(v2-design §3.4 / P6)。上一版一律说「手数不足或已结束」——
 * 盒上最常见的真实原因却是**分析还没回来**。说错原因比不说更坏:人会去数手数,该做的是等几秒。
 *
 *   analysis_pending  这一手的分数还没算出来(自动数子按这个退避重试)
 *   below_min_moves   手数没到门槛
 *   game_over         已经有结果了
 *   network           请求没到服务端(`fetch` 自己抛,不是 `ApiError`)
 *   http              到了,但被别的原因拒了(401/403/404/5xx,或 400 却不认识的 code)
 */
export type CountErrorCode = 'analysis_pending' | 'below_min_moves' | 'game_over' | 'network' | 'http';

const KNOWN_CODES: readonly CountErrorCode[] = ['analysis_pending', 'below_min_moves', 'game_over'];

/**
 * S2a 之前的后端,这三种 400 的 `detail` 是英文串(`server.py` 约 L1969 / L2019 / L2023)。
 * 盒上的服务比前端旧几天是常态,所以老串照认 —— 按前缀,不按全文。
 */
const LEGACY_PREFIXES: readonly (readonly [string, CountErrorCode])[] = [
  ['Analysis not available yet', 'analysis_pending'],
  ['Cannot count before', 'below_min_moves'],
  ['Game is already over', 'game_over'],
];

export function countErrorCode(err: unknown): CountErrorCode {
  if (!(err instanceof ApiError)) return 'network';
  const { detail } = err;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code: unknown }).code;
    const known = KNOWN_CODES.find((c) => c === code);
    if (known) return known;
  }
  if (typeof detail === 'string') {
    const hit = LEGACY_PREFIXES.find(([prefix]) => detail.startsWith(prefix));
    if (hit) return hit[1];
  }
  return 'http';
}

export function countErrorMessage(err: unknown, t: (key: string, fallback?: string) => string): string {
  switch (countErrorCode(err)) {
    case 'analysis_pending':
      return t('game:count_err_analysis_pending', '还在算这一手的形势，稍等再数');
    case 'below_min_moves':
      return t('game:count_err_below_min', '手数还不够，暂时不能数子');
    case 'game_over':
      return t('game:count_err_game_over', '这一局已经结束了');
    case 'network':
      return t('game:count_err_network', '分析服务连不上');
    default:
      return t('game:count_err_http', '数子失败（{status}），请重试')
        .replace('{status}', String((err as ApiError).status));
  }
}
```

- [ ] **Step 8: 跑测试，确认绿 + 既有用例不回归 + 类型检查**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/utils/countErrors.test.ts src/api.localPlayV2.test.ts src/api.quickAnalyze.test.ts src/hooks
npx tsc -b
```
预期：全部 passed（`countErrors` 9 条、`api.localPlayV2` 8 条）；`tsc -b` 无输出、exit 0。`api.ts` / `useGameSession.ts` 是**共享区** —— 两个构建留到 S2b-4 末尾一起跑（本 Task 只改签名、加可选参数，不引入新 import）。

- [ ] **Step 9: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/api.ts katrain/web/ui/src/hooks/useGameSession.ts katrain/web/ui/src/kiosk/utils/countErrors.ts katrain/web/ui/src/kiosk/utils/countErrors.test.ts katrain/web/ui/src/api.localPlayV2.test.ts
git commit -m "$(cat <<'MSG'
feat(kiosk-local): API 层能说出数子失败的真实原因，认输能说是哪一方

ApiError 挂上服务端 detail；新增 API.deleteSession（失败必抛）；
API.resign / handleAction 可带 color，不带时 body 形状逐字不变。
countErrorMessage 同时认新原因码与老后端英文串。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

### Task S2b-2: `useAutoCount` —— 双 pass 后自动数子、`analysis_pending` 退避约 15 s、失败说原因 + 重试

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/useAutoCount.ts`
- Test: `katrain/web/ui/src/kiosk/hooks/useAutoCount.test.ts`（新建）

**Interfaces:**
- Consumes：`API.requestCount(sessionId: string, token?: string): Promise<any>`（`api.ts` 约 L393，已存在）；`GameState.awaiting_count`、`countErrorCode`、`countErrorMessage`（S2b-1）；`useTranslation()`（`src/hooks/useTranslation.ts`）。
- Produces：
  - `type AutoCountStatus = 'idle' | 'counting' | 'failed'`
  - `const AUTO_COUNT_BACKOFF_MS: readonly number[]`（`[1000, 2000, 3000, 4000, 5000]`，累计 15 s，共 6 次请求）
  - `autoCountEligible(gs: GameState | null | undefined, engineMode: boolean): boolean`
  - `interface UseAutoCountOptions { sessionId: string | null | undefined; awaitingCount: boolean; nodeId: number | null | undefined; onState: (state: GameState) => void }`
  - `useAutoCount(opts: UseAutoCountOptions): { status: AutoCountStatus; reason: string | null; retry: () => void }`

- [ ] **Step 1: 执行时先核实 `autoCountEligible` 的前提**（大厅/星阵局后端 `game_type` 也是 `free`，座位是裸 `human`；kiosk 人机局 AI 座位是 `player:ai`）

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
grep -n 'player_type="player:ai"' katrain/web/server.py | head -3
grep -n "def create_multiplayer_session" -A 40 katrain/web/session.py | grep -n "game_type\|player_type\|start(" | head
grep -n "def start" -A 3 katrain/web/interface.py | grep -n game_type
```
预期：第一条命中 `server.py` 约 L1184；后两条能看到多人会话不传 `game_type`（落默认 `"free"`）、座位 `"human"`。**若不成立**（例如大厅局已有独立 `game_type`），把 `autoCountEligible` 简化为 `game_type ∈ {pvp_local, free} ∧ !engineMode`，并删掉测试表里「大厅对局」那一行，在 commit message 里写明。

- [ ] **Step 2: 写失败测试 `src/kiosk/hooks/useAutoCount.test.ts`**

```ts
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError, type GameState } from '../../api';
import { autoCountEligible, useAutoCount, type UseAutoCountOptions } from './useAutoCount';

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>();
  return { ...actual, API: { ...actual.API, requestCount: vi.fn() } };
});

const onState = vi.fn();
const opts = (over: Partial<UseAutoCountOptions> = {}): UseAutoCountOptions => ({
  sessionId: 's-1', awaitingCount: false, nodeId: 7, onState, ...over,
});
const pending = () =>
  new ApiError(400, 'Request failed 400: …', { code: 'analysis_pending', message: 'Analysis not available yet' });

beforeEach(() => { vi.mocked(API.requestCount).mockReset(); onState.mockReset(); });
afterEach(() => { vi.useRealTimers(); });

describe('useAutoCount', () => {
  it('不在等数子 ⇒ 一个请求都不发', () => {
    const { result } = renderHook(() => useAutoCount(opts()));
    expect(result.current.status).toBe('idle');
    expect(API.requestCount).not.toHaveBeenCalled();
  });

  it('awaiting 为真就自动数一次,终局 state 交回去;同一节点再推一次 state 不重复数', async () => {
    const ended = { end_result: 'B+3.5' } as GameState;
    vi.mocked(API.requestCount).mockResolvedValue({ session_id: 's-1', state: ended });
    const { result, rerender } = renderHook((p: UseAutoCountOptions) => useAutoCount(p), {
      initialProps: opts({ awaitingCount: true }),
    });
    expect(result.current.status).toBe('counting');
    await waitFor(() => expect(onState).toHaveBeenCalledWith(ended));
    rerender(opts({ awaitingCount: true }));
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    expect(API.requestCount).toHaveBeenCalledWith('s-1');
  });

  // 时间线:第 0 / 1 / 3 / 6 / 10 / 15 秒各发一次,第 6 次还是 analysis_pending 才说原因。
  it('analysis_pending 退避重试,约 15 秒后说出真实原因;按重试重新开始', async () => {
    vi.useFakeTimers();
    vi.mocked(API.requestCount).mockRejectedValue(pending());
    const { result } = renderHook(() => useAutoCount(opts({ awaitingCount: true })));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(14_999); });
    expect(API.requestCount).toHaveBeenCalledTimes(5);
    expect(result.current.status).toBe('counting');
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(API.requestCount).toHaveBeenCalledTimes(6);
    expect(result.current.status).toBe('failed');
    expect(result.current.reason).toBe('还在算这一手的形势，稍等再数');
    act(() => result.current.retry());
    expect(result.current.status).toBe('counting');
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(API.requestCount).toHaveBeenCalledTimes(7);
  });

  it('网络层失败不退避,直接说「分析服务连不上」', async () => {
    vi.mocked(API.requestCount).mockRejectedValue(new TypeError('Failed to fetch'));
    const { result } = renderHook(() => useAutoCount(opts({ awaitingCount: true })));
    await waitFor(() => expect(result.current.status).toBe('failed'));
    expect(result.current.reason).toBe('分析服务连不上');
    expect(API.requestCount).toHaveBeenCalledTimes(1);
  });

  it('退避中不再 awaiting ⇒ 掐掉计时器,不再请求', async () => {
    vi.useFakeTimers();
    vi.mocked(API.requestCount).mockRejectedValue(pending());
    const { result, rerender } = renderHook((p: UseAutoCountOptions) => useAutoCount(p), {
      initialProps: opts({ awaitingCount: true }),
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    rerender(opts({ awaitingCount: false }));
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000); });
    expect(API.requestCount).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe('idle');
  });
});

describe('autoCountEligible', () => {
  const seat = (player_type: string) => ({
    player_type, player_subtype: '', name: '', calculated_rank: null, periods_used: 0, main_time_used: 0,
  });
  const gs = (game_type: string, b: string, w: string) =>
    ({ game_type, players_info: { B: seat(b), W: seat(w) } }) as unknown as GameState;
  it.each([
    ['本地对局', gs('pvp_local', 'player:human', 'player:human'), false, true],
    ['人机自由对弈', gs('free', 'player:human', 'player:ai'), false, true],
    ['大厅对局(后端 game_type 也是 free)', gs('free', 'human', 'human'), false, false],
    ['星阵人机', gs('free', 'human', 'human'), true, false],
    ['升降级', gs('ai_ladder_ranked', 'player:human', 'player:ai'), false, false],
  ] as const)('%s', (_name, state, engineMode, expected) => {
    expect(autoCountEligible(state, engineMode)).toBe(expected);
  });
});
```

- [ ] **Step 3: 跑测试，确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/hooks/useAutoCount.test.ts
```
预期：`Failed to resolve import "./useAutoCount"`。

- [ ] **Step 4: 实现 `src/kiosk/hooks/useAutoCount.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { API, type GameState } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { countErrorCode, countErrorMessage } from '../utils/countErrors';

export type AutoCountStatus = 'idle' | 'counting' | 'failed';

/** `analysis_pending` 的退避间隔(毫秒)。累计 15 秒(v2-design §3.4),共 6 次请求;第 6 次仍 pending 就停。 */
export const AUTO_COUNT_BACKOFF_MS: readonly number[] = [1000, 2000, 3000, 4000, 5000];

/**
 * 这一局该不该**自动**数子:只给「这台机器上两边自己下完的局」—— 本地对局、人机自由对弈。
 * 不能只看 `game_type === 'free'`:大厅局和星阵人机局后端**也是 `free`**,数子在那两种局里是另一条协议。
 * 分得开它们的是座位字面量:kiosk 人机局 AI 座位是 `player:ai`,大厅/星阵两边都是裸 `human`。
 */
export function autoCountEligible(gs: GameState | null | undefined, engineMode: boolean): boolean {
  if (!gs || engineMode) return false;
  if (gs.game_type === 'pvp_local') return true;
  if ((gs.game_type ?? 'free') !== 'free') return false;
  return gs.players_info.B.player_type === 'player:ai' || gs.players_info.W.player_type === 'player:ai';
}

export interface UseAutoCountOptions {
  sessionId: string | null | undefined;
  /** 调用方算好的「现在就该数」:`state.awaiting_count` ∧ 没有结果 ∧ `autoCountEligible`。 */
  awaitingCount: boolean;
  /** 当前节点 id。**同一个节点只自动数一次** —— 分析结果回来会再推一次同节点的 state。 */
  nodeId: number | null | undefined;
  /** 数子成功后把终局 state 交回去(GamePage 传 `session.setGameState`)。 */
  onState: (state: GameState) => void;
}

export interface AutoCountView { status: AutoCountStatus; reason: string | null; retry: () => void }

/**
 * **状态是算出来的,不是 effect 里 set 的**:「该数且这一轮还没失败」就是 `counting`。
 * 失败结论带上它属于哪一轮(`key`);换节点 / 按重试 ⇒ `key` 变,旧结论自然作废。
 * 这样 effect 体里没有同步 setState(仓里 `react-hooks/set-state-in-effect` 开着)。
 */
export function useAutoCount({ sessionId, awaitingCount, nodeId, onState }: UseAutoCountOptions): AutoCountView {
  const { t } = useTranslation();
  const [epoch, setEpoch] = useState(0);
  const [failure, setFailure] = useState<{ key: string; error: unknown } | null>(null);
  const onStateRef = useRef(onState);
  useEffect(() => { onStateRef.current = onState; }, [onState]);

  const key = awaitingCount && sessionId ? `${sessionId}|${nodeId ?? ''}|${epoch}` : null;

  useEffect(() => {
    if (!key || !sessionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const attempt = async (n: number) => {
      try {
        const res = await API.requestCount(sessionId);
        if (cancelled) return;
        if (res?.state) onStateRef.current(res.state as GameState);
      } catch (error) {
        if (cancelled) return;
        if (countErrorCode(error) === 'analysis_pending' && n < AUTO_COUNT_BACKOFF_MS.length) {
          timer = setTimeout(() => { void attempt(n + 1); }, AUTO_COUNT_BACKOFF_MS[n]);
          return;
        }
        setFailure({ key, error });
      }
    };
    void attempt(0);
    return () => { cancelled = true; if (timer !== undefined) clearTimeout(timer); };
  }, [key, sessionId]);

  const retry = useCallback(() => { setEpoch((e) => e + 1); }, []);

  if (!key) return { status: 'idle', reason: null, retry };
  if (failure?.key === key) return { status: 'failed', reason: countErrorMessage(failure.error, t), retry };
  return { status: 'counting', reason: null, retry };
}
```

- [ ] **Step 5: 跑测试确认绿，再跑 lint（hook 规则开着）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/hooks/useAutoCount.test.ts
npx eslint src/kiosk/hooks/useAutoCount.ts src/kiosk/utils/countErrors.ts
```
预期：vitest 10 passed（useAutoCount 5 + autoCountEligible 5）；eslint 无输出。

- [ ] **Step 6: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/hooks/useAutoCount.ts katrain/web/ui/src/kiosk/hooks/useAutoCount.test.ts
git commit -m "$(cat <<'MSG'
feat(kiosk-local): useAutoCount —— 双方各停一手后自动数子

analysis_pending 按 1/2/3/4/5 秒退避（累计 15 秒）；其余失败立即停下，
按原因码说真话并给重试。只对本地对局与人机自由对弈生效。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

### Task S2b-3: 右栏按 `pvp_local` 收窄 ——「数子 · 停一手 · 认输」，门槛读 `count_min_moves`，等数子时键亮

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（import 区约 L1-10；右栏账注释约 L174-177；`countMin`/`canCount` 约 L187-189；`analysisActions` 定义约 L268；`.ghint` 三元约 L421-428）
- Test: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx`（在最后一个 `test(...)` 之后、`describe` 的 `});` 之前追加）

**Interfaces:**
- Consumes：`GameState.awaiting_count`（S2b-1）、`autoCountEligible(gs, engineMode)`（S2b-2）、`GameState.count_min_moves`（已存在，`api.ts` 约 L77）。
- Produces：无新导出。行为：`game_type === 'pvp_local'` 时 `data-testid="game-actions"` 下只有「数子 / 停一手 / 认输」三键；自由对弈、升降级、大厅、星阵的右栏不变。

- [ ] **Step 1: 写失败测试**（追加到 `GameControlPanel.test.tsx` 的 `describe('GameControlPanel')` 末尾；文件顶部 import 改为 `import { render, screen, within } from '@testing-library/react';`）

```tsx
  // ── 本地对局右栏(v2 D1)────────────────────────────────────────────────
  // 「领地」「AI 支招」**撤掉不是灰着**:这一局开局就定死不接引擎辅助,永久不可用 → 不渲染。
  // 结构断言(在不在 DOM),不是布局断言;右栏高度与滚动在 kiosk-screen-05-game.spec.ts 里量。
  const actionLabels = () =>
    within(screen.getByTestId('game-actions')).getAllByRole('button').map((b) => b.textContent?.trim());

  test('本地对局:右栏只有 数子 · 停一手 · 认输', () => {
    panel({ game_type: 'pvp_local', history: hist([]) });
    expect(actionLabels()).toEqual(['数子', '停一手', '认输']);
    expect(screen.queryByText('领地')).toBeNull();
    expect(screen.queryByText('AI支招')).toBeNull();
    expect(screen.getByRole('switch', { name: '坐标' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '手数' })).toBeInTheDocument();
  });

  test('自由对弈右栏不受影响:领地仍在', () => {
    panel({ game_type: 'free' });
    expect(screen.getByText('领地')).toBeInTheDocument();
  });

  test('「数子要下满 N 手」的 N 读服务端下发的 count_min_moves(9 路 22)', () => {
    panel({ game_type: 'pvp_local', board_size: [9, 9], count_min_moves: 22, history: hist([['E5', 'B']]) });
    expect(screen.getByText('数子要下满 22 手')).toBeInTheDocument();
    expect(screen.getByText('数子').closest('button')).toBeDisabled();
  });

  test('本地对局登录态之外也不说「领地 / 支招 / 图表 登录后可用」—— 那三颗键这一局根本没有', () => {
    panel({ game_type: 'pvp_local', count_min_moves: 22, history: hist([['E5', 'B']]) }, { analysisRequiresLogin: true });
    expect(screen.queryByText('领地 / 支招 / 图表 登录后可用')).toBeNull();
    expect(screen.getByText('数子要下满 22 手')).toBeInTheDocument();
  });

  test('双 pass 后后端在等数子(awaiting_count)⇒ 手数不够也亮,右端不再说门槛', () => {
    panel({
      game_type: 'pvp_local', count_min_moves: 100, awaiting_count: true,
      history: hist([['Q16', 'B'], ['pass', 'W'], ['pass', 'B']]),
      players_info: {
        ...mockGameState.players_info,
        B: { ...mockGameState.players_info.B, player_type: 'player:human' },
        W: { ...mockGameState.players_info.W, player_type: 'player:human' },
      },
    });
    expect(screen.getByText('数子').closest('button')).not.toBeDisabled();
    expect(screen.queryByText(/数子要下满/)).toBeNull();
  });
```

- [ ] **Step 2: 执行时先核实 prop 名，再跑测试确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
grep -n "analysisRequiresLogin" src/kiosk/components/game/GameControlPanel.tsx | head -3
npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx
```
预期：`analysisRequiresLogin` 是 props 解构里的名字（若它是由别的 prop 算出来的，把用例里的 `{ analysisRequiresLogin: true }` 换成那个 prop，写进 commit message）。vitest：「只有 数子 · 停一手 · 认输」红（多了 领地 / AI支招）、「登录后可用」那条红、「awaiting_count」那条红（按钮 disabled）；其余绿。

- [ ] **Step 3: 实现 `GameControlPanel.tsx`**

(a) import 区 `import { isRankedGameType } ...` 之后加：
```tsx
import { autoCountEligible } from '../../hooks/useAutoCount';
```
(b) 右栏账注释（`右栏 516 的账(自由对弈)…余 15 落在动作区上面。` 那两行）之后追加两行：
```tsx
 * 本地对局:44 + 60 + 60 + 40 + 52(三个键一行)+ 4×12 = 304,余 212 **全落在动作区上面**
 * —— 这个数只在真浏览器里量,见 `tests/kiosk-screen-05-game.spec.ts` 的本地对局那几条。
```
(c) `const canCount = !isGameOver && moves >= countMin;` 替换为：
```tsx
  // N 取服务端下发的 `count_min_moves`(S2a 起按路数缩放:19 路 100 / 13 路 47 / 9 路 22);
  // `?? 100` 只兜「老服务端不带这个字段」,不是前端自己的门槛。
  // 双 pass 之后后端在等数子(`awaiting_count`),`/api/count/request` 跳过手数门槛 ⇒ 键跟着亮。
  // 只认自动数子那两种局(大厅 / 星阵局后端也可能报这个位,但数子在那儿是另一条协议)。
  const awaitingCount = !!gameState.awaiting_count && autoCountEligible(gameState, engineMode);
  const canCount = !isGameOver && (awaitingCount || moves >= countMin);

  // 本地对局(两个人面对面)。v2 D1:**不接引擎辅助** ——「领地」「AI 支招」整颗撤掉(不是灰着:
  // 开局就定死没有,永久不可用 → 撤掉)。后台分析照跑、只给数子用,见 `GamePage` 的 `wantAnalysis`。
  const localGame = gameState.game_type === 'pvp_local';
```
(d) `const analysisActions: KioskAction[] = engineMode ? [] : [` 改为：
```tsx
  const analysisActions: KioskAction[] = (engineMode || localGame) ? [] : [
```
(e) `.ghint` 里 `?? (analysisRequiresLogin` 改为（没有分析键的局不说「登录后可用」）：
```tsx
            ?? (analysisRequiresLogin && analysisActions.length > 0
```

- [ ] **Step 4: 跑测试确认绿 + 类型检查**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/components/game/GameControlPanel.test.tsx
npx tsc -b
```
预期：全部 passed（原有用例 + 新增 5 条）；`tsc -b` exit 0。

- [ ] **Step 5: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.test.tsx
git commit -m "$(cat <<'MSG'
feat(kiosk-local): 本地对局右栏只留 数子 · 停一手 · 认输

撤掉「领地」「AI 支招」（永久不可用 → 撤掉，不是灰着）；
「数子要下满 N 手」读服务端 count_min_moves；awaiting_count 时数子键亮。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

### Task S2b-4: GamePage —— 两个出口（退出不保存 / 认输选方）、自动数子接线、数子失败说真实原因

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（import 约 L1-32；state 约 L170-172；`wantAnalysis` effect 约 L292-302 之后插 `useAutoCount`；`isGameOver` 约 L361 之后加 `localGame`；`handleAction` 的 count 分支约 L433-443；认输确认框约 L733-758；退出确认框约 L760-785；Snackbar 约 L864-870）
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`（GameControlPanel mock 约 L23-32 加一颗 `MOCK_COUNT`；文件末尾 `describe('3D board removed')` 之前追加一个 describe）

**Interfaces:**
- Consumes：`API.deleteSession`、`handleAction(action, opts?)`、`ApiError.detail`、`countErrorMessage`（S2b-1）；`useAutoCount`、`autoCountEligible`（S2b-2）；`clearActiveSession('game')`（`kiosk/utils/activeSession.ts`，已存在）。
- Produces：页面行为（无新导出）——
  - `pvp_local` 未终局按「退出对局」：确认框「这局还没下完，退出后不会保存」+「继续下 / 退出不保存」→ `API.deleteSession(sessionId)` → `clearActiveSession('game')` → `navigate('/kiosk/play')`；删除失败不离开、Snackbar 报错。
  - `pvp_local` 按「认输」：确认框「谁认输？」+「黑方认输 / 白方认输 / 取消」→ `session.handleAction('resign', { color })`。
  - 自动数子：`data-testid="auto-count-status"` 的 Alert，`counting` 时「正在数子…」，`failed` 时原因 + 「重试」键。
  - 其它模式的两个确认框逐字不变。

> **本 Task 不动 `wantAnalysis`**（spec §3.1：本地对局后台分析照跑，数子读的就是这份分数）。今天 `analysisToggles.score` 初值为 `true`，而本地对局右栏已没有「图表」开关能把它关掉 ⇒ `wantAnalysis` 恒真。下面加一条用例把「本地对局每换一手调 `analyzeCurrent`」钉住，防的是有人顺手把本地对局从这个 effect 里排除。

- [ ] **Step 1: 改 GameControlPanel mock**（`GamePage.test.tsx` 约 L28-30），在 `MOCK_RESIGN` 按钮下加一行：

```tsx
      <button onClick={() => props.onAction('count')}>MOCK_COUNT</button>
```

- [ ] **Step 2: 写失败测试**（追加在 `describe('3D board removed'` 之前；文件顶部 `import { API, type GameState } from '../../api';` 改为 `import { API, ApiError, type GameState } from '../../api';`）

```tsx
  describe('本地对局 v2:两个出口 + 数子', () => {
    const human = { ...basePlayer, name: '' };
    const localPair: GameState['players_info'] = {
      B: { ...human, player_type: 'player:human' }, W: { ...human, player_type: 'player:human' },
    };
    const local = (over: Partial<GameState> = {}) =>
      makeGameState({ players_info: localPair, game_type: 'pvp_local', ...over });

    it('认输先问谁认输,按「白方认输」⇒ handleAction 带 color=W', async () => {
      mockGameState = local();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      expect(screen.getByText('谁认输？')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '黑方认输' })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '白方认输' }));
      await waitFor(() => expect(mockHandleAction).toHaveBeenCalledWith('resign', { color: 'W' }));
    });

    it('认输框按「取消」⇒ 不发请求', () => {
      mockGameState = local();
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      fireEvent.click(screen.getByRole('button', { name: '取消' }));
      expect(mockHandleAction).not.toHaveBeenCalled();
    });

    it('未终局退出 ⇒ 删会话、清活动会话、回对弈首页,绝不认输', async () => {
      mockGameState = local();
      const del = vi.spyOn(API, 'deleteSession').mockResolvedValue(undefined);
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        expect(screen.getByText('这局还没下完，退出后不会保存')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '退出不保存' }));
        expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
        expect(del).toHaveBeenCalledWith('test-session');
        expect(clearActiveSession).toHaveBeenCalledWith('game');
        expect(mockHandleAction).not.toHaveBeenCalled();
      } finally { del.mockRestore(); }
    });

    it('删会话失败 ⇒ 不离开、说出来(不能装作已退出)', async () => {
      mockGameState = local();
      const del = vi.spyOn(API, 'deleteSession').mockRejectedValue(new ApiError(500, 'Request failed 500: boom'));
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        fireEvent.click(screen.getByRole('button', { name: '退出不保存' }));
        expect(await screen.findByText('退出失败，请重试')).toBeInTheDocument();
        expect(screen.queryByText('PLAY_PAGE')).toBeNull();
        expect(clearActiveSession).not.toHaveBeenCalledWith('game');
      } finally { del.mockRestore(); }
    });

    it('已终局 ⇒ 直接离开,不弹框、不删会话', async () => {
      mockGameState = local({ end_result: 'W+R' });
      const del = vi.spyOn(API, 'deleteSession').mockResolvedValue(undefined);
      try {
        renderPage();
        fireEvent.click(screen.getByText('退出对局'));
        expect(await screen.findByText('PLAY_PAGE')).toBeInTheDocument();
        expect(del).not.toHaveBeenCalled();
      } finally { del.mockRestore(); }
    });

    it('手动数子失败按原因码说真话,不再一律「手数不足或已结束」', async () => {
      mockGameState = local();
      const rc = vi.spyOn(API, 'requestCount')
        .mockRejectedValue(new ApiError(400, 'x', { code: 'analysis_pending', message: 'x' }));
      try {
        renderPage();
        fireEvent.click(screen.getByText('MOCK_COUNT'));
        expect(await screen.findByText('还在算这一手的形势，稍等再数')).toBeInTheDocument();
      } finally { rc.mockRestore(); }
    });

    it('awaiting_count ⇒ 自动数子,屏上说「正在数子…」', async () => {
      mockGameState = local({ awaiting_count: true });
      const rc = vi.spyOn(API, 'requestCount').mockReturnValue(new Promise(() => {}));
      try {
        renderPage();
        expect(await screen.findByText('正在数子…')).toBeInTheDocument();
        expect(rc).toHaveBeenCalledWith('test-session');
      } finally { rc.mockRestore(); }
    });

    it('本地对局后台分析照跑(数子读这份分数)—— 不许把 pvp_local 排除出 analyzeCurrent', () => {
      mockGameState = local();
      const an = vi.spyOn(API, 'analyzeCurrent').mockResolvedValue({} as never);
      try {
        renderPage();
        expect(an).toHaveBeenCalledWith('test-session');
      } finally { an.mockRestore(); }
    });

    it('非本地对局的认输框逐字不变:确认后 handleAction 只带 action', async () => {
      mockGameState = makeGameState({ players_info: localPair, game_type: 'free' });
      renderPage();
      fireEvent.click(screen.getByText('MOCK_RESIGN'));
      fireEvent.click(screen.getByRole('button', { name: '认输' }));
      await waitFor(() => expect(mockHandleAction).toHaveBeenCalledWith('resign'));
    });
  });
```

- [ ] **Step 3: 跑测试确认红**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.test.tsx
```
预期：新 describe 里「认输先问谁认输」「取消」（找不到「黑方认输」→ 其实取消那条可能绿，可接受）、「未终局退出」「删会话失败」「手动数子失败」「awaiting_count」红；「已终局直接离开」「analyzeCurrent」「非本地对局认输」绿（它们钉的是今天已成立、本 Task 不许改坏的行为）；原有用例全绿。**若 `analyzeCurrent` 那条红**：先 `grep -n "analyzeCurrent:" src/api.ts` 核对它是不是只收 `sessionId`，按实际签名改断言，不许改实现去迁就。

- [ ] **Step 4: 实现 `GamePage.tsx`**

(a) import 区 `import { AiLadderSettlementAlert, ...` 之后加：
```tsx
import { useAutoCount, autoCountEligible } from '../hooks/useAutoCount';
import { countErrorMessage } from '../utils/countErrors';
```
(b) `const [resignError, setResignError] = useState<string | null>(null);` 之后加：
```tsx
  const [exitError, setExitError] = useState<string | null>(null);
```
(c) `wantAnalysis` 那个 `useEffect(...)` 的结尾 `}, [engineMode, wantAnalysis, ...]);` 之后插入（**必须在任何 early return 之前** —— 它是 hook；执行时 `grep -n "return (" src/kiosk/pages/GamePage.tsx | head -3` 确认插入点在第一处 early return 之上）：
```tsx
  // 双 pass 之后自动数子(v2-design §3.4)。只给本地对局与人机自由对弈(`autoCountEligible`);
  // 判据取服务端下发的 `awaiting_count`,前端不自己数 pass。
  const autoCount = useAutoCount({
    sessionId,
    awaitingCount: !!gs && !gs.end_result && !!gs.awaiting_count && autoCountEligible(gs, engineMode),
    nodeId: gs?.current_node_id,
    onState: session.setGameState,
  });
```
(d) `const isGameOver = !!gameState.end_result;` 之后加：
```tsx
  // 本地对局(两个人面对面):退出 = 删会话不存谱;认输要说是哪一方(v2 D2)。
  const localGame = gameState.game_type === 'pvp_local';
```
(e) `handleAction` 的 count 分支：`} catch {` + `setCountError(t('Cannot count yet ...', '暂时不能数子（对局手数不足或已结束）'));` 替换为：
```tsx
      } catch (error) {
        // 按原因码说真话(P6):盒上最常见的是分析还没回来,不是手数不足。
        setCountError(countErrorMessage(error, t));
      }
```
同分支上方那两行注释里 `Errors are usually the min-move guard or an already-finished game.` 删掉（已不成立）。

(f) 在 `handleExit` 之后加：
```tsx
  // 本地对局「退出不保存」。删除失败**不离开**:装作退出了,会话却还在进程里、活动会话也还指着它。
  const handleExitWithoutSaving = async () => {
    if (!sessionId) return;
    try {
      await API.deleteSession(sessionId);
    } catch {
      setExitError(t('game:exit_failed', '退出失败，请重试'));
      return;
    }
    setShowExitConfirm(false);
    clearActiveSession('game');
    navigate('/kiosk/play');
  };

  const handleLocalResign = async (color: 'B' | 'W') => {
    try {
      await session.handleAction('resign', { color });
      setShowResignConfirm(false);
    } catch (error) {
      setResignError(error instanceof Error ? error.message : t('Resign failed, retry', '认输失败，请重试'));
    }
  };
```

(g) 认输确认框 `<Dialog open={showResignConfirm} ...>` 整块替换为「本地对局一支 + 原样一支」：
```tsx
      {/* Resign confirmation (state D) */}
      {localGame ? (
        /* 本地对局:两个人都在屏前,「认输」不能默认判轮到走的那一方(P5)—— 先问谁认输。 */
        <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
          <DialogTitle sx={{ color: 'text.primary' }}>{t('game:who_resigns', '谁认输？')}</DialogTitle>
          <DialogActions>
            <Button onClick={() => setShowResignConfirm(false)}>{t('Cancel', '取消')}</Button>
            <Button color="error" onClick={() => { void handleLocalResign('B'); }}>
              {t('game:black_resigns', '黑方认输')}
            </Button>
            <Button color="error" onClick={() => { void handleLocalResign('W'); }}>
              {t('game:white_resigns', '白方认输')}
            </Button>
          </DialogActions>
        </Dialog>
      ) : (
        <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
          {/* ……原有 DialogTitle / DialogActions 逐字保留,不改一个字符…… */}
        </Dialog>
      )}
```
（上面 `……原有……逐字保留` 那一行在执行时**就是**把原 `<Dialog>` 的子节点原封剪进来，不是占位文字；`git diff` 里原有子节点应只有缩进变化。）

(h) 退出确认框同样拆两支：
```tsx
      {/* Exit confirmation */}
      {localGame ? (
        /* 本地对局退出 = 删会话、不存谱(v2 D2)。已终局不会走到这里(handleExit 直接离开)。 */
        <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
          <DialogTitle>{t('game:exit_unsaved_title', '这局还没下完，退出后不会保存')}</DialogTitle>
          <DialogActions>
            <Button onClick={() => setShowExitConfirm(false)}>{t('game:keep_playing', '继续下')}</Button>
            <Button color="error" onClick={() => { void handleExitWithoutSaving(); }}>
              {t('game:exit_unsaved', '退出不保存')}
            </Button>
          </DialogActions>
        </Dialog>
      ) : (
        <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
          {/* ……原有子节点逐字保留(同上)…… */}
        </Dialog>
      )}
```

(i) `<Snackbar open={!!resignError} ...>...</Snackbar>` 之后加：
```tsx
      <Snackbar open={!!exitError} autoHideDuration={5000} onClose={() => setExitError(null)}>
        <Alert severity="error" onClose={() => setExitError(null)}>{exitError}</Alert>
      </Snackbar>
      {/* 自动数子:进行中与失败都**不自动消失** —— 失败那句是这一局唯一的出路说明,重试键就挂在它上面。 */}
      <Snackbar open={autoCount.status !== 'idle'} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert
          data-testid="auto-count-status"
          severity={autoCount.status === 'failed' ? 'warning' : 'info'}
          action={autoCount.status === 'failed'
            ? <Button color="inherit" size="small" onClick={autoCount.retry}>{t('game:retry', '重试')}</Button>
            : undefined}
        >
          {autoCount.status === 'failed' ? autoCount.reason : t('game:counting', '正在数子…')}
        </Alert>
      </Snackbar>
```

- [ ] **Step 5: 跑测试确认绿；lint、类型、两个构建（`api.ts`/`useGameSession.ts` 是共享区）**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
npx vitest run src/kiosk/pages/GamePage.test.tsx src/kiosk/components/game src/kiosk/hooks/useAutoCount.test.ts src/kiosk/utils/countErrors.test.ts src/api.localPlayV2.test.ts
npx eslint src/kiosk/pages/GamePage.tsx src/api.ts src/hooks/useGameSession.ts
npx tsc -b
npm run build
npm run build:kiosk-2d
```
预期：vitest 全部 passed；eslint 无输出；`tsc -b` exit 0；`npm run build` 以 `✓ built in` 结束；`build:kiosk-2d` 结尾 `verify:kiosk-2d` exit 0（无 `THREE.` / `@react-three` 命中）。

- [ ] **Step 6: Commit**

```bash
cd /Users/fan/Repositories/katrain-kiosk-local-play
git add katrain/web/ui/src/kiosk/pages/GamePage.tsx katrain/web/ui/src/kiosk/pages/GamePage.test.tsx
git commit -m "$(cat <<'MSG'
feat(kiosk-local): 退出不再等于认输，认输先问是哪一方；双 pass 自动数子

本地对局：退出 = 删会话不存谱（删除失败不离开）；认输框「黑方认输 / 白方认输 / 取消」。
awaiting_count 时自动数子并显示进度，失败说真实原因并给重试；手动数子失败同样按原因码出文案。
其它模式两个确认框逐字不变。

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
MSG
)"
```

---

---

## 切片 S3：按用时下（本地对局的钟真的会走、会判超时）

**目标**：本地对局（`game_type === 'pvp_local'`）设了用时时，玩家卡上显示真实倒计时（主时间 / 读秒 / 超时三态），轮到的一方钟走完时前端调 `/api/timeout`，后端先核实再判「对方+T」并落账；没用完回 409 附最新 state，前端据此重算。不限时、自由对弈、升降级、galaxy 的钟与超时行为不变。

**覆盖 spec**：§3.3 全部；§6.1「玩家卡计时三态」视觉关卡；§6.2 承重实测（玩家卡加钟）；§6.3 超时三条后端用例。**覆盖问题**：P1、P2（仅本地对局；自由对弈的「仅读秒」显示不在本切片）。

**Task 列表**
- Task S3-1: `computeClock` 纯函数（共享区）+ galaxy `PlayerCard` 改用它（行为逐格不变）
- Task S3-2: kiosk 玩家卡钟三态（界面，隔离 fixture）
- Task S3-3: 四图视觉关卡 + 承重实测 + ⏸ Fan 确认
- Task S3-4: 后端 `is_time_exhausted` + `/api/timeout` 在 pvp_local 下先核实
- Task S3-5: 前端到点调 `/api/timeout` + 409 重算 + 终局卡「黑方超时负」
- Task S3-6: 集成验收（真浏览器，真后端）+ 删除 fixture

---

### Task S3-1: computeClock 纯函数（共享区）+ PlayerCard 改用它

**Files:**
- Create: `katrain/web/ui/src/utils/gameClock.ts`
- Create: `katrain/web/ui/src/utils/gameClock.test.ts`
- Modify: `katrain/web/ui/src/components/PlayerCard.tsx`（约 L109-169：从 `// Timer Breakdown` 到 `const hasTimedOut = …` 那一行；L1-10 import 区加一行）

**Interfaces:**
- Consumes: 无（纯函数）
- Produces（契约原文，名字不许改）:
  ```ts
  export interface ClockSettings { main_time: number; byo_length: number; byo_periods: number } // main_time 单位：分钟
  export interface ClockInput { settings: ClockSettings | null | undefined; mainTimeUsed: number; periodsUsed: number; nodeTimeUsed: number; active: boolean; clientElapsed: number }
  export interface ClockView { showTimer: boolean; phase: 'main' | 'byoyomi' | 'expired'; mainTimeLeft: number; byoyomiLeft: number; periodsLeft: number }
  export function computeClock(input: ClockInput): ClockView;
  ```
  语义：`byo_length`/`byo_periods` 过 `max(1, …)`（与 `interface.py` `update_timer` 同一套）；「开没开用时」看**原始值** `main_time > 0 || byo_length > 0`；读秒扣次用 `>`；`phase === 'expired'` ⇔ 主时间剩 0 且读秒次数用满。

- [ ] **Step 1: 执行时先核实锚点**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
  grep -n "Timer Breakdown\|const hasTimedOut\|Countdown beep" src/components/PlayerCard.tsx
  ls src/utils/gameClock.ts 2>&1; grep -rn "computeClock" src | head
  ```
  预期：三处命中（HEAD 1b6c67b5 时为 L109 / L150 / L169）；`gameClock.ts` 不存在；`computeClock` 零命中。行号漂了以函数内文本为准。

- [ ] **Step 2: 写失败的测试** —— 新建 `src/utils/gameClock.test.ts`：

```ts
import { describe, expect, it } from 'vitest';
import { computeClock, type ClockInput } from './gameClock';

const S = (main_time: number, byo_length = 30, byo_periods = 3) => ({ main_time, byo_length, byo_periods });
const input = (over: Partial<ClockInput>): ClockInput => ({
  settings: S(10), mainTimeUsed: 0, periodsUsed: 0, nodeTimeUsed: 0, active: true, clientElapsed: 0, ...over,
});

/**
 * `components/PlayerCard.tsx`(HEAD 1b6c67b5,L109-166)抽函数**之前**的算法,逐行照抄,
 * 只删了提示音那段副作用。它在这里只做一件事:证明抽出来的 `computeClock` 在 galaxy
 * 能开出来的用时范围内**一个数都没变**。
 *
 * 删除条件:galaxy 玩家卡的钟**有意**改行为的那一次提交,连同下面那条「逐格对照」一起删。
 */
function legacyPlayerCard(i: ClockInput) {
  let mainTimeLeft = 0;
  let byoyomiLeft = 0;
  let periodsLeft = 0;
  let showTimer = false;
  const settings = i.settings;
  if (settings && (settings.main_time > 0 || settings.byo_length > 0)) {
    showTimer = true;
    const byoNum = settings.byo_periods;
    const byoLen = settings.byo_length;
    const mainTimeTotal = settings.main_time * 60;
    const currentMainUsed = i.mainTimeUsed + (i.active && mainTimeTotal > i.mainTimeUsed ? i.clientElapsed : 0);
    mainTimeLeft = Math.max(0, mainTimeTotal - currentMainUsed);
    if (mainTimeLeft > 0) {
      byoyomiLeft = byoLen;
      periodsLeft = byoNum - i.periodsUsed;
    } else {
      const mainTimeAvailableAtNodeStart = Math.max(0, mainTimeTotal - i.mainTimeUsed);
      const totalNodeTime = i.nodeTimeUsed + (i.active ? i.clientElapsed : 0);
      let effectiveNodeTimeUsed = Math.max(0, totalNodeTime - mainTimeAvailableAtNodeStart);
      let currentPeriodsUsed = i.periodsUsed;
      while (effectiveNodeTimeUsed > byoLen && currentPeriodsUsed < byoNum) {
        effectiveNodeTimeUsed -= byoLen;
        currentPeriodsUsed += 1;
      }
      if (currentPeriodsUsed >= byoNum) {
        byoyomiLeft = 0;
        periodsLeft = 0;
      } else {
        byoyomiLeft = Math.max(0, byoLen - effectiveNodeTimeUsed);
        periodsLeft = byoNum - currentPeriodsUsed;
      }
    }
  }
  const hasTimedOut = showTimer && mainTimeLeft <= 0 && periodsLeft <= 0 && byoyomiLeft <= 0;
  return { showTimer, mainTimeLeft, byoyomiLeft, periodsLeft, hasTimedOut };
}

describe('computeClock —— PlayerCard 抽函数前后逐格一致(galaxy 行为不变)', () => {
  it('galaxy 开得出的用时范围内,每一格的四个数和「超时」都和旧算法相同', () => {
    // galaxy 开局设置的滑块:主时间 0-60 分、读秒 5-60 秒、次数 1-10(galaxy/pages/AiSetupPage.tsx:771-786);
    // 不计时那一档写 main_time=0 / byo_length=0。
    const settingsGrid = [null, S(0, 0, 3), S(0, 30, 3), S(1, 5, 1), S(10, 30, 3), S(60, 60, 10)];
    let checked = 0;
    for (const settings of settingsGrid) {
      for (const mainTimeUsed of [0, 30, 59.5, 60, 600, 3600]) {
        for (const periodsUsed of [0, 1, 3]) {
          for (const nodeTimeUsed of [0, 4, 29.9]) {
            for (const active of [true, false]) {
              for (const clientElapsed of [0, 0.4, 25, 31, 95]) {
                const i = { settings, mainTimeUsed, periodsUsed, nodeTimeUsed, active, clientElapsed };
                const legacy = legacyPlayerCard(i);
                const v = computeClock(i);
                expect({ ...v, phase: undefined, hasTimedOut: v.phase === 'expired' && v.showTimer },
                  JSON.stringify(i)).toEqual({ ...legacy, phase: undefined });
                checked += 1;
              }
            }
          }
        }
      }
    }
    expect(checked).toBe(6 * 6 * 3 * 3 * 2 * 5);
  });
});

describe('computeClock —— 三个阶段', () => {
  it('没有设置 / 不限时那一档(main 0 · byo 0):不显示钟,四个数全 0', () => {
    expect(computeClock(input({ settings: null }))).toEqual(
      { showTimer: false, phase: 'main', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 });
    expect(computeClock(input({ settings: S(0, 0, 3), clientElapsed: 500 })).showTimer).toBe(false);
  });

  it('主时间阶段:剩余主时间随客户端流逝减少;没轮到的一方不减', () => {
    expect(computeClock(input({ mainTimeUsed: 18 }))).toMatchObject({ phase: 'main', mainTimeLeft: 582, byoyomiLeft: 30, periodsLeft: 3 });
    expect(computeClock(input({ mainTimeUsed: 18, clientElapsed: 12 })).mainTimeLeft).toBe(570);
    expect(computeClock(input({ mainTimeUsed: 18, clientElapsed: 12, active: false })).mainTimeLeft).toBe(582);
  });

  it('客户端流逝跨过主时间:只有超出主时间的那部分进读秒', () => {
    // 快照时主时间还剩 10 秒,又过了 20 秒 ⇒ 读秒用了 10 秒
    expect(computeClock(input({ mainTimeUsed: 590, clientElapsed: 20 })))
      .toMatchObject({ phase: 'byoyomi', mainTimeLeft: 0, byoyomiLeft: 20, periodsLeft: 3 });
  });

  it('读秒阶段:服务端残量 + 客户端流逝;用满一段才扣一次', () => {
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 1, nodeTimeUsed: 6 })))
      .toMatchObject({ phase: 'byoyomi', byoyomiLeft: 24, periodsLeft: 2 });
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 1, nodeTimeUsed: 6, clientElapsed: 30 })))
      .toMatchObject({ phase: 'byoyomi', byoyomiLeft: 24, periodsLeft: 1 });
  });

  it('次数用满 ⇒ expired,三个数全 0', () => {
    expect(computeClock(input({ mainTimeUsed: 600, periodsUsed: 3 })))
      .toEqual({ showTimer: true, phase: 'expired', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 });
  });
});

describe('computeClock —— 与后端 update_timer / is_time_exhausted 的边界一致', () => {
  // 同一组数在 tests/test_time_exhausted.py 里喂给真的 `WebKaTrain.update_timer`。
  // 「仅读秒 30秒×3」(setupOptions.ts 的 byoOnly):主时间 0。
  const byoOnly = (clientElapsed: number) =>
    computeClock(input({ settings: S(0, 30, 3), clientElapsed }));

  it('正好 90.0 秒:后端循环是 `>`,第三段还没用满 ⇒ 不是 expired', () => {
    expect(byoOnly(90)).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 0, periodsLeft: 1 });
  });

  it('89.5 秒:还剩半秒、一次', () => {
    expect(byoOnly(89.5)).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 0.5, periodsLeft: 1 });
  });

  it('90.5 秒:三段用满 ⇒ expired', () => {
    expect(byoOnly(90.5).phase).toBe('expired');
  });

  it('byo_periods 为 0 时按 max(1, …) 算一次(后端同一套);原 PlayerCard 会在主时间一到就判超时', () => {
    const v = computeClock(input({ settings: S(10, 30, 0), mainTimeUsed: 600 }));
    expect(v).toMatchObject({ phase: 'byoyomi', byoyomiLeft: 30, periodsLeft: 1 });
    expect(legacyPlayerCard(input({ settings: S(10, 30, 0), mainTimeUsed: 600 })).hasTimedOut).toBe(true);
  });
});
```

- [ ] **Step 3: 跑测试确认红**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/utils/gameClock.test.ts
  ```
  预期：FAIL，`Failed to resolve import "./gameClock"`。

- [ ] **Step 4: 写实现** —— 新建 `src/utils/gameClock.ts`：

```ts
/**
 * 对局钟 —— 前端**唯一一份**倒计时算法。galaxy 的 `components/PlayerCard.tsx` 和
 * kiosk 的 `kiosk/components/game/GameControlPanel.tsx` 都调它,免得两份算法走散。
 *
 * ## 与后端是同一套语义(`katrain/web/interface.py` 的 `update_timer`)
 *
 * - `byo_length` / `byo_periods` 先过 `max(1, …)`,后端就是这么取的。
 * - 读秒次数只在「这一段用满**之后还多出来**」时才扣(`>`,不是 `>=`):
 *   后端的循环是 `while cn.time_used > byo_len and periods_used < byo_num`。
 *   所以正好用到 30.0 秒那一刻**还没超时**,多一丁点才算。
 * - `nodeTimeUsed` 是后端的 `cn.time_used` —— 它**只装主时间用完之后溢出的那部分**,
 *   而且每扣一次读秒就减掉一个 `byo_length`。所以它是「本段读秒已用」,不是「这一手总共想了多久」。
 * - 超时 = 主时间剩 0 且读秒次数用满 —— 后端 `game_end_rules.is_time_exhausted` 的判据,
 *   在循环语义下读秒用尽那一刻 `periods_used` 恰好等于 `byo_periods`。
 *
 * ## 调用方的责任
 *
 * - `nodeTimeUsed` 只对**轮到的一方**有意义(后端只下发轮到方的 `current_node_time_used`)。
 *   这里**原样使用**,不按 `active` 清零 —— 那是 `PlayerCard` 抽函数之前的行为,galaxy 本轮不改;
 *   kiosk 调用方给非轮到的一方传 0。
 * - `clientElapsed` 是「上一份服务端状态到现在」客户端流逝的秒数,只在 `active` 时计入。
 */
export interface ClockSettings { main_time: number; byo_length: number; byo_periods: number } // main_time 单位：分钟
export interface ClockInput {
  settings: ClockSettings | null | undefined;
  mainTimeUsed: number;      // 秒，这一方累计
  periodsUsed: number;       // 这一方已用读秒次数
  nodeTimeUsed: number;      // 秒，当前节点已用（只对轮到的一方有意义）
  active: boolean;           // 是否轮到这一方
  clientElapsed: number;     // 秒，上次服务端状态以来客户端流逝
}
export interface ClockView {
  showTimer: boolean;
  phase: 'main' | 'byoyomi' | 'expired';
  mainTimeLeft: number;      // 秒
  byoyomiLeft: number;       // 秒
  periodsLeft: number;
}

const NO_TIMER: ClockView = { showTimer: false, phase: 'main', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 };

export function computeClock(input: ClockInput): ClockView {
  const { settings, mainTimeUsed, periodsUsed, nodeTimeUsed, active, clientElapsed } = input;
  // 「开没开用时」看的是**原始值**:不限时那一档后端写的是 main_time=0 / byo_length=0。
  // 先过 max(1, …) 再判的话,不限时的局会凭空多出一个 1 秒的读秒。
  if (!settings || !(settings.main_time > 0 || settings.byo_length > 0)) return NO_TIMER;

  const byoLen = Math.max(1, settings.byo_length);
  const byoNum = Math.max(1, settings.byo_periods);
  const mainTotal = settings.main_time * 60;

  const mainUsedNow = mainTimeUsed + (active && mainTotal > mainTimeUsed ? clientElapsed : 0);
  const mainTimeLeft = Math.max(0, mainTotal - mainUsedNow);
  if (mainTimeLeft > 0) {
    return { showTimer: true, phase: 'main', mainTimeLeft, byoyomiLeft: byoLen, periodsLeft: byoNum - periodsUsed };
  }

  // 主时间在**这份快照里**还剩多少 —— 客户端流逝里只有超出它的那部分进读秒。
  const mainAvailableAtSnapshot = Math.max(0, mainTotal - mainTimeUsed);
  const nodeTime = nodeTimeUsed + (active ? clientElapsed : 0);
  let effective = Math.max(0, nodeTime - mainAvailableAtSnapshot);
  let used = periodsUsed;
  while (effective > byoLen && used < byoNum) {
    effective -= byoLen;
    used += 1;
  }
  if (used >= byoNum) return { showTimer: true, phase: 'expired', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 };
  return { showTimer: true, phase: 'byoyomi', mainTimeLeft: 0, byoyomiLeft: Math.max(0, byoLen - effective), periodsLeft: byoNum - used };
}
```

- [ ] **Step 5: 跑测试确认绿**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/utils/gameClock.test.ts
  ```
  预期：`Tests  10 passed (10)`（逐格对照 1 + 三个阶段 5 + 后端边界 4），0 failed。

- [ ] **Step 6: PlayerCard 改用 computeClock**

  `src/components/PlayerCard.tsx` import 区（`import { RAIL_TIGHT } from './railStyles';` 之后）加：
  ```tsx
  import { computeClock } from '../utils/gameClock';
  ```
  把 `// Timer Breakdown` 起、到 `const hasTimedOut = showTimer && mainTimeLeft <= 0 && periodsLeft <= 0 && byoyomiLeft <= 0;` 止的整段（HEAD 时 L109-169）替换为：
  ```tsx
  // Timer Breakdown —— 算法在 utils/gameClock.ts；kiosk 本地对局的钟用的是同一份，别在这里再写一遍。
  const clock = computeClock({
    settings: timer?.settings,
    mainTimeUsed: info.main_time_used,
    periodsUsed: info.periods_used,
    nodeTimeUsed: timer?.current_node_time_used ?? 0,
    active,
    clientElapsed,
  });
  const { showTimer, mainTimeLeft, byoyomiLeft, periodsLeft } = clock;

  // Countdown beep in last 5 seconds of byoyomi
  if (clock.phase === 'byoyomi' && active && timer?.settings.sound && onPlaySound) {
    const secondsRemaining = Math.ceil(byoyomiLeft);

    if (secondsRemaining <= 5 && secondsRemaining >= 1 && secondsRemaining !== lastCountdownSecondRef.current) {
      onPlaySound('countdownbeep');
      lastCountdownSecondRef.current = secondsRemaining;
    }

    // Reset when exiting countdown zone (entering new period or time > 6s)
    if (byoyomiLeft > 6) {
      lastCountdownSecondRef.current = null;
    }
  }

  // Timeout detection - trigger forfeit when time exhausted
  const hasTimedOut = clock.phase === 'expired';
  ```
  其后的 `useEffect`（超时触发）、`isCritical` / `isWarning` 与 JSX **一个字不改**——它们读的四个名字由上面的解构提供。

- [ ] **Step 7: 类型检查 + 两个构建 + 相关测试**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
  npx tsc -b
  npx vitest run src/utils/gameClock.test.ts src/components
  npx eslint src/utils/gameClock.ts src/components/PlayerCard.tsx
  npm run build
  npm run build:kiosk-2d
  ```
  预期：`tsc -b` 无输出退出 0（**不要用 `tsc --noEmit`，它检查 0 个文件**）；vitest 全绿（`src/components` 下的用例条数与 Step 1 之前跑一遍记下的条数一致）；eslint 0 error；两个构建都成功，`build:kiosk-2d` 末尾 `verify:kiosk-2d` exit 0。

- [ ] **Step 8: Commit**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play
  git add katrain/web/ui/src/utils/gameClock.ts katrain/web/ui/src/utils/gameClock.test.ts katrain/web/ui/src/components/PlayerCard.tsx
  git commit -m "$(cat <<'MSG'
  refactor(clock): 倒计时算法抽成共享纯函数 computeClock,galaxy 玩家卡逐格不变

  kiosk 本地对局要显示同一只钟(spec §3.3),两份算法会走散。byo 参数与后端
  update_timer 同取 max(1, …);逐格对照用例钉住 galaxy 可开出的用时范围内行为不变。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

### Task S3-2: kiosk 玩家卡钟三态（仅 pvp_local）+ 到点边沿回调

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`
  - L1 `import { useEffect, useRef } from 'react';`
  - L9 `import { useTranslation } …` 之后加一行 import
  - `interface Props` 末尾（HEAD 时 L47 `hardwareFault?: string | null;` 之后）
  - `const formatTime = …`（HEAD 时 L115-118）之后
  - 组件参数解构（HEAD 时 L181 `… hardwareFault = null,`）
  - 时钟栏整段：从注释 `// 时钟栏。kiosk 的局**不设时限**` 起，到 `/* 游客(无主会话)那一句。` 之前止（HEAD 时 L244-258，内含 `clockFor`）
- Create: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.clock.test.tsx`

**Interfaces:**
- Consumes: `computeClock`, `ClockView`（Task S3-1，`src/utils/gameClock.ts`）；`GameState.timer`（`src/api.ts` 约 L63，已有：`paused / main_time_used / current_node_time_used / next_player_periods_used / settings{main_time, byo_length, byo_periods, minimal_use, sound}`）；`GameState.players_info[c].main_time_used / periods_used`（已有）。
- Produces: `GameControlPanel` 新 prop `onTimeExpired?: () => void` —— 仅 `game_type === 'pvp_local'` 且设了用时、未终局时，**轮到的一方** `computeClock(...).phase` 从非 `expired` 变为 `expired` 的那一刻调用一次（边沿触发；新的服务端状态让钟回到非 expired 后再到 0 会再调）。Task S3-5 在 `kiosk/pages/GamePage.tsx` 里接它。
- 新 i18n key（S5 补 11 语言）：`game:clock_timeout`「超时」、`game:clock_byo_left`「读秒 · 剩 {n} 次」、`game:clock_byo_spec`「读秒 {len}秒×{n}」。

> ⚠️ S2b 也改这个文件（右栏按键）。本 Task 在 S2 全部合入之后做，锚点一律按**注释/代码文本**找，不按行号。

- [ ] **Step 1: 执行时先核实锚点**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
  F=src/kiosk/components/game/GameControlPanel.tsx
  grep -n "^import { useEffect, useRef } from 'react';\|hardwareFault?: string | null;\|^const formatTime\|hardwareFault = null,\|时钟栏。kiosk 的局\|游客(无主会话)那一句\|const clockFor\|const toMove\|isGameOver = false" $F
  grep -rn "clock_timeout\|clock_byo_left\|onTimeExpired" src | head
  ```
  预期：前 9 个锚点各命中 1 次（`const toMove` 必须在「时钟栏」注释**之前**——新代码要用它）；第二条 grep 零命中。

- [ ] **Step 2: 写失败的组件行为测试** —— 新建 `GameControlPanel.clock.test.tsx`：

  ```tsx
  import { render, screen } from '@testing-library/react';
  import { describe, test, expect, vi } from 'vitest';
  import GameControlPanel from './GameControlPanel';
  import type { GameState } from '../../../api';

  /**
   * 本地对局玩家卡上的钟(spec §3.3)。只断言**文字和回调**,不断言布局 ——
   * 布局归 tests/kiosk-screen-05-local-clock.spec.ts 那条真浏览器承重实测。
   * 客户端流逝恒为 0(没有推进定时器):每一格的读数完全由快照决定。
   */
  const timer = (over: Partial<NonNullable<GameState['timer']>> = {}): NonNullable<GameState['timer']> => ({
    paused: false, main_time_used: 0, current_node_time_used: 0, next_player_periods_used: 0,
    settings: { main_time: 10, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false },
    ...over,
  });
  const state = (over: {
    game_type?: GameState['game_type']; timer?: GameState['timer']; B?: { main_time_used: number; periods_used: number };
  }): GameState => ({
    game_id: 'clock', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
    game_type: over.game_type ?? 'pvp_local', count_min_moves: 100,
    current_node_id: 0, current_node_index: 0, history: [{ node_id: 0, score: 0, winrate: 0.5 }],
    player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 }, analysis: null,
    commentary: '', is_root: true, is_pass: false, end_result: null, children: [], ghost_stones: [],
    players_info: {
      B: { player_type: 'player:human', player_subtype: '', name: '小明', calculated_rank: '', periods_used: 0, main_time_used: 0, ...over.B },
      W: { player_type: 'player:human', player_subtype: '', name: '小红', calculated_rank: '', periods_used: 0, main_time_used: 0 },
    },
    note: '', timer: over.timer,
    ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
      show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
  } as GameState);
  const panel = (gs: GameState, onTimeExpired = vi.fn(), isGameOver = false) => (
    <GameControlPanel gameState={gs} onAction={() => {}} onNavigate={() => {}} analysisToggles={{}}
      onToggleAnalysis={() => {}} isGameOver={isGameOver} onTimeExpired={onTimeExpired} />
  );

  describe('本地对局玩家卡上的钟', () => {
    test('主时间阶段:大字剩余主时间,副标读秒规格', () => {
      render(panel(state({ timer: timer(), B: { main_time_used: 18, periods_used: 0 } })));
      expect(screen.getByText('09:42')).toBeInTheDocument();
      expect(screen.getAllByText('读秒 30秒×3')).toHaveLength(2);   // 两张卡都有钟
    });

    test('读秒阶段:大字本次读秒剩余,副标剩几次', () => {
      render(panel(state({
        timer: timer({ current_node_time_used: 6 }), B: { main_time_used: 600, periods_used: 1 },
      })));
      expect(screen.getByText('00:24')).toBeInTheDocument();
      expect(screen.getByText('读秒 · 剩 2 次')).toBeInTheDocument();
    });

    test('用尽:00:00 · 超时,并且只调一次 onTimeExpired', () => {
      const onTimeExpired = vi.fn();
      const exhausted = () => state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } });
      const { rerender } = render(panel(exhausted(), onTimeExpired));
      expect(screen.getByText('00:00')).toBeInTheDocument();
      expect(screen.getByText('超时')).toBeInTheDocument();
      rerender(panel(exhausted(), onTimeExpired));          // 钟停在 0:不连调
      expect(onTimeExpired).toHaveBeenCalledTimes(1);
    });

    test('409 带回的新状态让钟回到读秒 ⇒ 再走到 0 会再调一次', () => {
      const onTimeExpired = vi.fn();
      const { rerender } = render(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
      rerender(panel(state({ timer: timer({ current_node_time_used: 20 }), B: { main_time_used: 600, periods_used: 2 } }), onTimeExpired));
      expect(screen.getByText('00:10')).toBeInTheDocument();
      rerender(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
      expect(onTimeExpired).toHaveBeenCalledTimes(2);
    });

    test('已终局:不调 onTimeExpired', () => {
      const onTimeExpired = vi.fn();
      render(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired, true));
      expect(onTimeExpired).not.toHaveBeenCalled();
    });

    test('不限时的本地对局(main 0 · byo 0 · paused):仍是「第 N 手 / 不限时」', () => {
      render(panel(state({ timer: timer({ paused: true, settings: { main_time: 0, byo_length: 0, byo_periods: 3, minimal_use: 0, sound: false } }) })));
      expect(screen.getByText('第 1 手')).toBeInTheDocument();
      expect(screen.getByText('不限时')).toBeInTheDocument();
      expect(screen.queryByText('00:00')).toBeNull();
    });

    test('自由对弈即使带了用时也不走新钟、不调 onTimeExpired(非 pvp_local 一字不改)', () => {
      const onTimeExpired = vi.fn();
      render(panel(state({ game_type: 'free', timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
      expect(screen.queryByText('超时')).toBeNull();
      expect(screen.getByText('本局已下')).toBeInTheDocument();   // 旧分支:main_time_used>0 ⇒ 「10:00 本局已下」
      expect(onTimeExpired).not.toHaveBeenCalled();
    });
  });
  ```

- [ ] **Step 3: 跑测试确认红**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/components/game/GameControlPanel.clock.test.tsx
  ```
  预期：前 4 条 FAIL（找不到 `09:42` / `00:24` / `00:00` / `00:10`）；「已终局」「不限时」「自由对弈」三条今天就是绿的（它们钉的是不变的行为，改完后必须仍绿）。

- [ ] **Step 4: 实现 —— import、prop、两个辅助**

  1. L1 改为 `import { useEffect, useRef, useState } from 'react';`
  2. `import { useTranslation } from '../../../hooks/useTranslation';` 之后加：
     ```tsx
     import { computeClock, type ClockView } from '../../../utils/gameClock';
     ```
  3. `interface Props` 里 `hardwareFault?: string | null;` 之后加：
     ```tsx
       /**
        * 本地对局、设了用时,**轮到的一方**的钟走到 0(主时间 0 且读秒次数用满)的那一刻调一次。
        * 边沿触发:钟停在 0 不会连调;服务端回 409 带来新状态、钟重新有了余量,再走到 0 才会再调。
        * 判负与否由服务端核实(`/api/timeout`),这里只负责「屏上算出来到点了」。
        */
       onTimeExpired?: () => void;
     ```
  4. `const formatTime = …};` 之后加：
     ```tsx
     /** 本地对局钟的读数:分钟也补两位(`09:42`、`00:24`),照 spec §3.3 那张表。 */
     const formatClock = (seconds: number) => {
       const total = Math.ceil(Math.max(0, seconds));
       return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
     };

     /**
      * 「上一份服务端状态到现在,客户端过了几秒」。
      *
      * **按快照对象的身份归零,不按某个数归零。** 服务端每推一次状态(WS、HTTP 返回体、409 附带的状态)
      * 都是一个新的 `timer` 对象,里面的已用时间已经包含了到那一刻为止的流逝 —— 不归零会把同一段时间算两遍。
      * galaxy `PlayerCard` 只在 `main_time_used` 变化时归零,读秒阶段那个数不变,于是会重复计时;这里不照抄。
      * 归零不在 effect 里 `setState(0)`(`react-hooks/set-state-in-effect`):记下这次计时属于哪个快照,
      * 快照换了就当 0 返回,等下一拍再写新值。
      */
     function useClientElapsed(snapshot: object | undefined, running: boolean): number {
       const [tick, setTick] = useState<{ snapshot: object | undefined; elapsed: number }>({ snapshot: undefined, elapsed: 0 });
       useEffect(() => {
         if (!running) return;
         const startedAt = Date.now();
         const id = window.setInterval(() => {
           setTick({ snapshot, elapsed: (Date.now() - startedAt) / 1000 });
         }, 200);
         return () => window.clearInterval(id);
       }, [snapshot, running]);
       return running && tick.snapshot === snapshot ? tick.elapsed : 0;
     }
     ```
  5. 组件参数解构 `… hardwareFault = null,` 改为 `… hardwareFault = null, onTimeExpired,`。

- [ ] **Step 5: 实现 —— 替换时钟栏整段**

  把从 `  // 时钟栏。kiosk 的局**不设时限**` 起、到 `  /* 游客(无主会话)那一句。` **之前**止的整段（含旧 `clockFor`）替换为下面这段（旧 `clockFor` 的「本局已下 / 第 N 手 · 不限时」后半段逐字保留在新 `clockFor` 里）：

  ```tsx
  // ── 本地对局的钟(spec §3.3)────────────────────────────────────────────
  // 只有 `pvp_local` 走共享的 `computeClock`;自由对弈 / 升降级 / 星阵的钟栏一字不改(见 `clockFor` 后半段)。
  // 不限时那一档服务端写的是 main_time=0 / byo_length=0,`computeClock` 判 `showTimer: false`,同样落到后半段。
  const timer = gameState.timer;
  const localClockOn = gameState.game_type === 'pvp_local' && !!timer;
  const ticking = localClockOn && !isGameOver && !timer?.paused;
  const clientElapsed = useClientElapsed(timer, ticking);
  const localClock = (c: 'B' | 'W'): ClockView => computeClock({
    settings: localClockOn ? timer?.settings : null,
    mainTimeUsed: gameState.players_info[c].main_time_used,
    periodsUsed: gameState.players_info[c].periods_used,
    // 服务端只下发**轮到的一方**的本节点已用;另一方下一手从一段完整的读秒开始。
    nodeTimeUsed: c === toMove ? (timer?.current_node_time_used ?? 0) : 0,
    active: ticking && c === toMove,
    clientElapsed,
  });

  // 到点那一刻调一次。回调走 ref:调用方每次渲染都给一个新函数,放进依赖会让「停在 0」连调。
  const timeExpired = !isGameOver && localClock(toMove).phase === 'expired';
  const onTimeExpiredRef = useRef(onTimeExpired);
  useEffect(() => { onTimeExpiredRef.current = onTimeExpired; });
  useEffect(() => {
    if (timeExpired) onTimeExpiredRef.current?.();
  }, [timeExpired]);

  // 时钟栏(非本地对局,或本地对局不限时)。`main_time_used` 只有在真配了时限时才累加 ——
  // 那时才有「本局已下」可写。没有时限时,这一栏唯一为真的量是
  // **当前是第几手**,而那是**局面的量、不是某一方的量** ⇒ 只挂在轮到的那张卡上,
  // 另一张卡的时钟栏不渲染。两张都写「不限时」是把同一句话说两遍;
  // 写 `0:00 本局已下` 更糟 —— 那不是「用了 0 秒」,是「压根没在计」。
  const clockFor = (c: 'B' | 'W'): { value: string; label: string } | null => {
    const lc = localClock(c);
    if (lc.showTimer) {
      if (lc.phase === 'expired') return { value: formatClock(0), label: t('game:clock_timeout', '超时') };
      if (lc.phase === 'byoyomi') {
        return {
          value: formatClock(lc.byoyomiLeft),
          label: t('game:clock_byo_left', '读秒 · 剩 {n} 次').replace('{n}', String(lc.periodsLeft)),
        };
      }
      return {
        value: formatClock(lc.mainTimeLeft),
        label: t('game:clock_byo_spec', '读秒 {len}秒×{n}')
          .replace('{len}', String(timer?.settings.byo_length ?? 0))
          .replace('{n}', String(timer?.settings.byo_periods ?? 0)),
      };
    }
    const used = gameState.players_info[c].main_time_used;
    if (used > 0) return { value: formatTime(used), label: t('game:spent_this_game', '本局已下') };
    if (c !== toMove || isGameOver) return null;
    return {
      value: t('game:move_n', '第 {n} 手').replace('{n}', String((gameState.current_node_index ?? 0) + 1)),
      label: t('game:untimed', '不限时'),
    };
  };
  ```
  JSX 里两处 `clock={clockFor('W')}` / `clock={clockFor('B')}` 不用改。

- [ ] **Step 6: 跑测试确认绿 + 既有测试不回归**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui
  npx vitest run src/kiosk/components/game/
  npx tsc -b
  npx eslint src/kiosk/components/game/GameControlPanel.tsx
  ```
  预期：`GameControlPanel.clock.test.tsx` 7 passed；同目录既有 `GameControlPanel.test.tsx` 等全部仍绿；`tsc -b` 退出 0；eslint 0 error（尤其没有 `react-hooks/set-state-in-effect`、`react-hooks/rules-of-hooks`）。

- [ ] **Step 7: Commit**

  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play
  git add katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx katrain/web/ui/src/kiosk/components/game/GameControlPanel.clock.test.tsx
  git commit -m "$(cat <<'MSG'
  feat(kiosk-local): 本地对局玩家卡显示真实倒计时 —— 主时间 / 读秒 / 超时三态

  P2:选了用时屏上仍写「不限时」。仅 pvp_local 走共享 computeClock;到点边沿触发
  onTimeExpired(接线在后续提交)。自由对弈/升降级的钟栏不变,有用例钉住。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

> Task S3-3（四图 + 承重实测 + ⏸ Fan）按「相称性裁定」第 2 条取消；S3-4、S3-5 见文末「补充 Task」。

---

## 切片 S4：下完能复盘

**目标**：在盒子上（严格包，`token` 恒为 null、身份靠 cookie）下完一局之后，屏 19 能看到这一局、标题不编名字、能生成报告；从报告「去研究」能落到真棋盘；首页跨平台区能拿到真状态；而没写结果的导入谱 / 棋谱库 / 研究存档不再被误标「未终局」、不再被禁止生成报告。

**覆盖 spec**：§4.3 后半（`PlayPage.tsx` token 闸，P16）、§4.4（`isPlaySource` / `rowState` / `canAnalyzeSelected` / `rowTitle` / 首帧 loading，P14 P15 P17）、§4.5（研究页 token 闸，P13）、§4.6（`_record_ai_game` 名字回填，P12）。

**任务列表**
- Task S4-1: 复盘列表的来源判定与行文案（纯函数）
- Task S4-2: 屏 19 页面 —— `canAnalyzeSelected` 同判定 + 首帧 loading 不依赖 token
- Task S4-3: 研究页 `?user_game_id=` 与首页跨平台区去掉 token 闸
- Task S4-4: 屏 19 真浏览器文案用例 + 四图 + ⏸ Fan 确认
- Task S4-5: 后端：本地对局不回填登录用户名

---

### Task S4-1: 复盘列表的来源判定与行文案（纯函数）

**Files:**
- Modify: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts`
  - 在 `pointsUnit`（约 L8-18）之前新增导出 `isPlaySource`
  - `rowTitle`（约 L68-89）：替换 L76 `play_local` 那一行，并在其后补 `research` 分支
  - `outcomeLine`（约 L96-100）：无结果分支按来源分流
  - `rowState` 末行（约 L183）
- Test: `katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts`（在现有 `describe` 块里追加用例，文件末尾追加一个 `describe`）

**Interfaces:**
- Consumes: `UserGameSummary`（`src/api/userGamesApi.ts`，字段 `source: string`、`result: string | null`、`player_black / player_white: string | null`、`title`、`move_count`）
- Produces（契约名，照抄）：
  ```ts
  export function isPlaySource(source: string | null | undefined): boolean; // play_ai / play_local / play_human → true
  ```
  行为变化：`rowState` 对非对弈来源且无 `result` 返回 `{ kind: 'unanalyzed' }`；`rowTitle` 新增 `review:row_local_unnamed`（「本地对局 · 未记名」）与 `review:row_research`（「研究存档」）；`outcomeLine` 对非对弈来源无结果返回 `review:no_result_line`（「谱里没写结果」）。三个新 i18n key 由 S5 补 11 种语言。

> 说明：spec §4.4 只点名了 `rowState` 与 `rowTitle`，但 P14 的症状原文是「说成『下到第 N 手就退出了 · 未终局』」—— 前半句出自 `outcomeLine` 的无结果分支（L98-99）。只改 `rowState` 会留下一行「下到第 187 手就退出了」挂在一份导入谱上，所以 `outcomeLine` 一并改。

- [ ] **Step 1：写失败的测试。** 打开 `reviewPresentation.test.ts`：

  1a. 第 4 行 import 改为：
  ```ts
  import { isPlaySource, outcomeLine, rowDisc, rowState, rowTitle, yourColor } from './reviewPresentation';
  ```

  1b. 在 `describe('rowTitle —— 这一行是什么局', ...)` 块的最后一个 `it` 之后（该块结尾 `});` 之前，今天约 L66）插入：
  ```ts
  // P15:屏 04 承诺「名字留空就不编名字」⇒ 两个名字都空的本地局照稿子写「未记名」。
  it('本地对局两个名字都空写「未记名」,有一个名字就是「两人」', () => {
    expect(rowTitle(game({ source: 'play_local', player_black: '', player_white: '' }), null, t)).toBe('本地对局 · 未记名');
    expect(rowTitle(game({ source: 'play_local', player_black: null, player_white: '  ' }), null, t)).toBe('本地对局 · 未记名');
    expect(rowTitle(game({ source: 'play_local', player_black: '小明', player_white: '' }), null, t)).toBe('本地对局 · 两人');
  });

  it('研究存档有自己的标题,不落成「人机对弈」', () => {
    expect(rowTitle(game({ source: 'research', title: '柯洁 vs 申真谞' }), null, t)).toBe('研究存档 · 柯洁 vs 申真谞');
    expect(rowTitle(game({ source: 'research', title: null, player_black: null, player_white: null }), null, t))
      .toBe('研究存档');
  });
  ```

  1c. 在 `describe('outcomeLine —— 这一局怎么结束的', ...)` 块里、`it('后端存了别的写法就原样念,不猜', ...)` 之前插入：
  ```ts
  // P14:导入的谱没写 RE 不等于「中途退出」—— 那一句只属于对弈局。
  it('导入的谱、棋谱库、研究存档没有结果时说「谱里没写结果」,不说「就退出了」', () => {
    for (const source of ['import', 'kifu_library', 'research']) {
      expect(outcomeLine(game({ source, result: null, move_count: 187 }), null, t)).toBe('谱里没写结果');
    }
  });
  ```

  1d. 在 `describe('rowState —— 分析到哪一步了', ...)` 块的最后一个 `it` 之后（该块结尾 `});` 之前）插入：
  ```ts
  // P14:「未终局」挡的是「半局报告 + 离线算完再回去接着下」,那只对对弈局成立。
  it('「未终局」只给对弈局;没写结果的导入谱、棋谱库、研究存档算「未分析」', () => {
    for (const source of ['play_ai', 'play_local', 'play_human']) {
      expect(rowState(game({ source, result: null }), {})).toEqual({ kind: 'unfinished' });
    }
    for (const source of ['import', 'kifu_library', 'research']) {
      expect(rowState(game({ source, result: null }), {})).toEqual({ kind: 'unanalyzed' });
    }
  });
  ```

  1e. 文件末尾追加：
  ```ts
  describe('isPlaySource —— 这一局是不是下出来的', () => {
    it('人机、本地两人、在线人人算;导入、棋谱库、研究存档和空值都不算', () => {
      expect(['play_ai', 'play_local', 'play_human'].map((s) => isPlaySource(s))).toEqual([true, true, true]);
      expect(['import', 'kifu_library', 'research', '', null, undefined].map((s) => isPlaySource(s)))
        .toEqual([false, false, false, false, false, false]);
    });
  });
  ```

- [ ] **Step 2：跑测试确认红。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/components/report/reviewPresentation.test.ts
  ```
  预期：FAIL。`isPlaySource is not a function`（或 import 报错）；「未记名」「研究存档」「谱里没写结果」「未分析」四条断言失败。原有用例（含 `rowState(game({ result: null }), {})` → `unfinished`，默认来源是 `play_ai`）仍应通过。

- [ ] **Step 3：实现。** 编辑 `reviewPresentation.ts`：

  3a. 在 `export type TFn = ...`（L6）之后、`pointsUnit` 的注释块之前插入：
  ```ts
  /**
   * 这一局是不是**下出来的**(人机 / 本地两人 / 在线人人)。
   *
   * 只有对弈局才有「没下完」这回事:没有 `result` 就是中途退出了。
   * 导入的 SGF、棋谱库、研究存档**本来就可能不带结果**(SGF 没写 `RE`)——
   * 那是「谱里没写」,不是「没下完」,不能拿对弈局的口径去念、更不能因此不给报告(P14)。
   */
  export function isPlaySource(source: string | null | undefined): boolean {
    return source === 'play_ai' || source === 'play_local' || source === 'play_human';
  }
  ```

  3b. `rowTitle` 里把这一行：
  ```ts
  if (game.source === 'play_local') return t('review:row_local', '本地对局 · 两人');
  ```
  替换为：
  ```ts
  if (game.source === 'play_local') {
    // 屏 04 承诺「名字留空就不编名字」(P12/P15)⇒ 两个名字都空时照稿子写「未记名」。
    // 只看**有没有**名字,不把名字念出来:两人对局没有「对手」,念一个就是替它选了一方。
    const named = [game.player_black, game.player_white].some((name) => Boolean(name?.trim()));
    return named
      ? t('review:row_local', '本地对局 · 两人')
      : t('review:row_local_unnamed', '本地对局 · 未记名');
  }
  if (game.source === 'research') {
    // galaxy 研究页存下来的局面(`galaxy/pages/ResearchPage.tsx` 存盘时 `source: 'research'`)。
    // 以前落到最后那一支,被念成「人机对弈」。
    const name = game.title || [game.player_black, game.player_white].filter(Boolean).join(' — ');
    return name ? `${t('review:row_research', '研究存档')} · ${name}` : t('review:row_research', '研究存档');
  }
  ```

  3c. `outcomeLine` 里 `if (!raw) {` 之后、`return interpolate(...)` 之前插入一行：
  ```ts
    if (!isPlaySource(game.source)) return t('review:no_result_line', '谱里没写结果');
  ```
  并把函数上方注释「没有 `result` 就是**没下完**」改为「**对弈局**没有 `result` 就是没下完;别的来源没有结果是谱里没写」。

  3d. `rowState` 最后一行：
  ```ts
  return game.result ? { kind: 'unanalyzed' } : { kind: 'unfinished' };
  ```
  替换为：
  ```ts
  // 「未终局」只给对弈局(P14)。它挡的是「半局的报告 + 离线算完再回去接着下」那条通道,
  // 导入的谱、棋谱库、研究存档没有「回去接着下」这回事 —— 没写结果照样能分析。
  if (game.result || !isPlaySource(game.source)) return { kind: 'unanalyzed' };
  return { kind: 'unfinished' };
  ```

- [ ] **Step 4：跑测试确认绿。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/components/report/reviewPresentation.test.ts
  ```
  预期：PASS，全部用例通过（比改前多 5 条）。

- [ ] **Step 5：提交。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git add katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts katrain/web/ui/src/kiosk/components/report/reviewPresentation.test.ts && git commit -m "$(cat <<'MSG'
  fix(kiosk-local): 屏 19 把没写结果的导入谱说成「未终局」、本地局标题恒为「两人」

  isPlaySource 判定对弈来源;未终局只给对弈局,导入/棋谱库/研究存档无结果算未分析、
  说「谱里没写结果」;本地局两名字都空写「未记名」;研究存档补标题分支(P14/P15)。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

### Task S4-2: 屏 19 页面 —— `canAnalyzeSelected` 同判定 + 首帧 loading 不依赖 token

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx`
  - import `reviewPresentation` 那一段（约 L20-22）加 `isPlaySource`
  - 约 L119 `const [gamesLoading, setGamesLoading] = useState(Boolean(token));`
  - 约 L405-413 `canAnalyzeSelected` 上方注释（判定本身**不改**，见说明）
  - 行组件里 `const sub = [...]`（约 L715-720，函数里有 `const mine = yourColor(game, username);`）
- Test: `katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx`（改 AuthContext mock 为可逐条改写；新增 `renderFirstFrame`；新增 2 条用例）

**Interfaces:**
- Consumes: `isPlaySource`、`rowState`（Task S4-1）；`useAuth(): { token: string | null; isAuthenticated: boolean; user }`
- Produces: 无新导出。行为：盒上（`token === null && isAuthenticated`）首帧即「正在读你的对局」；非对弈来源无结果的行可生成报告、副标题带手数。

> 说明（已核实）：`canAnalyzeSelected = Boolean(selectedSummary) && selectedState?.kind !== 'unfinished'`（约 L413），`selectedState` 由 `rowState` 算出 ⇒ Task S4-1 改了 `rowState`，这里**自动**是同一个判定，不要另写一份 `isPlaySource` 判断（写两份就会漂）。本 Task 只补注释，并用页面级用例钉住「导入谱无结果能按『标准』」。

- [ ] **Step 1：把 AuthContext mock 改成可逐条改写。** 在 `ReportsPage.test.tsx`：

  1a. 顶部 react import 之后（第 1 行 `@testing-library/react` 之后）加：
  ```ts
  import { useLayoutEffect, useRef, type ReactNode } from 'react';
  ```
  1b. `vi.hoisted` 的 `mocks` 对象里，`hookResult: {} as Record<string, unknown>,`（约 L40）之后加一行：
  ```ts
    auth: { token: 'token' as string | null, isAuthenticated: true, user: { username: '阿福' } },
  ```
  1c. 把
  ```ts
  vi.mock('../../context/AuthContext', () => ({
    useAuth: () => ({ token: 'token', isAuthenticated: true, user: { username: '阿福' } }),
  }));
  ```
  替换为：
  ```ts
  // 可以逐条改:严格盒端 SSO 里 token 恒为 null 而人是登录的 —— 这两个量在盒上本来就不同步,
  // 夹具只给「token 非空」就永远测不到盒子上的那条路。
  vi.mock('../../context/AuthContext', () => ({ useAuth: () => mocks.auth }));
  ```
  1d. `beforeEach(() => {`（约 L144）里 `vi.clearAllMocks();` 之后加：
  ```ts
    mocks.auth = { token: 'token', isAuthenticated: true, user: { username: '阿福' } };
  ```
  1e. 在 `function renderPage(...)`（约 L126-136）结束之后、`const rows = ...`（约 L138）之前加：
  ```tsx
  /**
   * 只读**第一帧**:外层的 layout effect 在子树第一次提交之后、任何 `useEffect` 之前跑,
   * 读到的正是「列表请求还没发出去」那一刻屏上写着什么。`render` 返回时 effect 早跑完了,
   * 直接查 DOM 看不见这一帧。
   */
  function renderFirstFrame(route = '/kiosk/report') {
    const frames: string[] = [];
    function FirstFrame({ children }: { children: ReactNode }) {
      const ref = useRef<HTMLDivElement>(null);
      useLayoutEffect(() => { frames.push(ref.current?.textContent ?? ''); }, []);
      return <div ref={ref}>{children}</div>;
    }
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={[route]}>
          <FirstFrame><ReportsPage /></FirstFrame>
        </MemoryRouter>
      </ThemeProvider>,
    );
    return frames;
  }
  ```

- [ ] **Step 2：写失败的用例。**

  2a. 在 `it('一局都没有时说的是「还没有下过的棋」,不是一片空白', ...)`（约 L251）**之前**插入：
  ```tsx
  /**
   * 回归钉子(P17):严格盒端 SSO 里 token 恒为 null。首帧的「正在读」原来按 `Boolean(token)` 判,
   * 盒上每次进屏都先闪一下「还没有下过的棋」。
   */
  it('盒上 token 为 null 但已登录:首帧就是「正在读」,不闪「还没有下过的棋」,列表照常拉', async () => {
    mocks.auth = { token: null, isAuthenticated: true, user: { username: '阿福' } };
    const frames = renderFirstFrame();
    expect(frames[0]).toContain('正在读你的对局');
    expect(frames[0]).not.toContain('还没有下过的棋');
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(mocks.list).toHaveBeenCalledWith(null, expect.objectContaining({ page: 1 }));
  });
  ```

  2b. 在 `it('计分局下完了照样能分析 —— 挡的是没下完,不是算不算分', ...)`（约 L541，和 `const selectedRow` 在同一个 `describe` 里）**之前**插入：
  ```tsx
  // P14:导入的谱没写 RE 不是「没下完」。以前被标「未终局」、念成「下到第 187 手就退出了」、不给报告。
  it('导入的谱没写结果:标「未分析」、不说「就退出了」,两张档位卡能按', async () => {
    mocks.list.mockResolvedValue(response([game('a', { source: 'import', title: '老谱', result: null, move_count: 187 })]));
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'unanalyzed'));
    await selectedRow();
    expect(within(rows()[0]).getByText('未分析')).toBeInTheDocument();
    expect(within(rows()[0]).getByText(/^谱里没写结果 · 187 手/)).toBeInTheDocument();
    expect(within(rows()[0]).queryByText(/就退出了/)).toBeNull();
    expect(screen.getByRole('button', { name: /标准/ })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /标准/ }));
    expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'a', reportType: 'normal', totalMoves: 187 });
  });
  ```

- [ ] **Step 3：跑测试确认红。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/pages/ReportsPage.test.tsx
  ```
  预期：FAIL 恰好 2 条 —— 「首帧」那条 `frames[0]` 含「还没有下过的棋」而不含「正在读你的对局」；「导入的谱」那条找不到 `/^谱里没写结果 · 187 手/`（Task S4-1 已让 `data-state` 变 `unanalyzed`、「标准」可按，但副标题没挂手数）。其余既有用例全部 PASS（mock 默认值仍是 `token: 'token'`）。
  若「导入的谱」那条在 `data-state` 处就红，说明 Task S4-1 没合进来，先停下核对 `git log --oneline -3`。

- [ ] **Step 4：实现。** 编辑 `ReportsPage.tsx`：

  4a. `reviewPresentation` 的 import 改为：
  ```ts
  import {
    isPlaySource, outcomeLine, rowDisc, rowState, rowTitle, yourColor, type RowState,
  } from '../components/report/reviewPresentation';
  ```
  4b. 约 L119：
  ```ts
  const [gamesLoading, setGamesLoading] = useState(Boolean(token));
  ```
  替换为：
  ```ts
  // ⚠️ 首帧按 `isAuthenticated` 判,**不按 token**(P17)。严格盒端 SSO 里 token 恒为 null ——
  // 按 token 判的话,盒上每次进这一屏首帧都先闪一下「还没有下过的棋」,下一帧才变成「正在读」。
  const [gamesLoading, setGamesLoading] = useState(isAuthenticated);
  ```
  4c. `canAnalyzeSelected` 上方注释块结尾 ` */` 之前加两行（判定本身不动）：
  ```ts
   * 「未终局」只由 `rowState` 给**对弈局**(`isPlaySource`)—— 导入的谱、棋谱库、研究存档
   * 没写结果不算没下完,没有「回去接着下」这回事,照样能分析(P14)。这里不另写一份判定。
  ```
  4d. 行组件里：
  ```ts
  // 没下完的那句话自己就带着手数(「下到第 22 手就退出了」),再挂一段「22 手」是同一个数说两遍。
  const sub = [
    outcomeLine(game, mine, t),
    game.result ? `${game.move_count} ${t('report:moves_unit', '手')}` : null,
  ```
  替换为：
  ```ts
  // 没下完的那句话自己就带着手数(「下到第 22 手就退出了」),再挂一段「22 手」是同一个数说两遍。
  // 只有对弈局会念那一句;导入的谱没写结果时念「谱里没写结果」,手数照常挂在后面。
  const sub = [
    outcomeLine(game, mine, t),
    game.result || !isPlaySource(game.source) ? `${game.move_count} ${t('report:moves_unit', '手')}` : null,
  ```

- [ ] **Step 5：跑测试确认绿 + 类型检查。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/pages/ReportsPage.test.tsx src/kiosk/components/report/reviewPresentation.test.ts && npx tsc -b
  ```
  预期：两个文件全部 PASS；`tsc -b` 无输出、退出码 0。

- [ ] **Step 6：提交。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git add katrain/web/ui/src/kiosk/pages/ReportsPage.tsx katrain/web/ui/src/kiosk/pages/ReportsPage.test.tsx && git commit -m "$(cat <<'MSG'
  fix(kiosk-local): 屏 19 首帧按 token 判 loading,盒上每次进屏先闪一下空态

  首帧 loading 改按 isAuthenticated(P17);没写结果的导入谱副标题照常挂手数;
  canAnalyzeSelected 沿用 rowState 的同一判定(P14)。夹具补上「token 为 null 但已登录」。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

### Task S4-3: 研究页 `?user_game_id=` 与首页跨平台区去掉 token 闸

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`（约 L437-455，`const userGameRef = useRef(false);` 之后那个 `useEffect`）
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`（约 L43 `useAuth()` 解构、L51 `if (token)`、L60 依赖数组）。**只动这三处**；S1 在同文件改游客卡片提示，两边合并时按行区间各取各的。
- Test: `katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx`、`katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx`

**Interfaces:**
- Consumes: `UserGamesAPI.get(token: string | null, id: string)`；`API.platformStatus(token: string | null | undefined)`（`api.ts` 约 L616）；`useAuth()` 的 `token` / `isAuthenticated`
- Produces: 无新导出。行为：`token === null && isAuthenticated` 时研究页照常按 `?user_game_id=` 读谱；首页照常请求平台状态。游客（`isAuthenticated === false`）仍不请求平台状态。

> 说明（已核实）：spec §4.3 写「去掉 `if (token)`，平台状态照常请求」。但 `GET /api/v1/platforms/status` 挂 `Depends(get_current_user)`（`katrain/web/api/v1/endpoints/platforms.py:233`），游客请求必 401 ⇒ 闸不是删掉而是**换成 `isAuthenticated`**，这与 spec 意图（盒上登录态照常请求）一致。研究页那一屏在 kiosk 登录守卫之内，直接删 `!token` 即可。

- [ ] **Step 1：研究页写失败用例。** `ResearchPage.userGame.test.tsx`：

  1a. 把
  ```ts
  vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
  ```
  替换为：
  ```ts
  // 可以逐条改 token:盒上(严格盒端 SSO)token 恒为 null 而人是登录的。
  const { auth } = vi.hoisted(() => ({ auth: { token: 'tok' as string | null } }));
  vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
  ```
  1b. `beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });` 改为：
  ```ts
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); auth.token = 'tok'; });
  ```
  1c. 在 `it('loads a recorded game by ?user_game_id', ...)` 之后、`describe` 结尾 `});` 之前加：
  ```tsx
  /**
   * 回归钉子(P13):上一条把 token mock 成 'tok',**正好避开了盒子上那条路**。
   * 严格盒端 SSO 里 token 恒为 null;原来的 `!token` 早退让盒上从报告点「去研究」落到空棋盘,
   * 而 `GET /api/v1/user-games/{id}` 本来就认 cookie。
   */
  it('盒上 token 恒为 null 时照样按 ?user_game_id 读谱', async () => {
    auth.token = null;
    renderAt('/kiosk/research?user_game_id=g1');
    await waitFor(() => expect(get).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });
  ```

- [ ] **Step 2：首页写失败用例。** `PlayPage.test.tsx`：

  2a. `it('keeps disconnected defaults after logout when an older request resolves', ...)`（约 L268）里：
  ```ts
  let auth = { user: { username: '友' }, isAuthenticated: true, token: 'A' as string | null };
  ```
  替换为：
  ```ts
  let auth = {
    user: { username: '友' } as { username: string } | null,
    isAuthenticated: true,
    token: 'A' as string | null,
  };
  ```
  同一条用例里的 `auth = { ...auth, token: null };` 替换为：
  ```ts
  // 登出 = user 和 token 一起清掉(`AuthContext.logout` 就是这么做的)。
  // 只清 token、人还登录着 —— 那是严格盒端 SSO 的**常态**,不是登出(见下一条)。
  auth = { user: null, isAuthenticated: false, token: null };
  ```
  2b. 该用例结束（约 L284 `  });`）之后、文件末尾 `});` 之前加：
  ```tsx
  /**
   * 回归钉子(P16):严格盒端 SSO 里 `token` 恒为 null,身份在 HttpOnly cookie 里。
   * 原来的 `if (token)` 让盒上**已登录**的人永远只看到兜底状态 ——
   * 而 `/api/v1/platforms/status` 认 cookie,请求发出去本来就会成功。
   */
  it('盒上 token 恒为 null 但已登录:照常请求平台状态,连上的平台照实显示', async () => {
    useAuthMock.mockReturnValue({ user: { username: 'fan' }, isAuthenticated: true, token: null });
    platformStatusMock.mockResolvedValue({ platforms: [platformRecord('golaxy', true)] });
    renderPage();
    await waitFor(() => expect(platformStatusMock).toHaveBeenCalledWith(null));
    await waitFor(() => expect(platformButtons()[1]).toHaveTextContent('已连接'));   // [1] = 星阵
  });

  it('游客不请求平台状态 —— 那个端点要登录,发了也是 401', () => {
    useAuthMock.mockReturnValue({ user: null, isAuthenticated: false, token: null });
    renderPage();
    expect(platformStatusMock).not.toHaveBeenCalled();
    expectAllDisconnected();
  });
  ```
  执行时先核实：`grep -n "const platformButtons\|function platformRecord\|const expectAllDisconnected\|已连接" katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx` 预期四者都有命中（若 `platformButtons()[1]` 不是星阵，按该文件里已有的星阵用例的下标写）。

- [ ] **Step 3：跑测试确认红。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx src/kiosk/pages/PlayPage.test.tsx
  ```
  预期：FAIL 恰好 2 条 —— 「盒上 token 恒为 null 时照样按 ?user_game_id 读谱」（`get` 未被调用，waitFor 超时）；「盒上 token 恒为 null 但已登录:照常请求平台状态」（`platformStatusMock` 未被调用）。「游客不请求平台状态」与改写后的 logout 用例今天就是绿的（`token` 为 null 本来就不请求），它们守的是 Step 4 不能把闸删成「无条件请求」。

- [ ] **Step 4：实现。**

  4a. `ResearchPage.tsx`，`const userGameRef = useRef(false);` 之后的 effect：
  ```ts
    if (!id || userGameRef.current || !token) return;
  ```
  替换为：
  ```ts
    // ⚠️ **不许再挂 `!token`**(P13)。严格盒端 SSO 里 token 恒为 null,身份在 HttpOnly cookie 里 ——
    // 挂着它,盒上从报告点「去研究」落到的是一块空棋盘。这一屏在 `KioskAuthGuard` 里,
    // 走到这儿的人按定义都已登录;`token` 只当凭据传,有就带 Authorization 头,没有就靠 cookie。
    if (!id || userGameRef.current) return;
  ```
  同一个 effect 结尾：
  ```ts
  }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps
  ```
  替换为：
  ```ts
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps
  ```

  4b. `PlayPage.tsx`：
  - `const { user, token } = useAuth();` → `const { user, token, isAuthenticated } = useAuth();`
  - `if (token) {` → 
    ```ts
    // 闸挂在「登录了没有」,**不挂 token**(P16):严格盒端 SSO 里 token 恒为 null,凭据在 cookie 里。
    // 游客仍不请求 —— `/api/v1/platforms/status` 要登录(`platforms.py` 的 `get_current_user`)。
    if (isAuthenticated) {
    ```
  - `}, [token]);` → `}, [isAuthenticated, token]);`

- [ ] **Step 5：跑测试确认绿 + 类型检查 + lint。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx vitest run src/kiosk/pages/ResearchPage.userGame.test.tsx src/kiosk/pages/PlayPage.test.tsx && npx tsc -b && npx eslint src/kiosk/pages/ResearchPage.tsx src/kiosk/pages/PlayPage.tsx
  ```
  预期：两个测试文件全部 PASS；`tsc -b` 退出码 0；eslint 无 error（`ResearchPage.tsx` 那行原有的 `eslint-disable-line` 保留）。

- [ ] **Step 6：提交。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git add katrain/web/ui/src/kiosk/pages/ResearchPage.tsx katrain/web/ui/src/kiosk/pages/ResearchPage.userGame.test.tsx katrain/web/ui/src/kiosk/pages/PlayPage.tsx katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx && git commit -m "$(cat <<'MSG'
  fix(kiosk-local): 盒上从报告「去研究」落到空棋盘、首页跨平台区永远是兜底数据

  研究页 ?user_game_id= 删掉 !token 早退(P13);首页平台状态的闸从 token 换成
  isAuthenticated(P16)。两处夹具补上「token 为 null 但已登录」,原夹具恰好避开了盒上那条路。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

### Task S4-4: 屏 19 真浏览器文案用例 + 四图 + ⏸ Fan 确认

**Files:**
- Create: `katrain/web/ui/tests/kiosk-review-row-labels.spec.ts`（真浏览器 1024×600，走 `playwright.visual.config.ts` 起的 vite dev server，不需要先 build）
- 可能 Modify（仅当有真变化时）：`superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600/{implementation,side-by-side,diff}.png`
- **不改** `tests/kiosk-screen-19-review.fourup.spec.ts` 的 fixture：它的六行是对着参考图造的，改了会让四图对比失真。

**Interfaces:**
- Consumes: Task S4-1/S4-2 的行文案；`tests/helpers/fourup.ts` 的 `freezeClock(page, iso?)`、`stubBackendStatics(page, lang?)`、`KIOSK_VIEWPORT`；行 DOM `[data-testid="review-row"]`（带 `data-state`）、标题 `.kiosk-row__t`（`ReportsPage.tsx` 约 L723-731）
- Produces: 无代码导出。产物：一条真浏览器用例 + 屏 19 四图的判定记录。

> 说明（已核实）：屏 19 四图 fixture 的六行在 S4 之后**文案一个字都不变** —— g4 / g6 是 `play_local` 但黑白有名字（「小明 / 小红」）⇒ 仍是「本地对局 · 两人」；g6 无结果但是对弈来源 ⇒ 仍是「未终局」；g5 导入谱带结果 ⇒ 不走新分支。且 g4 / g6 在截图可视区之外。所以四图**预期无真变化**，新文案（「未记名」「研究存档」「谱里没写结果」「未分析」）改由本 Task 的真浏览器用例证明它真出现在屏上、且在滚动区里够得着。

- [ ] **Step 1：写真浏览器用例。** 创建 `katrain/web/ui/tests/kiosk-review-row-labels.spec.ts`：
  ```ts
  import { expect, test } from '@playwright/test';
  import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

  test.use({ viewport: KIOSK_VIEWPORT });

  /**
   * 屏 19 新文案(P14 / P15)在真浏览器里上屏。三行都排在第 4 行之后,**默认落在列表可视区之外** ——
   * 断言前先滚到那一行,证明「滚得到、念得对」,而不是 jsdom 里拼出来的一句话。
   */
  const at = (iso: string) => new Date(iso).toISOString();
  const base = {
    user_id: 1, board_size: 19, rules: 'chinese', komi: 7.5, category: 'game', black_rank: null, white_rank: null,
    event: null, round_name: null, game_date: '2026-08-20', updated_at: null, game_type: 'free',
  };
  const filler = (id: string, hour: number) => ({
    ...base, id, title: null, player_black: '访客', player_white: 'KataGo', result: 'W+R', move_count: 120,
    source: 'play_ai', created_at: at(`2026-08-20T${String(hour).padStart(2, '0')}:00:00`),
  });
  const GAMES = [
    filler('f1', 15), filler('f2', 14), filler('f3', 13), filler('f4', 12),
    { ...base, id: 'u1', title: null, player_black: '', player_white: '', result: 'B+R', move_count: 96,
      source: 'play_local', created_at: at('2026-08-19T19:20:00') },
    { ...base, id: 'r1', title: '柯洁 vs 申真谞', player_black: null, player_white: null, result: null, move_count: 80,
      source: 'research', game_type: null, created_at: at('2026-08-18T10:00:00') },
    { ...base, id: 'i1', title: '老谱', player_black: null, player_white: null, result: null, move_count: 187,
      source: 'import', game_type: null, created_at: at('2026-08-17T10:00:00') },
  ];
  const row = (page: import('@playwright/test').Page, i: number) =>
    page.locator('[data-testid="review-row"]').nth(i);

  test('屏 19:未记名 / 研究存档 / 谱里没写结果 在滚动区里够得着且念得对', async ({ page }) => {
    await freezeClock(page);
    await page.addInitScript(() => {
      localStorage.setItem('token', 'labels');
      localStorage.setItem('katrain_language', 'cn');
    });
    await stubBackendStatics(page);
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } }));
    await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
      json: { phase: 'disabled', session_calibrated: false, last_error: null,
        capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false } },
    }));
    await page.route('**/api/v1/user-games/*', (route) => route.fulfill({ json: { ...GAMES[0], sgf_content: '(;FF[4]GM[1]SZ[19])' } }));
    await page.route('**/api/v1/user-games**', (route) => route.fulfill({ json: { items: GAMES, total: GAMES.length, page: 1, page_size: 12 } }));
    await page.route('**/api/v1/reports/summary', (route) => route.fulfill({ json: { pending: 0, running: 0, completed: 0, failed: 0 } }));
    await page.route('**/api/v1/reports/', (route) => route.fulfill({ json: [] }));

    await page.goto('/kiosk/report');
    await expect(page.locator('[data-testid="review-row"]')).toHaveCount(7);

    await row(page, 4).scrollIntoViewIfNeeded();
    await expect(row(page, 4)).toBeInViewport();
    await expect(row(page, 4)).toContainText('本地对局 · 未记名');

    await row(page, 5).scrollIntoViewIfNeeded();
    await expect(row(page, 5)).toContainText('研究存档 · 柯洁 vs 申真谞');
    await expect(row(page, 5)).toHaveAttribute('data-state', 'unanalyzed');

    await row(page, 6).scrollIntoViewIfNeeded();
    await expect(row(page, 6)).toBeInViewport();
    await expect(row(page, 6)).toContainText('谱里没写结果 · 187 手');
    await expect(row(page, 6)).not.toContainText('就退出了');
    await expect(row(page, 6)).toHaveAttribute('data-state', 'unanalyzed');

    await page.screenshot({ path: 'test-results/kiosk-review-row-labels.png' });
  });
  ```

- [ ] **Step 2：跑用例（应绿）。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx playwright test --config=playwright.visual.config.ts tests/kiosk-review-row-labels.spec.ts
  ```
  预期：`1 passed`。这条用例在 Task S4-1/S4-2 之后才写，所以不演示红；它守的是「真浏览器里念得对、滚得到」。若想确认它不是空过：临时把 `reviewPresentation.ts` 里 `'本地对局 · 未记名'` 的缺省文案改成别的字再跑一次，应在 `row(page, 4)` 那条 `toContainText` 处 FAIL；确认后用编辑器改回（**不许** `git checkout` 该文件），`git diff --stat katrain/web/ui/src` 应为空。
  若在 `toHaveCount(7)` 处超时：先 `grep -n "user-games" tests/kiosk-screen-19-review.fourup.spec.ts` 对照现成 spec 的路由写法，只修路由，不改断言。

- [ ] **Step 3：跑两次屏 19 四图，判定有无真变化。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play/katrain/web/ui && npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-19-review.fourup.spec.ts 2>&1 | grep 'fourup 19-review' \
    && cp ../../../superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600/implementation.png /tmp/s4-19-run1.png \
    && npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-19-review.fourup.spec.ts 2>&1 | grep 'fourup 19-review'
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git status --short superpowers/tracks/kiosk-go-shell-align/visual/19-review/
  ```
  预期：两次都打印 `[fourup 19-review] both=… refOnly=… implOnly=…`，两次数字相差在屏 19 的抖动地板内（屏 19 的棋盘是 SVG，量级约 200 像素以内）；与 `git show HEAD:superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600/implementation.png` 相比也只在抖动地板内（上面「说明」已论证六行文案不变）。
  判定：
  - **只有抖动** ⇒ 这一屏不提交截图，把工作树里的屏 19 图还原：`git checkout HEAD -- superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600/`（执行前先 `git status --short` 确认该目录下只有本步刚生成的改动）。
  - **有聚集在行区域的真变化** ⇒ 说明 fixture 某行走了新分支，与「说明」的推断不符：停下，在交付说明里写明是哪一行、为什么，把四图一起提交（implementation / side-by-side / diff 三张同时），参考图与 `reference-shots.json` 不动。

- [ ] **Step 4：⏸ 停下，等 Fan 确认。** 把下面三样发给 Fan，**等明确确认；未确认不得进入 Task S4-5**：
  1. 屏 19 四图四个路径：`superpowers/tracks/kiosk-go-shell-align/visual/19-review/1024x600/{reference,implementation,side-by-side,diff}.png`，以及 Step 3 的判定（「只有抖动，未提交」或「有真变化，已提交」+ 原因）；
  2. `katrain/web/ui/test-results/kiosk-review-row-labels.png`（滚到底后的列表，能看到「本地对局 · 未记名」「研究存档 · 柯洁 vs 申真谞」「谱里没写结果 · 187 手」三行）；
  3. 三个新文案原文，请 Fan 拍板措辞：`review:row_local_unnamed` =「本地对局 · 未记名」（照稿子 `go-kiosk.tmpl.html` 约 1775/1777 行）、`review:row_research` =「研究存档」、`review:no_result_line` =「谱里没写结果」（后两个稿子里没有，是本切片起的名）。
  Fan 若改措辞：只改 `reviewPresentation.ts` 的缺省文案与两份测试里的期望字符串，重跑 Task S4-1 Step 4、Task S4-2 Step 5、本 Task Step 2，再回到本步。

- [ ] **Step 5：提交。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git add katrain/web/ui/tests/kiosk-review-row-labels.spec.ts && git commit -m "$(cat <<'MSG'
  test(kiosk-local): 屏 19 新行文案在真浏览器里滚得到、念得对

  未记名 / 研究存档 / 谱里没写结果三行排在可视区之外,滚到再断言;
  屏 19 四图 fixture 六行文案不变,两次取图只有抖动,未提交截图。Fan 已确认。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```
  （若 Step 3 判为真变化，把那三张图也路径限定地 `git add`，并把 message 第二段改成实际情况。）

---

### Task S4-5: 后端：本地对局不回填登录用户名

**Files:**
- Modify: `katrain/web/server.py` —— `create_app()` 内的闭包 `_record_ai_game_locked(session, app, current_user, result)`（约 L1599；`_record_ai_game` 在约 L1864，是它的加锁包装，**不改**）。只动「Fill in username」那段（约 L1617-1621）与下面 `game_type = getattr(session, "game_type", "free")`（约 L1655）这一行的位置。
- Test: `tests/test_local_play_recording.py`（在 `@pytest.fixture` 的 `def client(` 之前插入 3 条用例 + 1 个辅助函数）

**Interfaces:**
- Consumes: `server._RECORD_FN`（`create_app()` 调用后由模块全局暴露的测试钩子，文件头注释已说明）；`session.game_type`（`pvp_local` 在 `server.py` 约 L1235 写入）；`players_info["B"|"W"].human / .name`
- Produces: 行为 —— `session.game_type == "pvp_local"` 时，`user_games_create(data=...)` 的 `player_black` / `player_white` 保持用户填的原值（空就是 `""`）；其它 game_type 照旧把 `current_user.username` 回填进 human 那一方的空名字。

- [ ] **Step 1：写失败的测试。** 在 `tests/test_local_play_recording.py` 里、`def client(` 那个 fixture 的装饰器行之前插入：
  ```python
  def _named_session(game_type, black_name, white_name, both_human=True):
      s = _make_session(both_human=both_human)
      s.game_type = game_type
      s.katrain.players_info = {"B": _Info(True, black_name), "W": _Info(both_human, white_name)}
      return s


  async def _recorded_data(session, username="fan"):
      app = MagicMock()
      app.state.repository_dispatcher.user_games_create = AsyncMock(return_value={"id": "g1"})
      await server._RECORD_FN(session, app, types.SimpleNamespace(id=42, username=username), "B+R")
      app.state.repository_dispatcher.user_games_create.assert_awaited_once()
      return app.state.repository_dispatcher.user_games_create.await_args.kwargs["data"]


  # P12:屏 04 承诺「名字留空就不编名字」。以前两个座位都是 human ⇒ 登录用户名被同时写进黑白两方,
  # 屏 19 那一行就成了「fan — fan」,「本地对局 · 未记名」永远认不出来。
  @pytest.mark.asyncio
  async def test_pvp_local_blank_names_stay_blank():
      data = await _recorded_data(_named_session("pvp_local", "", ""))
      assert data["source"] == "play_local"
      assert data["player_black"] == ""
      assert data["player_white"] == ""


  @pytest.mark.asyncio
  async def test_pvp_local_keeps_the_one_name_given():
      data = await _recorded_data(_named_session("pvp_local", "小明", ""))
      assert data["player_black"] == "小明"
      assert data["player_white"] == ""


  @pytest.mark.asyncio
  async def test_ai_game_still_fills_username_into_the_human_seat():
      data = await _recorded_data(_named_session("free", "", "", both_human=False))
      assert data["source"] == "play_ai"
      assert data["player_black"] == "fan"
      assert data["player_white"] != "fan"
  ```

- [ ] **Step 2：跑测试确认红。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && CI=true uv run pytest tests/test_local_play_recording.py -q; git status --short katrain/config.json
  ```
  预期：`2 failed`（`test_pvp_local_blank_names_stay_blank`：`assert 'fan' == ''`；`test_pvp_local_keeps_the_one_name_given`：`player_white` 为 `'fan'`），其余全部 passed（含 `test_ai_game_still_fills_username_into_the_human_seat`，它守的是人机局不被误伤）。
  `git status` 若显示 ` M katrain/config.json`：执行 `git checkout -- katrain/config.json`（唯一允许的 checkout，只针对这个文件）。

- [ ] **Step 3：实现。** 在 `server.py` 的 `_record_ai_game_locked` 里，把：
  ```python
              # Fill in username for the human side if still empty
              if current_user:
  ```
  替换为：
  ```python
              game_type = getattr(session, "game_type", "free")
              # Fill in username for the human side if still empty —— 只对人机局。
              # 本地两人对局(pvp_local)两个座位都是 human,回填会把登录用户名同时写进黑白两方;
              # 而屏 04 承诺「名字留空就不编名字」,屏 19 要靠两个名字都空才认得出「未记名」(P12)。
              if current_user and game_type != "pvp_local":
  ```
  再删掉同一函数下方（约 L1655，`rules = state.get("ruleset", "chinese")` 之后）原来那一行重复的：
  ```python
              game_type = getattr(session, "game_type", "free")
  ```
  执行时先核实：`grep -n 'game_type = getattr(session, "game_type", "free")' katrain/web/server.py` 改前在 `_record_ai_game_locked` 范围内（约 L1599-1700）只有 1 处命中，改后仍只有 1 处且行号在「Fill in username」注释之前。

- [ ] **Step 4：跑测试确认绿 + 格式化。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && uv run black -l 120 katrain/web/server.py tests/test_local_play_recording.py && CI=true uv run pytest tests/test_local_play_recording.py tests/test_local_play_setup.py -q; git status --short katrain/config.json
  ```
  预期：两个文件全部 passed。`black` 若改动了 `server.py` 中本 Task 以外的行，说明该文件原本不合 black：用 `git diff --stat katrain/web/server.py` 看改动行数，若远超 5 行，则只保留本 Task 那几行（手工撤回其余格式化改动），不要夹带全文件格式化。config.json 被改则 `git checkout -- katrain/config.json`。

- [ ] **Step 5：提交。**
  ```bash
  cd /Users/fan/Repositories/katrain-kiosk-local-play && git add katrain/web/server.py tests/test_local_play_recording.py && git commit -m "$(cat <<'MSG'
  fix(kiosk-local): 本地对局名字留空时,落账把登录用户名同时写进黑白两方

  _record_ai_game_locked 在 game_type == "pvp_local" 时不回填 current_user.username(P12),
  人机局照旧回填。屏 19 的「本地对局 · 未记名」依赖两个名字都空。

  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EBdHXxZbSWFhkun2ywA7mQ
  MSG
  )"
  ```

---

---

## 补充 Task（整合时补写；比切片正文短，执行者按 spec 与设计稿文案表自行写出代码）

### Task S1-5: 首页「本地对局」卡片未登录时说要先登录

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`（「本地对局」`KioskCard` 的 `sub`，约 L118-123）
- Test: `katrain/web/ui/src/kiosk/pages/PlayPage.test.tsx`

**Interfaces:** Consumes `useAuth()` 的 `isAuthenticated`（`src/context/AuthContext.tsx`，**不要用 `token`**：盒上严格 SSO 下 token 恒为 null）。

- [ ] **Step 1: 写失败测试**：`isAuthenticated=false` 时卡片副标是 `要先登录 · 下完自动存谱`；`isAuthenticated=true` 时仍是 `两人在同一块实体盘上下`。按文件里已有的 AuthContext mock 写法造两种状态。
- [ ] **Step 2:** `npx vitest run src/kiosk/pages/PlayPage.test.tsx` 预期新用例红。
- [ ] **Step 3: 实现**：`sub={isAuthenticated ? t('Two players on the same physical board', '两人在同一块实体盘上下') : t('play:local_needs_login', '要先登录 · 下完自动存谱')}`。点击行为不变（路由本身在 `KioskAuthGuard` 里，会带去登录）。⚠️ 泳道 C 的 S4-3 也改这个文件的 `if (token)`，只动卡片这一处。
- [ ] **Step 4:** 同一命令预期全绿；`npx tsc -b` 无报错。
- [ ] **Step 5: Commit** `feat(kiosk-local): 首页本地对局卡片在未登录时直接说要先登录`

---

### Task S3-4: 后端 `/api/timeout` 在本地对局上先核实再判负

**Files:**
- Modify: `katrain/web/core/game_end_rules.py`（加 `is_time_exhausted`）
- Modify: `katrain/web/server.py`（`@app.post("/api/timeout")`，约 L2119；只改 `with session.lock:` 那一段）
- Test: `tests/test_local_play_timeout.py`（新建；session 的造法照 `tests/test_local_play_recording.py`）

**Interfaces:**
- Produces: `is_time_exhausted(iface) -> bool`（契约见附录 A）；`/api/timeout` 对 `pvp_local` 未用尽时回 `409`，`detail = {"code": "time_not_expired", "state": <get_state()>}`。

- [ ] **Step 1: 写失败测试**（每条都走真 `WebKaTrain` + HTTP）：
  1. `pvp_local`、`time_enabled`、`main_time=1`（分钟）、`byo_length=30`、`byo_periods=1`：把轮到一方的 `main_time_used_by_player` 设成 60、`periods_used` 设成 1 → `POST /api/timeout` 200，`state.end_result` 为对方 `+T`，且落账被调用一次（落账观察方式照 recording 测试）。
  2. 同上但主时间还剩 → 409，`detail.code == "time_not_expired"`，`detail.state` 存在，`end_result` 仍为空。
  3. 已终局（先认输）再发 timeout → 不改写结果。
  4. 非 `pvp_local`（`free`）→ 行为与今天一致：直接判 `+T`。
- [ ] **Step 2:** `CI=true uv run pytest tests/test_local_play_timeout.py -q` 预期 1–3 红；查 `git status --short katrain/config.json`。
- [ ] **Step 3: 实现 `is_time_exhausted`**：

  ```python
  def is_time_exhausted(iface) -> bool:
      """轮到的一方钟走完了没有。调用方先 iface.update_timer()。

      判据与 WebKaTrain.update_timer 同一套:暂停(不限时)恒 False;主时间剩余 ≤ 0;
      periods_used ≥ max(1, byo_periods)。update_timer 的循环在 periods_used 到 byo_periods 时停住,
      所以 ≥ 与「用尽」等价。
      """
      if getattr(iface, "timer_paused", True):
          return False
      timer = getattr(iface, "active_game_timer", None) or {}
      player = iface.next_player_info.player
      main_left = timer.get("main_time", 0) * 60 - iface.main_time_used_by_player.get(player, 0)
      if main_left > 0:
          return False
      return iface.next_player_info.periods_used >= max(1, timer.get("byo_periods", 5))
  ```
  执行时先核实：`grep -n "timer_paused\|active_game_timer\|main_time_used_by_player\|periods_used" katrain/web/interface.py` 这四个名字都在，默认值与 `update_timer` 一致（不一致以 `update_timer` 为准并改上面的默认值）。

- [ ] **Step 4: 改端点**（`with session.lock:` 内）：

  ```python
  with session.lock:
      guard_ai_ladder_ranked_human_action(session, current_user, "timeout")
      katrain = session.katrain
      if getattr(session, "game_type", None) == "pvp_local":
          # 前端的钟只说明「屏上算到 0 了」;判负前服务端自己核一遍(spec D3)。已终局的局不改写结果。
          if not katrain.game.end_result:
              katrain.update_timer()
              if not is_time_exhausted(katrain):
                  state = katrain.get_state()
                  session.last_state = state
                  raise HTTPException(status_code=409, detail={"code": "time_not_expired", "state": state})
              katrain("timeout")
      else:
          katrain("timeout")
      state = katrain.get_state()
      session.last_state = state
  ```
  执行时先核实 `session.game_type` 的真实取法（S2a-1 核实过，照它）。落账分支不动：`pvp_local` 非多人局，走 `_record_ai_game`。
- [ ] **Step 5:** 测试全绿；`uv run black -l 120` 两个文件；查 config.json。
- [ ] **Step 6: Commit** `feat(local-play): 本地对局超时判负前后端核实用时,没用完回 409 附最新局面`

---

### Task S3-5: 前端到点调 `/api/timeout`，409 用附带局面重算，判负后右栏状态条

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/GamePage.tsx`（给 `GameControlPanel` 传 `onTimeExpired`；右栏状态条在超时判负后显示）
- Modify（如需）: `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx`（状态条的渲染位置：开关行之上；若 S2b-4 已把状态条做成 GameControlPanel 的一个 prop / slot，复用它）
- Test: `katrain/web/ui/src/kiosk/pages/GamePage.test.tsx`

**Interfaces:** Consumes `onTimeExpired`（S3-2）、`API.timeout(sessionId)`（`src/api.ts` L391，已有）、`ApiError.detail`（S2b-1）、`session.setGameState`（`useGameSession` 已导出）。

- [ ] **Step 1: 写失败测试**（mock `API.timeout`）：
  1. `pvp_local` 局触发 `onTimeExpired` → 调一次 `API.timeout(sessionId)`；返回的 state 被 `setGameState` 用上。
  2. `API.timeout` 抛 `ApiError(409)` 且 `detail.code === 'time_not_expired'` → 用 `detail.state` 调 `setGameState`，**不**弹错误。
  3. 非 409 错误 → 右栏状态条或 Snackbar 说「超时判定没有完成」（沿用页面已有报错通道），不崩。
  4. 终局且 `end_result` 以 `+T` 结尾 → 状态条标题 `黑方超时负` / `白方超时负`，副行 `{W|B}超时胜 · 第 {n} 手 · 已存进历史对局`，有 `复盘本局` 键（复用终局已有的复盘入口）。
  5. 非 `pvp_local` 局不传 `onTimeExpired`（其它模式不调 timeout）。
- [ ] **Step 2:** `npx vitest run src/kiosk/pages/GamePage.test.tsx` 预期新用例红。
- [ ] **Step 3: 实现**；同一个到点只发一次请求（请求在途时不重发，用 ref 记）。
- [ ] **Step 4:** 测试全绿；`npx tsc -b`；`npm run build` 与 `npm run build:kiosk-2d` 都绿。
- [ ] **Step 5: Commit** `feat(kiosk-local): 钟走到 0 请后端核实,判负后右栏写明结果`

---

## 切片 S5：收尾

### Task S5-1: i18n 补 11 种语言

- [ ] **Step 1: 收集本轮新增 / 改动的 key**：
  ```bash
  git diff 1b6c67b5 --unified=0 -- katrain/web/ui/src | grep -o "t('[a-zA-Z_]*:[a-zA-Z0-9_]*'" | sort -u
  ```
  另加 spec P19 的 52 个 key（屏 02/03 共用，清单在 `v2-design.md` P19 条目的证据里；找不到清单就用 `uv run python i18n.py -todo` 的输出里 kiosk 相关的缺项）。
- [ ] **Step 2:** 用 **katrain-i18n-expert** 技能把这些 key 补进 `katrain/i18n/locales/*/LC_MESSAGES/katrain.po`（11 种语言，`cn` ≠ `zh`、`jp` ≠ `ja`），中文取代码里的默认值。
- [ ] **Step 3:** `uv run python i18n.py` 不报错；`git status --short katrain/config.json`。
- [ ] **Step 4: Commit** `i18n(kiosk-local): 本地对局 v2 新增文案补齐 11 种语言`

### Task S5-2: 全量检查 + 真浏览器截图给 Fan

- [ ] **Step 1:** 后端：`CI=true uv run pytest tests/test_local_play_setup.py tests/test_local_play_recording.py tests/test_local_play_game_end.py tests/test_local_play_timeout.py tests/test_game_end_rules.py -q`（S2a 实际建的文件名以仓内为准）全绿；查 config.json。
- [ ] **Step 2:** 前端：`cd katrain/web/ui && npx vitest run` 全绿（与 `1b6c67b5` 的基线比，只看新增失败）；`npx tsc -b`；`npm run lint`。
- [ ] **Step 3:** `npm run build && npm run build:kiosk-2d`（`verify:kiosk-2d` exit 0）。
- [ ] **Step 4:** `npm run test:e2e -- tests/kiosk-screen-05-game.spec.ts`（本地对局右栏键名那几条已按 S2b-3 改过）以及 S4-4 新建的屏 19 文案用例，全绿。
- [ ] **Step 5: 截图**：本地起 server 模式 katrain，登录后在 1024×600 真浏览器里走：屏 04（顶部 + 滚到底部说明）、本地对局对局屏（设 5 分钟用时）、认输确认框、退出确认框、双方各停一手后的状态条、屏 19。截图存 `superpowers/tracks/kiosk-local-play/impl-shots/`，和 `design/` 同名对照，发给 Fan。
- [ ] **Step 6: Commit** 截图（path-limited）。

### Task S5-3: RK3562 上板终验（⏸ 需要 Fan）

- [ ] **Step 1:** SendMessage 问 `katrain-kiosk-debug` 板子是否空闲；得到答复前不动。
- [ ] **Step 2:** ⏸ 把要部署的提交 sha 和目标目录 `/mnt/data/<dir>/` 发给 Fan，等确认。
- [ ] **Step 3:** 部署（独立端口 + 独立 HOME/SQLite，严格 kiosk 包 `npm run build:kiosk-2d`），一次只跑一项，按 spec §7-1 走一遍：开局（屏幕 / 实体盘）→ 落子 → 双 pass 自动数子 → 手动数子 → 认输选方 → 退出不存 → 超时判负 → 屏 19 → 报告 → 去研究；9 路、让子、拿除灯各一次。
- [ ] **Step 4:** 结果写进 `superpowers/tracks/kiosk-local-play/v2-acceptance.md`，P1–P20 每条标「已修」或「本轮不做 + 原因」。Commit。

---

## 附录 A：共享契约

### 后端

| 名字 | 位置 | 签名 / 语义 | 用在 |
|---|---|---|---|
| `ResignRequest` | `katrain/web/models.py` | `session_id: str`；`color: Literal["B","W"] \| None = None` | S2 |
| `/api/resign` | `katrain/web/server.py` | 请求体改用 `ResignRequest`。`session.game_type == "pvp_local"`：必须带 color，否则 400；其它模式带 color → 400，不带 → 行为不变 | S2 |
| `_do_resign(self, color=None)` | `katrain/web/interface.py` | color 给定：`end_state = f"{对方}+R"`；不给：保持 `f"{current_node.player}+R"` | S2 |
| 模块 `katrain/web/core/game_end_rules.py` | 新建 | 纯函数，不 import server/session | S2/S3 |
| `scaled_count_min_moves(base: int, board_size: int) -> int` | 同上 | `max(1, round(base * board_size * board_size / 361))`；19→base，13→47，9→22（base=100） | S2 |
| `is_awaiting_count(iface) -> bool` | 同上 | §3.4 五条件：`getattr(iface, "suppress_auto_eval", False)` ∧ `game_type ∈ {"free","pvp_local"}` ∧ 当前节点与父节点都是 pass ∧ `current_node.end_state` 为空 ∧ `game.manual_score` 为空。`iface` = `WebKaTrain` 实例（`session.katrain`）；game_type 从哪取由 planner 核实 | S2 |
| `is_time_exhausted(iface) -> bool` | 同上 | 先由调用方 `iface.update_timer()`；判据 `not timer_paused ∧ 主时间剩余 ≤ 0 ∧ next_player_info.periods_used ≥ max(1, byo_periods)`；未开用时（paused）恒 False | S3 |
| state 字段 `awaiting_count: bool` | `interface.py get_state` | 由 `is_awaiting_count(self)` 算 | S2 |
| state 字段 `count_min_moves: int` | `interface.py get_state`（今天在约 L611） | 改为 `scaled_count_min_moves(config("game/count_min_moves", 100), board_size)` | S2 |
| 数子 400 的 detail | `/api/count/request` | `{"code": <code>, "message": <英文>}`；code ∈ `below_min_moves` / `game_over` / `analysis_pending`。**改动前 planner 必须 grep 这三处 400 的现有消费者（galaxy 也算）**，写明兼容做法 | S2 |
| 超时 409 的 detail | `/api/timeout` | 仅 `pvp_local`：`{"code": "time_not_expired", "state": <get_state()>}` | S3 |
| 数子归属校验 | `/api/count/request` | 调 `guard_session_terminator(session, current_user, "request-count")`，位置和 resign/timeout 一致 | S2 |

### 前端（`katrain/web/ui/src`）

| 名字 | 位置 | 签名 / 语义 | 用在 |
|---|---|---|---|
| `ApiError.detail` | `api.ts`（`ApiError` 类） | 新增可选字段 `detail?: unknown`：`apiPost` 失败时尝试 `JSON.parse(body).detail`，解析失败为 `undefined`。现有 `message` 格式不变 | S2/S3 |
| `API.resign` | `api.ts:389` | `resign(sessionId: string, token?: string, color?: 'B' \| 'W')`，color 有值才放进 body | S2 |
| `API.deleteSession` | `api.ts` | `deleteSession(sessionId: string): Promise<void>` → `DELETE /api/session/{id}`（planner 先 grep 是否已有等价物） | S2 |
| `GameState.awaiting_count` | `api.ts` 的 `GameState` | `awaiting_count?: boolean` | S2 |
| `handleAction` | `hooks/useGameSession.ts:171` | 签名改为 `(action: string, opts?: { color?: 'B' \| 'W' })`；`resign` 分支把 `opts?.color` 传给 `API.resign` | S2 |
| `countErrorMessage(err: unknown, t): string` | `kiosk/utils/countErrors.ts`（新建） | 按 `ApiError.detail.code` 出中文文案；网络层失败出「分析服务连不上」 | S2 |
| `useAutoCount` | `kiosk/hooks/useAutoCount.ts`（新建） | `awaiting_count` 为真时自动调 `API.requestCount`，遇 `analysis_pending` 退避重试总计约 15 s，暴露 `{ status: 'idle'\|'counting'\|'failed', reason: string \| null, retry(): void }` | S2 |
| `computeClock` | `utils/gameClock.ts`（新建，**共享区**） | 见下 | S3 |
| `ActiveSession.onBoard` | `kiosk/utils/activeSession.ts` | 新增可选 `onBoard?: boolean`；开局设置屏写入 `playInput` 合成出的 `onBoard`；`readActiveSession` 的校验不能因为缺这个字段就判无效 | S1 |
| `PlayInputGuard` | `kiosk/components/PlayInputGuard.tsx`（路径以实际为准） | 活动会话的 `route` 与当前路径相同且 `onBoard` 有定义时，用它决定是否套 `PhysicalBoardGuard`；否则回落 `readPlayOnBoard()` | S1 |
| `isPlaySource(source: string \| null \| undefined): boolean` | `kiosk/components/report/reviewPresentation.ts` | `play_ai` / `play_local` / `play_human` → true | S4 |
| 提示音 | `utils/audioPrefs.ts`（已存在） | 统一走 `readAudioPref('sfx')` / `writeAudioPref('sfx', v)`；`kioskPlaySound` 全仓删除 | S1 |

```ts
// utils/gameClock.ts
export interface ClockSettings { main_time: number; byo_length: number; byo_periods: number } // main_time 单位：分钟
export interface ClockInput {
  settings: ClockSettings | null | undefined;
  mainTimeUsed: number;      // 秒，这一方累计
  periodsUsed: number;       // 这一方已用读秒次数
  nodeTimeUsed: number;      // 秒，当前节点已用（只对轮到的一方有意义）
  active: boolean;           // 是否轮到这一方
  clientElapsed: number;     // 秒，上次服务端状态以来客户端流逝
}
export interface ClockView {
  showTimer: boolean;
  phase: 'main' | 'byoyomi' | 'expired';
  mainTimeLeft: number;      // 秒
  byoyomiLeft: number;       // 秒
  periodsLeft: number;
}
export function computeClock(input: ClockInput): ClockView;
// byo_length / byo_periods 与后端 update_timer 同一套 max(1, …)
```

### 切片 ↔ 文件（并行时防撞）

- **S1**：`PvpLocalSetupPage.tsx`、`AiSetupPage.tsx`（仅 free 分支）、`playInput.ts`、`activeSession.ts`、`PlayInputGuard.tsx`、`useGameSession.ts`（**只动 playSound 那几行**）、`PlayPage.tsx`（**只动游客卡片提示**）、`SettingsPage` 相关测试
- **S2a 后端**：`models.py`、`server.py`（resign / count / play_move 钩子）、`interface.py`（`_do_resign`、get_state 两个字段）、新建 `game_end_rules.py`、`tests/`
- **S2b 前端**：`api.ts`、`useGameSession.ts`（**只动 handleAction**）、`GamePage.tsx`、`GameControlPanel.tsx`、新建 `countErrors.ts`、`useAutoCount.ts`、Playwright spec
- **S3**：`gameClock.ts`、`components/PlayerCard.tsx`、`GameControlPanel.tsx`（钟）、`GamePage.tsx`（超时派发）、`server.py`（timeout）、`game_end_rules.py`（`is_time_exhausted`）
- **S4**：`reviewPresentation.ts`、`ReportsPage.tsx`、`ResearchPage.tsx`、`PlayPage.tsx`（**只动 L51 token 闸**）、`server.py` 的 `_record_ai_game`（**只动名字回填**）
- **S0/S5**：track 目录下的走查记录、i18n po 文件、构建

## 附录 B：切片起草时记下的依赖、契约冲突与核实

### S4

#### 本切片的依赖与并行

- **切片内顺序**：S4-1 → S4-2 → S4-3 → S4-4（⏸ Fan 确认）→ S4-5。S4-2 依赖 S4-1 的 `rowState` / `isPlaySource`；S4-3 与 S4-1/S4-2 无代码依赖，可在 S4-1 之后任意时刻做，但必须在 S4-4 的 Fan 闸之前完成；S4-5（后端）按垂直切片规矩排在 Fan 确认之后。S4-4 用例里「未记名」一行的真数据来源正是 S4-5（前端夹具先行、后端后补）。
- **依赖的契约项**：只 Produces `isPlaySource`（contract 前端表）。不 Consume 任何其它切片的新名字。
- **与其它切片并行**：可与 S1、S2a、S2b、S3 并行。
  - 与 **S1** 同改 `kiosk/pages/PlayPage.tsx`：S4 只动 `useAuth()` 解构（约 L43）、`if (token)`（约 L51）、effect 依赖（约 L60）；S1 动游客卡片提示。合并时按行区间各取各的；两家都改 `PlayPage.test.tsx` 时注意各自追加在文件末尾 `});` 之前，冲突按「两边都留」解。
  - 与 **S2a / S3** 同改 `katrain/web/server.py`：S4 只动 `_record_ai_game_locked` 里名字回填那 5 行（约 L1614-1621）和删掉约 L1655 一行；S2a 动 resign / count / play_move，S3 动 timeout，行区间不重叠。
- **S5 要接的活**：三个新 i18n key `review:row_local_unnamed`、`review:row_research`、`review:no_result_line` 补 11 种语言（今天 `review:*` 整组 key 在 `katrain/i18n` 下都没有 po 条目，全靠 `t(key, 中文缺省)`，S5 统一处理）。
- **会动到的文件**：
  - `katrain/web/ui/src/kiosk/components/report/reviewPresentation.ts` / `.test.ts`
  - `katrain/web/ui/src/kiosk/pages/ReportsPage.tsx` / `.test.tsx`
  - `katrain/web/ui/src/kiosk/pages/ResearchPage.tsx`、`ResearchPage.userGame.test.tsx`
  - `katrain/web/ui/src/kiosk/pages/PlayPage.tsx` / `.test.tsx`
  - `katrain/web/ui/tests/kiosk-review-row-labels.spec.ts`（新建）
  - `katrain/web/server.py`（`_record_ai_game_locked`）、`tests/test_local_play_recording.py`
  - 全部在 `src/kiosk/**`，**不碰共享区** ⇒ 不需要 `npm run build:kiosk-2d` 双构建（S5 统一构建时仍会覆盖）。

#### 契约冲突

无名字冲突。两处需要 integrator 知悉的**细化**（不是换名）：

1. **§4.3「去掉 `if (token)`」落成「换成 `if (isAuthenticated)`」**。`GET /api/v1/platforms/status` 挂 `Depends(get_current_user)`（`katrain/web/api/v1/endpoints/platforms.py:233`），无条件请求会让游客态每次进首页打一条 401。行为对登录态与 spec 一致。
2. **§4.6 与 contract 写的函数名是 `_record_ai_game`，实际要改的是 `_record_ai_game_locked`**（`server.py:1599`）；`_record_ai_game`（`server.py:1864`）是加锁包装，测试钩子 `server._RECORD_FN` 指向包装。contract「切片 ↔ 文件」一栏写 `_record_ai_game` 不影响执行，Task S4-5 已写明实际位置。

