import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BaipuStep } from '../../api/baipuApi';

/**
 * 摆谱 AI 支招:分析**谱上**第 k 手之后的局面(不是摄像头看到的),走本机 KataGo 的 quick-analyze。
 * 量四件事:请求只带前 k 步且带 token、走白时换视角、候选点转成白灯、三种收起。
 */

const { quickAnalyze } = vi.hoisted(() => ({ quickAnalyze: vi.fn() }));
vi.mock('../../api', () => ({ API: { quickAnalyze } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 't1' }) }));

import { buildHintRequest, useBaipuHint } from './useBaipuHint';

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

beforeEach(() => { vi.useRealTimers(); quickAnalyze.mockReset(); quickAnalyze.mockResolvedValue(RESP); });

describe('buildHintRequest', () => {
  it('只带前 k 步;setup 进 initial_stones;pass 记 pass;贴目与规则取谱', () => {
    const steps = [setup('B', 15, 3), mv('B', 3, 15), pass('W'), mv('B', 2, 2)];
    expect(buildHintRequest(steps, 3, 19, { player_black: '', player_white: '', handicap: 0, komi: 6.5, ruleset: 'japanese' }))
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
