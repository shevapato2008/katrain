export interface LocalMoveSubmission {
  input: 'screen' | 'physical';
  action: 'move' | 'pass';
  coords: [number, number] | null;
  request_id: string;
}

interface Options {
  scope: string;
  input: 'screen' | 'physical';
  enabled: boolean;
  recognizing: boolean;
  submit: (request: LocalMoveSubmission) => Promise<{ accepted: boolean }>;
}

export function useLocalMoveConfirmation({ scope, input, enabled, recognizing, submit }: Options) {
  const [draft, setDraft] = useState({ scope, point: null as { x: number; y: number } | null, sending: false, failed: false });
  const inFlight = useRef<{ scope: string; id: string } | null>(null);
  const retryRequest = useRef<{ key: string; id: string } | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  // A node/session change invalidates the draft synchronously, including the first
  // frame after a WebSocket update; it never becomes part of gameState.stones.
  if (draft.scope !== scope) setDraft({ scope, point: null, sending: false, failed: false });
  const current = draft.scope === scope ? draft : { point: null, sending: false, failed: false };
  const busy = current.sending || recognizing;

  const select = (x: number, y: number) => {
    if (!enabled || input !== 'screen' || recognizing || inFlight.current?.scope === scope) return;
    retryRequest.current = null;
    setDraft({ scope, point: { x, y }, sending: false, failed: false });
  };
  const send = async (action: 'move' | 'pass') => {
    if (!enabled || recognizing || inFlight.current?.scope === scope) return;
    if (action === 'move' && input === 'screen' && !current.point) return;
    const coords: [number, number] | null = action === 'move' && input === 'screen' && current.point
      ? [current.point.x, current.point.y] : null;
    const key = JSON.stringify([scope, input, action, coords]);
    const id = retryRequest.current?.key === key ? retryRequest.current.id : crypto.randomUUID();
    retryRequest.current = { key, id };
    const attempt = { scope, id };
    inFlight.current = attempt;
    setDraft((previous) => previous.scope === scope ? { ...previous, sending: true, failed: false } : previous);
    try {
      const result = await submit({ input, action, coords, request_id: id });
      if (retryRequest.current?.id === id) retryRequest.current = null;
      if (mounted.current) setDraft((previous) => previous.scope === scope
        ? { ...previous, point: result.accepted ? null : previous.point, failed: !result.accepted } : previous);
    } catch {
      // Keep the same id after a transport failure: retry can retrieve a committed
      // result instead of submitting a second move when the first reply was lost.
      if (mounted.current) setDraft((previous) => previous.scope === scope ? { ...previous, failed: true } : previous);
    } finally {
      if (inFlight.current === attempt) inFlight.current = null;
      if (mounted.current) setDraft((previous) => previous.scope === scope ? { ...previous, sending: false } : previous);
    }
  };
  return { point: current.point, busy, failed: current.failed, select, confirm: () => send('move'), pass: () => send('pass') };
}
import { useEffect, useRef, useState } from 'react';

