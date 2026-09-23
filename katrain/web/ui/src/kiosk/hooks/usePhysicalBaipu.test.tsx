import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { VisionSyncEvent } from './useVisionSync';

/**
 * 摆谱识别的 IO 层:命令**串行**执行(识别层约束 5)、生命周期清场(约束 6)、事件消费、卡住计时。
 * 状态机规则本身由 `physicalBaipuMachine.test.ts` 管,这里只量「命令真的按那个顺序打到接口上」。
 *
 * 变异记录(2026-09-23):把命令队列改回 fire-and-forget(`commands.forEach(run)`)⇒
 * 「试下结束」那条红 —— mock 的 setupMode 故意慢 10 ms,乱序才看得见(不慢的话两种写法记录顺序相同,测不出)。
 */

const calls: string[] = [];
const slow = (ms: number) => new Promise((r) => setTimeout(r, ms));
vi.mock('../../api', () => {
  const rec = (name: string, delay = 0) => vi.fn(async () => { if (delay) await slow(delay); calls.push(name); });
  return {
    API: {
      visionMonitor: rec('monitor'),
      visionSetupMode: rec('setup', 10),
      visionExpectedBoard: rec('expected'),
      visionMoveDetection: rec('arm'),
      visionPause: rec('pause'),
      visionDetectedBoard: vi.fn(async () => ({ board: Array.from({ length: 19 }, () => Array(19).fill(0)) })),
    },
  };
});
const { ledPoints, ledClear } = vi.hoisted(() => ({
  ledPoints: vi.fn(async () => ({ ok: true, connected: true })),
  ledClear: vi.fn(async () => ({ ok: true, connected: true })),
}));
vi.mock('../../api/ledApi', () => ({ LedAPI: { points: ledPoints, clear: ledClear } }));

import { usePhysicalBaipu, type PhysicalBaipuOptions } from './usePhysicalBaipu';

const empty = () => Array.from({ length: 19 }, () => Array<number>(19).fill(0));
const settle = () => act(async () => { await slow(60); });
const ev = (seq: number, type: string, data: Record<string, unknown> = {}) => ({ seq, type, data }) as VisionSyncEvent;
const base: PhysicalBaipuOptions = {
  enabled: true, visionConnected: true, syncEvents: [], k: 0, board: empty(),
  next: { row: 3, col: 15, color: 1 }, paused: false, hintLeds: [], onMatched: () => {},
};

beforeEach(() => { calls.length = 0; vi.useRealTimers(); ledPoints.mockClear(); ledClear.mockClear(); });

describe('usePhysicalBaipu', () => {
  it('进场:先开监视模式,再撤臂、setup —— 一次都不许倒过来', async () => {
    renderHook(() => usePhysicalBaipu(base));
    await settle();
    expect(calls).toEqual(['monitor', 'arm', 'setup']);
  });

  it('WS 没连上之前什么都不发(否则空盘的 setup_complete 会丢)', async () => {
    renderHook(() => usePhysicalBaipu({ ...base, visionConnected: false }));
    await settle();
    expect(calls).toEqual([]);
  });

  it('setup_complete 之后推期望盘面并布臂;认到正确的下一手 → onMatched 一次', async () => {
    const onMatched = vi.fn();
    const { rerender } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: { ...base, onMatched } });
    await settle();
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete')] });
    await settle();
    expect(calls.slice(3)).toEqual(['arm', 'expected', 'arm']);
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete'), ev(1, 'move_confirmed', { row: 3, col: 15, color: 1 })] });
    await settle();
    expect(onMatched).toHaveBeenCalledTimes(1);
  });

  it('放错(颜色不对)→ 不调 onMatched,回到 setup', async () => {
    const onMatched = vi.fn();
    const { rerender, result } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: { ...base, onMatched } });
    await settle();
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete'), ev(1, 'move_confirmed', { row: 3, col: 15, color: 2 })] });
    await settle();
    expect(onMatched).not.toHaveBeenCalled();
    expect(result.current).toMatchObject({ phase: 'setup', reason: 'wrong', wrong: [3, 15] });
  });

  it('推进一手(无提子)→ 直接 AWAIT 新盘面,不走 setup', async () => {
    const onMatched = vi.fn();
    const { rerender, result } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: { ...base, onMatched } });
    const evs = [ev(0, 'setup_complete'), ev(1, 'move_confirmed', { row: 3, col: 15, color: 1 })];
    rerender({ ...base, onMatched, syncEvents: evs });
    await settle();
    calls.length = 0;
    const b1 = empty(); b1[3][15] = 1;
    rerender({ ...base, onMatched, syncEvents: evs, k: 1, board: b1, next: { row: 15, col: 3, color: 2 } });
    await settle();
    expect(result.current.phase).toBe('await');
    expect(calls).toEqual(['arm', 'expected', 'arm']);
  });

  it('撤回(k 变小)→ setup(undo)', async () => {
    const b1 = empty(); b1[3][15] = 1;
    const { rerender, result } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p),
      { initialProps: { ...base, k: 1, board: b1, next: { row: 15, col: 3, color: 2 } } });
    await settle();
    rerender({ ...base, k: 0, board: empty() });
    await settle();
    expect(result.current).toMatchObject({ phase: 'setup', reason: 'undo' });
  });

  it('setup 没对上时下一步是虚手、页面自己跳过 → 仍留在 setup(被提的子还没拿走)', async () => {
    const { rerender, result } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: base });
    await settle();
    rerender({ ...base, k: 1, next: null });
    await settle();
    expect(result.current).toMatchObject({ phase: 'setup', reason: 'entry' });
  });

  it('试下结束:撤臂 → setupMode → 解除暂停,依次 await(setupMode 慢也不许被解除暂停抢先)', async () => {
    const { rerender } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: base });
    await settle();
    rerender({ ...base, paused: true });
    await settle();
    calls.length = 0;
    rerender({ ...base, paused: false });
    await settle();
    expect(calls).toEqual(['arm', 'setup', 'pause']);
  });

  it('暂停时的事件一律跳过', async () => {
    const onMatched = vi.fn();
    const { rerender } = renderHook((p: PhysicalBaipuOptions) => usePhysicalBaipu(p), { initialProps: { ...base, onMatched } });
    rerender({ ...base, onMatched, syncEvents: [ev(0, 'setup_complete')] });
    await settle();
    rerender({ ...base, onMatched, paused: true, syncEvents: [ev(0, 'setup_complete'), ev(1, 'move_confirmed', { row: 3, col: 15, color: 1 })] });
    await settle();
    expect(onMatched).not.toHaveBeenCalled();
  });

  it('卸载清场:撤臂、解除暂停、关监视,灯全灭', async () => {
    const { unmount } = renderHook(() => usePhysicalBaipu(base));
    await settle();
    calls.length = 0;
    ledClear.mockClear();
    unmount();
    await settle();
    expect(calls).toEqual(['arm', 'pause', 'monitor']);
    expect(ledClear).toHaveBeenCalled();
  });

  it('setup 10 秒没对上 → stuck;adopt 按摄像头现在看到的盘面重新 setup', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePhysicalBaipu(base));
    await act(async () => { await vi.advanceTimersByTimeAsync(9_900); });
    expect(result.current.stuck).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    expect(result.current.stuck).toBe(true);
    await act(async () => { result.current.adopt(); await vi.advanceTimersByTimeAsync(50); });
    expect(result.current).toMatchObject({ phase: 'setup', reason: 'adopt', stuck: false });
  });
});
