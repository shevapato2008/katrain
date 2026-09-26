import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminApiError, type createAdminApi } from '../../api/client';
import TrainingPage, { type TrainingPending, type TrainingSelection } from './TrainingPage';
import type { TrainingDataset, TrainingModel, TrainingParameters, TrainingPresets, TrainingRun, TrainingStartInput, TrainingStatus } from './types';

export default function TrainingDashboard({ api, onUnauthorized, onCapture }: { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void; onCapture: () => void }) {
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [datasets, setDatasets] = useState<TrainingDataset[]>([]);
  const [presets, setPresets] = useState<TrainingPresets | null>(null);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [run, setRun] = useState<TrainingRun | null>(null);
  const [models, setModels] = useState<TrainingModel[]>([]);
  const [parameters, setParameters] = useState<TrainingParameters>({ epochs: 100, batch: 8, imgsz: 960, seed: 0 });
  const [selection, setSelection] = useState<TrainingSelection>({ dataset_id: '', weights_id: '', augmentation: '', gpu_id: '' });
  const [pendingAction, setPendingAction] = useState<TrainingPending | null>(null);
  const [busy, setBusy] = useState('读取训练状态');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [authorized, setAuthorized] = useState(true);
  const mounted = useRef(false);
  const generation = useRef(0);
  const selectedId = useRef('');
  const pending = useRef(false);
  const retryInput = useRef<TrainingStartInput | null>(null);
  const actionRequest = useRef<AbortController | null>(null);
  const pollRequest = useRef<AbortController | null>(null);
  const pollInFlight = useRef(false);
  const lastReadStarted = useRef(0);
  const modelsLoaded = useRef(false);
  const snapshot = useRef<{ status: TrainingStatus | null; run: TrainingRun | null; activeRun: TrainingRun | null; presets: TrainingPresets | null }>({ status: null, run: null, activeRun: null, presets: null });
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const current = useCallback((signal: AbortSignal, version: number) => mounted.current && !signal.aborted && generation.current === version, []);
  const fail = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    if (cause instanceof AdminApiError && cause.status === 401) {
      ++generation.current; actionRequest.current?.abort(); pollRequest.current?.abort();
      snapshot.current = { status: null, run: null, activeRun: null, presets: null };
      modelsLoaded.current = false;
      setAuthorized(false); setStatus(null); setRun(null); setRuns([]); setModels([]); setPresets(null); setDatasets([]); setPendingAction(null);
      unauthorized.current(); return;
    }
    setError((cause instanceof Error ? cause.message : '读取失败，请重试。'));
  }, []);
  const load = useCallback(async (signal: AbortSignal, version: number, resources: boolean, desiredId?: string) => {
    let nextStatus = await api.trainingStatus(signal);
    if (!current(signal, version)) return;
    if (!nextStatus.enabled) {
      selectedId.current = '';
      snapshot.current = { status: nextStatus, run: null, activeRun: null, presets: null };
      modelsLoaded.current = false;
      setStatus(nextStatus); setRun(null); setRuns([]); setModels([]); setDatasets([]); setPresets(null);
      setSelection({ dataset_id: '', weights_id: '', augmentation: '', gpu_id: '' });
      return;
    }
    const readCatalog = resources || !snapshot.current.presets;
    let history: TrainingRun[] | null = null;
    if (readCatalog) {
      const [nextDatasets, nextPresets] = await Promise.all([api.trainingDatasets(signal), api.trainingPresets(signal)]);
      if (!current(signal, version)) return;
      setDatasets(nextDatasets); setPresets(nextPresets);
      setSelection((oldSelection) => {
        const dataset = nextDatasets.find((item) => item.id === oldSelection.dataset_id) ?? nextDatasets[0];
        const augmentation = nextPresets.augmentations.find((item) => item.mode === dataset?.mode && item.id === oldSelection.augmentation) ?? nextPresets.augmentations.find((item) => item.mode === dataset?.mode);
        return { dataset_id: dataset?.id ?? '', weights_id: nextPresets.weights.some((item) => item.id === oldSelection.weights_id) ? oldSelection.weights_id : nextPresets.weights[0]?.id ?? '', augmentation: augmentation?.id ?? '', gpu_id: nextStatus.gpu_ids.includes(oldSelection.gpu_id) ? oldSelection.gpu_id : nextStatus.gpu_ids[0] ?? '' };
      });
      snapshot.current.presets = nextPresets;
    }
    const activeId = nextStatus.active_run_id;
    const activeRun = activeId ? await api.trainingRun(activeId, signal) : null;
    if (!current(signal, version)) return;
    if (activeId && activeRun?.id !== activeId) throw new AdminApiError(503, '运行响应身份不符；保留上次观察并禁用写入。');
    let id = desiredId ?? (selectedId.current || activeId || '');
    if (!id && readCatalog) {
      history = await api.trainingRuns(signal);
      if (!current(signal, version)) return;
      id = history[0]?.id ?? '';
    }
    const nextRun = id === activeId ? activeRun : id ? await api.trainingRun(id, signal) : null;
    if (!current(signal, version)) return;
    if (id && nextRun?.id !== id) throw new AdminApiError(503, '运行响应身份不符；保留上次观察并禁用写入。');
    if (activeRun && ['completed', 'failed', 'cancelled'].includes(activeRun.state)) {
      nextStatus = await api.trainingStatus(signal);
      if (!current(signal, version)) return;
    }
    const runChanged = snapshot.current.run?.id !== nextRun?.id || snapshot.current.run?.state !== nextRun?.state || snapshot.current.run?.model_id !== nextRun?.model_id;
    const activeChanged = snapshot.current.activeRun?.id !== activeRun?.id || snapshot.current.activeRun?.state !== activeRun?.state || snapshot.current.activeRun?.model_id !== activeRun?.model_id;
    const modelPublished = (nextRun?.model_id && snapshot.current.run?.model_id !== nextRun.model_id) || (activeRun?.model_id && snapshot.current.activeRun?.model_id !== activeRun.model_id);
    if (!history && (readCatalog || runChanged || activeChanged)) history = await api.trainingRuns(signal);
    if (!current(signal, version)) return;
    if (readCatalog || !modelsLoaded.current || modelPublished) {
      const nextModels = await api.trainingModels(signal);
      if (!current(signal, version)) return;
      setModels(nextModels);
      modelsLoaded.current = true;
    }
    if (history) setRuns(history);
    selectedId.current = id;
    snapshot.current = { ...snapshot.current, status: nextStatus, run: nextRun, activeRun };
    setStatus(nextStatus); setRun(nextRun);
  }, [api, current]);

  useEffect(() => {
    mounted.current = true;
    const request = new AbortController(); actionRequest.current = request;
    const version = ++generation.current;
    lastReadStarted.current = Date.now();
    void load(request.signal, version, true).catch((cause: unknown) => { if (current(request.signal, version)) fail(cause); }).finally(() => { if (current(request.signal, version)) setBusy(''); });
    return () => { mounted.current = false; actionRequest.current?.abort(); pollRequest.current?.abort(); };
  }, [load, current, fail]);

  useEffect(() => {
    if (busy || !authorized) return;
    let stopped = false;
    let timer: number | undefined;
    const version = generation.current;
    const poll = async () => {
      if (stopped || !mounted.current || version !== generation.current) return;
      if (pollInFlight.current) { timer = window.setTimeout(() => { void poll(); }, 2000); return; }
      pollInFlight.current = true;
      const request = new AbortController(); pollRequest.current = request;
      lastReadStarted.current = Date.now();
      try { await load(request.signal, version, false); if (current(request.signal, version)) setError(''); }
      catch (cause) { if (current(request.signal, version)) fail(cause); }
      finally { pollInFlight.current = false; }
      if (!stopped && current(request.signal, version)) timer = window.setTimeout(() => { void poll(); }, 2000);
    };
    timer = window.setTimeout(() => { void poll(); }, Math.max(0, 2000 - (Date.now() - lastReadStarted.current)));
    return () => { stopped = true; window.clearTimeout(timer); pollRequest.current?.abort(); };
  }, [api, busy, authorized, load, fail, current]);

  async function perform(label: string, operation: (signal: AbortSignal, version: number) => Promise<void>) {
    if (!mounted.current || pending.current || !authorized) return;
    pending.current = true;
    actionRequest.current?.abort(); pollRequest.current?.abort();
    const request = new AbortController(); actionRequest.current = request;
    const version = ++generation.current; lastReadStarted.current = Date.now();
    setBusy(label); setError(''); setMessage(''); setPendingAction(null);
    try { await operation(request.signal, version); }
    catch (cause) { if (current(request.signal, version)) fail(cause); }
    finally { pending.current = false; if (current(request.signal, version)) setBusy(''); }
  }
  const dataset = datasets.find((item) => item.id === selection.dataset_id);
  const augmentation = presets?.augmentations.find((item) => item.id === selection.augmentation && item.mode === dataset?.mode);
  const validParameters = !!presets && Object.values(parameters).every(Number.isInteger) && parameters.epochs >= presets.limits.epochs[0] && parameters.epochs <= presets.limits.epochs[1] && presets.limits.batch.includes(parameters.batch) && presets.limits.imgsz.includes(parameters.imgsz) && parameters.seed >= presets.limits.seed[0] && parameters.seed <= presets.limits.seed[1];
  const reserved = !!status?.active_run_id || status?.state === 'busy' || status?.state === 'interrupted' || !!status?.reason;
  const canCreate = !!status?.enabled && authorized && !busy && (retryInput.current !== null || (!error && !reserved && !!dataset && !!augmentation && !!presets?.weights.some((item) => item.id === selection.weights_id) && !!status.gpu_ids.includes(selection.gpu_id) && validParameters));
  const canCancel = !!run && run.id === status?.active_run_id && run.state === 'running' && !error && authorized && !busy;
  function createIntent() {
    if (!canCreate || !dataset || !augmentation) return;
    setPendingAction({ kind: 'create', input: retryInput.current ?? { ...parameters, request_id: crypto.randomUUID(), dataset_id: dataset.id, dataset_manifest_sha256: dataset.manifest_sha256, weights_id: selection.weights_id, augmentation: augmentation.id, gpu_id: selection.gpu_id, confirmed: true } });
  }
  function confirm() {
    if (!pendingAction) return;
    if (pendingAction.kind === 'create') {
      if (!canCreate) return;
      const input = pendingAction.input; retryInput.current = input;
      void perform('创建运行', async (signal, version) => {
        let created: TrainingRun;
        try { created = await api.trainingStart(input, signal); }
        catch (cause) { if (cause instanceof AdminApiError && cause.status >= 400 && cause.status < 500) retryInput.current = null; throw cause; }
        if (!current(signal, version)) return;
        retryInput.current = null; selectedId.current = created.id; setRun(created);
        setMessage('运行请求已确认；状态、日志与产物以服务器观察为准。');
        await load(signal, version, true, created.id);
      });
    } else {
      if (!canCancel || pendingAction.run_id !== run?.id) return;
      const id = pendingAction.run_id;
      void perform('取消运行', async (signal, version) => {
        const cancelled = await api.trainingCancel(id, true, signal);
        if (!current(signal, version)) return;
        if (cancelled.id !== id) throw new AdminApiError(503, '取消响应身份不符。');
        setRun(cancelled); snapshot.current.run = cancelled;
        setMessage('取消请求已发送；进程组退出尚未核实前不会释放占用。');
        await load(signal, version, false, id);
      });
    }
  }
  return <TrainingPage status={status} datasets={datasets} presets={presets} runs={runs} run={run} models={models} parameters={parameters} selection={selection} pendingAction={pendingAction} busy={busy} error={error} message={message} canCreate={canCreate} canCancel={canCancel} retryCreate={!!retryInput.current} authorized={authorized}
    onSelectionChange={(value) => { const changedIntent = retryInput.current !== null; retryInput.current = null; const chosen = datasets.find((item) => item.id === value.dataset_id); setSelection({ ...value, augmentation: presets?.augmentations.find((item) => item.mode === chosen?.mode && item.id === value.augmentation)?.id ?? presets?.augmentations.find((item) => item.mode === chosen?.mode)?.id ?? '' }); if (changedIntent) void perform('核实当前占用', (signal, version) => load(signal, version, true)); }}
    onParametersChange={(value) => { const changedIntent = retryInput.current !== null; retryInput.current = null; setParameters(value); if (changedIntent) void perform('核实当前占用', (signal, version) => load(signal, version, true)); }} onCreate={createIntent}
    onCancel={() => { if (canCancel && run) setPendingAction({ kind: 'cancel', run_id: run.id }); }} onConfirm={confirm} onDismiss={() => setPendingAction(null)}
    onRefresh={() => { void perform('读取训练状态', (signal, version) => load(signal, version, true)); }}
    onRunChange={(id) => { selectedId.current = id; setRun(null); void perform('读取运行', (signal, version) => load(signal, version, false, id)); }}
    onCapture={onCapture} />;
}
