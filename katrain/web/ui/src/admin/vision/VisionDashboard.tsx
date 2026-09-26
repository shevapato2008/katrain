import { useCallback, useEffect, useRef, useState } from 'react';
import { AdminApiError, type createAdminApi } from '../api/client';
import VisionLivePage from './VisionLivePage';
import type { KifuAlbumList, VisionDevices, VisionFrozen, VisionPreview, VisionReviewFailure, VisionSampleReview, VisionSession, VisionSessionList, VisionStatus } from './types';

type Props = { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void };
export default function VisionDashboard({ api, onUnauthorized }: Props) {
  const [status, setStatus] = useState<VisionStatus | null>(null);
  const [devices, setDevices] = useState<VisionDevices['candidates']>([]);
  const [sessions, setSessions] = useState<VisionSessionList | null>(null);
  const [session, setSession] = useState<VisionSession | null>(null);
  const [preview, setPreview] = useState<VisionPreview | null>(null);
  const [review, setReview] = useState<VisionSampleReview | null>(null);
  const [reviewFailure, setReviewFailure] = useState<VisionReviewFailure | null>(null);
  const [frozen, setFrozen] = useState<VisionFrozen | null>(null);
  const [labelPreview, setLabelPreview] = useState<{ overlay: VisionSampleReview | null; error: string | null } | null>(null);
  const labelRequest = useRef<AbortController | null>(null);
  const [kifu, setKifu] = useState<{ query: string; list: KifuAlbumList | null; error: string; loading: boolean }>({ query: '', list: null, error: '', loading: false });
  const kifuRequest = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState('读取状态');
  const [error, setError] = useState('');
  const [previewError, setPreviewError] = useState('');
  const [message, setMessage] = useState('');
  const [authorized, setAuthorized] = useState(true);
  const [previewPaused, setPreviewPaused] = useState(false);
  const [contextVersion, setContextVersion] = useState(0);
  const active = useRef(false);
  const statusSnapshot = useRef<VisionStatus | null>(null);
  const generation = useRef(0);
  const operationContext = useRef(0);
  const actionRequest = useRef<AbortController | null>(null);
  const previewRequest = useRef<AbortController | null>(null);
  const lastPreviewStarted = useRef<number | null>(null);
  const pending = useRef(false);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);

  const fail = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    if (cause instanceof AdminApiError && cause.status === 401) {
      ++generation.current; actionRequest.current?.abort(); previewRequest.current?.abort();
      statusSnapshot.current = null;
      setAuthorized(false); setPreview(null); setReview(null); setReviewFailure(null); unauthorized.current(); return;
    }
    setError(cause instanceof Error ? cause.message : '请求失败，请重试。');
  }, []);

  const refresh = useCallback(async (signal: AbortSignal, version: number) => {
    const next = await api.visionStatus(signal);
    const [available, saved, selected] = next.enabled ? await Promise.all([
      api.visionDevices(signal), api.visionSessions(signal),
      next.sgf.game_id ? api.visionSession(next.sgf.game_id, signal) : Promise.resolve(null),
    ]) : [null, null, null];
    if (!active.current || signal.aborted || version !== generation.current) return;
    statusSnapshot.current = next;
    setStatus(next); setDevices(available?.candidates ?? []); setSessions(saved); setSession(selected);
    setReview(null); setReviewFailure(null);
    setFrozen((previous) => next.dataset.state === 'frozen' && previous?.id === next.dataset.id ? previous : null);
  }, [api]);

  useEffect(() => {
    active.current = true;
    const controller = new AbortController(); actionRequest.current = controller;
    const version = ++generation.current;
    void refresh(controller.signal, version).catch((cause: unknown) => {
      if (active.current && !controller.signal.aborted && version === generation.current) fail(cause);
    }).finally(() => { if (active.current && !controller.signal.aborted && version === generation.current) setBusy(''); });
    return () => {
      active.current = false; statusSnapshot.current = null;
      actionRequest.current?.abort(); previewRequest.current?.abort();
    };
  }, [refresh, fail]);

  const connected = status?.camera.state === 'connected';
  const cameraId = status?.camera.device_id;
  const mode = status?.mode;
  const revision = status?.geometry.revision;
  const gameId = status?.sgf.game_id;
  const nextStep = status?.sgf.next_step;
  const sampleCount = status?.dataset.count;
  useEffect(() => {
    if (!connected || busy || !authorized || previewPaused) return;
    let stopped = false;
    let timer: number | undefined;
    const version = generation.current;
    const poll = async () => {
      const controller = new AbortController(); previewRequest.current = controller;
      lastPreviewStarted.current = Date.now();
      try {
        const frame = await api.visionPreview(controller.signal);
        if (!stopped && !controller.signal.aborted && version === generation.current && active.current) {
          setPreview(frame); setPreviewError('');
        }
      } catch (cause) {
        if (stopped || controller.signal.aborted || version !== generation.current || !active.current) return;
        if (cause instanceof AdminApiError && cause.status === 401) { fail(cause); return; }
        setPreview(null); setPreviewError(cause instanceof Error ? cause.message : '预览暂不可用。');
        try {
          const actual = await api.visionStatus(controller.signal);
          if (!stopped && !controller.signal.aborted && version === generation.current && active.current) {
            if (actual.sgf.game_id !== gameId || actual.sgf.next_step !== nextStep || actual.dataset.count !== sampleCount) await refresh(controller.signal, version);
            else { statusSnapshot.current = actual; setStatus(actual); }
          }
        } catch (statusCause) {
          if (!stopped && !controller.signal.aborted && version === generation.current && active.current) fail(statusCause);
        }
      }
      if (!stopped && active.current && version === generation.current && !controller.signal.aborted) timer = window.setTimeout(() => { void poll(); }, 500);
    };
    const delay = lastPreviewStarted.current === null ? 0 : Math.max(0, 500 - (Date.now() - lastPreviewStarted.current));
    if (delay) timer = window.setTimeout(() => { void poll(); }, delay);
    else void poll();
    return () => { stopped = true; window.clearTimeout(timer); previewRequest.current?.abort(); };
  }, [api, connected, cameraId, mode, revision, gameId, nextStep, sampleCount, busy, authorized, previewPaused, fail, refresh]);

  async function perform<T>(label: string, operation: (signal: AbortSignal) => Promise<T>, accept?: (result: T) => void, reload = true) {
    if (!active.current || pending.current || !authorized) return;
    const previousStatus = statusSnapshot.current;
    pending.current = true;
    statusSnapshot.current = null;
    actionRequest.current?.abort(); previewRequest.current?.abort();
    const controller = new AbortController(); actionRequest.current = controller;
    const version = ++generation.current;
    setBusy(label); setError(''); setMessage(''); setPreview(null); setPreviewError('');
    setContextVersion(++operationContext.current);
    setPreviewPaused(false);
    try {
      const result = await operation(controller.signal);
      if (!active.current || controller.signal.aborted || version !== generation.current) return;
      accept?.(result);
      if (reload) await refresh(controller.signal, version);
      else statusSnapshot.current = previousStatus;
    } catch (cause) {
      if (active.current && !controller.signal.aborted && version === generation.current) fail(cause);
    } finally {
      pending.current = false;
      if (active.current && !controller.signal.aborted && version === generation.current) setBusy('');
    }
  }

  const latestFrame = session?.frames.at(-1)?.frame_id;
  const onLabel = useCallback(() => {
    labelRequest.current?.abort();
    setLabelPreview(null);
    if (!gameId || !latestFrame || !authorized) return;
    const controller = new AbortController(); labelRequest.current = controller;
    api.visionReviewSample(gameId, latestFrame, controller.signal).then(
      (overlay) => { if (!controller.signal.aborted && active.current) setLabelPreview({ overlay, error: null }); },
      (cause: unknown) => {
        if (controller.signal.aborted || !active.current) return;
        if (cause instanceof AdminApiError && cause.status === 401) { fail(cause); return; }
        setLabelPreview({ overlay: null, error: cause instanceof Error ? `最新样本检查未通过：${cause.message}` : '最新样本检查未通过。' });
      },
    );
  }, [api, gameId, latestFrame, authorized, fail]);
  useEffect(() => () => { labelRequest.current?.abort(); kifuRequest.current?.abort(); }, []);
  const onSearchKifu = useCallback((query: string) => {
    kifuRequest.current?.abort();
    if (!authorized) return;
    const controller = new AbortController(); kifuRequest.current = controller;
    setKifu((previous) => ({ ...previous, query, loading: true, error: '' }));
    api.kifuSearch(query, controller.signal).then(
      (list) => { if (!controller.signal.aborted && active.current) setKifu({ query, list, error: '', loading: false }); },
      (cause: unknown) => {
        if (controller.signal.aborted || !active.current) return;
        if (cause instanceof AdminApiError && cause.status === 401) { fail(cause); return; }
        setKifu({ query, list: null, loading: false, error: cause instanceof Error ? cause.message : '棋谱库暂不可用。' });
      },
    );
  }, [api, authorized, fail]);

  return <VisionLivePage
    labelPreview={labelPreview} onLabel={onLabel}
    kifu={kifu} onSearchKifu={onSearchKifu}
    onImportKifu={(id, expectedStatus, expectedContext) => {
      if (statusSnapshot.current !== expectedStatus || operationContext.current !== expectedContext) return;
      void perform('导入棋谱', async (signal) => { const album = await api.kifuAlbum(id, signal); return api.visionImportSgf(album.sgf_content, signal); }, () => { setFrozen(null); setReview(null); setMessage('新会话已保存。先拍摄初始帧。'); });
    }}
    status={status} devices={devices} sessions={sessions} session={session} preview={preview}
    review={review} reviewFailure={reviewFailure} frozen={frozen} busy={busy} error={error} previewError={previewError} message={message} authorized={authorized} contextVersion={contextVersion}
    onRefresh={() => { void perform('读取状态', async () => undefined); }}
    onConnect={(id, selectedMode) => { void perform('连接摄像头', (signal) => api.visionConnect(id, selectedMode, signal)); }}
    onDisconnect={() => { void perform('断开连接', (signal) => api.visionDisconnect(signal)); }}
    onCalibrate={() => { void perform('空盘标定', (signal) => api.visionCalibrate(true, signal), () => setMessage('标定已保存；更换视角后须导入新会话，原会话几何不会被改写。')); }}
    onImport={(text, expectedStatus, expectedContext) => {
      if (statusSnapshot.current !== expectedStatus || operationContext.current !== expectedContext) return;
      void perform('导入棋谱', (signal) => api.visionImportSgf(text, signal), () => { setFrozen(null); setReview(null); setMessage('新会话已保存。先拍摄初始帧。'); });
    }}
    onResume={(id) => { void perform('恢复会话', (signal) => api.visionResumeSession(id, signal), () => { setFrozen(null); setReview(null); setMessage('会话已恢复。保存的标定须用当前网格复核。'); }); }}
    onPausePreview={setPreviewPaused}
    onVerify={(frame) => {
      if (!gameId || !preview || preview.frame_id !== frame) return;
      void perform('复核保存的标定', (signal) => api.visionVerifyGeometry(gameId, frame, true, signal));
    }}
    onCapture={(index, retake = false) => {
      if (!gameId) return;
      void perform(retake ? '重拍样本' : '采集当前手', (signal) => api.visionCapture({ game_id: gameId, move_index: index, operator_confirmed: true, overwrite_existing: retake }, signal), (frame) => {
        if (!frame.idempotent) setFrozen(null);
        setReview(null); setReviewFailure(null); setMessage(frame.idempotent ? '该手已有已核实样本，未重复写入。' : retake ? '样本已重拍；后续样本保留。' : '样本已保存并校验。');
      });
    }}
    onReview={(frame) => {
      const selected = session?.frames.find((item) => item.frame_id === frame);
      if (!gameId || !selected) return;
      void perform('检查样本', async (signal) => {
        try { return { sample: await api.visionReviewSample(gameId, frame, signal), failure: null }; }
        catch (cause) {
          if (signal.aborted || (cause instanceof AdminApiError && cause.status === 401)) throw cause;
          return { sample: null, failure: { frame: selected, message: cause instanceof Error ? cause.message : '样本检查失败。' } };
        }
      }, (result) => { setReview(result.sample); setReviewFailure(result.failure); }, false);
    }}
    onCloseReview={() => { setReview(null); setReviewFailure(null); }}
    onFreeze={() => {
      if (!gameId) return;
      void perform('冻结数据集', (signal) => api.visionFreezeSession(gameId, {}, signal), (result) => {
        setFrozen(result); setMessage(`只读版本 ${result.id} 已冻结；尚未上传。`);
      });
    }}
  />;
}
