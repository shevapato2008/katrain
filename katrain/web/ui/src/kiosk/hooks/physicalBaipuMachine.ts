// 摆谱(屏 17)实体盘识别的纯状态机。没有 IO —— reduce() 把 (state, event) 映射成
// (state, 声明式命令),由 usePhysicalBaipu 依次执行。
//
// Fan 2026-09-23:「不要每走一步都要按屏幕上的确认键……应该使用摄像头确认。」
// 复用死活题实体盘那条路的**监视模式**(physicalTsumegoMachine 同一套识别原语),不用对弈的服务端会话 ——
// 摆谱没有对局会话,下一手是谱上写死的。
//
// 整页只有两个识别状态:
//  · **await 等下一手**:期望盘面 = 谱上第 k 手之后,落子检测开,下一手那颗灯亮(红黑 / 绿白)。
//    `move_confirmed` 的坐标**和颜色**都等于第 k+1 手才算(worker 不查颜色,`BS:218`),否则就是放错。
//  · **setup 把盘面摆对**:`setupMode(target)`,缺的按目标色常亮、多的**闪蓝**。放错、提子、撤回、
//    试下 / 支招结束、进场有残子,全都走这一条收敛;`setup_complete` 回到 await。
// 另有两个过渡态:`advancing`(认到了、等页面把 k 推进,挡住途中到的第二个事件)、`paused`(试下 / 支招)。
//
// **提升规则**(setup 里):没缺子、只多出**恰好是下一手**的那一颗(坐标与颜色都对)⇒ 直接算落子。
// 于是放错之后人手的三种自然做法都走得通:直接把 C6 挪到 C7(多出来的只剩 C7 ⇒ 提升)、先拿走再放
// (C6 拿走 ⇒ setup_complete ⇒ await ⇒ 放 C7 ⇒ 认到)、先放对再拿走错的(拿走那一刻多出来的只剩 C7 ⇒ 提升)。
//
// **setup 里不点下一手的灯**(包括放错那一态):子压在亮着的红灯上可能被认成 `led_red`,那就永远对不上;
// await 里有「目标点 move_pending 先熄灯、3 s 后再点」这条补救(对弈编排器同一个修法,
// `physical_play.py:59-64`),setup 里没有。下一手只在屏上画圈。
//
// 坐标:识别坐标,row 0 在上;盘面矩阵 0 空 / 1 黑 / 2 白。

import type { LedColor } from '../../api/ledApi';

export type Board = number[][];
export interface NextStone { row: number; col: number; color: 1 | 2 }
export interface LedPoint { row: number; col: number; color: LedColor }

export type BaipuPhase = 'off' | 'setup' | 'await' | 'advancing' | 'paused';
/** 为什么在 setup —— 只决定屏上说哪句话,收敛规则一样。 */
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
  phase: BaipuPhase;
  reason: SetupReason | null;
  /** setup 的目标 / await 的期望盘面。 */
  target: Board | null;
  next: NextStone | null;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  /** 最近一次放错的点(待摆卡要说「把 C6 那颗拿起来」)。 */
  wrong: [number, number] | null;
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

export const initialState: BaipuMachineState = {
  phase: 'off',
  reason: null,
  target: null,
  next: null,
  missing: [],
  extra: [],
  wrong: null,
};

const OFF: Command = { kind: 'leds', steady: [], blink: [] };
const stoneLed = (v: number): LedColor => (v === 2 ? 'white' : 'black');
const nextLeds = (n: NextStone | null): LedPoint[] => (n ? [{ row: n.row, col: n.col, color: stoneLed(n.color) }] : []);
const isNext = (n: NextStone | null, r: number, c: number, v: number) =>
  !!n && n.row === r && n.col === c && n.color === v;

/** setup 时的灯:缺的按目标色常亮;多的闪蓝 —— 但「恰好是下一手」那一颗不闪(那一颗是对的)。 */
export function setupLeds(s: BaipuMachineState): { steady: LedPoint[]; blink: LedPoint[] } {
  const t = s.target;
  return {
    steady: s.missing.map(([row, col]) => ({ row, col, color: stoneLed(t?.[row]?.[col] ?? 1) })),
    blink: s.extra
      .filter(([r, c, v]) => !isNext(s.next, r, c, v))
      .map(([row, col]) => ({ row, col, color: 'remove' as LedColor })),
  };
}

