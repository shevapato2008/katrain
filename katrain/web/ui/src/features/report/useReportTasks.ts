import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  ReportsAPI,
  type ReportQueueSummary,
  type ReportTaskSummary,
  type ReportType,
} from '../../api/reportApi';
import { membershipApi } from '../../api/membershipApi';
import { notifyMembershipChanged } from '../membership/useMembership';
import type { BillingQuote, MembershipCatalog } from '../membership/types';
import { useMembershipI18n } from '../membership/useMembershipI18n';
import { membershipErrorCode, membershipErrorText, type MembershipErrorCode } from '../membership/presentation';
import {
  buildReportStatesByGame,
  createOptimisticReportTask,
  isActiveReportTask,
  reconcileReportTasks,
  type OptimisticReportTask,
  type ReportStatesByGame,
} from './reportModel';
import { requestFailureKind, type RequestFailureKind } from '../../utils/requestFailure';

const POLL_INTERVAL_MS = 2000;

export interface CreateReportParams {
  userGameId: string;
  reportType?: ReportType;
  totalMoves: number;
  force?: boolean;
}

interface PendingReportQuote { quote: BillingQuote; params: CreateReportParams; taskId?: number; idempotencyKey: string; scope: string }

export interface UseReportTasksResult {
  tasks: ReportTaskSummary[];
  queueSummary: ReportQueueSummary | null;
  reportStatesByGame: ReportStatesByGame;
  loading: boolean;
  error: string | null;
  billingError?: boolean;
  /**
   * 这条错属于哪一类(`utils/requestFailure.ts`)。**屏上说什么由调用方按它定** ——
   * 旧列表/导入错误沿用原有分类；会员消耗错误已映射为安全的本地化文案。
   */
  errorKind: RequestFailureKind | null;
  clearError: () => void;
  refresh: () => Promise<void>;
  createReport: (params: CreateReportParams) => Promise<ReportTaskSummary | null>;
  retryReport: (taskId: number) => Promise<ReportTaskSummary | null>;
  pendingQuote: PendingReportQuote | null;
  quoteBusy: boolean;
  confirmQuote: () => Promise<ReportTaskSummary | null>;
  cancelQuote: () => void;
}

interface Failure {
  message: string;
  kind: RequestFailureKind;
  membershipCode?: MembershipErrorCode;
}

function failureOf(error: unknown, fallback: string, billingFallback?: MembershipErrorCode): Failure {
  const carrier = (error && typeof error === 'object' ? error : {}) as { detail?: unknown; body?: unknown; message?: unknown };
  // Legacy list/import failures keep their historical presentation unless a billing code is explicit.
  const code = membershipErrorCode(billingFallback ? error : { detail: carrier.detail, body: carrier.body, message: carrier.message }, billingFallback ?? 'report_failed');
  const membershipCode = billingFallback || code !== 'report_failed' ? code : undefined;
  return { message: membershipCode ? '' : error instanceof Error ? error.message : fallback, membershipCode,
    kind: membershipCode === 'insufficient' ? 'no_credits' : requestFailureKind(error) };
}

