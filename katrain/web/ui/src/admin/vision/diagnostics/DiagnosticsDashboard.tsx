import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminApiError, type createAdminApi } from '../../api/client';
import DiagnosticsPage from './DiagnosticsPage';
import type { DiagnosticsSnapshot, DiagnosticsStatus, VisionModels, VisionStatus } from '../types';

type Props = { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void; onCapturePage: () => void };

export default function DiagnosticsDashboard({ api, onUnauthorized, onCapturePage }: Props) {
  const [capture, setCapture] = useState<VisionStatus | null>(null);
  const [models, setModels] = useState<VisionModels | null>(null);
  const [status, setStatus] = useState<DiagnosticsStatus | null>(null);
  const [snapshot, setSnapshot] = useState<DiagnosticsSnapshot | null>(null);
  const [busy, setBusy] = useState('读取状态');
  const [error, setError] = useState('');
  const [authorized, setAuthorized] = useState(true);
  const active = useRef(false);
  const generation = useRef(0);
  const request = useRef<AbortController | null>(null);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);

  const fail = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    if (cause instanceof AdminApiError && cause.status === 401) {
      ++generation.current; request.current?.abort(); setAuthorized(false); setSnapshot(null); unauthorized.current(); return;
    }
    setError(cause instanceof Error ? cause.message : '请求失败，请重试。');
  }, []);

  const load = useCallback(async (signal: AbortSignal, version: number) => {
    const next = await api.visionStatus(signal);
    const [registry, diagnostics] = next.enabled ? await Promise.all([api.visionModels(signal), api.diagnosticsStatus(signal)]) : [null, null];
    if (!active.current || signal.aborted || version !== generation.current) return;
    setCapture(next); setModels(registry); setStatus(diagnostics);
    if (!diagnostics || diagnostics.state === 'idle') setSnapshot(null);
  }, [api]);

  const perform = useCallback(async (label: string, operation: (signal: AbortSignal) => Promise<unknown>) => {
    if (!active.current) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const version = ++generation.current;
    setBusy(label); setError('');
    try {
      await operation(controller.signal);
      await load(controller.signal, version);
    } catch (cause) {
      if (active.current && !controller.signal.aborted && version === generation.current) {
        fail(cause);
        await load(controller.signal, version).catch(() => undefined);
      }
    } finally {
      if (active.current && !controller.signal.aborted && version === generation.current) setBusy('');
    }
  }, [load, fail]);

  useEffect(() => {
    active.current = true;
    void perform('读取状态', async () => undefined);
    return () => { active.current = false; request.current?.abort(); };
  }, [perform]);

  // Serial snapshot polling, at most 2 Hz, only while the viewer runs. A failed poll keeps the whole old snapshot.
  const running = status?.state === 'running';
  useEffect(() => {
    if (!running || !authorized) return;
    let stopped = false;
    let timer: number | undefined;
    const poll = async () => {
      const controller = new AbortController();
      try {
        const [next, current] = await Promise.all([api.diagnosticsSnapshot(controller.signal).catch((cause: unknown) => {
          if (cause instanceof AdminApiError && cause.status === 404) return null;
          throw cause;
        }), api.diagnosticsStatus(controller.signal)]);
        if (stopped || !active.current) return;
        if (next) setSnapshot(next);
        setStatus(current);
      } catch (cause) {
        if (stopped || !active.current) return;
        if (cause instanceof AdminApiError && cause.status === 401) { fail(cause); return; }
        setError(cause instanceof Error ? `快照读取失败：${cause.message}` : '快照读取失败。');
      }
      if (!stopped) timer = window.setTimeout(() => { void poll(); }, 500);
    };
    void poll();
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [api, running, authorized, fail]);

  return <DiagnosticsPage
    capture={capture} models={models} status={status} snapshot={snapshot} busy={busy} error={error} authorized={authorized}
    onRefresh={() => { void perform('读取状态', async () => undefined); }}
    onActivate={(id) => { void perform('核对并加载模型', (signal) => api.visionActivateModel(id, signal)); }}
    onRollback={() => { void perform('回滚模型', (signal) => api.visionRollbackModel(signal)); }}
    onStart={() => { void perform('启动诊断', (signal) => api.diagnosticsStart(signal)); }}
    onStop={() => { void perform('停止诊断', (signal) => api.diagnosticsStop(signal)); }}
    onCapturePage={onCapturePage}
  />;
}
