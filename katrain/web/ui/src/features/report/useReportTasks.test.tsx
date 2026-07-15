import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportQueueSummary, ReportTaskSummary } from '../../api/reportApi';

const mockList = vi.fn();
const mockSummary = vi.fn();
const mockCreate = vi.fn();
const mockRetry = vi.fn();

vi.mock('../../api/reportApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/reportApi')>();
  return {
    ...original,
    ReportsAPI: {
      ...original.ReportsAPI,
      list: (...args: unknown[]) => mockList(...args),
      summary: (...args: unknown[]) => mockSummary(...args),
      create: (...args: unknown[]) => mockCreate(...args),
      retry: (...args: unknown[]) => mockRetry(...args),
    },
  };
});

import { useReportTasks } from './useReportTasks';

const emptySummary: ReportQueueSummary = { pending: 0, running: 0, completed: 0, failed: 0 };

function task(overrides: Partial<ReportTaskSummary> = {}): ReportTaskSummary {
  return {
    id: 1,
    user_game_id: 'game-1',
    status: 'pending',
    report_type: 'normal',
    total_moves: 120,
    analyzed_moves: 0,
    requested_visits: 500,
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function settle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  mockList.mockResolvedValue([]);
  mockSummary.mockResolvedValue(emptySummary);
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe('useReportTasks', () => {
  it('loads from the current lifecycle when StrictMode replays mount effects', async () => {
    mockList.mockResolvedValue([task()]);
    mockSummary.mockResolvedValue({ ...emptySummary, pending: 1 });

    const { result } = renderHook(() => useReportTasks('token-a'), { wrapper: StrictMode });
    await settle();

    expect(mockList).toHaveBeenCalledTimes(2);
    expect(mockSummary).toHaveBeenCalledTimes(2);
    expect(result.current.tasks).toEqual([task()]);
    expect(result.current.queueSummary).toEqual({ ...emptySummary, pending: 1 });
    expect(result.current.loading).toBe(false);
  });

  it('loads the task list and queue summary in parallel on mount', async () => {
    const listRequest = deferred<ReportTaskSummary[]>();
    const summaryRequest = deferred<ReportQueueSummary>();
    mockList.mockReturnValue(listRequest.promise);
    mockSummary.mockReturnValue(summaryRequest.promise);

    const { result } = renderHook(() => useReportTasks('token-a'));
    const initialRefresh = result.current.refresh;

    expect(mockList).toHaveBeenCalledWith('token-a');
    expect(mockSummary).toHaveBeenCalledWith('token-a');
    expect(result.current.loading).toBe(true);

    listRequest.resolve([task()]);
    summaryRequest.resolve({ ...emptySummary, pending: 1 });
    await settle();

    expect(result.current.tasks).toEqual([task()]);
    expect(result.current.queueSummary).toEqual({ ...emptySummary, pending: 1 });
    expect(result.current.reportStatesByGame['game-1'].activeNormal).toEqual(task());
    expect(result.current.loading).toBe(false);
    expect(result.current.refresh).toBe(initialRefresh);
  });

  it('polls every 2000ms only while a task is pending or running, then stops after a terminal response', async () => {
    mockList
      .mockResolvedValueOnce([task({ status: 'pending' })])
      .mockResolvedValueOnce([task({ status: 'running' })])
      .mockResolvedValueOnce([task({ status: 'completed' })]);

    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    await act(async () => vi.advanceTimersByTimeAsync(1999));
    expect(mockList).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(mockList).toHaveBeenCalledTimes(2);
    expect(result.current.tasks[0].status).toBe('running');

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(mockList).toHaveBeenCalledTimes(3);
    expect(result.current.tasks[0].status).toBe('completed');

    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(mockList).toHaveBeenCalledTimes(3);
  });

  it('does not poll when all tasks are terminal', async () => {
    mockList.mockResolvedValue([task({ status: 'failed' })]);
    renderHook(() => useReportTasks('token-a'));
    await settle();

    await act(async () => vi.advanceTimersByTimeAsync(6000));

    expect(mockList).toHaveBeenCalledTimes(1);
    expect(mockSummary).toHaveBeenCalledTimes(1);
  });

  it('serializes slow polling and schedules the next poll only after the prior refresh settles', async () => {
    const slowList = deferred<ReportTaskSummary[]>();
    const slowSummary = deferred<ReportQueueSummary>();
    mockList
      .mockResolvedValueOnce([task({ status: 'pending' })])
      .mockReturnValueOnce(slowList.promise)
      .mockResolvedValueOnce([task({ status: 'completed' })]);
    mockSummary
      .mockResolvedValueOnce({ ...emptySummary, pending: 1 })
      .mockReturnValueOnce(slowSummary.promise)
      .mockResolvedValueOnce({ ...emptySummary, completed: 1 });
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(mockList).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(mockList).toHaveBeenCalledTimes(2);

    slowList.resolve([task({ status: 'running' })]);
    slowSummary.resolve({ ...emptySummary, running: 1 });
    await settle();
    expect(result.current.tasks[0].status).toBe('running');

    await act(async () => vi.advanceTimersByTimeAsync(1999));
    expect(mockList).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(mockList).toHaveBeenCalledTimes(3);
  });

  it('inserts unique decreasing optimistic tasks before POST resolves and reconciles each server response', async () => {
    const historical = task({ id: 9, status: 'completed' });
    const firstCreate = deferred<ReportTaskSummary>();
    const secondCreate = deferred<ReportTaskSummary>();
    mockList.mockResolvedValue([historical]);
    mockCreate.mockReturnValueOnce(firstCreate.promise).mockReturnValueOnce(secondCreate.promise);

    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    let firstPromise!: Promise<ReportTaskSummary>;
    let secondPromise!: Promise<ReportTaskSummary>;
    act(() => {
      firstPromise = result.current.createReport({ userGameId: 'game-1', reportType: 'normal', totalMoves: 120 });
      secondPromise = result.current.createReport({ userGameId: 'game-1', reportType: 'normal', totalMoves: 120 });
    });

    const optimisticTasks = result.current.tasks.filter((candidate) => candidate.id < 0);
    expect(optimisticTasks).toHaveLength(2);
    expect(optimisticTasks[0].id).toBeLessThan(optimisticTasks[1].id);
    expect(result.current.reportStatesByGame['game-1'].activeNormal?.id).toBe(optimisticTasks[0].id);
    expect(mockCreate).toHaveBeenNthCalledWith(1, 'token-a', {
      user_game_id: 'game-1',
      report_type: 'normal',
    });

    firstCreate.resolve(task({ id: 10, status: 'completed' }));
    await act(async () => { await firstPromise; });
    expect(result.current.tasks.map(({ id }) => id)).toContain(10);
    expect(result.current.tasks.filter((candidate) => candidate.id < 0)).toHaveLength(1);

    secondCreate.resolve(task({ id: 11, status: 'pending' }));
    await act(async () => { await secondPromise; });
    expect(result.current.tasks.filter((candidate) => candidate.id < 0)).toHaveLength(0);
    expect(result.current.tasks.map(({ id }) => id)).toEqual(expect.arrayContaining([9, 10, 11]));
  });

  it('keeps one same-key optimistic placeholder when polling observes only one real task', async () => {
    const historical = task({ id: 9, status: 'completed' });
    const firstCreate = deferred<ReportTaskSummary>();
    const secondCreate = deferred<ReportTaskSummary>();
    mockList
      .mockResolvedValueOnce([historical])
      .mockResolvedValueOnce([historical, task({ id: 10, status: 'running' })]);
    mockCreate.mockReturnValueOnce(firstCreate.promise).mockReturnValueOnce(secondCreate.promise);
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    act(() => {
      void result.current.createReport({ userGameId: 'game-1', totalMoves: 120, force: true });
      void result.current.createReport({ userGameId: 'game-1', totalMoves: 120, force: true });
    });
    await act(async () => vi.advanceTimersByTimeAsync(2000));

    expect(result.current.tasks.filter((candidate) => candidate.id < 0)).toHaveLength(1);
    expect(mockCreate).toHaveBeenNthCalledWith(2, 'token-a', {
      user_game_id: 'game-1',
      report_type: 'normal',
      force: true,
    });
  });

  it('retries a task and refreshes both task endpoints afterward', async () => {
    mockList.mockResolvedValueOnce([task({ id: 4, status: 'failed' })]).mockResolvedValueOnce([
      task({ id: 4, status: 'pending' }),
    ]);
    mockRetry.mockResolvedValue(task({ id: 4, status: 'pending' }));
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    await act(async () => {
      await result.current.retryReport(4);
    });

    expect(mockRetry).toHaveBeenCalledWith('token-a', 4);
    expect(mockList).toHaveBeenCalledTimes(2);
    expect(mockSummary).toHaveBeenCalledTimes(2);
    expect(result.current.tasks[0].status).toBe('pending');
  });

  it('starts a fresh snapshot after retry when an older refresh is already in flight', async () => {
    const staleList = deferred<ReportTaskSummary[]>();
    const staleSummary = deferred<ReportQueueSummary>();
    const retryRequest = deferred<ReportTaskSummary>();
    const failedTask = task({ id: 4, status: 'failed' });
    const retriedTask = task({ id: 4, status: 'pending' });
    mockList
      .mockResolvedValueOnce([failedTask])
      .mockReturnValueOnce(staleList.promise)
      .mockResolvedValueOnce([retriedTask]);
    mockSummary
      .mockResolvedValueOnce({ ...emptySummary, failed: 1 })
      .mockReturnValueOnce(staleSummary.promise)
      .mockResolvedValueOnce({ ...emptySummary, pending: 1 });
    mockRetry.mockReturnValue(retryRequest.promise);
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    const staleRefreshPromise = result.current.refresh();
    let retryPromise!: Promise<ReportTaskSummary>;
    act(() => {
      retryPromise = result.current.retryReport(4);
    });
    retryRequest.resolve(retriedTask);
    await settle();
    expect(mockList).toHaveBeenCalledTimes(2);

    staleList.resolve([failedTask]);
    staleSummary.resolve({ ...emptySummary, failed: 1 });
    await act(async () => {
      await Promise.all([staleRefreshPromise, retryPromise]);
    });

    expect(mockList).toHaveBeenCalledTimes(3);
    expect(mockSummary).toHaveBeenCalledTimes(3);
    expect(result.current.tasks[0].status).toBe('pending');
    expect(result.current.queueSummary).toEqual({ ...emptySummary, pending: 1 });
  });

  it('retains prior data on a transient refresh failure and recovers on the next refresh', async () => {
    const original = task({ id: 3, status: 'completed' });
    const recovered = task({ id: 5, status: 'failed' });
    mockList.mockResolvedValueOnce([original]);
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    mockList.mockRejectedValueOnce(new Error('temporary outage'));
    await act(async () => { await result.current.refresh(); });

    expect(result.current.tasks).toEqual([original]);
    expect(result.current.queueSummary).toEqual(emptySummary);
    expect(result.current.error).toBe('temporary outage');

    mockList.mockResolvedValueOnce([recovered]);
    await act(async () => { await result.current.refresh(); });

    expect(result.current.tasks).toEqual([recovered]);
    expect(result.current.error).toBeNull();
  });

  it('clears a visible error without changing the current task snapshot', async () => {
    const original = task({ id: 3, status: 'completed' });
    mockList.mockResolvedValueOnce([original]);
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    mockList.mockRejectedValueOnce(new Error('temporary outage'));
    await act(async () => { await result.current.refresh(); });
    expect(result.current.error).toBe('temporary outage');

    act(() => result.current.clearError());

    expect(result.current.error).toBeNull();
    expect(result.current.tasks).toEqual([original]);
    expect(result.current.queueSummary).toEqual(emptySummary);
  });

  it('uses the translated fallback for non-Error failures and recovers from a failed create', async () => {
    const createRequest = deferred<ReportTaskSummary>();
    mockCreate.mockReturnValue(createRequest.promise);
    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    let createPromise!: Promise<ReportTaskSummary>;
    act(() => {
      createPromise = result.current.createReport({ userGameId: 'game-2', reportType: 'deep', totalMoves: 80 });
    });
    expect(result.current.tasks.some((candidate) => candidate.id < 0)).toBe(true);

    createRequest.reject('no details');
    await act(async () => {
      await expect(createPromise).rejects.toBe('no details');
    });

    expect(result.current.tasks.some((candidate) => candidate.id < 0)).toBe(false);
    expect(result.current.error).toBe('Failed to create report task');
  });

  it('cleans up polling and ignores stale responses when the token changes or the hook unmounts', async () => {
    const staleList = deferred<ReportTaskSummary[]>();
    const staleSummary = deferred<ReportQueueSummary>();
    mockList.mockReturnValueOnce(staleList.promise).mockResolvedValueOnce([task({ id: 22, user_game_id: 'game-b' })]);
    mockSummary.mockReturnValueOnce(staleSummary.promise).mockResolvedValueOnce({ ...emptySummary, pending: 1 });

    const { result, rerender, unmount } = renderHook(({ token }) => useReportTasks(token), {
      initialProps: { token: 'token-a' as string | null },
    });

    rerender({ token: 'token-b' });
    await settle();
    expect(mockList).toHaveBeenLastCalledWith('token-b');
    expect(result.current.tasks[0].id).toBe(22);

    staleList.resolve([task({ id: 1, user_game_id: 'stale-game' })]);
    staleSummary.resolve({ ...emptySummary, pending: 1 });
    await settle();
    expect(result.current.tasks[0].id).toBe(22);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(mockList).toHaveBeenCalledTimes(2);
  });

  it('does not apply an old-token create response after the token changes', async () => {
    const createRequest = deferred<ReportTaskSummary>();
    mockCreate.mockReturnValue(createRequest.promise);
    const { result, rerender } = renderHook(({ token }) => useReportTasks(token), {
      initialProps: { token: 'token-a' as string | null },
    });
    await settle();

    let createPromise!: Promise<ReportTaskSummary>;
    act(() => {
      createPromise = result.current.createReport({ userGameId: 'game-a', totalMoves: 20 });
    });
    rerender({ token: 'token-b' });
    await settle();

    createRequest.resolve(task({ id: 30, user_game_id: 'game-a' }));
    await act(async () => { await createPromise; });

    expect(result.current.tasks).toEqual([]);
  });

  it('does not let callbacks captured for an old token make requests after rerender', async () => {
    const { result, rerender } = renderHook(({ token }) => useReportTasks(token), {
      initialProps: { token: 'token-a' as string | null },
    });
    await settle();
    const oldRefresh = result.current.refresh;
    const oldCreate = result.current.createReport;

    rerender({ token: 'token-b' });
    await settle();
    expect(mockList).toHaveBeenCalledTimes(2);

    await act(async () => { await oldRefresh(); });
    await act(async () => {
      await expect(oldCreate({ userGameId: 'stale-game', totalMoves: 10 })).rejects.toThrow();
    });

    expect(mockList).toHaveBeenCalledTimes(2);
    expect(mockCreate).not.toHaveBeenCalled();
    expect(result.current.tasks).toEqual([]);
  });

  it('merges a created task with unrelated task and summary updates from an in-flight refresh', async () => {
    const historical = task({ id: 9, status: 'completed' });
    const createRequest = deferred<ReportTaskSummary>();
    const staleList = deferred<ReportTaskSummary[]>();
    const staleSummary = deferred<ReportQueueSummary>();
    mockList.mockResolvedValueOnce([historical]).mockReturnValueOnce(staleList.promise);
    mockSummary.mockResolvedValueOnce(emptySummary).mockReturnValueOnce(staleSummary.promise);
    mockCreate.mockReturnValue(createRequest.promise);

    const { result } = renderHook(() => useReportTasks('token-a'));
    await settle();

    let createPromise!: Promise<ReportTaskSummary>;
    act(() => {
      createPromise = result.current.createReport({ userGameId: 'game-1', totalMoves: 120 });
    });
    const refreshPromise = result.current.refresh();

    createRequest.resolve(task({ id: 10, status: 'pending' }));
    await settle();
    const unrelated = task({ id: 20, user_game_id: 'game-2', status: 'failed' });
    staleList.resolve([historical, unrelated]);
    staleSummary.resolve({ ...emptySummary, failed: 1 });
    await act(async () => { await Promise.all([createPromise, refreshPromise]); });

    expect(result.current.tasks.map(({ id }) => id)).toContain(10);
    expect(result.current.tasks.map(({ id }) => id)).toContain(20);
    expect(result.current.queueSummary).toEqual({ ...emptySummary, failed: 1 });
  });
});
