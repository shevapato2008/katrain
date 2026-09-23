import { describe, expect, it } from 'vitest';
import {
  initialState, reduce, setupLeds,
  type Board, type BaipuMachineState, type Command, type NextStone,
} from './physicalBaipuMachine';

/**
 * 摆谱识别状态机(纯函数)。规则编号对应 `plan-2026-09-23-baipu-camera.md` Task 2。
 *
 * 变异记录(2026-09-23,两处都已还原):
 *  · 规则 6 只比坐标不比颜色 ⇒「坐标对、颜色错」那条红。
 *  · 规则 10 把 `pause(false)` 挪到 `setupMode` 之前 ⇒「RESUME 顺序」那条红。
 */

const empty = (): Board => Array.from({ length: 19 }, () => Array<number>(19).fill(0));
const withStone = (b: Board, r: number, c: number, v: number): Board => {
  const x = b.map((row) => [...row]);
  x[r][c] = v;
  return x;
};
const C7: NextStone = { row: 12, col: 2, color: 1 };
const kinds = (cmds: Command[]) => cmds.map((c) => c.kind);
const OFF = { kind: 'leds', steady: [], blink: [] };
const awaiting = (board = empty(), next: NextStone | null = C7) => reduce(initialState, { type: 'AWAIT', board, next }).state;
const settingUp = (reason: BaipuMachineState['reason'], board = empty(), next: NextStone | null = C7) =>
  reduce(initialState, { type: 'SETUP', board, next, reason: reason! }).state;

