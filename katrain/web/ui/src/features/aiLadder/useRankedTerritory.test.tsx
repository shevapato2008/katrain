import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRankedTerritory } from './useRankedTerritory';

const { quota, request } = vi.hoisted(() => ({ quota: vi.fn(), request: vi.fn() }));
vi.mock('./api', () => ({ getAiLadderTerritoryQuota: quota, requestAiLadderTerritory: request }));

beforeEach(() => {
  quota.mockReset().mockResolvedValue({ remaining: 3, in_flight: false });
  request.mockReset();
});

describe('ranked territory', () => {
  const answer = (remaining = 0) => ({ remaining, move_count: 5, ownership: Array(361).fill(1), black_area: 78, white_area: 66 });

  it('dismisses and reopens a cached territory result with zero remaining uses', async () => {
    request.mockResolvedValue(answer());
    const { result } = renderHook(() => useRankedTerritory('s1', true, 'n5', 5));
    await waitFor(() => expect(result.current.remaining).toBe(3));
    await act(async () => { await result.current.request(); });
    expect(result.current.visible).toBe(true);
    act(() => result.current.dismiss());
    expect(result.current.overlay).toBeNull();
    expect(result.current.result).toEqual(answer());
    expect(result.current.disabled).toBe(false);
    await act(async () => { await result.current.request(); });
    expect(result.current.visible).toBe(true);
    expect(result.current.overlay?.kind).toBe('area');
    await act(async () => { await result.current.request(); });
    expect(result.current.visible).toBe(false);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it('caches a late territory result after pending dismissal without reopening', async () => {
    let resolve!: (value: unknown) => void;
    request.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { result } = renderHook(() => useRankedTerritory('s1', true, 'n5', 5));
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    expect(result.current.visible).toBe(true);
    act(() => result.current.dismiss());
    await act(async () => { resolve(answer()); });
    expect(result.current.result).toEqual(answer());
    expect(result.current.remaining).toBe(0);
    expect(result.current.visible).toBe(false);
    expect(result.current.overlay).toBeNull();
    await act(async () => { await result.current.request(); });
    expect(result.current.visible).toBe(true);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it('can reopen pending territory without another POST', async () => {
    let resolve!: (value: unknown) => void;
    request.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { result } = renderHook(() => useRankedTerritory('s1', true, 'n5', 5));
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    act(() => result.current.dismiss());
    act(() => { void result.current.request(); });
    expect(result.current.visible).toBe(true);
    expect(result.current.phase).toBe('loading');
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(answer()); });
  });

  it('keeps a same-game territory request single-flight across an enable cycle', async () => {
    let resolve!: (value: unknown) => void;
    request.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { result, rerender } = renderHook(({ enabled }) => useRankedTerritory('s1', enabled, 'n5', 5), { initialProps: { enabled: true } });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    rerender({ enabled: false });
    rerender({ enabled: true });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(answer(2)); });
    expect(result.current.visible).toBe(false);
    expect(result.current.result).toBeUndefined();
    expect(result.current.remaining).toBe(2);
  });

  it.each(['account', 'game', 'moves', 'enable'] as const)('invalidates territory when %s scope changes, even if revisited', async (change) => {
    let resolve!: (value: unknown) => void;
    request.mockReturnValue(new Promise((r) => { resolve = r; }));
    const initial = { enabled: true, accountKey: 'a1', gameId: 'g1', positionIdentity: 'B:D4,W:Q16' };
    const { result, rerender } = renderHook((scope) => useRankedTerritory('s1', scope.enabled, 'n5', 5, scope), { initialProps: initial });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    rerender({ ...initial, ...(change === 'enable' ? { enabled: false }
      : change === 'account' ? { accountKey: 'a2' }
      : change === 'game' ? { gameId: 'g2' } : { positionIdentity: 'B:Q4,W:D16' }) });
    rerender(initial);
    await act(async () => { resolve(answer(1)); });
    expect(result.current.visible).toBe(false);
    expect(result.current.result).toBeUndefined();
    expect(result.current.overlay).toBeNull();
  });

  it.each(['success', 'failure'] as const)('does not let an old session %s overwrite current quota or error', async (outcome) => {
    let resolve!: (value: unknown) => void;
    let reject!: (reason: unknown) => void;
    request.mockReturnValue(new Promise((r, j) => { resolve = r; reject = j; }));
    quota.mockImplementation((session: string) => Promise.resolve({ remaining: session === 's1' ? 3 : 1, in_flight: false }));
    const { result, rerender } = renderHook(({ session }) => useRankedTerritory(session, true, 'n5', 5), { initialProps: { session: 's1' } });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    rerender({ session: 's2' });
    await waitFor(() => expect(result.current.remaining).toBe(1));
    await act(async () => { if (outcome === 'success') resolve(answer(0)); else reject(new Error('old session')); });
    expect(result.current.remaining).toBe(1);
    expect(result.current.phase).toBe('idle');
    expect(result.current.visible).toBe(false);
    expect(quota).toHaveBeenCalledTimes(2);
  });

  it('shows a result for the current position and clears it after a move', async () => {
    request.mockResolvedValue({ remaining: 2, move_count: 5, ownership: Array(361).fill(1), black_area: 78, white_area: 66 });
    const { result, rerender } = renderHook(({ node }) => useRankedTerritory('s1', true, node, 5), { initialProps: { node: 'n5' } });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    await act(async () => { await result.current.request(); });
    expect(result.current.phase).toBe('result');
    expect(result.current.overlay?.ownership).toHaveLength(361);
    expect(result.current.overlay?.ownership[0]).toEqual({ col: 0, row: 18, value: 1 });
    expect(result.current.overlay?.ownership[360]).toEqual({ col: 18, row: 0, value: 1 });
    rerender({ node: 'n6' });
    expect(result.current.overlay).toBeNull();
    expect(result.current.phase).toBe('idle');
  });

  it('rejects a result that arrives after the board has advanced', async () => {
    let resolve!: (value: unknown) => void;
    request.mockReturnValue(new Promise((r) => { resolve = r; }));
    const { result, rerender } = renderHook(({ node, count }) => useRankedTerritory('s1', true, node, count), { initialProps: { node: 'n5', count: 5 } });
    await waitFor(() => expect(result.current.remaining).toBe(3));
    act(() => { void result.current.request(); });
    rerender({ node: 'n6', count: 6 });
    await act(async () => { resolve({ remaining: 2, move_count: 5, ownership: Array(361).fill(1), black_area: 78, white_area: 66 }); });
    expect(result.current.overlay).toBeNull();
    expect(result.current.remaining).toBe(2);
  });

  it('reuses the request ID after failure and does not decrement locally', async () => {
    quota.mockResolvedValueOnce({ remaining: 3, in_flight: false }).mockResolvedValueOnce({ remaining: 2, in_flight: false });
    request.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ remaining: 2, move_count: 5, ownership: Array(361).fill(0), black_area: 1, white_area: 2 });
    const { result } = renderHook(() => useRankedTerritory('s1', true, 'n5', 5));
    await waitFor(() => expect(result.current.remaining).toBe(3));
    await act(async () => { await result.current.request(); });
    expect(result.current.phase).toBe('error');
    await waitFor(() => expect(result.current.remaining).toBe(2));
    await act(async () => { await result.current.request(); });
    expect(request.mock.calls[1][1]).toBe(request.mock.calls[0][1]);
    expect(result.current.remaining).toBe(2);
  });

  it('exits remote loading if a quota poll fails', async () => {
    quota.mockResolvedValueOnce({ remaining: 2, in_flight: true }).mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useRankedTerritory('s1', true, 'n5', 5));
    await waitFor(() => expect(result.current.phase).toBe('loading'));
    await waitFor(() => expect(result.current.phase).toBe('error'), { timeout: 3000 });
    expect(result.current.disabled).toBe(false);
  });
});
