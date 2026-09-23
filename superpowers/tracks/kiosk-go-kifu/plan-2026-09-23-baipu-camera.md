# 屏 17 摆谱:摄像头自动推进 + 试下 + AI 支招 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摆谱上线态不再逐手按「确认落子」—— 摄像头认到下一手就自动推进;放错 / 提子 / 撤回 / 试下结束都由灯引导把盘面摆对;加「试下」开关与「AI 支招」;摄像头用不了时临时露出手动确认。

**Architecture:** 复用死活题实体盘那条路的**监视模式**(前端推期望盘面、收 `move_confirmed`、`setupMode` 报缺/多),
不用对弈的服务端会话。新写一个纯 reducer `physicalBaipuMachine.ts`(两态 SETUP / AWAIT + 暂停 + 推进中)
和它的 IO 层 `usePhysicalBaipu.ts`(串行命令队列、灯的闪烁、WS 事件消费、卡住计时);AI 支招是独立的
`useBaipuHint.ts`(`/api/v1/analysis/quick-analyze`)。`BaipuSessionPage` 按「采集机 / 手动兜底 / 摄像头」三路
拼动作区与待摆卡。**后端不改。**

**Tech Stack:** React 19 + TypeScript + Vite(vitest / Playwright 1.57 `routeWebSocket`)。

**Spec:** `superpowers/tracks/kiosk-go-kifu/spec-2026-09-23-baipu-camera.md`(Fan 原话、三项拍板、识别层七条约束)。
设计稿 artifact `e4d3c7ef` 第 37 版,smartbox `feat/kiosk-go-kifu-list-design-2026-09-23` `df8d78b8b`(17a 文案随后在下一提交改为「放到 C7」),
`go-kiosk.tmpl.html` 的 17 / 17a / 17b / 17c / 17d。参考图 sha256:
`17-baipu.png a0746d61…1265` · `17a-baipu-restore.png b122916e…7a3f` · `17b-baipu-try.png 55093033…cac2` ·
`17c-baipu-hint.png defe2ff7…77bc` · `17d-baipu-manual.png cdec4fca…5822`(全值见 Task 7)。

## Global Constraints

- 坐标:识别 / 灯 / `BaipuStep` 同一套 —— `row` 从上往下数,`col` 从左往右;盘面矩阵 `0 空 / 1 黑 / 2 白`。
  屏上一律 GTP 串(`canonToGtp(row, col, 19)`)。
- **采集机(`collect=true`)整条不变**:手动确认 + 拍照 + 「已移除」+ 「完成」+ 撤回确认框,一个字不动。
- 灯色:下一手 红(黑)/绿(白)常亮;该拿走 `remove`(蓝)**闪**;AI 候选 `hint`(白)**闪**。闪烁周期 450 ms(同死活题)。
- 识别层七条(spec「识别层的约束」)每一条都是本计划的硬要求:先 setup、比坐标**和颜色**、改期望前先撤臂、
  不屏蔽下一手那颗灯 + 目标点 `move_pending` 先熄灯 3 s 再点、`disarm → setupMode → unpause` 依次 await、卸载清场、
  `illegal_change` / `ambiguous_stone` 忽略。
- 文案一律 `t('ns:key', '中文默认')`,中文默认必须与 cn PO 一致(`kiosk-shell-contract` 闸)。复用已有 key:
  `Hints`「AI支招」、`Try`「试下」、`play:analysis_requires_login`「登录后可用」、`baipu:confirm`「确认落子」、
  `baipu:relight`「重新点灯」、`baipu:removal_title`「请拿走被提的 {n} 子」。新 key 在 Task 6 补齐 11 语种。
- 摄像头可用判据照抄 `TsumegoProblemPage.tsx:101-105`:`visionStatus.enabled && visionStatus.recognitionReady && geometryConfirmed`
  (`geometryConfirmed` = 无 GeometryProvider,或 phase `disabled`,或 `ready && session_calibrated && capabilities.geometry_ready`),
  再加 `boardSize === 19`(非 19 路本来就进不了这一屏)。
- 页控条右上「重新点灯」图标 `arrows-clockwise`;动作区图标:撤回 `arrow-counter-clockwise`、试下 `hand-pointing`、
  AI 支招 `lightbulb`、兜底「确认落子」`arrow-right`、「摆好了，继续」`arrow-right`。

---

### Task 1: 盘上两种新标记(该拿走 / AI 候选)与盘面矩阵

**Files:**
- Modify: `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`(props 与 ghost 同层渲染)
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css:64-74`(紧跟 `.gob .atari`)
- Modify: `katrain/web/ui/src/utils/baipuReplay.ts`(加 `replayBaipuMatrix`)
- Test: `katrain/web/ui/src/kiosk/shell/GoBoardSvg.test.tsx`(新建)、`katrain/web/ui/src/utils/baipuReplay.test.ts`(已有则追加,没有就新建)

**Interfaces:**
- Produces: `GoBoardSvg` 新增可选 props `remove?: readonly string[]`、`hint?: readonly string[]`(GTP 串),
  渲染 `<circle class="remove">` / `<circle class="hint">`,半径 `STONE_R * 0.62`,画在子**之后**(压在子上也看得见)。
- Produces: `replayBaipuMatrix(steps: readonly BaipuStep[], stepCount: number, size: number): number[][]`
  —— 与 `replayBaipuSteps` 同一播放规则,输出识别坐标矩阵(`0/1/2`)。

- [ ] **Step 1: 写失败的测试**

```tsx
// GoBoardSvg.test.tsx
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GoBoardSvg } from './GoBoardSvg';

describe('GoBoardSvg · 摆谱的两种圈', () => {
  it('remove 画蓝圈、hint 画白圈,各一颗一个', () => {
    const { container } = render(<GoBoardSvg black={['C6']} remove={['C6']} hint={['C7', 'R3']} />);
    expect(container.querySelectorAll('circle.remove')).toHaveLength(1);
    expect(container.querySelectorAll('circle.hint')).toHaveLength(2);
  });
  it('不传就一个都不画(四个既有消费者不受影响)', () => {
    const { container } = render(<GoBoardSvg black={['C6']} />);
    expect(container.querySelectorAll('circle.remove, circle.hint')).toHaveLength(0);
  });
});
```

```ts
// baipuReplay.test.ts(追加)
import { replayBaipuMatrix } from './baipuReplay';
it('replayBaipuMatrix:落子进矩阵、提子出矩阵,row 从上往下', () => {
  const m = (i: number, row: number, col: number, color: 'B' | 'W', removed: { row: number; col: number }[] = []) =>
    ({ kind: 'move', move_index: i, property: color, row, col, color, removed, board_hash: `h${i}` }) as const;
  const steps = [m(0, 0, 1, 'B'), m(1, 0, 0, 'W'), m(2, 1, 0, 'B', [{ row: 0, col: 0 }])];
  const b = replayBaipuMatrix(steps as never, 3, 19);
  expect(b[0][1]).toBe(1);
  expect(b[0][0]).toBe(0);  // 被提
  expect(b[1][0]).toBe(1);
  expect(replayBaipuMatrix(steps as never, 2, 19)[0][0]).toBe(2);
});
```

- [ ] **Step 2: 跑,确认红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/shell/GoBoardSvg.test.tsx src/utils/baipuReplay.test.ts`
Expected: FAIL(`remove` 不是 prop / `replayBaipuMatrix` 未导出)

