import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BaipuStep } from '../../api/baipuApi';

/**
 * 摆谱 AI 支招:分析**谱上**第 k 手之后的局面(不是摄像头看到的),走本机 KataGo 的 quick-analyze。
 * 量四件事:请求只带前 k 步且带 token、走白时换视角、候选点转成白灯、三种收起。
 */

const { quickAnalyze, auth } = vi.hoisted(() => ({ quickAnalyze: vi.fn(), auth: { token: 't1' } }));
vi.mock('../../api', () => ({ API: { quickAnalyze } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));

import { buildHintRequest, hintMover, useBaipuHint } from './useBaipuHint';

const mv = (color: 'B' | 'W', row: number, col: number, removed: Array<{ row: number; col: number }> = []): BaipuStep => ({
  kind: 'move', move_index: 0, property: color, row, col, color, removed, board_hash: '',
});
const setup = (color: 'B' | 'W', row: number, col: number): BaipuStep => ({
  kind: 'setup', move_index: 0, property: `A${color}`, row, col, color, removed: [], board_hash: '',
});
const pass = (color: 'B' | 'W'): BaipuStep => ({
  kind: 'pass', move_index: 0, property: color, row: null, col: null, color, removed: [], board_hash: '',
});
const clear = (row: number, col: number): BaipuStep => ({
  kind: 'clear', move_index: 0, property: 'AE', row: null, col: null, color: null, removed: [{ row, col }], board_hash: '',
});

// 黑方视角的三手(后端口径)
const RESP = {
  turnInfos: [{
    moveInfos: [
      { move: 'Q16', winrate: 0.6, scoreLead: 2.5, visits: 120 },
      { move: 'D4', winrate: 0.55, scoreLead: 1.0, visits: 50 },
      { move: 'C3', winrate: 0.5, scoreLead: 0, visits: 20 },
      { move: 'K10', winrate: 0.4, scoreLead: -3, visits: 10 },
    ],
  }],
};

const STEPS = [setup('B', 15, 3), mv('B', 3, 15), mv('W', 15, 15), mv('B', 2, 2)];
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

beforeEach(() => { vi.useRealTimers(); auth.token = 't1'; quickAnalyze.mockReset(); quickAnalyze.mockResolvedValue(RESP); });

describe('buildHintRequest', () => {
  it('snapshots late setup instead of hoisting it before the played moves', () => {
    // Exact backend v2 steps for (;SZ[19];B[aa];W[ba];AW[ab];B[ac];B[bb];W[dd]).
    // AW[A18] follows B[A19], so moving it into initial_stones would capture
    // A19 early and produce a different board even when all moves are legal.
    const steps: BaipuStep[] = [
      { kind: 'move', move_index: 0, property: 'B', row: 0, col: 0, color: 'B', pre_removed: [], removed: [], requires_placement: true, board_hash: 'bde4ba64d5dd546d' },
      { kind: 'move', move_index: 1, property: 'W', row: 0, col: 1, color: 'W', pre_removed: [], removed: [], requires_placement: true, board_hash: 'bdc6d7fc7a9979e4' },
      { kind: 'setup', move_index: 2, property: 'AW', row: 1, col: 0, color: 'W', pre_removed: [], removed: [], requires_placement: true, board_hash: '0e5e89bd74dc8f61' },
      { kind: 'move', move_index: 3, property: 'B', row: 2, col: 0, color: 'B', pre_removed: [], removed: [], requires_placement: true, board_hash: '50e75aa073be6186' },
      { kind: 'move', move_index: 4, property: 'B', row: 1, col: 1, color: 'B', pre_removed: [], removed: [{ row: 1, col: 0 }], requires_placement: true, board_hash: 'cd85bcce25ce8387' },
      { kind: 'move', move_index: 5, property: 'W', row: 3, col: 3, color: 'W', pre_removed: [], removed: [], requires_placement: true, board_hash: '471e55ce4ae271f0' },
    ];
    expect(buildHintRequest(steps, 5, 19, null)).toMatchObject({
      initial_stones: [['B', 'A19'], ['B', 'A17'], ['B', 'B18'], ['W', 'B19']],
      moves: [['B', 'pass']], max_visits: 200,
    });
  });

  it.each([
    { name: 'opposite replacement', previous: 'W', operation: { pre_removed: [{ row: 0, col: 0 }], requires_placement: true }, expected: [['B', 'A9']] },
    { name: 'same-color repeat', previous: 'B', operation: { requires_placement: false }, expected: [['B', 'A9']] },
    { name: 'legacy occupied move', previous: 'W', operation: {}, expected: [['B', 'A9']] },
    { name: 'self-capture', previous: 'W', operation: { removed: [{ row: 0, col: 0 }] }, expected: [] },
  ] as const)('uses an authoritative snapshot after an applied $name', ({ previous, operation, expected }) => {
    const steps = [mv(previous, 0, 0), { ...mv('B', 0, 0), ...operation }, mv('B', 8, 8)] as BaipuStep[];
    const request = buildHintRequest(steps, 2, 9, null);
    expect(request.initial_stones).toEqual(expected);
    expect(request.moves).toEqual([]);
    expect(request.max_visits).toBe(200);
  });

  it('does not fall back for an unapplied future replacement', () => {
    const steps = [mv('W', 0, 0), { ...mv('B', 0, 0), pre_removed: [{ row: 0, col: 0 }] }];
    expect(buildHintRequest(steps, 1, 9, null)).toMatchObject({ initial_stones: [], moves: [['W', 'A9']] });
  });

  it('snapshots a self-capture at an empty destination while retaining other stones', () => {
    const steps = [setup('W', 0, 1), mv('B', 0, 0, [{ row: 0, col: 0 }]), mv('B', 8, 8)];
    expect(buildHintRequest(steps, 2, 9, null)).toMatchObject({ initial_stones: [['W', 'B9']], moves: [] });
  });

  it('keeps legal history for an ordinary opponent capture', () => {
    const steps = [setup('W', 0, 1), mv('B', 0, 0, [{ row: 0, col: 1 }]), mv('W', 8, 8)];
    expect(buildHintRequest(steps, 2, 9, null)).toMatchObject({ initial_stones: [['W', 'B9']], moves: [['B', 'A9']] });
  });

  it('uses the recorded pass property when its backend color is null', () => {
    const steps = [mv('B', 0, 0), { ...pass('W'), color: null }];
    expect(hintMover(steps, 1)).toBe('W');
    expect(hintMover(steps, 2)).toBe('B');
    expect(buildHintRequest(steps, 2, 9, null).moves).toEqual([['B', 'A9'], ['W', 'pass']]);
  });

  it('keeps the player from a color-null pass after snapshot fallback', () => {
    const steps = [mv('B', 0, 0), clear(0, 0), { ...pass('W'), color: null }];
    expect(buildHintRequest(steps, 3, 9, null)).toMatchObject({ initial_stones: [], moves: [] });
  });

  it('只带前 k 步;setup 进 initial_stones;pass 记 pass;贴目与规则取谱', () => {
    const steps = [setup('B', 15, 3), mv('B', 3, 15), pass('W'), mv('B', 2, 2)];
    expect(buildHintRequest(steps, 3, 19, { player_black: '', player_white: '', result: '', handicap: 0, komi: 6.5, ruleset: 'japanese' }))
      .toEqual({
        moves: [['B', 'Q16'], ['W', 'pass']],
        initial_stones: [['B', 'D4']],
        board_size: 19, komi: 6.5, rules: 'japanese', max_visits: 200,
      });
  });

  it('没谱信息时贴目 7.5、规则 chinese', () => {
    expect(buildHintRequest(STEPS, 0, 19, null)).toMatchObject({ moves: [], komi: 7.5, rules: 'chinese' });
  });

  it('让子谱 k=0 轮白:后端不收 initialPlayer ⇒ 补一手黑 pass,KataGo 才会替白算', () => {
    const steps = [setup('B', 15, 3), setup('B', 3, 15), mv('W', 2, 2)];
    expect(buildHintRequest(steps, 2, 19, null)).toMatchObject({
      moves: [['B', 'pass']], initial_stones: [['B', 'D4'], ['B', 'Q16']],
    });
  });

  it('前 k 步里有 AE(clear)⇒ 退化成整盘 initial_stones、moves 为空', () => {
    const steps = [mv('B', 3, 15), mv('W', 15, 15), clear(3, 15), mv('B', 2, 2)];
    const r = buildHintRequest(steps, 3, 19, null);
    expect(r.moves).toEqual([]);
    expect(r.initial_stones).toEqual([['W', 'Q4']]);
  });
});

describe('useBaipuHint', () => {
  it.each(['user-a:source-b', 'user-b:source-a'])('closes same-cursor hints across session %s and does not reopen old scope', async sessionKey => {
    const { result, rerender } = renderHook((key: string) => useBaipuHint({
      steps: STEPS, k: 2, boardSize: 19, meta: null, sessionKey: key,
    }), { initialProps: 'user-a:source-a' });
    act(() => result.current.toggle());
    await flush();
    expect(result.current.leds).toHaveLength(3);
    rerender(sessionKey);
    expect(result.current).toMatchObject({ open: false, status: 'idle', rows: [], leds: [] });
    rerender('user-a:source-a');
    expect(result.current.open).toBe(false);
  });

  it('closes same-cursor hints when authoritative steps are replaced', async () => {
    const { result, rerender } = renderHook((steps: BaipuStep[]) => useBaipuHint({ steps, k: 2, boardSize: 19, meta: null }), { initialProps: STEPS });
    act(() => result.current.toggle());
    await flush();
    rerender([...STEPS]);
    expect(result.current).toMatchObject({ open: false, status: 'idle', rows: [], leds: [] });
  });

  it('closes same-cursor hints when account credentials change', async () => {
    const { result, rerender } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    auth.token = 't2';
    rerender();
    expect(result.current).toMatchObject({ open: false, status: 'idle', rows: [], leds: [] });
  });

  it('rejects late old-session analysis at the same cursor', async () => {
    let resolveOld: (value: unknown) => void = () => {};
    quickAnalyze.mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }));
    const { result, rerender } = renderHook((sessionKey: string) => useBaipuHint({
      steps: STEPS, k: 2, boardSize: 19, meta: null, sessionKey,
    }), { initialProps: 'user-a:source-a' });
    act(() => result.current.toggle());
    rerender('user-b:source-b');
    expect(result.current.open).toBe(false);
    act(() => result.current.toggle());
    await flush();
    expect(quickAnalyze).toHaveBeenCalledTimes(2);
    expect(result.current.rows[0].move).toBe('Q16');
    await act(async () => { resolveOld({ moveInfos: [{ move: 'T1', winrate: 0.9 }] }); await Promise.resolve(); });
    expect(result.current.rows[0].move).toBe('Q16');
    expect(result.current.leds[0]).toEqual({ row: 3, col: 15, color: 'hint' });
  });

  it('toggle 开:请求带 token、只含前 k 手;回来取前 3 手', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    expect(result.current).toMatchObject({ open: true, status: 'loading' });
    await flush();
    expect(quickAnalyze).toHaveBeenCalledTimes(1);
    const [params, token] = quickAnalyze.mock.calls[0];
    expect(token).toBe('t1');
    expect(params.moves).toEqual([['B', 'Q16']]);
    expect(result.current.status).toBe('ok');
    expect(result.current.rows.map((r) => r.move)).toEqual(['Q16', 'D4', 'C3']);
  });

  it('轮黑走:胜率目差原样(后端就是黑方视角)', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 3, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current.rows[0]).toEqual({ move: 'Q16', winrate: 0.6, scoreLead: 2.5 });
  });

  it('轮白走:胜率 = 1 - 原值、目差取反', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current.rows[0].winrate).toBeCloseTo(0.4);
    expect(result.current.rows[0].scoreLead).toBe(-2.5);
  });

  it('摆到最后(没有第 k+1 步):走子方取最后一步的反色', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: STEPS.length, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current.rows[0].scoreLead).toBe(-2.5); // 最后一步是黑 ⇒ 轮白
  });

  it('候选点转成白灯(识别坐标,row 0 在上)', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current.leds).toEqual([
      { row: 3, col: 15, color: 'hint' },
      { row: 15, col: 3, color: 'hint' },
      { row: 16, col: 2, color: 'hint' },
    ]);
  });

  it('候选里的 pass 不点灯', async () => {
    quickAnalyze.mockResolvedValue({ moveInfos: [{ move: 'pass', winrate: 0.5, scoreLead: 0, visits: 5 }] });
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current.rows).toHaveLength(1);
    expect(result.current.leds).toEqual([]);
  });

  it('再按一次收起;收起时 leds 清空', async () => {
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    act(() => result.current.toggle());
    expect(result.current).toMatchObject({ open: false, status: 'idle', rows: [], leds: [] });
  });

  it('30 秒自动收起', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await act(async () => { await vi.advanceTimersByTimeAsync(29_000); });
    expect(result.current.open).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(result.current.open).toBe(false);
  });

  it('k 变了就收起;晚到的旧响应不回填', async () => {
    let resolve: (v: unknown) => void = () => {};
    quickAnalyze.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { result, rerender } = renderHook((k: number) => useBaipuHint({ steps: STEPS, k, boardSize: 19, meta: null }), { initialProps: 2 });
    act(() => result.current.toggle());
    rerender(3);
    expect(result.current.open).toBe(false);
    await act(async () => { resolve(RESP); await Promise.resolve(); });
    expect(result.current).toMatchObject({ open: false, status: 'idle', rows: [] });
  });

  it('失败 ⇒ status error,不留假数', async () => {
    quickAnalyze.mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useBaipuHint({ steps: STEPS, k: 2, boardSize: 19, meta: null }));
    act(() => result.current.toggle());
    await flush();
    expect(result.current).toMatchObject({ open: true, status: 'error', rows: [], leds: [] });
  });
});
