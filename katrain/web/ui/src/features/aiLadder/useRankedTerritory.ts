import { useCallback, useEffect, useRef, useState } from 'react';
import type { EngineOverlay } from '../../components/Board';
import { getAiLadderTerritoryQuota, requestAiLadderTerritory, type AiLadderTerritoryResult } from './api';

type Phase = 'idle' | 'loading' | 'result' | 'error';
type View = { key: string; phase: Phase; visible: boolean; result?: AiLadderTerritoryResult };
type Scope = { accountKey?: string; gameId?: string; positionIdentity?: string };

/** One mounted page's current answer; hiding it never starts another paid request. */
export function useRankedTerritory(
  sessionId: string | undefined, enabled: boolean, nodeId: string | number | null | undefined,
  moveCount: number, scope: Scope = {},
) {
  const quotaKey = JSON.stringify([sessionId, scope.accountKey, scope.gameId]);
  const position = JSON.stringify([quotaKey, enabled, nodeId, moveCount, scope.positionIdentity]);
  const current = useRef({ position, generation: 0, quotaKey, quotaGeneration: 0 });
  if (current.current.position !== position) current.current = {
    position, generation: current.current.generation + 1, quotaKey,
    quotaGeneration: current.current.quotaGeneration + Number(current.current.quotaKey !== quotaKey),
  };
  const { generation, quotaGeneration } = current.current;
  const viewKey = `${generation}:${position}`;
  const [quota, setQuota] = useState<{ generation: number; remaining: number | null; inFlight: boolean }>({
    generation: quotaGeneration, remaining: null, inFlight: false,
  });
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const [view, setView] = useState<View>({ key: viewKey, phase: 'idle', visible: false });
  const viewRef = useRef(view);
  if (viewRef.current.key !== viewKey) viewRef.current = { key: viewKey, phase: 'idle', visible: false };
  const updateView = useCallback((next: View) => { viewRef.current = next; setView(next); }, []);
  const pendingRef = useRef<{ generation: number; quotaGeneration: number } | null>(null);
  const retryRef = useRef<{ key: string; id: string } | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const remaining = enabled && quota.generation === quotaGeneration ? quota.remaining : null;
  const remoteInFlight = enabled && quota.generation === quotaGeneration && quota.inFlight;

  useEffect(() => {
    if (!enabled || !sessionId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const response = await getAiLadderTerritoryQuota(sessionId, controller.signal);
        if (controller.signal.aborted || !mounted.current || current.current.quotaGeneration !== quotaGeneration) return;
        setQuota({ generation: quotaGeneration, remaining: response.remaining, inFlight: response.in_flight });
        if (response.in_flight) timer = setTimeout(refresh, 2000);
      } catch {
        if (controller.signal.aborted || !mounted.current || current.current.quotaGeneration !== quotaGeneration) return;
        setQuota((previous) => ({ generation: quotaGeneration,
          remaining: previous.generation === quotaGeneration ? previous.remaining : null, inFlight: false }));
        if (!viewRef.current.result && !pendingRef.current) updateView({ ...viewRef.current, phase: 'error' });
      }
    };
    void refresh();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [sessionId, enabled, quotaGeneration, quotaRefreshKey, updateView]);

  const dismiss = useCallback(() => updateView({ ...viewRef.current, visible: false }), [updateView]);
  const activate = useCallback(async () => {
    if (!enabled || !sessionId) return;
    const active = viewRef.current;
    // A cached answer or current pending view is a local toggle, even at quota zero.
    if (active.result || (active.phase === 'loading' && pendingRef.current?.generation === generation)) {
      updateView({ ...active, visible: !active.visible });
      return;
    }
    if (pendingRef.current?.quotaGeneration === quotaGeneration || remoteInFlight) {
      updateView({ ...active, phase: 'loading', visible: !active.visible });
      return;
    }
    if (remaining === 0 && retryRef.current?.key !== viewKey) return;
    const requestId = retryRef.current?.key === viewKey ? retryRef.current.id : crypto.randomUUID();
    retryRef.current = { key: viewKey, id: requestId };
    const pending = { generation, quotaGeneration };
    pendingRef.current = pending;
    updateView({ key: viewKey, phase: 'loading', visible: true });
    const sameQuota = () => mounted.current && current.current.quotaGeneration === quotaGeneration;
    const samePosition = () => sameQuota() && current.current.generation === generation;
    try {
      const result = await requestAiLadderTerritory(sessionId, requestId);
      if (!sameQuota()) return;
      setQuota({ generation: quotaGeneration, remaining: result.remaining, inFlight: false });
      if (retryRef.current?.key === viewKey) retryRef.current = null;
      if (!samePosition()) return;
      if (result.stale || result.move_count !== moveCount) {
        updateView({ key: viewKey, phase: 'idle', visible: false });
        return;
      }
      updateView({ key: viewKey, phase: 'result', result, visible: viewRef.current.visible });
    } catch {
      if (!sameQuota()) return;
      if (samePosition()) updateView({ key: viewKey, phase: 'error', visible: viewRef.current.visible });
      setQuotaRefreshKey((key) => key + 1);
    } finally {
      if (pendingRef.current === pending) pendingRef.current = null;
      if (sameQuota() && !samePosition() && viewRef.current.phase === 'loading') {
        updateView({ ...viewRef.current, phase: 'idle', visible: false });
      }
    }
  }, [enabled, sessionId, generation, quotaGeneration, remoteInFlight, remaining, viewKey, moveCount, updateView]);

  const active = enabled && view.key === viewKey ? view : undefined;
  const phase: Phase = active?.phase && active.phase !== 'idle' ? active.phase : remoteInFlight ? 'loading' : 'idle';
  const result = active?.result;
  const visible = !!active?.visible;
  const overlay: EngineOverlay | null = visible && result && result.ownership.length === 361
    ? { kind: 'area', ownership: result.ownership.map((value, index) => ({
      col: index % 19, row: 18 - Math.floor(index / 19), value,
    })) } : null;

  return { remaining, phase, result, visible, overlay, activate, request: activate, dismiss,
    retrySameRequest: retryRef.current?.key === viewKey,
    disabled: !enabled || !sessionId || (!result && phase !== 'loading' && remaining === 0 && retryRef.current?.key !== viewKey) };
}
