import { useState, useEffect, useRef, useCallback } from 'react';
import { API } from '../../api';
import { websocketUrl } from '../../utils/websocketUrl';

// ---- Types ----------------------------------------------------------------

export type SyncEventType =
  | 'board_diff'
  | 'setup_progress'
  | 'setup_complete'
  | 'sync_error'
  | 'move_detected'
  | 'board_reset'
  | 'move_confirmed'
  | 'degraded'
  | 'board_reacquired'
  | 'ambiguous_stone'
  | 'capture_pending'
  | 'captures_cleared'
  | 'illegal_change'
  | 'board_lost'
  | 'move_pending'
  | 'synced';

export interface VisionSyncEvent {
  seq: number; // frontend-local monotonic sequence (survives MAX_EVENTS trimming)
  type: SyncEventType;
  data: Record<string, unknown>;
}

export interface VisionSyncState {
  syncEvents: VisionSyncEvent[];
  latestEvent: VisionSyncEvent | null;
  setupProgress: { matched: number; total: number; missing: Array<[number, number]>; extra: Array<[number, number, number]> } | null;
  isSetupComplete: boolean;
  /** WS open. Consumers must not arm setup/move detection before this — the pump only
   *  fans out to already-registered connections, so events fired earlier are lost. */
  connected: boolean;
  bindState: 'idle' | 'preparing' | 'ready' | 'error';
  retryBind: () => Promise<boolean>;
}

// ---- Hook ------------------------------------------------------------------

const MAX_EVENTS = 100;

export function useVisionSync(sessionId: string | null, onBound?: (sessionId: string) => Promise<void>): VisionSyncState {
  const [syncEvents, setSyncEvents] = useState<VisionSyncEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<VisionSyncEvent | null>(null);
  const [setupProgress, setSetupProgress] = useState<{ matched: number; total: number; missing: Array<[number, number]>; extra: Array<[number, number, number]> } | null>(null);
  const [isSetupComplete, setIsSetupComplete] = useState(false);
  const [connected, setConnected] = useState(false);
  const [bindState, setBindState] = useState<VisionSyncState['bindState']>(sessionId ? 'preparing' : 'idle');
  const retryBindRef = useRef<() => Promise<boolean>>(async () => false);
  const retryBind = useCallback(() => retryBindRef.current(), []);

  const onBoundRef = useRef(onBound);
  useEffect(() => { onBoundRef.current = onBound; }, [onBound]);
  const wsRef = useRef<WebSocket | null>(null);
  const nextSeqRef = useRef(0);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const parsed = JSON.parse(event.data) as Omit<VisionSyncEvent, 'seq'>;
      const evt: VisionSyncEvent = { ...parsed, seq: nextSeqRef.current++ };
      setLatestEvent(evt);
      setSyncEvents(prev => {
        const next = [...prev, evt];
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
      });

      if (evt.type === 'setup_progress') {
        const { matched, total, missing, extra } = evt.data as {
          matched: number; total: number;
          missing?: Array<[number, number]>; extra?: Array<[number, number, number]>;
        };
        setSetupProgress({ matched, total, missing: missing ?? [], extra: extra ?? [] });
      } else if (evt.type === 'setup_complete') {
        setIsSetupComplete(true);
        setSetupProgress(null);
      }
    } catch (err) {
      console.error('Failed to parse vision sync message', err);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    let binding = false;
    const bind = async () => {
      if (!sessionId || binding || cancelled) return false;
      binding = true;
      setBindState('preparing');
      try {
        await API.visionBind(sessionId);
        if (cancelled) return false;
        await onBoundRef.current?.(sessionId);
        if (cancelled) return false;
        setBindState('ready');
        return true;
      } catch (err) {
        if (!cancelled) setBindState('error');
        console.error('Vision bind failed', err);
        return false;
      } finally {
        binding = false;
      }
    };
    retryBindRef.current = bind;

    const connect = async () => {
      if (sessionId) await bind();
      if (cancelled) return;

      /* `/ws/vision` 是盒端本地通道，服务端不鉴权（server.py 的 vision_websocket
         直接 accept），所以不传 token —— helper 在 token 缺席时不会拼空参数。 */
      const ws = new WebSocket(websocketUrl('/ws/vision'));
      wsRef.current = ws;
      ws.onopen = () => { if (!cancelled) setConnected(true); };
      ws.onmessage = handleMessage;
      ws.onerror = (err) => console.error('Vision WebSocket error', err);
      ws.onclose = () => { wsRef.current = null; setConnected(false); };
    };

    connect();

    return () => {
      cancelled = true;
      retryBindRef.current = async () => false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (sessionId) {
        API.visionUnbind().catch((err) => console.error('Vision unbind failed during cleanup', err));
      }
      setSyncEvents([]);
      setLatestEvent(null);
      setSetupProgress(null);
      setIsSetupComplete(false);
      setConnected(false);
      setBindState('idle');
    };
  }, [sessionId, handleMessage]);

  return { syncEvents, latestEvent, setupProgress, isSetupComplete, connected, bindState, retryBind };
}
