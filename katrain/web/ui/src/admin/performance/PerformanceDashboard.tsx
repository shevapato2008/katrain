import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminApiError, type createAdminApi, type PerformanceConfig } from '../api/client';
import PerformancePage from './PerformancePage';

type Props = { api: ReturnType<typeof createAdminApi>; environmentLabel: string; onUnauthorized: () => void };

const valid = (value: unknown): value is PerformanceConfig => {
  const config = value as PerformanceConfig | null;
  return !!config && ['unconfigured', 'invalid', 'configured'].includes(config.state) && Array.isArray(config.dashboards);
};

export default function PerformanceDashboard({ api, environmentLabel, onUnauthorized }: Props) {
  const [config, setConfig] = useState<PerformanceConfig | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);

  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError('');
    api.performance(controller.signal).then((next) => {
      if (!valid(next)) throw new Error('服务返回的看板配置格式不对');
      setConfig(next);
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof AdminApiError && cause.status === 401) { unauthorized.current(); return; }
      setError(cause instanceof Error ? cause.message : '请求失败，请重试。');
    }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [api, attempt]);

  return <PerformancePage config={config} environmentLabel={environmentLabel} busy={busy} error={error} onRetry={retry} />;
}
