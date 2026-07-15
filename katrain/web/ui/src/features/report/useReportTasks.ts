import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  ReportsAPI,
  type ReportQueueSummary,
  type ReportTaskSummary,
  type ReportType,
} from '../../api/reportApi';
import { useTranslation } from '../../hooks/useTranslation';
import {
  buildReportStatesByGame,
  createOptimisticReportTask,
  isActiveReportTask,
  reconcileReportTasks,
  type OptimisticReportTask,
  type ReportStatesByGame,
} from './reportModel';

const POLL_INTERVAL_MS = 2000;

export interface CreateReportParams {
  userGameId: string;
  reportType?: ReportType;
  totalMoves: number;
  force?: boolean;
}

export interface UseReportTasksResult {
  tasks: ReportTaskSummary[];
  queueSummary: ReportQueueSummary | null;
  reportStatesByGame: ReportStatesByGame;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createReport: (params: CreateReportParams) => Promise<ReportTaskSummary>;
  retryReport: (taskId: number) => Promise<ReportTaskSummary>;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function useReportTasks(token: string | null | undefined): UseReportTasksResult {
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;
  const currentTokenRef = useRef(token);
  currentTokenRef.current = token;

  const [serverTasks, setServerTasks] = useState<ReportTaskSummary[]>([]);
  const [optimisticTasks, setOptimisticTasks] = useState<OptimisticReportTask[]>([]);
  const [queueSummary, setQueueSummary] = useState<ReportQueueSummary | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState<string | null>(null);
  const lifecycleGenerationRef = useRef(0);
  const nextOptimisticIdRef = useRef(0);
  const activeRefreshRef = useRef<{
    token: string;
    lifecycleGeneration: number;
    promise: Promise<void>;
  } | null>(null);

  const tasks = useMemo(
    () => reconcileReportTasks(serverTasks, optimisticTasks),
    [serverTasks, optimisticTasks],
  );
  const reportStatesByGame = useMemo(() => buildReportStatesByGame(tasks), [tasks]);

  const refresh = useCallback(async () => {
    if (!token || currentTokenRef.current !== token) return;
    const lifecycleGeneration = lifecycleGenerationRef.current;
    const activeRefresh = activeRefreshRef.current;
    if (
      activeRefresh?.token === token
      && activeRefresh.lifecycleGeneration === lifecycleGeneration
    ) return activeRefresh.promise;

    const request = (async () => {
      try {
        const [nextTasks, nextSummary] = await Promise.all([
          ReportsAPI.list(token),
          ReportsAPI.summary(token),
        ]);
        if (
          lifecycleGeneration !== lifecycleGenerationRef.current
          || currentTokenRef.current !== token
        ) return;

        setServerTasks(nextTasks);
        setQueueSummary(nextSummary);
        setError(null);
      } catch (refreshError) {
        if (
          lifecycleGeneration !== lifecycleGenerationRef.current
          || currentTokenRef.current !== token
        ) return;
        setError(errorMessage(
          refreshError,
          translationRef.current('report:load_tasks_failed', 'Failed to load report tasks'),
        ));
      } finally {
        if (
          lifecycleGeneration === lifecycleGenerationRef.current
          && currentTokenRef.current === token
        ) setLoading(false);
      }
    })();
    const activeEntry = { token, lifecycleGeneration, promise: request };
    const trackedRequest = request.finally(() => {
      if (activeRefreshRef.current === activeEntry) activeRefreshRef.current = null;
    });
    activeEntry.promise = trackedRequest;
    activeRefreshRef.current = activeEntry;
    return trackedRequest;
  }, [token]);

  const refreshAfterActiveSnapshot = useCallback(async () => {
    if (!token || currentTokenRef.current !== token) return;
    const lifecycleGeneration = lifecycleGenerationRef.current;
    const activeRefresh = activeRefreshRef.current;
    if (
      activeRefresh?.token === token
      && activeRefresh.lifecycleGeneration === lifecycleGeneration
    ) await activeRefresh.promise;
    if (
      lifecycleGeneration !== lifecycleGenerationRef.current
      || currentTokenRef.current !== token
    ) return;
    await refresh();
  }, [refresh, token]);

  useEffect(() => {
    const lifecycleGeneration = lifecycleGenerationRef;
    ++lifecycleGenerationRef.current;
    setServerTasks([]);
    setOptimisticTasks([]);
    setQueueSummary(null);
    setError(null);
    setLoading(Boolean(token));
    if (token) void refresh();

    return () => {
      ++lifecycleGeneration.current;
    };
  }, [refresh, token]);

  const hasActiveTasks = useMemo(() => tasks.some(isActiveReportTask), [tasks]);
  useEffect(() => {
    if (!token || !hasActiveTasks) return;
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
  }, [hasActiveTasks, refresh, token]);

  const createReport = useCallback(async ({
    userGameId,
    reportType = 'normal',
    totalMoves,
    force,
  }: CreateReportParams) => {
    if (!token || currentTokenRef.current !== token) throw new Error('Report task token changed');

    const lifecycleGeneration = lifecycleGenerationRef.current;
    const optimisticId = --nextOptimisticIdRef.current;
    const baselineServerTaskIds = serverTasks.map((task) => task.id);
    const optimisticTask = createOptimisticReportTask(
      userGameId,
      reportType,
      totalMoves,
      optimisticId,
      baselineServerTaskIds,
    );
    setOptimisticTasks((current) => [optimisticTask, ...current]);
    setError(null);

    try {
      const created = await ReportsAPI.create(token, {
        user_game_id: userGameId,
        report_type: reportType,
        ...(force === undefined ? {} : { force }),
      });
      if (
        lifecycleGeneration !== lifecycleGenerationRef.current
        || currentTokenRef.current !== token
      ) return created;
      const activeRefresh = activeRefreshRef.current;
      if (
        activeRefresh?.token === token
        && activeRefresh.lifecycleGeneration === lifecycleGeneration
      ) await activeRefresh.promise;
      if (
        lifecycleGeneration !== lifecycleGenerationRef.current
        || currentTokenRef.current !== token
      ) return created;
      setServerTasks((current) => [created, ...current.filter((task) => task.id !== created.id)]);
      setOptimisticTasks((current) => current
        .filter((task) => task.id !== optimisticId)
        .map((task) => {
          if (task.user_game_id !== created.user_game_id || task.report_type !== created.report_type) return task;
          return {
            ...task,
            baseline_server_task_ids: [...(task.baseline_server_task_ids ?? []), created.id],
          };
        }));
      setError(null);
      return created;
    } catch (createError) {
      if (lifecycleGeneration !== lifecycleGenerationRef.current) throw createError;
      setOptimisticTasks((current) => current.filter((task) => task.id !== optimisticId));
      setError(errorMessage(
        createError,
        translationRef.current('report:create_task_failed', 'Failed to create report task'),
      ));
      throw createError;
    }
  }, [serverTasks, token]);

  const retryReport = useCallback(async (taskId: number) => {
    if (!token || currentTokenRef.current !== token) throw new Error('Report task token changed');
    const lifecycleGeneration = lifecycleGenerationRef.current;
    setError(null);
    try {
      const retried = await ReportsAPI.retry(token, taskId);
      if (lifecycleGeneration !== lifecycleGenerationRef.current) return retried;
      await refreshAfterActiveSnapshot();
      return retried;
    } catch (retryError) {
      if (lifecycleGeneration !== lifecycleGenerationRef.current) throw retryError;
      setError(errorMessage(
        retryError,
        translationRef.current('report:retry_failed', 'Failed to retry report'),
      ));
      throw retryError;
    }
  }, [refreshAfterActiveSnapshot, token]);

  return {
    tasks,
    queueSummary,
    reportStatesByGame,
    loading,
    error,
    refresh,
    createReport,
    retryReport,
  };
}
