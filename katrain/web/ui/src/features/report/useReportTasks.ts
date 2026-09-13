import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  ReportsAPI,
  type ReportQueueSummary,
  type ReportTaskSummary,
  type ReportType,
} from '../../api/reportApi';
import { useTranslation } from '../../hooks/useTranslation';
import { i18n } from '../../i18n';
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
  clearError: () => void;
  refresh: () => Promise<void>;
  createReport: (params: CreateReportParams) => Promise<ReportTaskSummary>;
  retryReport: (taskId: number) => Promise<ReportTaskSummary>;
}

function errorMessage(error: unknown, fallback: string): string {
  /* 402 有两种，用户该做的事完全不同：没绑手机 → 去绑（一步就有免费额度）；
     真没钱 → 去充值。合成一句「余额不足」是把前者的出路藏起来。
     `detail` 由 api/reportApi.ts 在 !response.ok 那里挂上来。
     注：`/retry` 的 402 **有意不带** `free_weekly_blocked`（reports.py:365 明写
     「这个键只加在这里，不加到 /retry」）⇒ 那里落到「余额不足」那一支，正好是对的。 */
  const e = error as { status?: number; detail?: { free_weekly_blocked?: string | null } } | null;
  if (e?.status === 402) {
    return e.detail?.free_weekly_blocked === 'phone_unbound'
      ? i18n.t('report:err_402_phone', '绑定手机号可每周免费复盘一局。到左下角「设置 → 绑定手机号」。')
      : i18n.t('report:err_402_credits', '余额不足，请先充值。');
  }
  return error instanceof Error ? error.message : fallback;
}

export function useReportTasks(
  token: string | null | undefined,
  /**
   * 认证就绪与否 —— **必须由调用方按 `isAuthenticated` 传进来，不能从 `token` 推**。
   * 严格盒端 SSO(`VITE_BOX_SSO_STRICT`)里 `token` 恒为 `null` 而人是登录的
   * (凭据在 HttpOnly cookie 里，JS 看不见)，所以拿 `!token` 当「未登录」用，
   * 会让盒子上所有报告请求一个都发不出去 —— 2026-09-13 板上实测：复盘列表恒显示
   * 「本机 0 局」，而同一时刻接口自己回 200、云端有 21 局。
   * `token` 在本文件里只剩一个用途：**身份键**(换人/换登录要作废在途请求)。
   */
  enabled: boolean,
): UseReportTasksResult {
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;
  const currentTokenRef = useRef(token);
  currentTokenRef.current = token;

  const [serverTasks, setServerTasks] = useState<ReportTaskSummary[]>([]);
  const [optimisticTasks, setOptimisticTasks] = useState<OptimisticReportTask[]>([]);
  const [queueSummary, setQueueSummary] = useState<ReportQueueSummary | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const clearError = useCallback(() => setError(null), []);
  const lifecycleGenerationRef = useRef(0);
  const nextOptimisticIdRef = useRef(0);
  const activeRefreshRef = useRef<{
    token: string | null | undefined;
    lifecycleGeneration: number;
    promise: Promise<void>;
  } | null>(null);

  const tasks = useMemo(
    () => reconcileReportTasks(serverTasks, optimisticTasks),
    [serverTasks, optimisticTasks],
  );
  const reportStatesByGame = useMemo(() => buildReportStatesByGame(tasks), [tasks]);

  const refresh = useCallback(async () => {
    if (!enabled || currentTokenRef.current !== token) return;
    const lifecycleGeneration = lifecycleGenerationRef.current;
    const activeRefresh = activeRefreshRef.current;
    if (
      // 同上：token 可为 undefined，`?.` 那种写法在 activeRefresh 为 null 时会判真。
      activeRefresh !== null
      && activeRefresh.token === token
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
  }, [enabled, token]);

  const refreshAfterActiveSnapshot = useCallback(async () => {
    if (!enabled || currentTokenRef.current !== token) return;
    const lifecycleGeneration = lifecycleGenerationRef.current;
    const activeRefresh = activeRefreshRef.current;
    if (
      // 同上：token 可为 undefined，`?.` 那种写法在 activeRefresh 为 null 时会判真。
      activeRefresh !== null
      && activeRefresh.token === token
      && activeRefresh.lifecycleGeneration === lifecycleGeneration
    ) await activeRefresh.promise;
    if (
      lifecycleGeneration !== lifecycleGenerationRef.current
      || currentTokenRef.current !== token
    ) return;
    await refresh();
  }, [enabled, refresh, token]);

  useEffect(() => {
    const lifecycleGeneration = lifecycleGenerationRef;
    ++lifecycleGenerationRef.current;
    setServerTasks([]);
    setOptimisticTasks([]);
    setQueueSummary(null);
    setError(null);
    setLoading(enabled);
    if (enabled) void refresh();

    return () => {
      ++lifecycleGeneration.current;
    };
  }, [enabled, refresh, token]);

  const hasActiveTasks = useMemo(() => tasks.some(isActiveReportTask), [tasks]);
  useEffect(() => {
    if (!enabled || !hasActiveTasks) return;
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
  }, [enabled, hasActiveTasks, refresh, token]);

  const createReport = useCallback(async ({
    userGameId,
    reportType = 'normal',
    totalMoves,
    force,
  }: CreateReportParams) => {
    if (!enabled || currentTokenRef.current !== token) throw new Error('Report task token changed');

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
        // token 可为 undefined，`?.` 写法在 activeRefresh 为 null 时会判真。
        activeRefresh !== null
        && activeRefresh.token === token
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
  }, [enabled, serverTasks, token]);

  const retryReport = useCallback(async (taskId: number) => {
    if (!enabled || currentTokenRef.current !== token) throw new Error('Report task token changed');
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
  }, [enabled, refreshAfterActiveSnapshot, token]);

  return {
    tasks,
    queueSummary,
    reportStatesByGame,
    loading,
    error,
    clearError,
    refresh,
    createReport,
    retryReport,
  };
}
