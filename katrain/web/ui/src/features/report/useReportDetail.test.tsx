import { act, renderHook } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskMove, ReportTaskSummary } from '../../api/reportApi';
import type { UserGameDetail } from '../../api/userGamesApi';

const mockReportGet = vi.fn();
const mockReportGetMoves = vi.fn();
const mockUserGameGet = vi.fn();

vi.mock('../../api/reportApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/reportApi')>();
  return {
    ...original,
    ReportsAPI: {
      ...original.ReportsAPI,
      get: (...args: unknown[]) => mockReportGet(...args),
      getMoves: (...args: unknown[]) => mockReportGetMoves(...args),
    },
  };
});

vi.mock('../../api/userGamesApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/userGamesApi')>();
  return {
    ...original,
    UserGamesAPI: {
      ...original.UserGamesAPI,
      get: (...args: unknown[]) => mockUserGameGet(...args),
    },
  };
});

import { useReportDetail } from './useReportDetail';

function task(overrides: Partial<ReportTaskSummary> = {}): ReportTaskSummary {
  return {
    id: 7,
    user_game_id: 'game-1',
    status: 'completed',
    report_type: 'normal',
    total_moves: 3,
    analyzed_moves: 2,
    requested_visits: 500,
    started_at: null,
    completed_at: null,
    ...overrides,
  };
}

function move(moveNumber: number, overrides: Partial<ReportTaskMove> = {}): ReportTaskMove {
  return {
    id: moveNumber,
    task_id: 7,
    move_number: moveNumber,
    status: 'success',
    winrate: 0.5 + moveNumber / 100,
    score_lead: moveNumber,
    visits: 500,
    top_moves: [],
    ownership: null,
    actual_move: moveNumber % 2 ? 'Q16' : 'D4',
    actual_player: moveNumber % 2 ? 'B' : 'W',
    delta_score: 0,
    delta_winrate: 0,
    ...overrides,
  };
}

