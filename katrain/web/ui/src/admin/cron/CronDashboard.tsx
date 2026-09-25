import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminApiError, type createAdminApi } from '../api/client';
import CronPage from './CronPage';
import type { CronView } from './types';

const initialView: CronView = { state: 'loading', observed_at: null, jobs: [], runs: {}, queues: null };
const errorText = (cause: unknown) => cause instanceof AdminApiError
  ? `${cause.status || '网络'}：${cause.message}`
  : cause instanceof Error ? cause.message : '请求失败，请重试。';
const isMissingTable = (cause: unknown) => cause instanceof AdminApiError
  && cause.status === 503 && cause.message.startsWith('cron 状态表不存在');

export default function CronDashboard({ api, onUnauthorized }: { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void }) {
  const [view, setView] = useState<CronView>(initialView);
  const [refreshCount, setRefreshCount] = useState(0);
  const active = useRef(true);
  const requestGeneration = useRef(0);
  const onUnauthorizedRef = useRef(onUnauthorized);
  onUnauthorizedRef.current = onUnauthorized;

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    try {
      const [jobResponse, queueResponse] = await Promise.all([api.cronJobs(), api.cronQueues()]);
      if (!active.current || generation !== requestGeneration.current) return;
      const state: CronView['state'] = jobResponse.jobs.length === 0 ? 'empty'
        : jobResponse.jobs.some((job) => job.health.state === 'offline') ? 'offline'
        : jobResponse.jobs.some((job) => ['failed', 'errors', 'stuck', 'overdue'].includes(job.health.state)) ? 'failed'
        : 'healthy';
      setView((previous) => ({
        ...previous, state, observed_at: jobResponse.observed_at, jobs: jobResponse.jobs,
        queues: { live_analysis: queueResponse.live_analysis, report_tasks: queueResponse.report_tasks }, error: undefined,
      }));
    } catch (cause) {
      if (!active.current || generation !== requestGeneration.current) return;
      if (cause instanceof AdminApiError && cause.status === 401) { onUnauthorizedRef.current(); return; }
      setView((previous) => ({
        ...previous,
        state: isMissingTable(cause) ? 'no-table' : 'api-error',
        error: errorText(cause),
      }));
    }
  }, [api]);

  useEffect(() => {
    active.current = true;
    void load();
    const timer = window.setInterval(() => { void load(); }, 15_000);
    return () => { active.current = false; window.clearInterval(timer); };
  }, [load]);

  useEffect(() => { if (refreshCount) void load(); }, [refreshCount, load]);

  const selectJob = useCallback(async (name: string) => {
    setView((previous) => ({ ...previous, historyLoading: true, historyError: undefined }));
    try {
      const result = await api.cronRuns(name, 200);
      if (active.current) setView((previous) => ({ ...previous, runs: { ...previous.runs, [name]: result.runs }, historyLoading: false }));
    } catch (cause) {
      if (!active.current) return;
      if (cause instanceof AdminApiError && cause.status === 401) { onUnauthorizedRef.current(); return; }
      setView((previous) => ({ ...previous, historyLoading: false, historyError: errorText(cause) }));
    }
  }, [api]);

  return <CronPage view={view} onRefresh={() => setRefreshCount((count) => count + 1)} onSelectJob={selectJob} />;
}