- [ ] **Step 3: 实现**

`GoBoardSvg.tsx`:在解构里加 `remove = [], hint = []`,类型块加

```tsx
  /** 摆谱:该拿走的点(蓝灯)。圈的颜色就是那颗灯的颜色(`LED_HEX.remove`)。 */
  remove?: readonly string[];
  /** 摆谱:AI 支招候选点(白灯)。 */
  hint?: readonly string[];
```

在 `atari` 那段之后加:

```tsx
      {remove.map((c) => { const p = P(c); return <circle key={`rm${c}`} className="remove" cx={p.x} cy={p.y} r={STONE_R * 0.62} />; })}
      {hint.map((c) => { const p = P(c); return <circle key={`hi${c}`} className="hint" cx={p.x} cy={p.y} r={STONE_R * 0.62} />; })}
```

`go-screens.css`(与稿子 `go-kiosk.tmpl.html` 同值):

```css
/* 摆谱:蓝圈 = 该拿走(蓝灯 #2f6fff),白圈 = AI 支招候选(白灯)。浅木盘上发虚,加一圈暗晕 */
.gob .remove { fill: rgba(47, 111, 255, .55); stroke: #2f6fff; stroke-width: 6; stroke-dasharray: 10 8; }
.gob .hint { fill: rgba(255, 255, 255, .70); stroke: #fff; stroke-width: 6; stroke-dasharray: 10 8; }
.gob .remove, .gob .hint { filter: drop-shadow(0 0 4px rgba(20, 10, 0, .55)); }
```

`baipuReplay.ts`:

```ts
/** 与 `replayBaipuSteps` 同一播放规则,输出识别坐标矩阵(row 0 在上;0 空 / 1 黑 / 2 白)。 */
export function replayBaipuMatrix(steps: readonly BaipuStep[], stepCount: number, size: number): number[][] {
  const b = Array.from({ length: size }, () => Array<number>(size).fill(0));
  for (let i = 0; i < stepCount && i < steps.length; i += 1) {
    const s = steps[i];
    if (s.row != null && s.col != null && s.color) b[s.row][s.col] = s.color === 'B' ? 1 : 2;
    for (const p of s.removed) b[p.row][p.col] = 0;
  }
  return b;
}
```

- [ ] **Step 4: 跑,确认绿**(同 Step 2 命令,PASS)
- [ ] **Step 5: 提交** `git commit -m "feat(kiosk-go): 盘上加「该拿走」蓝圈与 AI 候选白圈,摆谱盘面出识别矩阵"`

---

### Task 2: 纯 reducer `physicalBaipuMachine.ts`

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.ts`
- Test: `katrain/web/ui/src/kiosk/hooks/physicalBaipuMachine.test.ts`

**Interfaces:**
- Produces(Task 3 / 4 用):

```ts
export type Board = number[][];
export interface NextStone { row: number; col: number; color: 1 | 2 }
export interface LedPoint { row: number; col: number; color: LedColor }
export type BaipuPhase = 'off' | 'setup' | 'await' | 'advancing' | 'paused';
export type SetupReason = 'entry' | 'capture' | 'wrong' | 'undo' | 'restore' | 'adopt' | 'verify';
export type Command =
  | { kind: 'setupMode'; board: Board }
  | { kind: 'expectedBoard'; board: Board }
  | { kind: 'armMoves'; armed: boolean }
  | { kind: 'pause'; paused: boolean }
  | { kind: 'leds'; steady: LedPoint[]; blink: LedPoint[] }
  | { kind: 'relightLater'; ms: number }
  | { kind: 'matched'; promoted: boolean };
export interface BaipuMachineState {
  phase: BaipuPhase; reason: SetupReason | null; target: Board | null; next: NextStone | null;
  missing: Array<[number, number]>; extra: Array<[number, number, number]>; wrong: [number, number] | null;
}
export type MachineEvent =
  | { type: 'SETUP'; board: Board; next: NextStone | null; reason: SetupReason }
  | { type: 'AWAIT'; board: Board; next: NextStone | null }
  | { type: 'SETUP_PROGRESS'; missing: Array<[number, number]>; extra: Array<[number, number, number]> }
  | { type: 'SETUP_COMPLETE' }
  | { type: 'MOVE_CONFIRMED'; row: number; col: number; color: number }
  | { type: 'MOVE_PENDING'; row: number; col: number }
  | { type: 'RELIGHT' }
  | { type: 'PAUSE'; leds: LedPoint[] }
  | { type: 'RESUME'; board: Board; next: NextStone | null }
  | { type: 'STOP' };
export const initialState: BaipuMachineState;
export function reduce(s: BaipuMachineState, e: MachineEvent): { state: BaipuMachineState; commands: Command[] };
export function setupLeds(s: BaipuMachineState): { steady: LedPoint[]; blink: LedPoint[] };
```

规则(每条都要有测试):
1. `SETUP` → phase `setup`,`target = board`;命令 `armMoves(false)`、`leds([],[])`、`setupMode(board)`,**按此顺序**。`wrong` 只在 reason 为 `wrong` 时保留。
2. `SETUP_PROGRESS`(仅 setup):记 missing/extra。**提升**:reason ≠ `adopt`,`next` 非空,`missing` 空,`extra` 恰好一颗且坐标与颜色都等于 `next`
   ⇒ phase `advancing`,命令 `leds([],[])`、`matched(promoted:true)`。否则命令 `leds(setupLeds(state))`。
3. `setupLeds`:missing 按 target 色常亮(1→`black`,2→`white`);extra **除去「恰好是下一手」那一颗**全部 `remove` 闪。
   **不点下一手的灯**(包括 reason `wrong`):压在灯上的子可能被认成 `led_red`,setup 里没有 `move_pending` 那条补救。
4. `SETUP_COMPLETE`(仅 setup)→ phase `await`;命令 `armMoves(false)`、`expectedBoard(target)`、`armMoves(true)`、`leds(nextLed,[])`。
5. `AWAIT` → phase `await`,`target = board`;命令同 4(用新 board)。
6. `MOVE_CONFIRMED`(仅 await):坐标**与颜色**都等于 `next` ⇒ phase `advancing`,命令 `armMoves(false)`、`leds([],[])`、`matched(promoted:false)`;
   否则 ⇒ phase `setup`,reason `wrong`,`wrong=[row,col]`,target 不变,命令 `armMoves(false)`、`leds([],[])`、`setupMode(target)`。其余 phase 忽略。
7. `MOVE_PENDING`(仅 await 且坐标 = `next`)→ 命令 `leds([],[])`、`relightLater(3000)`。
8. `RELIGHT`:await → `leds(nextLed,[])`;setup → `leds(setupLeds(state))`;其余无命令。
9. `PAUSE` → phase `paused`;命令 `armMoves(false)`、`pause(true)`、`leds([], leds)`。
10. `RESUME`(仅 paused)→ phase `setup`,reason `restore`,target=board,next;命令 `leds([],[])`、`armMoves(false)`、`setupMode(board)`、`pause(false)` —— **这个顺序是约束 5**。
11. `STOP` → `initialState`,无命令。

- [ ] **Step 1: 写失败的测试**(`physicalBaipuMachine.test.ts`,覆盖 1–11;示例几条,其余照同一形状写全)

```ts
import { describe, expect, it } from 'vitest';
import { initialState, reduce, setupLeds, type Board, type NextStone } from './physicalBaipuMachine';

