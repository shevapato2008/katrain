import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useKifuAnalysis } from './useKifuAnalysis';

const getAnalysis = vi.hoisted(() => vi.fn());
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAnalysis } }));
afterEach(() => { vi.useRealTimers(); getAnalysis.mockReset(); });

it('downloads a completed report once', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValue({ status: 'completed', moves: [] });
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.detail?.status).toBe('completed');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(1);
});

it('polls a running report, stops when complete, and ignores a departed game', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValueOnce({ status: 'running', moves: [] })
    .mockResolvedValueOnce({ status: 'completed', moves: [] });
  const { result, rerender } = renderHook(({ id }) => useKifuAnalysis(id), { initialProps: { id: 7 as number | null } });
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(result.current.detail?.status).toBe('completed');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(2);
  rerender({ id: null });
  expect(result.current.detail).toBeNull();
});
