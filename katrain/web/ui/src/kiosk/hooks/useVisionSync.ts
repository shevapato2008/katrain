import { useState, useEffect, useRef, useCallback } from 'react';
import { API } from '../../api';

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
  | 'board_lost';

export interface VisionSyncEvent {
  type: SyncEventType;
  data: Record<string, unknown>;
}

export interface VisionSyncState {
  syncEvents: VisionSyncEvent[];
  latestEvent: VisionSyncEvent | null;
  setupProgress: { matched: number; total: number } | null;
  isSetupComplete: boolean;
}

// ---- Hook ------------------------------------------------------------------

const MAX_EVENTS = 100;

export function useVisionSync(sessionId: string | null): VisionSyncState {
  const [syncEvents, setSyncEvents] = useState<VisionSyncEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<VisionSyncEvent | null>(null);
  const [setupProgress, setSetupProgress] = useState<{ matched: number; total: number } | null>(null);
  const [isSetupComplete, setIsSetupComplete] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const parsed: VisionSyncEvent = JSON.parse(event.data);
      setLatestEvent(parsed);
      setSyncEvents(prev => {
        const next = [...prev, parsed];
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
      });

      if (parsed.type === 'setup_progress') {
        const { matched, total } = parsed.data as { matched: number; total: number };
        setSetupProgress({ matched, total });
      } else if (parsed.type === 'setup_complete') {
        setIsSetupComplete(true);
        setSetupProgress(null);
      }
    } catch (err) {
      console.error('Failed to parse vision sync message', err);
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    const connect = async () => {
      try {
        // Bind this session on the vision backend before opening the WS.
        await API.visionBind(sessionId);
      } catch (err) {
        console.error('Vision bind failed', err);
        // Still try to open the WebSocket — the backend may already be bound.
      }

      if (cancelled) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/vision`);
      wsRef.current = ws;

      ws.onmessage = handleMessage;

      ws.onerror = (err) => {
        console.error('Vision WebSocket error', err);
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    };

    connect();

    return () => {
      cancelled = true;

      // Close the WebSocket connection first.
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // Unbind the session so the vision backend releases it.
      API.visionUnbind().catch((err) => {
        console.error('Vision unbind failed during cleanup', err);
      });

      // Reset local state for re-mount clarity.
      setSyncEvents([]);
      setLatestEvent(null);
      setSetupProgress(null);
      setIsSetupComplete(false);
    };
  }, [sessionId, handleMessage]);

  return { syncEvents, latestEvent, setupProgress, isSetupComplete };
}