const empty = (): Board => Array.from({ length: 19 }, () => Array(19).fill(0));
const withStone = (b: Board, r: number, c: number, v: number) => { const x = b.map((row) => [...row]); x[r][c] = v; return x; };
const C7: NextStone = { row: 12, col: 2, color: 1 };
const kinds = (cmds: { kind: string }[]) => cmds.map((c) => c.kind);

describe('摆谱识别状态机', () => {
  it('SETUP:撤臂 → 清灯 → setupMode,按这个顺序', () => {
    const { state, commands } = reduce(initialState, { type: 'SETUP', board: empty(), next: C7, reason: 'entry' });
    expect(state.phase).toBe('setup');
    expect(kinds(commands)).toEqual(['armMoves', 'leds', 'setupMode']);
    expect(commands[0]).toEqual({ kind: 'armMoves', armed: false });
  });

  it('SETUP_COMPLETE:撤臂 → 推期望盘面 → 布臂 → 点下一手的灯(黑 = 红)', () => {
    const s = reduce(initialState, { type: 'SETUP', board: empty(), next: C7, reason: 'entry' }).state;
    const { state, commands } = reduce(s, { type: 'SETUP_COMPLETE' });
    expect(state.phase).toBe('await');
    expect(kinds(commands)).toEqual(['armMoves', 'expectedBoard', 'armMoves', 'leds']);
    expect(commands[3]).toEqual({ kind: 'leds', steady: [{ row: 12, col: 2, color: 'black' }], blink: [] });
  });

  it('MOVE_CONFIRMED 坐标对、颜色对 → advancing + matched(promoted:false)', () => {
    const s = reduce(initialState, { type: 'AWAIT', board: empty(), next: C7 }).state;
    const { state, commands } = reduce(s, { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 1 });
    expect(state.phase).toBe('advancing');
    expect(commands.at(-1)).toEqual({ kind: 'matched', promoted: false });
  });

  it('坐标对、颜色错(白子放在黑子该放的点)= 放错,不推进', () => {
    const s = reduce(initialState, { type: 'AWAIT', board: empty(), next: C7 }).state;
    const { state, commands } = reduce(s, { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 2 });
    expect(state.phase).toBe('setup');
    expect(state.reason).toBe('wrong');
    expect(kinds(commands)).not.toContain('matched');
  });

  it('放错到 C6 → setup(wrong),目标仍是第 k 手的局面,记下错点', () => {
    const board = empty();
    const s = reduce(initialState, { type: 'AWAIT', board, next: C7 }).state;
    const { state, commands } = reduce(s, { type: 'MOVE_CONFIRMED', row: 13, col: 2, color: 1 });
    expect(state).toMatchObject({ phase: 'setup', reason: 'wrong', wrong: [13, 2] });
    expect(commands.at(-1)).toEqual({ kind: 'setupMode', board });
  });

  it('提升:setup 里只多出正确的下一手 → 直接算落子(C6 直接挪到 C7)', () => {
    const s = reduce(initialState, { type: 'SETUP', board: empty(), next: C7, reason: 'wrong' }).state;
    const { state, commands } = reduce(s, { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] });
    expect(state.phase).toBe('advancing');
    expect(commands.at(-1)).toEqual({ kind: 'matched', promoted: true });
  });

  it('多出来的是下一手那颗,但颜色不对 → 不提升,闪蓝', () => {
    const s = reduce(initialState, { type: 'SETUP', board: empty(), next: C7, reason: 'wrong' }).state;
    const { state, commands } = reduce(s, { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 2]] });
    expect(state.phase).toBe('setup');
    expect(commands).toEqual([{ kind: 'leds', steady: [], blink: [{ row: 12, col: 2, color: 'remove' }] }]);
  });

  it('adopt 不提升(盘上现状就是新的目标)', () => {
    const s = reduce(initialState, { type: 'SETUP', board: empty(), next: C7, reason: 'adopt' }).state;
    expect(reduce(s, { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] }).state.phase).toBe('setup');
  });

  it('setupLeds:缺的按目标色常亮,多的闪蓝,正确的下一手那颗不闪、也不另点', () => {
    const target = withStone(empty(), 3, 3, 2);
    const s = { ...initialState, phase: 'setup' as const, reason: 'capture' as const, target, next: C7,
      missing: [[3, 3]] as Array<[number, number]>, extra: [[12, 2, 1], [0, 0, 1]] as Array<[number, number, number]> };
    expect(setupLeds(s)).toEqual({
      steady: [{ row: 3, col: 3, color: 'white' }],
      blink: [{ row: 0, col: 0, color: 'remove' }],
    });
  });

  it('MOVE_PENDING 在目标点 → 先熄灯,3 秒后再点(红灯压在黑子下会被读成 led_red)', () => {
    const s = reduce(initialState, { type: 'AWAIT', board: empty(), next: C7 }).state;
    expect(reduce(s, { type: 'MOVE_PENDING', row: 12, col: 2 }).commands)
      .toEqual([{ kind: 'leds', steady: [], blink: [] }, { kind: 'relightLater', ms: 3000 }]);
    expect(reduce(s, { type: 'MOVE_PENDING', row: 0, col: 0 }).commands).toEqual([]);
  });

  it('RESUME:清灯 → 撤臂 → setupMode → 解除暂停(解除暂停不重建基线,顺序不能换)', () => {
    const p = reduce(initialState, { type: 'PAUSE', leds: [] }).state;
    const { state, commands } = reduce(p, { type: 'RESUME', board: empty(), next: C7 });
    expect(state).toMatchObject({ phase: 'setup', reason: 'restore' });
    expect(kinds(commands)).toEqual(['leds', 'armMoves', 'setupMode', 'pause']);
    expect(commands.at(-1)).toEqual({ kind: 'pause', paused: false });
  });

  it('PAUSE:撤臂 → 暂停识别 → 只点支招白灯(闪)', () => {
    const hint = [{ row: 12, col: 2, color: 'hint' as const }];
    const { state, commands } = reduce(initialState, { type: 'PAUSE', leds: hint });
    expect(state.phase).toBe('paused');
    expect(commands).toEqual([
      { kind: 'armMoves', armed: false }, { kind: 'pause', paused: true }, { kind: 'leds', steady: [], blink: hint },
    ]);
  });

  it('非 await 时的 MOVE_CONFIRMED 一律忽略(setup / advancing / paused)', () => {
    for (const phase of ['setup', 'advancing', 'paused', 'off'] as const) {
      const s = { ...initialState, phase, next: C7, target: empty() };
      expect(reduce(s, { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 1 }).commands).toEqual([]);
    }
  });
});
```

- [ ] **Step 2: 跑,确认红** — `npx vitest run src/kiosk/hooks/physicalBaipuMachine.test.ts`,FAIL(模块不存在)

- [ ] **Step 3: 实现**(照上面的规则 1–11 与接口写全;文件头注写明:两态、`advancing` 挡住推进途中到的第二个事件、
  提升规则的三种人手路径(直接挪 / 先拿后放 / 先放后拿)、为什么 setup 里不点下一手的灯。)

```ts
import type { LedColor } from '../../api/ledApi';
// …类型见 Interfaces…
const stoneLed = (v: number): LedColor => (v === 2 ? 'white' : 'black');
const nextLeds = (n: NextStone | null): LedPoint[] => (n ? [{ row: n.row, col: n.col, color: stoneLed(n.color) }] : []);
const isNext = (n: NextStone | null, r: number, c: number, v: number) => !!n && n.row === r && n.col === c && n.color === v;
const OFF: Command = { kind: 'leds', steady: [], blink: [] };

