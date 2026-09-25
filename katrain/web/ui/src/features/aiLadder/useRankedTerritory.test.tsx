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
