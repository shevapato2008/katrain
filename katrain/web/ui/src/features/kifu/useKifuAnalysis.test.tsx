import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useKifuAnalysis } from './useKifuAnalysis';
import { kifuAnalysisStatus } from './kifuAnalysisStatus';

const getAnalysis = vi.hoisted(() => vi.fn());
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAnalysis } }));
afterEach(() => { vi.useRealTimers(); getAnalysis.mockReset(); });

it('withholds unverified rows and treats unresolved rules as a terminal, honest status', async () => {
  vi.useFakeTimers();
  getAnalysis.mockResolvedValue({ status: 'rules_unresolved', parameters_verified: false, analysis_parameters: null,
    parameter_error: { code: 'rules_missing', message: 'SGF has no RU' }, moves: [{ move_number: 1, winrate: .8, score_lead: 4 }] });
  const { result } = renderHook(() => useKifuAnalysis(7));
  await act(async () => {});
  expect(result.current.analysisByMove).toEqual({});
  expect(kifuAnalysisStatus(result.current.detail, false, (_key, fallback) => fallback)).toBe('规则待核验');
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(getAnalysis).toHaveBeenCalledTimes(1);
});

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