export function setupLeds(s: BaipuMachineState) {
  const t = s.target;
  return {
    steady: s.missing.map(([row, col]) => ({ row, col, color: stoneLed(t?.[row]?.[col] ?? 1) })),
    blink: s.extra.filter(([r, c, v]) => !isNext(s.next, r, c, v)).map(([row, col]) => ({ row, col, color: 'remove' as LedColor })),
  };
}

const toAwait = (s: BaipuMachineState, board: Board, next: NextStone | null) => ({
  state: { ...s, phase: 'await' as const, reason: null, target: board, next, missing: [], extra: [], wrong: null },
  commands: [
    { kind: 'armMoves', armed: false }, { kind: 'expectedBoard', board }, { kind: 'armMoves', armed: true },
    { kind: 'leds', steady: nextLeds(next), blink: [] },
  ] as Command[],
});

const toSetup = (s: BaipuMachineState, board: Board, next: NextStone | null, reason: SetupReason, wrong: [number, number] | null = null) => ({
  state: { ...s, phase: 'setup' as const, reason, target: board, next, missing: [], extra: [], wrong },
  commands: [{ kind: 'armMoves', armed: false }, OFF, { kind: 'setupMode', board }] as Command[],
});

export function reduce(s: BaipuMachineState, e: MachineEvent) { /* switch 按规则 1–11 */ }
```

- [ ] **Step 4: 跑,确认绿**(同 Step 2,全部 PASS)
- [ ] **Step 5: 变异自检**:把规则 6 的颜色比较删掉(只比坐标),跑测试确认「颜色错」那条变红;把规则 10 的 `pause(false)` 挪到
  `setupMode` 之前,确认 RESUME 那条变红。两处都还原,记进测试文件头注释(`reference_every_gate_branch_must_execute_once`)。
- [ ] **Step 6: 提交** `git commit -m "feat(kiosk-go): 摆谱识别状态机 —— 等下一手 / 把盘面摆对两态,放错与提子走同一条收敛"`

---

### Task 3: IO 层 `usePhysicalBaipu.ts`

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.ts`
- Modify: `katrain/web/ui/src/api.ts`(Vision API 块末尾加 `visionDetectedBoard`)
- Test: `katrain/web/ui/src/kiosk/hooks/usePhysicalBaipu.test.tsx`

**Interfaces:**
- Consumes: Task 2 全部导出;`useVisionSync` 的 `VisionSyncEvent`;`API.vision*`;`LedAPI.points/clear`。
- Produces:

```ts
export interface PhysicalBaipuOptions {
  enabled: boolean;            // 摄像头可用 && 非采集机 && 页面在摆(guiding) && 没有「接着摆?」对话框
  visionConnected: boolean;    // useVisionSync(null).connected
  syncEvents: VisionSyncEvent[];
  k: number;                   // 已摆手数
  board: number[][];           // replayBaipuMatrix(steps, k, 19)
  next: NextStone | null;      // steps[k] 可摆时;pass / AE / 摆完为 null
  paused: boolean;             // 试下 || AI 支招开着
  hintLeds: LedPoint[];        // 支招候选点(白闪);没开时 []
  onMatched: () => void;       // 摄像头认到正确的下一手 → 页面 advance()
}
export interface PhysicalBaipuState {
  phase: BaipuPhase; reason: SetupReason | null; missing: Array<[number, number]>;
  extra: Array<[number, number, number]>; wrong: [number, number] | null;
  stuck: boolean;              // setup 连续 10 s 没对上
  ledOk: boolean;
  relight: () => void;         // 页控条「重新点灯」
  adopt: () => void;           // 「摆好了，继续」:按摄像头现在看到的盘面重新 setup
}
export function usePhysicalBaipu(opts: PhysicalBaipuOptions): PhysicalBaipuState;
```

- `api.ts`:`visionDetectedBoard: (): Promise<{ board: number[][] }> => fetch("/api/v1/vision/detected-board").then(r => r.json()),`

行为(每条对应测试):
1. **串行命令队列**:`queueRef = useRef(Promise.resolve())`,每条命令 `await` 完再下一条(约束 5);单条失败吞掉继续(`catch(() => {})`),
   但 `leds` 失败把 `ledOk` 置 false。
2. 生命周期:`enabled && visionConnected` 变真 → 入队 `visionMonitor(true)` 后 dispatch `SETUP(entry)`;变假 / 卸载 → 状态回 `initialState`,
   入队 `visionMoveDetection(false)`、`visionPause(false)`、`visionMonitor(false)`,再 `LedAPI.clear()`,清掉所有计时器(约束 6)。
