import { useCallback, useEffect, useRef, useState } from 'react';
import type { EngineOverlay } from '../../components/Board';
import {
  getAiLadderTerritoryQuota,
  requestAiLadderTerritory,
  type AiLadderTerritoryResult,
} from './api';

type Phase = 'idle' | 'loading' | 'result' | 'error';
type View = { position: string; phase: Phase; result?: AiLadderTerritoryResult };

/** A territory answer belongs to one session and one board node, including while the request is pending. */
export function useRankedTerritory(sessionId: string | undefined, enabled: boolean, nodeId: string | number | null | undefined, moveCount: number) {
  const position = `${sessionId ?? ''}|${nodeId ?? ''}|${moveCount}`;
  const positionRef = useRef(position);
  positionRef.current = position;
  const [remaining, setRemaining] = useState<number | null>(null);
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const [remoteInFlight, setRemoteInFlight] = useState(false);
  const [view, setView] = useState<View>({ position, phase: 'idle' });
  const pendingRef = useRef(false);
  const retryRef = useRef<{ position: string; id: string } | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const quota = await getAiLadderTerritoryQuota(sessionId, controller.signal);
        if (controller.signal.aborted) return;
        setRemaining(quota.remaining);
        setRemoteInFlight(quota.in_flight);
        if (quota.in_flight) timer = setTimeout(refresh, 2000);
      } catch {
        if (!controller.signal.aborted) {
          setRemoteInFlight(false);
          setView({ position: positionRef.current, phase: 'error' });
        }
      }
    };
    void refresh();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [sessionId, enabled, quotaRefreshKey]);

  const request = useCallback(async () => {
    if (!enabled || !sessionId || pendingRef.current || remoteInFlight) return;
    const requestedPosition = positionRef.current;
    if (remaining === 0 && retryRef.current?.position !== requestedPosition) return;
    const requestId = retryRef.current?.position === requestedPosition
      ? retryRef.current.id : crypto.randomUUID();
    retryRef.current = { position: requestedPosition, id: requestId };
    pendingRef.current = true;
    setView({ position: requestedPosition, phase: 'loading' });
    try {
      const result = await requestAiLadderTerritory(sessionId, requestId);
      setRemaining(result.remaining);
      retryRef.current = null;
      if (positionRef.current !== requestedPosition) return;
      if (result.stale || result.move_count !== moveCount) {
        setView({ position: requestedPosition, phase: 'idle' });
        return;
      }
      setView({ position: requestedPosition, phase: 'result', result });
    } catch {
      if (positionRef.current === requestedPosition) setView({ position: requestedPosition, phase: 'error' });
      setQuotaRefreshKey((key) => key + 1);
    } finally {
      pendingRef.current = false;
    }
  }, [enabled, sessionId, remoteInFlight, remaining, moveCount]);

  const phase: Phase = !enabled ? 'idle' : remoteInFlight ? 'loading'
    : view.position === position ? view.phase : 'idle';
  const result = phase === 'result' ? view.result : undefined;
  const overlay: EngineOverlay | null = result && result.ownership.length === 361
    ? { kind: 'area', ownership: result.ownership.map((value, index) => ({
      col: index % 19, row: 18 - Math.floor(index / 19), value,
    })) }
    : null;

  return { remaining: enabled ? remaining : null, phase, result, overlay, request,
    retrySameRequest: retryRef.current?.position === position,
    disabled: !enabled || pendingRef.current || remoteInFlight
      || (remaining === 0 && retryRef.current?.position !== position) };
}
