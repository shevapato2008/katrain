import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  ReportsAPI,
  isActiveReportStatus,
  type ReportTaskMove,
  type ReportTaskSummary,
} from '../../api/reportApi';
import { UserGamesAPI, type UserGameDetail } from '../../api/userGamesApi';
import type { MoveAnalysis } from '../../types/live';
import { nextReportCursor, toMoveAnalysisMap } from './reportModel';

const POLL_INTERVAL_MS = 2000;
const INVALID_TASK_ID_ERROR = 'Invalid report task ID';

export interface UseReportDetailResult {
  task: ReportTaskSummary | null;
  game: UserGameDetail | null;
  moves: ReportTaskMove[];
  analysisByMove: Record<number, MoveAnalysis>;
  currentMove: number;
  setCurrentMove: (move: number) => void;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

function parseTaskId(taskId: string | number | null | undefined): number | null {
  if (typeof taskId === 'number') {
    return Number.isSafeInteger(taskId) && taskId > 0 ? taskId : null;
  }
  if (typeof taskId !== 'string' || !/^\d+$/.test(taskId)) return null;
  const parsed = Number(taskId);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load report';
}

function nextAvailableCursor(
  previousCursor: number,
  previousFrontier: number,
  analysisByMove: Record<number, MoveAnalysis>,
  analyzedMoves: number,
): { cursor: number; frontier: number } {
  const availableMoves = Object.keys(analysisByMove)
    .map(Number)
    .filter((moveNumber) => (
      Number.isSafeInteger(moveNumber)
      && moveNumber >= 0
      && moveNumber <= analyzedMoves
    ))
    .sort((left, right) => left - right);
  const frontier = availableMoves.at(-1) ?? 0;
  const requestedCursor = nextReportCursor(previousCursor, previousFrontier, frontier);
  const cursor = availableMoves.includes(requestedCursor)
    ? requestedCursor
    : [...availableMoves].reverse().find((moveNumber) => moveNumber <= requestedCursor)
      ?? availableMoves[0]
      ?? 0;
  return { cursor, frontier };
}

export function useReportDetail(
  token: string | null | undefined,
  taskId: string | number | null | undefined,
): UseReportDetailResult {
  const parsedTaskId = useMemo(() => parseTaskId(taskId), [taskId]);
  const currentTokenRef = useRef(token);
  const currentTaskIdRef = useRef(parsedTaskId);
  currentTokenRef.current = token;
  currentTaskIdRef.current = parsedTaskId;

  const [task, setTask] = useState<ReportTaskSummary | null>(null);
  const [game, setGame] = useState<UserGameDetail | null>(null);
  const [moves, setMoves] = useState<ReportTaskMove[]>([]);
  const [currentMove, setCurrentMoveState] = useState(0);
  const currentMoveRef = useRef(0);
  const setCurrentMove = useCallback((move: number) => {
    currentMoveRef.current = move;
    setCurrentMoveState(move);
  }, []);
  const [loading, setLoading] = useState(Boolean(token && parsedTaskId));
  const [error, setError] = useState<string | null>(
    token && parsedTaskId === null ? INVALID_TASK_ID_ERROR : null,
  );
  const frontierRef = useRef(0);
  const lifecycleGenerationRef = useRef(0);
  const activeRefreshRef = useRef<{
    token: string;
    taskId: number;
    lifecycleGeneration: number;
    promise: Promise<void>;
  } | null>(null);

  const isCurrentLifecycle = useCallback(
    (lifecycleGeneration: number, requestToken: string, requestTaskId: number) => (
      lifecycleGenerationRef.current === lifecycleGeneration
      && currentTokenRef.current === requestToken
      && currentTaskIdRef.current === requestTaskId
    ),
    [],
  );

  const refresh = useCallback(async () => {
    if (!token || parsedTaskId === null) return;
    if (currentTokenRef.current !== token || currentTaskIdRef.current !== parsedTaskId) return;

    const lifecycleGeneration = lifecycleGenerationRef.current;
    const activeRefresh = activeRefreshRef.current;
    if (
      activeRefresh?.token === token
      && activeRefresh.taskId === parsedTaskId
      && activeRefresh.lifecycleGeneration === lifecycleGeneration
    ) return activeRefresh.promise;

    const request = (async () => {
      try {
        const nextTask = await ReportsAPI.get(token, parsedTaskId);
        if (!isCurrentLifecycle(lifecycleGeneration, token, parsedTaskId)) return;

        const [movesResult, gameResult] = await Promise.allSettled([
          ReportsAPI.getMoves(token, parsedTaskId),
          UserGamesAPI.get(token, nextTask.user_game_id),
        ]);
        if (!isCurrentLifecycle(lifecycleGeneration, token, parsedTaskId)) return;
        if (movesResult.status === 'rejected') throw movesResult.reason;
        if (gameResult.status === 'rejected') throw gameResult.reason;
        const nextMoves = movesResult.value;
        const nextGame = gameResult.value;

        const previousFrontier = frontierRef.current;
        const nextAnalysisByMove = toMoveAnalysisMap(nextMoves, nextTask.user_game_id);
        const { cursor: nextCursor, frontier: nextFrontier } = nextAvailableCursor(
          currentMoveRef.current,
          previousFrontier,
          nextAnalysisByMove,
          nextTask.analyzed_moves,
        );
        frontierRef.current = nextFrontier;
        setTask(nextTask);
        setMoves(nextMoves);
        setGame(nextGame);
        setCurrentMove(nextCursor);
        setError(null);
      } catch (refreshError) {
        if (!isCurrentLifecycle(lifecycleGeneration, token, parsedTaskId)) return;
        setError(errorMessage(refreshError));
      } finally {
        if (isCurrentLifecycle(lifecycleGeneration, token, parsedTaskId)) setLoading(false);
      }
    })();

    const activeEntry = {
      token,
      taskId: parsedTaskId,
      lifecycleGeneration,
      promise: request,
    };
    const trackedRequest = request.finally(() => {
      if (activeRefreshRef.current === activeEntry) activeRefreshRef.current = null;
    });
    activeEntry.promise = trackedRequest;
    activeRefreshRef.current = activeEntry;
    return trackedRequest;
  }, [isCurrentLifecycle, parsedTaskId, setCurrentMove, token]);

  useEffect(() => {
    const lifecycleGeneration = lifecycleGenerationRef;
    ++lifecycleGenerationRef.current;
    setTask(null);
    setGame(null);
    setMoves([]);
    setCurrentMove(0);
    frontierRef.current = 0;
    setLoading(Boolean(token && parsedTaskId));
    setError(token && parsedTaskId === null ? INVALID_TASK_ID_ERROR : null);
    if (token && parsedTaskId !== null) void refresh();

    return () => {
      ++lifecycleGeneration.current;
    };
  }, [parsedTaskId, refresh, setCurrentMove, token]);

  useEffect(() => {
    if (!token || parsedTaskId === null || !task || !isActiveReportStatus(task.status)) return;
    let cancelled = false;
    let timer: number | undefined;

    const schedule = () => {
      timer = window.setTimeout(async () => {
        timer = undefined;
        await refresh();
        if (!cancelled) schedule();
      }, POLL_INTERVAL_MS);
    };
    schedule();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [parsedTaskId, refresh, task, token]);

  const analysisByMove = useMemo(
    () => toMoveAnalysisMap(moves, task?.user_game_id ?? ''),
    [moves, task?.user_game_id],
  );

  return {
    task,
    game,
    moves,
    analysisByMove,
    currentMove,
    setCurrentMove,
    loading,
    error,
    refresh,
  };
}