3. WS 事件:同死活题的 seq 去重;`paused` 时全部跳过;映射 `setup_progress`→SETUP_PROGRESS、`setup_complete`→SETUP_COMPLETE、
   `move_confirmed`→MOVE_CONFIRMED(`color` 取 `data.color`)、`move_pending`→MOVE_PENDING;其它类型忽略(约束 7)。
4. 执行 `matched`:记 `matchedRef = { promoted }`,调 `onMatched()`。
5. 盘面变化(`board` 的 JSON 键或 `k` 变,且 phase ≠ off、未暂停):
   - 有 `matchedRef`:`promoted` → `SETUP(board, 有子被移除 ? 'capture' : 'verify')`;否则新盘面 = 旧盘面 + 恰好一颗 → `AWAIT`,否则 `SETUP(capture)`。
   - 没有(页面自己改的 k):`k > prevK` 且盘面没变(pass)→ `AWAIT`;`k < prevK` → `SETUP(undo)`;其它 → `SETUP(capture)`。
   - 「有子被移除」= 旧盘面上某点非 0 而新盘面为 0。
6. `paused` 由假变真 → `PAUSE(hintLeds)`;由真变假 → `RESUME(board, next)`;暂停中 `hintLeds` 变了 → 只重设灯。
7. `leds` 命令:存 steady / blink,450 ms 翻转 blink 的显隐(只在 blink 非空时发请求);全空发 `LedAPI.clear()`,否则 `LedAPI.points(steady ∪ blink?)`;
   同一组点不重复发(键去重,同死活题 `lastLedKeyRef`)。
8. `relightLater(ms)`:存一个计时器,到点 dispatch `RELIGHT`;任何新的 `AWAIT`/`SETUP`/`STOP` 清掉它。
9. `stuck`:phase 进 `setup` 起 10 s 计时,到点置真;phase / reason / target 变了重置。
10. `adopt()`:`API.visionDetectedBoard()` → dispatch `SETUP(detected, next, 'adopt')`。

- [ ] **Step 1: 写失败的测试**(`vi.mock('../../api', …)` 记下每个 vision 调用的**顺序**;`vi.mock('../../api/ledApi')`;`renderHook`)

```tsx
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const calls: string[] = [];
vi.mock('../../api', () => {
  const rec = (name: string) => vi.fn(async (arg?: unknown) => { calls.push(`${name}:${JSON.stringify(arg ?? null).slice(0, 12)}`); });
  return { API: {
    visionMonitor: rec('monitor'), visionSetupMode: rec('setup'), visionExpectedBoard: rec('expected'),
    visionMoveDetection: rec('arm'), visionPause: rec('pause'),
    visionDetectedBoard: vi.fn(async () => ({ board: Array.from({ length: 19 }, () => Array(19).fill(0)) })),
  } };
});
vi.mock('../../api/ledApi', () => ({ LedAPI: {
  points: vi.fn(async () => ({ ok: true, connected: true })), clear: vi.fn(async () => ({ ok: true, connected: true })),
} }));
import { usePhysicalBaipu } from './usePhysicalBaipu';

const empty = () => Array.from({ length: 19 }, () => Array(19).fill(0));
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const base = { enabled: true, visionConnected: true, syncEvents: [], k: 0, board: empty(),
  next: { row: 3, col: 15, color: 1 as const }, paused: false, hintLeds: [], onMatched: vi.fn() };

beforeEach(() => { calls.length = 0; vi.useRealTimers(); });

describe('usePhysicalBaipu', () => {
  it('进场:先开监视模式,再 setup —— 一次都不许倒过来', async () => {
    renderHook(() => usePhysicalBaipu(base));
    await flush();
    expect(calls.map((c) => c.split(':')[0])).toEqual(['monitor', 'arm', 'setup']);
  });

  it('认到正确的下一手 → onMatched', async () => {
    const onMatched = vi.fn();
    const { rerender } = renderHook((p) => usePhysicalBaipu(p), { initialProps: { ...base, onMatched } });
    const ev = (seq: number, type: string, data: Record<string, unknown> = {}) => ({ seq, type, data }) as never;
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete')] });
    await flush();
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete'), ev(1, 'move_confirmed', { row: 3, col: 15, color: 1 })] });
    await flush();
    expect(onMatched).toHaveBeenCalledTimes(1);
  });

  it('试下结束:撤臂 → setupMode → 解除暂停,依次 await', async () => {
    const { rerender } = renderHook((p) => usePhysicalBaipu(p), { initialProps: base });
    await flush();
    rerender({ ...base, paused: true }); await flush();
    calls.length = 0;
    rerender({ ...base, paused: false }); await flush();
    expect(calls.map((c) => c.split(':')[0])).toEqual(['arm', 'setup', 'pause']);
  });

  it('卸载清场:撤臂、解除暂停、关监视,灯全灭', async () => {
    const { unmount } = renderHook(() => usePhysicalBaipu(base));
    await flush(); calls.length = 0;
    unmount(); await flush();
    expect(calls.map((c) => c.split(':')[0])).toEqual(['arm', 'pause', 'monitor']);
  });

  it('setup 10 秒没对上 → stuck', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePhysicalBaipu(base));
    await act(async () => { await vi.advanceTimersByTimeAsync(9_900); });
    expect(result.current.stuck).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    expect(result.current.stuck).toBe(true);
  });
});
```

- [ ] **Step 2: 跑,确认红** — `npx vitest run src/kiosk/hooks/usePhysicalBaipu.test.tsx`
- [ ] **Step 3: 实现**(照行为 1–10;结构参照 `usePhysicalTsumego.ts`,但命令执行走串行队列而不是 fire-and-forget,
  文件头注写明这一处差异的理由:约束 5)
- [ ] **Step 4: 跑,确认绿**;再跑 `npx vitest run src/kiosk/hooks` 确认死活题那两份没被带红
- [ ] **Step 5: 变异自检**:把队列改回 fire-and-forget(`commands.forEach(run)`),确认「试下结束」那条仍绿 ⇒ 说明它量不到顺序;
  若仍绿,把 mock 的 `visionSetupMode` 改成 `await` 一个 10 ms 延迟后再记录,让乱序能被看见,直到这条变异能被测红。还原,记进头注释。
- [ ] **Step 6: 提交** `git commit -m "feat(kiosk-go): 摆谱识别 IO 层 —— 串行命令队列、蓝灯闪、卡住计时与按现状接着摆"`

---

### Task 4: AI 支招 `useBaipuHint.ts`

**Files:**
- Create: `katrain/web/ui/src/kiosk/hooks/useBaipuHint.ts`
- Test: `katrain/web/ui/src/kiosk/hooks/useBaipuHint.test.tsx`