export function useReportTasks(
  token: string | null | undefined,
  /**
   * 认证就绪与否 —— **必须由调用方按 `isAuthenticated` 传进来，不能从 `token` 推**。
   * 严格盒端 SSO(`VITE_BOX_SSO_STRICT`)里 `token` 恒为 `null` 而人是登录的
   * (凭据在 HttpOnly cookie 里，JS 看不见)，所以拿 `!token` 当「未登录」用，
   * 会让盒子上所有报告请求一个都发不出去 —— 2026-09-13 板上实测：复盘列表恒显示
   * 「本机 0 局」，而同一时刻接口自己回 200、云端有 21 局。
   * 调用页面同时传入 AuthContext 的 identityKey/status；Cookie 身份切换同样作废在途请求。
   */
  isAuthenticated: boolean,
  identityKey: string | null | undefined = token ?? 'cookie-session',
  authStatus: string = isAuthenticated ? 'authenticated' : 'anonymous',
): UseReportTasksResult {
  const enabled = isAuthenticated && authStatus === 'authenticated' && identityKey != null;
  const { t } = useMembershipI18n();
  const translationRef = useRef(t);
  translationRef.current = t;
  const scope = JSON.stringify([identityKey, authStatus, enabled, token]);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const [dataScope, setDataScope] = useState(scope);
  const catalogRef = useRef<{ scope: string; catalog: MembershipCatalog } | null>(null);
  const [pendingQuote, setPendingQuote] = useState<PendingReportQuote | null>(null);
  const pendingRef = useRef<PendingReportQuote | null>(null);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const confirmRef = useRef<{ scope: string; promise: Promise<ReportTaskSummary | null> } | null>(null);
  const updatePending = useCallback((next: PendingReportQuote | null) => { pendingRef.current = next; setPendingQuote(next); }, []);
  const cancelQuote = useCallback(() => { if (!confirmRef.current) updatePending(null); }, [updatePending]);

  const [serverTasks, setServerTasks] = useState<ReportTaskSummary[]>([]);
  const [optimisticTasks, setOptimisticTasks] = useState<OptimisticReportTask[]>([]);
  const [queueSummary, setQueueSummary] = useState<ReportQueueSummary | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [failure, setFailure] = useState<Failure | null>(null);
  const clearError = useCallback(() => setFailure(null), []);
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
    if (!enabled || scopeRef.current !== scope) return;
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
          || scopeRef.current !== scope
        ) return;

        setServerTasks(nextTasks);
        setQueueSummary(nextSummary);
        setFailure(null);
      } catch (refreshError) {
        if (
          lifecycleGeneration !== lifecycleGenerationRef.current
          || scopeRef.current !== scope
        ) return;
        setFailure(failureOf(
          refreshError,
          translationRef.current('report:load_tasks_failed', 'Failed to load report tasks'),
        ));
      } finally {
        if (
          lifecycleGeneration === lifecycleGenerationRef.current
          && scopeRef.current === scope
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
  }, [enabled, token, scope]);

  const refreshAfterActiveSnapshot = useCallback(async () => {
    if (!enabled || scopeRef.current !== scope) return;
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
      || scopeRef.current !== scope
    ) return;
    await refresh();
  }, [enabled, refresh, token, scope]);

  useEffect(() => {
    const lifecycleGeneration = lifecycleGenerationRef;
    ++lifecycleGenerationRef.current;
    const catalogGeneration = lifecycleGenerationRef.current;
    setDataScope(scope);
    catalogRef.current = null;
    updatePending(null);
    confirmRef.current = null;
    setQuoteBusy(false);
    if (enabled) {
      void membershipApi.getCatalog(token).then((catalog) => {
        if (scopeRef.current === scope && lifecycleGenerationRef.current === catalogGeneration) catalogRef.current = { scope, catalog };
      }).catch(() => { /* Consumption remains blocked until a fresh catalog succeeds. */ });
    }
    setServerTasks([]);
    setOptimisticTasks([]);
    setQueueSummary(null);
    setFailure(null);
    setLoading(enabled);
    if (enabled) void refresh();

    return () => {
      ++lifecycleGeneration.current;
    };
  }, [enabled, refresh, token, scope]);

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
  }, [enabled, hasActiveTasks, refresh, token, scope]);

  const executeCreate = useCallback(async ({
    userGameId,
    reportType = 'normal',
    totalMoves,
    force,
  }: CreateReportParams, authorization?: { quote_token: string; idempotency_key: string }) => {
    if (!enabled || scopeRef.current !== scope) throw new Error('Report task token changed');

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
    setFailure(null);

    try {
      const created = await ReportsAPI.create(token, {
        user_game_id: userGameId,
        report_type: reportType,
        ...(force === undefined ? {} : { force }),
        ...authorization,
      });
      if (
        lifecycleGeneration !== lifecycleGenerationRef.current
        || scopeRef.current !== scope
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
        || scopeRef.current !== scope
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
      setFailure(null);
      return created;
    } catch (createError) {
      if (lifecycleGeneration !== lifecycleGenerationRef.current) throw createError;
      setOptimisticTasks((current) => current.filter((task) => task.id !== optimisticId));
      setFailure(failureOf(
        createError,
        translationRef.current('report:create_task_failed', 'Failed to create report task'),
        authorization ? 'report_failed' : undefined,
      ));
      throw createError;
    }
  }, [enabled, serverTasks, token, scope]);

  const executeRetry = useCallback(async (taskId: number, authorization?: { quote_token: string; idempotency_key: string }) => {
    if (!enabled || scopeRef.current !== scope) throw new Error('Report task token changed');
    const lifecycleGeneration = lifecycleGenerationRef.current;
    setFailure(null);
    try {
      const retried = await (authorization ? ReportsAPI.retry(token, taskId, authorization) : ReportsAPI.retry(token, taskId));
      if (lifecycleGeneration !== lifecycleGenerationRef.current) return retried;
      await refreshAfterActiveSnapshot();
      return retried;
    } catch (retryError) {
      if (lifecycleGeneration !== lifecycleGenerationRef.current) throw retryError;
      setFailure(failureOf(
        retryError,
        translationRef.current('report:retry_failed', 'Failed to retry report'),
        authorization ? 'report_failed' : undefined,
      ));
      throw retryError;
    }
  }, [enabled, refreshAfterActiveSnapshot, token, scope]);

  const prepareQuote = useCallback(async (params: CreateReportParams, taskId?: number) => {
    if (!enabled || scopeRef.current !== scope) throw new Error('Report identity changed');
    const generation = lifecycleGenerationRef.current;
    setFailure(null);
    try {
      const catalog = catalogRef.current?.scope === scope ? catalogRef.current.catalog : await membershipApi.getCatalog(token);
      if (scopeRef.current !== scope || lifecycleGenerationRef.current !== generation) return null;
      catalogRef.current = { scope, catalog };
      if (catalog.membership_mode === 'legacy') return taskId === undefined ? executeCreate(params) : executeRetry(taskId);
      if (catalog.membership_mode !== 'enabled' || !catalog.capabilities.quotes) throw new Error(catalog.membership_mode === 'paused' ? 'membership_paused' : 'membership_disabled');
      const quote = await membershipApi.createQuote({ kind: 'report', profile: params.reportType === 'deep' ? 'advanced' : 'normal', game_id: params.userGameId }, token);
      if (scopeRef.current !== scope || lifecycleGenerationRef.current !== generation) return null;
      updatePending({ quote, params, taskId, idempotencyKey: crypto.randomUUID(), scope });
      return null;
    } catch (error) {
      if (scopeRef.current === scope && lifecycleGenerationRef.current === generation) setFailure(failureOf(error, '', 'quote_failed'));
      throw error;
    }
  }, [enabled, executeCreate, executeRetry, scope, token, updatePending]);

  const createReport = useCallback((params: CreateReportParams) => {
    // Keep the historical immediate optimistic feedback only when the server explicitly says legacy.
    if (catalogRef.current?.scope === scope && catalogRef.current.catalog.membership_mode === 'legacy') return executeCreate(params);
    return prepareQuote(params);
  }, [executeCreate, prepareQuote, scope]);
  const retryReport = useCallback((taskId: number) => {
    if (catalogRef.current?.scope === scope && catalogRef.current.catalog.membership_mode === 'legacy') return executeRetry(taskId);
    const task = serverTasks.find((entry) => entry.id === taskId);
    if (!task) {
      setFailure({ message: '', kind: 'not_found', membershipCode: 'report_missing' });
      return Promise.reject(new Error('report_not_found'));
    }
    return prepareQuote({ userGameId: task.user_game_id, reportType: task.report_type, totalMoves: task.total_moves }, taskId);
  }, [executeRetry, prepareQuote, scope, serverTasks]);
  const confirmQuote = useCallback((): Promise<ReportTaskSummary | null> => {
    if (confirmRef.current?.scope === scope) return confirmRef.current.promise;
    const pending = pendingRef.current;
    if (!enabled || !pending || pending.scope !== scope || scopeRef.current !== scope) return Promise.resolve(null);
    setQuoteBusy(true);
    const authorization = { quote_token: pending.quote.token, idempotency_key: pending.idempotencyKey };
    const execute = () => pending.taskId === undefined ? executeCreate(pending.params, authorization) : executeRetry(pending.taskId, authorization);
    const promise = (async () => {
      try {
        let result: ReportTaskSummary;
        try { result = await execute(); } catch (error) {
          // A lost HTTP response may be replayed once, with exactly the same authorization.
          if (error instanceof TypeError && scopeRef.current === scope) result = await execute();
          else throw error;
        }
        if (scopeRef.current === scope) { updatePending(null); notifyMembershipChanged(); }
        return result;
      } catch (error) {
        if (scopeRef.current === scope && /quote/.test(String((error as { body?: unknown })?.body ?? error))) {
          await prepareQuote(pending.params, pending.taskId);
        }
        throw error;
      } finally {
        if (scopeRef.current === scope) { setQuoteBusy(false); confirmRef.current = null; }
      }
    })();
    confirmRef.current = { scope, promise };
    return promise;
  }, [enabled, executeCreate, executeRetry, prepareQuote, scope, updatePending]);

  return {
    tasks: dataScope === scope ? tasks : [],
    queueSummary: dataScope === scope ? queueSummary : null,
    reportStatesByGame: dataScope === scope ? reportStatesByGame : {},
    loading,
    error: dataScope === scope && failure ? failure.membershipCode ? membershipErrorText(failure.membershipCode, t) : failure.message : null,
    billingError: dataScope === scope && !!failure?.membershipCode,
    errorKind: dataScope === scope ? failure?.kind ?? null : null,
    clearError,
    refresh,
    createReport,
    retryReport,
    pendingQuote: pendingQuote?.scope === scope ? pendingQuote : null,
    quoteBusy: dataScope === scope && quoteBusy, confirmQuote, cancelQuote,
  };
}