function game(id = 'game-1'): UserGameDetail {
  return {
    id,
    user_id: 1,
    title: 'Report game',
    player_black: 'Black',
    player_white: 'White',
    black_rank: null,
    white_rank: null,
    result: null,
    board_size: 19,
    rules: 'chinese',
    komi: 7.5,
    move_count: 3,
    source: 'import',
    category: 'game',
    game_type: null,
    event: null,
    round_name: null,
    game_date: null,
    created_at: null,
    updated_at: null,
    sgf_content: '(;FF[4]SZ[19];B[pd];W[dp];B[qq])',
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
  mockReportGet.mockResolvedValue(task());
  mockReportGetMoves.mockResolvedValue([move(1), move(2)]);
  mockUserGameGet.mockResolvedValue(game());
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe('useReportDetail', () => {
  /**
   * 回归钉子：屏 20（报告详情）的主加载。严格盒端 token 恒为 null，
   * 原来的 `!token` 闸让它在盒上一次都不跑 —— 报告生成得出来，详情页却是空的。
   * 变异验证：把 refresh 里的 `!enabled` 改回 `!token`，这条立刻红。
   */
  it('still loads the report when the credential is null but the caller says authenticated', async () => {
    const { result } = renderHook(() => useReportDetail(null, '7', true));
    await settle();

    expect(mockReportGet).toHaveBeenCalledWith(null, 7);
    expect(result.current.error).toBeNull();
  });

  it('does not load when the caller says not authenticated, even with a credential', async () => {
    renderHook(() => useReportDetail('token-a', '7', false));
    await settle();

    expect(mockReportGet).not.toHaveBeenCalled();
  });

  it('rejects a malformed task ID without making requests', async () => {
    const { result } = renderHook(() => useReportDetail('token-a', '7oops', true));
    await settle();

    expect(mockReportGet).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Invalid report task ID');
    expect(result.current.errorKind).toBe('not_found');
    expect(result.current.task).toBeNull();
  });

  // N24:盒上云端连不上时本机回 503。屏 20 要据此说「连不上」,不说「未找到」,也不印原文。
  it('读失败时 errorKind 给出是哪一类(503 ⇒ offline),error 原文照旧', async () => {
    const body = '{"detail":"Remote report service unavailable"}';
    mockReportGet.mockRejectedValueOnce(
      Object.assign(new Error(`Request failed 503: ${body}`), { status: 503, body }),
    );
    const { result } = renderHook(() => useReportDetail(null, '7', true));
    await settle();

    expect(result.current.game).toBeNull();
    expect(result.current.error).toBe(`Request failed 503: ${body}`);
    expect(result.current.errorKind).toBe('offline');
  });

  // 报告接口不退缓存,上游 404 原码透传 ⇒ 那是云端说「没有这份报告」。
  // 对局那一路(GET /user-games/{id})盒上云端失败会退本机缓存,缓存没有也 404 ⇒ 证明不了「没有」,降为 other。
  // 变异验证:把对局那一路也改用 requestFailureKind,第二段红。
  it('报告 404 ⇒ not_found;对局那一路 404 ⇒ other(可能只是本机缓存里没有)', async () => {
    const notFound = (detail: string) => Object.assign(
      new Error(`Request failed 404: {"detail":"${detail}"}`), { status: 404, body: `{"detail":"${detail}"}` },
    );
    mockReportGet.mockRejectedValueOnce(notFound('Report task not found'));
    const first = renderHook(() => useReportDetail(null, '7', true));
    await settle();
    expect(first.result.current.errorKind).toBe('not_found');
    first.unmount();

    mockUserGameGet.mockRejectedValueOnce(notFound('Game not found'));
    const second = renderHook(() => useReportDetail(null, '7', true));
    await settle();
    expect(second.result.current.game).toBeNull();
    expect(second.result.current.errorKind).toBe('other');
  });

  it('looks up the task before fetching moves and the corresponding game in parallel', async () => {
    const taskRequest = deferred<ReportTaskSummary>();
    const movesRequest = deferred<ReportTaskMove[]>();
    const gameRequest = deferred<UserGameDetail>();
    mockReportGet.mockReturnValue(taskRequest.promise);
    mockReportGetMoves.mockReturnValue(movesRequest.promise);
    mockUserGameGet.mockReturnValue(gameRequest.promise);

    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    const initialRefresh = result.current.refresh;

    expect(mockReportGet).toHaveBeenCalledWith('token-a', 7);
    expect(mockReportGetMoves).not.toHaveBeenCalled();
    expect(mockUserGameGet).not.toHaveBeenCalled();
    taskRequest.resolve(task());
    await settle();

    expect(mockReportGetMoves).toHaveBeenCalledWith('token-a', 7);
    expect(mockUserGameGet).toHaveBeenCalledWith('token-a', 'game-1');
    movesRequest.resolve([move(1), move(2)]);
    gameRequest.resolve(game());
    await settle();

    expect(result.current.task).toEqual(task());
    expect(result.current.game).toEqual(game());
    expect(result.current.moves).toEqual([move(1), move(2)]);
    expect(result.current.analysisByMove[2]).toMatchObject({ move_number: 2, match_id: 'game-1' });
    expect(result.current.currentMove).toBe(2);
    expect(result.current.loading).toBe(false);
    expect(result.current.refresh).toBe(initialRefresh);
  });

  it('polls pending and running reports every 2000ms, then stops at a terminal task', async () => {
    mockReportGet
      .mockResolvedValueOnce(task({ status: 'pending', analyzed_moves: 0 }))
      .mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 1 }))
      .mockResolvedValueOnce(task({ status: 'completed', analyzed_moves: 2 }));
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();

    await act(async () => vi.advanceTimersByTimeAsync(1999));
    expect(mockReportGet).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(mockReportGet).toHaveBeenCalledTimes(2);
    expect(result.current.task?.status).toBe('running');
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(mockReportGet).toHaveBeenCalledTimes(3);
    expect(result.current.task?.status).toBe('completed');
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(mockReportGet).toHaveBeenCalledTimes(3);
  });

  it('exposes a failed task and does not poll it', async () => {
    mockReportGet.mockResolvedValue(task({ status: 'failed', analyzed_moves: 1 }));
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();

    expect(result.current.task?.status).toBe('failed');
    expect(result.current.game).toEqual(game());
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(mockReportGet).toHaveBeenCalledTimes(1);
  });

  it('serializes slow polling and starts the next timeout after the request settles', async () => {
    const slowTask = deferred<ReportTaskSummary>();
    mockReportGet
      .mockResolvedValueOnce(task({ status: 'pending' }))
      .mockReturnValueOnce(slowTask.promise)
      .mockResolvedValueOnce(task({ status: 'completed' }));
    renderHook(() => useReportDetail('token-a', '7', true));
    await settle();

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(mockReportGet).toHaveBeenCalledTimes(2);

    slowTask.resolve(task({ status: 'running' }));
    await settle();
    await act(async () => vi.advanceTimersByTimeAsync(1999));
    expect(mockReportGet).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(mockReportGet).toHaveBeenCalledTimes(3);
  });

  it('keeps prior detail data when a refresh fails', async () => {
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();
    const priorTask = result.current.task;
    const priorMoves = result.current.moves;
    const priorGame = result.current.game;
    mockReportGet.mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 3 }));
    mockReportGetMoves.mockRejectedValueOnce(new Error('temporary outage'));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error).toBe('temporary outage');
    expect(result.current.task).toBe(priorTask);
    expect(result.current.moves).toBe(priorMoves);
    expect(result.current.game).toBe(priorGame);
  });

  it('keeps a failed detail pair single-flight until its slower sibling settles', async () => {
    const slowGame = deferred<UserGameDetail>();
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();
    const priorTask = result.current.task;
    const priorMoves = result.current.moves;
    const priorGame = result.current.game;
    mockReportGet.mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 3 }));
    mockReportGetMoves.mockRejectedValueOnce(new Error('moves unavailable'));
    mockUserGameGet.mockReturnValueOnce(slowGame.promise);

    let firstRefresh!: Promise<void>;
    act(() => {
      firstRefresh = result.current.refresh();
    });
    await settle();
    let joinedRefresh!: Promise<void>;
    act(() => {
      joinedRefresh = result.current.refresh();
    });
    await settle();

    expect(mockReportGet).toHaveBeenCalledTimes(2);
    expect(mockReportGetMoves).toHaveBeenCalledTimes(2);
    expect(mockUserGameGet).toHaveBeenCalledTimes(2);
    expect(result.current.task).toBe(priorTask);
    expect(result.current.moves).toBe(priorMoves);
    expect(result.current.game).toBe(priorGame);

    slowGame.resolve(game());
    await act(async () => {
      await Promise.all([firstRefresh, joinedRefresh]);
    });
    expect(result.current.error).toBe('moves unavailable');
  });

  it.each([
    {
      label: 'position zero through the analyzed move',
      analyzedMoves: 3,
      rows: [move(0), move(1), move(2), move(3)],
      expected: 3,
    },
    {
      label: 'sparse and duplicate move numbers',
      analyzedMoves: 5,
      rows: [move(0), move(2), move(2, { id: 20 }), move(5)],
      expected: 5,
    },
    {
      label: 'rows beyond the task frontier',
      analyzedMoves: 2,
      rows: [move(0), move(2), move(5)],
      expected: 2,
    },
    {
      label: 'malformed and incomplete analysis rows',
      analyzedMoves: 5,
      rows: [
        move(0),
        move(-1),
        move(2.5),
        move(3, { winrate: null }),
        move(4, { score_lead: null }),
        move(5, { status: 'failed', winrate: null, score_lead: null }),
      ],
      expected: 0,
    },
  ])('derives the available cursor from usable $label', async ({ analyzedMoves, rows, expected }) => {
    mockReportGet.mockResolvedValue(task({ analyzed_moves: analyzedMoves }));
    mockReportGetMoves.mockResolvedValue(rows);
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();

    expect(result.current.currentMove).toBe(expected);
    expect(result.current.analysisByMove[expected]).toBeDefined();
  });

  it('follows a growing frontier while pinned there and clamps when it shrinks', async () => {
    mockReportGet
      .mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 2 }))
      .mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 3 }))
      .mockResolvedValueOnce(task({ status: 'completed', analyzed_moves: 1 }));
    mockReportGetMoves
      .mockResolvedValueOnce([move(1), move(2)])
      .mockResolvedValueOnce([move(1), move(2), move(3)])
      .mockResolvedValueOnce([move(1)]);
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();
    expect(result.current.currentMove).toBe(2);

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(result.current.currentMove).toBe(3);
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(result.current.currentMove).toBe(1);
  });

  it('does not force a historical selection forward when the frontier grows', async () => {
    mockReportGet
      .mockResolvedValueOnce(task({ status: 'running', analyzed_moves: 2 }))
      .mockResolvedValueOnce(task({ status: 'completed', analyzed_moves: 3 }));
    mockReportGetMoves
      .mockResolvedValueOnce([move(1), move(2)])
      .mockResolvedValueOnce([move(1), move(2), move(3)]);
    const { result } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();
    act(() => result.current.setCurrentMove(1));

    await act(async () => vi.advanceTimersByTimeAsync(2000));

    expect(result.current.currentMove).toBe(1);
  });

  it('ignores stale responses and clears timers across token changes and unmount', async () => {
    const staleTask = deferred<ReportTaskSummary>();
    mockReportGet.mockReturnValueOnce(staleTask.promise).mockResolvedValueOnce(
      task({ id: 8, user_game_id: 'game-2', status: 'pending' }),
    );
    mockUserGameGet.mockResolvedValueOnce(game('game-2'));
    const { result, rerender, unmount } = renderHook(
      ({ token, taskId }) => useReportDetail(token, taskId, Boolean(token)),
      { initialProps: { token: 'token-a', taskId: '7' } },
    );
    rerender({ token: 'token-b', taskId: '8' });
    await settle();
    expect(result.current.task?.id).toBe(8);

    staleTask.resolve(task({ id: 7 }));
    await settle();
    expect(result.current.task?.id).toBe(8);
    unmount();
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(mockReportGet).toHaveBeenCalledTimes(2);
  });

  it('clears its timeout and ignores pending detail responses after unmount', async () => {
    const slowMoves = deferred<ReportTaskMove[]>();
    const slowGame = deferred<UserGameDetail>();
    mockReportGet.mockResolvedValue(task({ status: 'pending' }));
    const { unmount } = renderHook(() => useReportDetail('token-a', '7', true));
    await settle();
    expect(vi.getTimerCount()).toBe(1);

    mockReportGetMoves.mockReturnValueOnce(slowMoves.promise);
    mockUserGameGet.mockReturnValueOnce(slowGame.promise);
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(vi.getTimerCount()).toBe(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);

    slowMoves.resolve([move(1), move(2)]);
    slowGame.resolve(game());
    await settle();
    expect(mockReportGet).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('survives StrictMode effect replay without accepting the cancelled lifecycle', async () => {
    mockReportGet.mockResolvedValue(task({ status: 'completed' }));
    const { result } = renderHook(() => useReportDetail('token-a', '7', true), { wrapper: StrictMode });
    await settle();

    expect(mockReportGet).toHaveBeenCalledTimes(2);
    expect(result.current.task).toEqual(task({ status: 'completed' }));
    expect(result.current.loading).toBe(false);
  });
});