describe('摆谱识别状态机', () => {
  it('规则 1 · SETUP:撤臂 → 清灯 → setupMode,按这个顺序', () => {
    const board = empty();
    const { state, commands } = reduce(initialState, { type: 'SETUP', board, next: C7, reason: 'entry' });
    expect(state).toMatchObject({ phase: 'setup', reason: 'entry', target: board, next: C7, wrong: null });
    expect(commands).toEqual([{ kind: 'armMoves', armed: false }, OFF, { kind: 'setupMode', board }]);
  });

  it('规则 2 · 提升:setup 里只多出正确的下一手 → 直接算落子(C6 直接挪到 C7)', () => {
    const { state, commands } = reduce(settingUp('wrong'), { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] });
    expect(state.phase).toBe('advancing');
    expect(commands).toEqual([OFF, { kind: 'matched', promoted: true }]);
  });

  it('规则 2 · 多出的是下一手那一点但颜色不对 → 不提升,闪蓝', () => {
    const { state, commands } = reduce(settingUp('wrong'), { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 2]] });
    expect(state.phase).toBe('setup');
    expect(commands).toEqual([{ kind: 'leds', steady: [], blink: [{ row: 12, col: 2, color: 'remove' }] }]);
  });

  it('规则 2 · 还缺子时不提升(提子没拿干净 / 撤回没放回)', () => {
    const target = withStone(empty(), 3, 3, 2);
    const s = settingUp('undo', target);
    const { state } = reduce(s, { type: 'SETUP_PROGRESS', missing: [[3, 3]], extra: [[12, 2, 1]] });
    expect(state.phase).toBe('setup');
  });

  it('规则 2 · adopt 不提升(盘上现状就是新的目标)', () => {
    const { state } = reduce(settingUp('adopt'), { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] });
    expect(state.phase).toBe('setup');
  });

  it('规则 2 · 没有下一手(摆到最后 / pass)时不提升', () => {
    const { state } = reduce(settingUp('capture', empty(), null), { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] });
    expect(state.phase).toBe('setup');
  });

  it('规则 3 · setupLeds:缺的按目标色常亮,多的闪蓝,正确的下一手那颗不闪、也不另点', () => {
    const target = withStone(empty(), 3, 3, 2);
    const s: BaipuMachineState = {
      ...initialState, phase: 'setup', reason: 'capture', target, next: C7,
      missing: [[3, 3]], extra: [[12, 2, 1], [0, 0, 1]],
    };
    expect(setupLeds(s)).toEqual({
      steady: [{ row: 3, col: 3, color: 'white' }],
      blink: [{ row: 0, col: 0, color: 'remove' }],
    });
  });

  it('规则 3 · 放错(wrong)也不点下一手的灯 —— 压在灯上的子会被认成 led_red', () => {
    const s = { ...settingUp('wrong'), extra: [[13, 2, 1]] as Array<[number, number, number]> };
    expect(setupLeds(s)).toEqual({ steady: [], blink: [{ row: 13, col: 2, color: 'remove' }] });
  });

  it('规则 4 · SETUP_COMPLETE:撤臂 → 推期望盘面 → 布臂 → 点下一手的灯(黑 = 红)', () => {
    const board = empty();
    const { state, commands } = reduce(settingUp('entry', board), { type: 'SETUP_COMPLETE' });
    expect(state).toMatchObject({ phase: 'await', reason: null, target: board, missing: [], extra: [] });
    expect(commands).toEqual([
      { kind: 'armMoves', armed: false }, { kind: 'expectedBoard', board }, { kind: 'armMoves', armed: true },
      { kind: 'leds', steady: [{ row: 12, col: 2, color: 'black' }], blink: [] },
    ]);
  });

  it('规则 4 · 不在 setup 时的 SETUP_COMPLETE 忽略', () => {
    expect(reduce(awaiting(), { type: 'SETUP_COMPLETE' }).commands).toEqual([]);
  });

  it('规则 5 · AWAIT:白子的下一手点绿灯', () => {
    const W: NextStone = { row: 3, col: 3, color: 2 };
    const { state, commands } = reduce(initialState, { type: 'AWAIT', board: empty(), next: W });
    expect(state.phase).toBe('await');
    expect(kinds(commands)).toEqual(['armMoves', 'expectedBoard', 'armMoves', 'leds']);
    expect(commands.at(-1)).toEqual({ kind: 'leds', steady: [{ row: 3, col: 3, color: 'white' }], blink: [] });
  });

  it('规则 5 · 没有下一手时不点灯', () => {
    const { commands } = reduce(initialState, { type: 'AWAIT', board: empty(), next: null });
    expect(commands.at(-1)).toEqual(OFF);
  });

  it('规则 6 · MOVE_CONFIRMED 坐标对、颜色对 → advancing + matched(promoted:false)', () => {
    const { state, commands } = reduce(awaiting(), { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 1 });
    expect(state.phase).toBe('advancing');
    expect(commands).toEqual([{ kind: 'armMoves', armed: false }, OFF, { kind: 'matched', promoted: false }]);
  });

  it('规则 6 · 坐标对、颜色错(白子放在黑子该放的点)= 放错,不推进', () => {
    const { state, commands } = reduce(awaiting(), { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 2 });
    expect(state).toMatchObject({ phase: 'setup', reason: 'wrong', wrong: [12, 2] });
    expect(kinds(commands)).not.toContain('matched');
  });

  it('规则 6 · 放错到 C6 → setup(wrong),目标仍是第 k 手的局面,记下错点', () => {
    const board = empty();
    const { state, commands } = reduce(awaiting(board), { type: 'MOVE_CONFIRMED', row: 13, col: 2, color: 1 });
    expect(state).toMatchObject({ phase: 'setup', reason: 'wrong', wrong: [13, 2], target: board, next: C7 });
    expect(commands).toEqual([{ kind: 'armMoves', armed: false }, OFF, { kind: 'setupMode', board }]);
  });

  it('规则 6 · 非 await 时的 MOVE_CONFIRMED 一律忽略', () => {
    for (const phase of ['setup', 'advancing', 'paused', 'off'] as const) {
      const s: BaipuMachineState = { ...initialState, phase, next: C7, target: empty() };
      const r = reduce(s, { type: 'MOVE_CONFIRMED', row: 12, col: 2, color: 1 });
      expect(r.commands).toEqual([]);
      expect(r.state).toBe(s);
    }
  });

  it('规则 7 · MOVE_PENDING 在目标点 → 先熄灯,3 秒后再点;别的点不理', () => {
    expect(reduce(awaiting(), { type: 'MOVE_PENDING', row: 12, col: 2 }).commands)
      .toEqual([OFF, { kind: 'relightLater', ms: 3000 }]);
    expect(reduce(awaiting(), { type: 'MOVE_PENDING', row: 0, col: 0 }).commands).toEqual([]);
    expect(reduce(settingUp('entry'), { type: 'MOVE_PENDING', row: 12, col: 2 }).commands).toEqual([]);
  });

  it('规则 8 · RELIGHT:await 点下一手;setup 重放收敛灯;其余无命令', () => {
    expect(reduce(awaiting(), { type: 'RELIGHT' }).commands)
      .toEqual([{ kind: 'leds', steady: [{ row: 12, col: 2, color: 'black' }], blink: [] }]);
    const s = { ...settingUp('capture'), extra: [[0, 0, 1]] as Array<[number, number, number]> };
    expect(reduce(s, { type: 'RELIGHT' }).commands)
      .toEqual([{ kind: 'leds', steady: [], blink: [{ row: 0, col: 0, color: 'remove' }] }]);
    expect(reduce(initialState, { type: 'RELIGHT' }).commands).toEqual([]);
  });

  it('规则 9 · PAUSE:撤臂 → 暂停识别 → 只点支招白灯(闪)', () => {
    const hint = [{ row: 12, col: 2, color: 'hint' as const }];
    const { state, commands } = reduce(awaiting(), { type: 'PAUSE', leds: hint });
    expect(state.phase).toBe('paused');
    expect(commands).toEqual([
      { kind: 'armMoves', armed: false }, { kind: 'pause', paused: true }, { kind: 'leds', steady: [], blink: hint },
    ]);
  });

  it('规则 10 · RESUME:清灯 → 撤臂 → setupMode → 解除暂停(解除暂停不重建基线,顺序不能换)', () => {
    const p = reduce(awaiting(), { type: 'PAUSE', leds: [] }).state;
    const board = withStone(empty(), 3, 15, 1);
    const { state, commands } = reduce(p, { type: 'RESUME', board, next: C7 });
    expect(state).toMatchObject({ phase: 'setup', reason: 'restore', target: board, next: C7 });
    expect(commands).toEqual([
      OFF, { kind: 'armMoves', armed: false }, { kind: 'setupMode', board }, { kind: 'pause', paused: false },
    ]);
  });

  it('规则 10 · 没暂停时的 RESUME 忽略', () => {
    expect(reduce(awaiting(), { type: 'RESUME', board: empty(), next: C7 }).commands).toEqual([]);
  });

  it('规则 11 · STOP 回到初态,无命令', () => {
    expect(reduce(awaiting(), { type: 'STOP' })).toEqual({ state: initialState, commands: [] });
  });

  it('暂停中 setup 事件不理(识别层暂停时本来就不喂,这里再挡一道)', () => {
    const p = reduce(awaiting(), { type: 'PAUSE', leds: [] }).state;
    expect(reduce(p, { type: 'SETUP_PROGRESS', missing: [], extra: [[12, 2, 1]] }).commands).toEqual([]);
    expect(reduce(p, { type: 'SETUP_COMPLETE' }).commands).toEqual([]);
  });
});