**Interfaces:**
- Consumes: `API.quickAnalyze(params, token)`、`useAuth().token`、`BaipuStep`、`BaipuMeta`、`canonToGtp`。
- Produces:

```ts
export interface HintRow { move: string; winrate: number; scoreLead: number } // 走子方视角
export interface BaipuHint {
  open: boolean; status: 'idle' | 'loading' | 'ok' | 'error'; rows: HintRow[];
  leds: LedPoint[];            // rows 的白灯(color 'hint'),给 usePhysicalBaipu / 手动态点灯
  toggle: () => void; close: () => void;
}
export function useBaipuHint(o: { steps: BaipuStep[]; k: number; boardSize: number; meta: BaipuMeta | null }): BaipuHint;
```

行为:
- `toggle()` 开:`moves` = `steps.slice(0,k)` 里 `kind==='move'` 的 `[color, gtp]`(pass 记 `[color,'pass']`),`kind==='setup'` 进 `initial_stones`;
  前 k 步里有 `kind==='clear'` 时退化为 `initial_stones = replayBaipuSteps 的全盘、moves = []`(注释写明:AE 在 quick-analyze 里无从表达,罕见)。
  `komi = meta?.komi ?? 7.5`,`rules = meta?.ruleset || 'chinese'`,`max_visits: 200`,`token` 必传(`ResearchPage.tsx:139` 那条教训)。
- 走子方 = `steps[k]?.color`,没有时取最后一步的反色,再没有取 `'B'`。回来的 `turnInfos?.[0] ?? result` 的 `moveInfos` 取前 3,
  胜率 / 目差按走子方翻转(黑方视角 → `ResearchPage.toRows` 同口径)。GTP → 行列:`row = 19 - 数字`,`col = 'ABCDEFGHJKLMNOPQRST'.indexOf(字母)`。
- 30 s 自动收起;`k` 变了收起;再按一次收起。失败 `status='error'`。

- [ ] **Step 1: 写失败的测试**(mock `API.quickAnalyze` 回黑方视角的三手;白走时断言胜率 = 1 - 原值、目差取反;
  断言请求带 `token`、`moves` 只含前 k 步;fake timers 断言 30 s 后 `open=false`)
- [ ] **Step 2: 跑,确认红** — `npx vitest run src/kiosk/hooks/useBaipuHint.test.tsx`
- [ ] **Step 3: 实现**
- [ ] **Step 4: 跑,确认绿**
- [ ] **Step 5: 提交** `git commit -m "feat(kiosk-go): 摆谱 AI 支招 —— 分析谱上当前局面,走本机 KataGo,候选点白灯"`

---

### Task 5: `BaipuSessionPage` 接三路(采集机 / 手动兜底 / 摄像头)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx`
- Test: `katrain/web/ui/src/kiosk/__tests__/BaipuSessionPage.test.tsx`、`BaipuSessionPage.back.test.tsx`(mock 补 `useVision` / `useOptionalGeometry` / `useVisionSync`)

**Interfaces:**
- Consumes: Task 1 `replayBaipuMatrix` 与 `GoBoardSvg` 的 `remove`/`hint`;Task 3 `usePhysicalBaipu`;Task 4 `useBaipuHint`;
  `useVision`、`useOptionalGeometry`、`useVisionSync(null)`。

改法:
1. **判据**:`cameraReady`(Global Constraints 那条)、`camera = !collect && cameraReady`、`manual = !collect && !cameraReady`。
   不可用原因 `camWhy`(照 `TsumegoProblemPage.tsx:120-131` 的分支):没开视觉 → `baipu:cam_none`「没接摄像头」;几何 degraded/failed →
   `baipu:cam_geo_drift`「棋盘标定已失效」;几何其它非 ready → `baipu:cam_geo_confirm`「棋盘还没标定」;其余 → `baipu:cam_connecting`「正在连接摄像头」。
2. **状态**:`const [trying, setTrying] = useState(false)`;`hint = useBaipuHint({ steps, k, boardSize, meta })`;
   `next` 由 `currentStep`(可摆时 `{row, col, color: B→1 W→2}`);`visionBoard = useMemo(() => replayBaipuMatrix(steps, k, boardSize))`;
   `physical = usePhysicalBaipu({ enabled: camera && phase === 'guiding' && resumePrompt === null, visionConnected: visionSync.connected,
   syncEvents: visionSync.syncEvents, k, board: visionBoard, next, paused: trying || hint.open, hintLeds: hint.leds, onMatched: advance })`。
   开试下时若支招开着先 `hint.close()`。
3. **灯**:原来那个「灯跟着屏走」的 effect 只在 `!camera` 时跑;手动态 `hint.open` 时改点 `hint.leds`(白),收起后按原逻辑重点。
4. **摆完**:`phase === 'done' && !collect` 时 effect 里 `clearProgress(source, store)` 一次(「完成」键删了)。
5. **页控条**:`action.icon` 改 `'arrows-clockwise'`;`onClick` 摄像头态 `physical.relight`,其余原 `relight`;`state` 摄像头态看 `physical.ledOk`。
6. **待摆卡**(摄像头态,优先级写死:`done` > `trying` > `hint.open` > `physical.phase==='setup'`(按 reason)> 等下一手):
   - 等下一手:原 `baipu:place_at` + `baipu:led_on_camera`「灯已点亮 —— 把{color}子放在亮着的那个交叉点，摄像头认到就自动下一手」,`.pcard.turn`
   - setup:`.pcard.removal`,按 reason ——
     `entry`:k===0 ? `baipu:setup_clear_title`「先把盘上的子都拿下来」: `baipu:setup_entry_title`「先把盘面摆成第 {n} 手」,
       hint `baipu:setup_entry_hint`「蓝灯的子拿走、红绿灯处放上 —— 对上了自动开始」;
     `capture`:`baipu:removal_title`(n = extra 数)+ `baipu:capture_hint_camera`「亮蓝灯的那几颗 —— 拿干净了自动下一手」;
     `wrong`:`baipu:wrong_title`「放错了 · 应该在 {c}」+ `baipu:wrong_hint`「把蓝灯那颗（{w}）拿起来，放到 {c} —— 对上了自动继续」;
     `undo`:`baipu:undo_title`「撤回到第 {n} 手」+ `baipu:undo_hint_camera`「蓝灯的子拿走，被提的子放回红绿灯处 —— 对上了自动继续」;
     `restore`:`baipu:restore_title`「把盘面摆回第 {n} 手」+ `baipu:restore_hint`「试下的子拿走、挪动的放回 —— 对上了自动接着摆」;
     `adopt` / `verify`:`baipu:verify_title`「正在对一下盘面」+ `baipu:verify_hint`「多出来的子亮蓝灯 —— 拿走就继续」
   - trying:`.pcard`(无 turn)`baipu:trying_title`「试下中 · 摄像头暂停识别」+ `baipu:trying_hint`「盘上随便摆、推演。再按「试下」回到谱上，灯会带你把盘面摆回去」
   - hint.open:`.pcard.turn` 原标题 + `baipu:hint_on_hint`「AI 支招中，识别暂停 —— 白灯是 AI 的候选点，收起支招后接着摆」
   - done:原 `baipu:done_title` + `baipu:done_hint_auto`「一共 {n} 手 · 进度已清掉，按左上角返回」
   手动态:原来的 guiding / removal 两态,guiding 的说明改为 `baipu:manual_hint`「{why} —— 摆好后按「确认落子」」
   (几何类原因再接 `baipu:manual_hint_calib`「；标定在「设置」里」)。采集机:原样。