const toSetup = (
  s: BaipuMachineState, board: Board, next: NextStone | null, reason: SetupReason, wrong: [number, number] | null = null,
) => ({
  state: { ...s, phase: 'setup' as const, reason, target: board, next, missing: [], extra: [], wrong },
  commands: [{ kind: 'armMoves', armed: false }, OFF, { kind: 'setupMode', board }] as Command[],
});

// 先撤臂再改期望盘面(改期望会 force_sync 检测基线),再布臂、点灯。
const toAwait = (s: BaipuMachineState, board: Board, next: NextStone | null) => ({
  state: { ...s, phase: 'await' as const, reason: null, target: board, next, missing: [], extra: [], wrong: null },
  commands: [
    { kind: 'armMoves', armed: false },
    { kind: 'expectedBoard', board },
    { kind: 'armMoves', armed: true },
    { kind: 'leds', steady: nextLeds(next), blink: [] },
  ] as Command[],
});

const none = (state: BaipuMachineState) => ({ state, commands: [] as Command[] });

export function reduce(s: BaipuMachineState, e: MachineEvent): { state: BaipuMachineState; commands: Command[] } {
  switch (e.type) {
    case 'SETUP':
      return toSetup(s, e.board, e.next, e.reason, e.reason === 'wrong' ? s.wrong : null);

    case 'AWAIT':
      return toAwait(s, e.board, e.next);

    case 'SETUP_PROGRESS': {
      if (s.phase !== 'setup') return none(s);
      const base = { ...s, missing: e.missing, extra: e.extra };
      if (
        s.reason !== 'adopt'
        && e.missing.length === 0
        && e.extra.length === 1
        && isNext(s.next, e.extra[0][0], e.extra[0][1], e.extra[0][2])
      ) {
        return { state: { ...base, phase: 'advancing' }, commands: [OFF, { kind: 'matched', promoted: true }] };
      }
      return { state: base, commands: [{ kind: 'leds', ...setupLeds(base) }] };
    }

    case 'SETUP_COMPLETE':
      if (s.phase !== 'setup' || !s.target) return none(s);
      return toAwait(s, s.target, s.next);

    case 'MOVE_CONFIRMED': {
      if (s.phase !== 'await' || !s.target) return none(s);
      if (isNext(s.next, e.row, e.col, e.color)) {
        return {
          state: { ...s, phase: 'advancing' },
          commands: [{ kind: 'armMoves', armed: false }, OFF, { kind: 'matched', promoted: false }],
        };
      }
      return toSetup(s, s.target, s.next, 'wrong', [e.row, e.col]);
    }

    case 'MOVE_PENDING':
      if (s.phase !== 'await' || !s.next || s.next.row !== e.row || s.next.col !== e.col) return none(s);
      return { state: s, commands: [OFF, { kind: 'relightLater', ms: 3000 }] };

    case 'RELIGHT':
      if (s.phase === 'await') return { state: s, commands: [{ kind: 'leds', steady: nextLeds(s.next), blink: [] }] };
      if (s.phase === 'setup') return { state: s, commands: [{ kind: 'leds', ...setupLeds(s) }] };
      return none(s);

    case 'PAUSE':
      return {
        state: { ...s, phase: 'paused' },
        commands: [{ kind: 'armMoves', armed: false }, { kind: 'pause', paused: true }, { kind: 'leds', steady: [], blink: e.leds }],
      };

    case 'RESUME':
      if (s.phase !== 'paused') return none(s);
      // 顺序是约束:解除暂停**不重建基线**,先撤臂、先进 setup,暂停时盘上摆的子才不会被当成落子。
      return {
        state: { ...s, phase: 'setup', reason: 'restore', target: e.board, next: e.next, missing: [], extra: [], wrong: null },
        commands: [OFF, { kind: 'armMoves', armed: false }, { kind: 'setupMode', board: e.board }, { kind: 'pause', paused: false }],
      };

    case 'STOP':
      return { state: initialState, commands: [] };

    default:
      return none(s);
  }
}
