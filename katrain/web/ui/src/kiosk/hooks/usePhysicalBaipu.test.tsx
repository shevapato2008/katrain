import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { VisionSyncEvent } from './useVisionSync';
import type { BaipuStep } from '../../api/baipuApi';
const calls: string[] = [];
const slow = (ms: number) => new Promise(r => setTimeout(r, ms));
const { setup, detected, arm, monitor } = vi.hoisted(() => ({ setup: vi.fn(), detected: vi.fn(), arm: vi.fn(), monitor: vi.fn() }));
vi.mock('../../api', () => ({ API: {
  visionMonitor: monitor, visionSetupMode: setup, visionMoveDetection: arm,
  visionExpectedBoard: vi.fn(async () => { calls.push('expected'); }),
  visionPause: vi.fn(async () => { calls.push('pause'); }), visionDetectedBoard: detected,
} }));
const { ledPoints, ledClear } = vi.hoisted(() => ({ ledPoints: vi.fn(), ledClear: vi.fn() }));
vi.mock('../../api/ledApi', () => ({ LedAPI: { points: ledPoints, clear: ledClear } }));
import { usePhysicalBaipu, type PhysicalBaipuOptions } from './usePhysicalBaipu';
const empty = () => Array.from({ length: 3 }, () => Array(3).fill(0));
const step: BaipuStep = { kind: 'move', move_index: 0, property: 'B', row: 1, col: 1, color: 'B', removed: [], board_hash: 'h' };
const ev = (seq: number, type: string, data: Record<string, unknown> = {}) => ({ seq, type, data }) as VisionSyncEvent;
const settle = () => act(async () => { await slow(40); });
const setupId = () => setup.mock.calls.at(-1)![1] as string;
const base = (): PhysicalBaipuOptions => ({ enabled: true, visionConnected: true, syncEvents: [], identity: 'u1:g1', k: 0,
  board: empty(), step, next: { row: 1, col: 1, color: 1 }, paused: false, hintLeds: [], onMatched: vi.fn() });
beforeEach(() => {
  vi.clearAllMocks(); calls.length = 0; vi.useRealTimers();
  setup.mockImplementation(async () => { await slow(5); calls.push('setup'); });
  arm.mockImplementation(async () => { calls.push('arm'); });
  monitor.mockImplementation(async () => { calls.push('monitor'); });
  ledPoints.mockResolvedValue({ connected: true }); ledClear.mockResolvedValue({ connected: true });
});
describe('physical transaction IO', () => {
  it('waits for websocket and serializes clear before setup with a fresh ID', async () => {
    const opts = base();
    const { rerender } = renderHook(p => usePhysicalBaipu(p), { initialProps: { ...opts, visionConnected: false } });
    await settle(); expect(calls).toEqual([]);
    let finish!: (v: { connected: boolean }) => void;
    ledClear.mockImplementationOnce(() => new Promise(r => { finish = r; }));
    rerender(opts); await settle(); expect(calls).toEqual(['monitor', 'arm']);
    await act(async () => { finish({ connected: true }); }); await settle();
    expect(calls).toEqual(['monitor', 'arm', 'setup']);
    expect(setupId()).toContain(':0:entry:');
  });
  it('ignores stale setup completion and commits a placement only once', async () => {
    const opts = base(); const { rerender, result } = renderHook(p => usePhysicalBaipu(p), { initialProps: opts });
    await settle(); const id = setupId();
    rerender({ ...opts, syncEvents: [ev(0, 'setup_complete', { setup_id: 'old' })] }); await settle();
    expect(result.current.phase).toBe('setup');
    rerender({ ...opts, syncEvents: [ev(1, 'setup_complete', { setup_id: id }), ev(2, 'move_confirmed', { row: 1, col: 1, color: 1 }), ev(3, 'move_confirmed', { row: 1, col: 1, color: 1 })] });
    await settle(); expect(opts.onMatched).toHaveBeenCalledTimes(1);
  });
  it('final self-removal keeps k uncommitted until its new setup target is confirmed', async () => {
    const opts = { ...base(), step: { ...step, removed: [{ row: 1, col: 1 }] } };
    const { rerender, result } = renderHook(p => usePhysicalBaipu(p), { initialProps: opts });
    await settle(); const entryId = setupId();
    rerender({ ...opts, syncEvents: [ev(0, 'setup_complete', { setup_id: entryId }), ev(1, 'move_confirmed', { row: 1, col: 1, color: 1 })] });
    await settle(); expect(result.current.stage).toBe('post'); expect(opts.onMatched).not.toHaveBeenCalled();
    const postId = setupId(); expect(postId).not.toBe(entryId);
    rerender({ ...opts, syncEvents: [ev(2, 'setup_complete', { setup_id: entryId })] }); await settle();
    expect(opts.onMatched).not.toHaveBeenCalled();
    rerender({ ...opts, syncEvents: [ev(3, 'setup_complete', { setup_id: postId })] }); await settle();
    expect(opts.onMatched).toHaveBeenCalledTimes(1);
  });
  it('rechecks authoritative target without reading or adopting the observed board', async () => {
    const opts = base(); const { result } = renderHook(() => usePhysicalBaipu(opts)); await settle();
    const id = setupId(); act(() => result.current.recheck()); await settle();
    expect(setup.mock.calls.at(-1)![0]).toEqual(opts.board); expect(setupId()).not.toBe(id);
    expect(detected).not.toHaveBeenCalled();
  });
  it('pause cancels pending completion and resume establishes entry before unpausing', async () => {
    const opts = base(); const { rerender } = renderHook(p => usePhysicalBaipu(p), { initialProps: opts });
    await settle(); const id = setupId();
    rerender({ ...opts, paused: true, syncEvents: [ev(0, 'setup_complete', { setup_id: id }), ev(1, 'move_confirmed', { row: 1, col: 1, color: 1 })] });
    await settle(); expect(opts.onMatched).not.toHaveBeenCalled(); calls.length = 0;
    rerender(opts); await settle(); expect(calls).toEqual(['arm', 'setup', 'pause']);
    expect(setupId()).not.toBe(id);
  });
  it('identity change and unmount disarm, unpause, stop monitor and clear lights', async () => {
    const opts = base(); const { rerender, unmount } = renderHook(p => usePhysicalBaipu(p), { initialProps: opts });
    await settle(); const id = setupId(); rerender({ ...opts, identity: 'u2:g1' }); await settle();
    expect(setupId()).not.toBe(id); calls.length = 0; unmount(); await settle();
    expect(calls).toEqual(['arm', 'pause', 'monitor']); expect(ledClear).toHaveBeenCalled();
  });
});