7. **折叠块**:`hint.open` 时换成 `<KioskFold fold="hint" testId="baipu-hint-fold" title={t('baipu:hint_title','AI 支招 · 白灯闪烁处')}
   value={t('baipu:hint_value','再按一次收起')} bodyClassName="ledger">`,三行 `<b>{i+1} · {move}</b><i>{interpolate(t('baipu:hint_row','胜率 {w}% · 目差 {s}'), …)}</i>`,
   loading 一行 `baipu:hint_loading`「AI 正在算这一手…」,error 一行 `baipu:hint_failed`「没算出来 —— 再按一次试试」。
   否则原「灯 · 颜色对照」块,`value`:trying → `baipu:led_value_try`「试下中 · 暂停识别」;camera → `baipu:led_value_camera`「摄像头在看」;
   manual → `baipu:led_value_manual`「手动确认」并给 `.kiosk-fold__head b` 加 warn 色(`KioskFold` 若无 `valueTone` 就加一个可选 prop)。
8. **盘面**:`ghost` 试下 / 支招开着时不画;`remove` = 摄像头态 setup 的 extra(去掉「恰好是下一手」那颗)转 GTP;`hint` = `hint.open ? rows.map(r=>r.move) : []`。
9. **动作区**:
   - 采集机:原样三格(确认/已移除、撤回确认框、完成)。
   - 手动:`[确认/已移除(icon arrow-right / 已移除仍 hand-pointing), 撤回(确认框), 试下(disabled, reason baipu:try_off_reason「摄像头没在识别」), AI支招]`
   - 摄像头:`[...(physical.phase==='setup' && physical.stuck ? [{ key:'adopt', icon:'arrow-right', label:t('baipu:setup_continue','摆好了，继续'), onClick: physical.adopt }] : []),
     撤回(**立刻** k-1 + saveProgress,无确认框;disabled k===0 || trying,reason 试下中 → baipu:undo_try_reason「试下中不能撤回」),
     试下(pressed=trying;disabled phase==='done'),
     AI支招(pressed=hint.open;disabled isGuest || trying || phase==='done',reason isGuest → play:analysis_requires_login,trying → baipu:hint_try_reason「试下中摄像头不看盘，AI 不知道盘上是什么局面」)]`
   - AI 支招 `label: t('Hints','AI支招')`、试下 `label: t('Try','试下')`(已有 key)。
10. 页头大注释改写「## 两态」「## 动作区」两节为本次的三路 + 摄像头两态,删掉「三格 / 完成常驻」那段过期的论证,
    保留「沉浸模式」「盘不用 LiveBoard」两段。

- [ ] **Step 1: 改测试**:`BaipuSessionPage.test.tsx` 顶部加三个 mock(`useVision` 返回可切换的 `visionStatus`;`useOptionalGeometry` 返回 ready+calibrated;
  `useVisionSync` 返回可注入的 `syncEvents` + `connected:true`),`usePhysicalBaipu` **不 mock**(连同 reducer 一起走)。新增用例:
  - 摄像头态:注入 `setup_complete` → `move_confirmed(3,15,1)` ⇒ 待摆卡换成第 2 手、`saveProgress` 的 k=1;屏上**没有**「确认落子」「完成」「虚手」。
  - 摄像头态放错:`move_confirmed(0,0,1)` ⇒ `data-mood` 为 setup、卡上是「放错了 · 应该在 Q16」。
  - 摄像头态撤回:点「撤回上一手」⇒ **没有**确认框、k 立刻减一、卡上「撤回到第 1 手」。
  - 试下:点「试下」⇒ `aria-pressed=true`、卡上「试下中 · 摄像头暂停识别」、撤回与 AI 支招 disabled。
  - AI 支招:mock `API.quickAnalyze`;点「AI支招」⇒ 折叠块换成三行候选;访客(`isGuest:true`)时键 disabled。
  - 手动兜底:`visionStatus.enabled=false` ⇒ 第一格「确认落子」、卡上说明含「没接摄像头」、试下 disabled;按确认照旧推进。
  - 摆完:最后一手认到 ⇒ 「这份谱摆完了」且 `localStorage` 里这份的进度被清掉。
  - 原「上线态不拍照 / 采集态一个字没变 / 只摆 19 路」三组保留;「摆完按完成」那条改为采集机下仍成立(`collect=true`)。
- [ ] **Step 2: 跑,确认新用例红** — `npx vitest run src/kiosk/__tests__/BaipuSessionPage`
- [ ] **Step 3: 实现**(照改法 1–10)
- [ ] **Step 4: 跑,确认绿**;再跑 `npx vitest run src/kiosk` 全目录与 `npx tsc -b`(类型检查以 `tsc -b` 为准,`--noEmit` 是空的)
- [ ] **Step 5: 提交** `git commit -m "feat(kiosk-go): 屏 17 摆谱改摄像头自动推进 —— 去确认/完成,加试下与 AI 支招,摄像头用不了时手动兜底"`

---

### Task 6: 新文案补齐 11 语种

**Files:**
- Modify: `katrain/i18n/locales/{cn,en,de,es,fr,jp,ko,ru,tr,tw,ua}/LC_MESSAGES/katrain.po`

- [ ] **Step 1**:`grep -o "t('baipu:[a-z_]*', '[^']*')" katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx | sort -u`,与 cn PO 比出新 key 清单
  (预计:`led_on_camera setup_clear_title setup_entry_title setup_entry_hint capture_hint_camera wrong_title wrong_hint undo_title undo_hint_camera
  restore_title restore_hint verify_title verify_hint setup_continue trying_title trying_hint hint_on_hint hint_title hint_value hint_row hint_loading
  hint_failed done_hint_auto manual_hint manual_hint_calib cam_none cam_geo_drift cam_geo_confirm cam_connecting led_value_camera led_value_try
  led_value_manual try_off_reason undo_try_reason hint_try_reason`)。
- [ ] **Step 2**:用 `katrain-i18n-expert` skill 写 11 语种(cn 与代码默认值**逐字**一致;tw 繁体;jp≠ja、cn≠zh;占位符 `{n}{c}{w}{s}{color}{why}` 原样保留)。
- [ ] **Step 3**:`uv run python i18n.py` 只用来**校验**占位符一致(它会回写 PO:跑完 `git diff --stat` 只应有这 11 个文件);
  `cd katrain/web/ui && npx playwright test tests/kiosk-shell-contract.spec.ts --config=playwright.config.ts`(需先 `npm run build`)闸四绿。
- [ ] **Step 4: 提交** `git commit -m "i18n(kiosk-go): 摆谱摄像头推进 / 试下 / AI 支招新文案 11 语种"`

---

### Task 7: 真浏览器验收(四图 17–17d + e2e + 承重)

**Files:**
- Modify: `katrain/web/ui/tests/kiosk-screen-17-baipu.fourup.spec.ts`(一个文件五条)
- Modify: `katrain/web/ui/tests/helpers/reference-shots.json`(17 改钉 + 17a–17d 新钉,`shotFrom: "feat/kiosk-go-kifu-list-design-2026-09-23"`)
- Modify: `katrain/web/ui/tests/baipu.spec.ts`(e2e 服务无摄像头 ⇒ 走手动兜底)
- Archive: `superpowers/tracks/kiosk-go-shell-align/visual/17*-baipu*/1024x600/*`

参考图 sha256(smartbox `df8d78b8b`):
- `17-baipu.png` `a0746d61a9324064c424d49ad9b09b06286c29a1e33f0ba3695416b306dc1265`
- `17a-baipu-restore.png` `b122916e8f37c08663d667ba3ed1c93aec52ce01c811a3fc186bea2616c27a3f`(smartbox `5374b3f10`)
- `17b-baipu-try.png` `55093033270d9f39ee2e49c86c9832b4fd7564eb78a3b10f8e567dbbb0d2cac2`
- `17c-baipu-hint.png` `defe2ff738b77a05c5210036bfa0dcb37e4e1ac88637fe751c2cbbdfe64777bc`
- `17d-baipu-manual.png` `cdec4fca9ae960b6c8171ce7eb51f26dc8f5d4b628bf3f083de18251069b5822`

- [ ] **Step 1: 四图 spec**:`boot()` 里钉 `/api/v1/vision/status`(`enabled:true, recognition_ready:true, camera_connected:true`)、
  `/api/v1/geometry/status`(ready + session_calibrated + geometry_ready)、`/api/v1/vision/*` POST 一律 `{ok:true}`、`/api/v1/health`;
  `page.routeWebSocket('**/ws/vision', ws => …)`:收到 `setup-mode` 的 POST 时 `ws.send(JSON.stringify({type:'setup_complete',data:{}}))`。
  - 17:摆到第 13 手 —— 前 12 手用 `ws.send({type:'move_confirmed', data:{row,col,color}})` 逐手推进(和真人在盘上摆一样)。
  - 17a:在 17 的基础上发 `move_confirmed{row:13,col:2,color:1}`(C6),再发 `setup_progress{missing:[],extra:[[13,2,1]]}`;
    这一帧的 setup 路由**不**回 `setup_complete`。
  - 17b:在 17 的基础上点「试下」。
  - 17c:`/api/v1/analysis/quick-analyze` 回三手(C7 / C9 / R3,黑方视角 .524/.518/.506、+0.9/+0.6/+0.2),点「AI支招」。
  - 17d:`vision/status` 改 `enabled:false`,手动点 12 次「确认落子」到第 13 手。
  caption 写清剩下的预期差异(稿子顶栏「访客」是占位;稿子 17 有「虚手」的那段已随稿子删;17a 实现不点 C7 的灯、屏上仍画 C7 的圈 —— 见 spec 约束与 reducer 规则 3)。
- [ ] **Step 2: 重钉参考图**(上面五个 sha256),跑 `KATRAIN_PW_VISUAL_PORT=5287 npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-17-baipu.fourup.spec.ts`,
  逐张看 side-by-side 与 diff;列表 / 右栏构图应只剩边缘差。
- [ ] **Step 3: e2e**:`baipu.spec.ts` 里依赖「完成」「三格」的两条改成手动兜底的四格(确认 / 撤回 / 试下灰 / AI支招)与「摆完自动清进度」;
  `npm run build` 后 `KATRAIN_SECRET_KEY=… KATRAIN_PW_E2E_PORT=… npx playwright test tests/baipu.spec.ts tests/kiosk-shell-scroll.spec.ts tests/kiosk-shell-geometry.spec.ts tests/kiosk-shell-contract.spec.ts`。
  失败集与 develop 基线按**名字**比(`comm`),只认新增的。
- [ ] **Step 4: 承重自检**:右栏这一屏的高度链没动(折叠块仍三行、动作区仍贴底);四格(兜底 / 卡住)时 `kiosk-shell-scroll` 已量到的
  「动作区贴底、着法块自滚」对四格同样成立 —— 在 scroll spec 的摆谱用例里加一次手动兜底四格的断言(关系式:动作区底 = 右栏底,着法块 `scrollHeight > clientHeight`)。
- [ ] **Step 5: 全量** `npx vitest run` + `npx tsc -b` + `npm run build` + `npm run build:kiosk-2d` + `npm run build:smartbox-kiosk-2d`。
- [ ] **Step 6: 提交** `git commit -m "test(kiosk-go): 屏 17 五帧四图、e2e 改手动兜底、右栏四格承重"`
- [ ] **Step 7: 停,交 Fan 看四图**(硬关卡)。

---

### Task 8: 上板(Fan 确认四图之后)

- [ ] 按 `reference_rk3562_katrain_deploy_recipe`:本地路径把 `vendor/katrain` 检出到本分支 HEAD → `build:smartbox-kiosk-2d` → 板上备份
  (`cat katrain-latest` 记旧值、`cp -al`、三处设备状态)→ `git archive | rsync`(根层不加 `--delete`)→ 包 `rsync --delete` →
  **本区间 `.po` 有改动 ⇒ 板上用 polib 编 `.mo`(写 `.new` 再 `os.replace`)** → 只在 `smartbox-go.target` 激活时重启 katrain
  (读状态与重启在同一条盒上命令里)→ 验 `/kiosk` 200、旧入口 404、启动日志 Vision/LED/worker_inprocess 三行。
- [ ] 请 Fan 在板上实摆:入场清盘 → 正常落子自动推进 → 放错一颗 → 提子 → 撤回 → 试下再退出 → AI 支招 → 故意让盘面对不上看「摆好了，继续」。
  `journalctl -u smartbox-katrain` 里按 `move_confirmed` / `setup_complete` 对时间线;有问题回到对应 Task。
