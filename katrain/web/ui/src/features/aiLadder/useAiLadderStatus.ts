import { useCallback, useEffect, useRef, useState } from 'react';
import { AiLadderApiError, getAiLadderStatus } from './api';
import { AI_LADDER_COPY } from './copy';
import type { AiLadderStatus } from './types';

/**
 * The message the player sees. The server's `detail` is English operator text
 * ("Ranked AI ladder authority is unavailable on this node") and was being rendered
 * verbatim on a Chinese kiosk, so translate the cases we actually produce and fall back
 * to a generic line rather than leaking the raw body.
 */
export const aiLadderStatusErrorMessage = (error: unknown): string => {
  if (error instanceof AiLadderApiError) {
    if (error.status === 503) return AI_LADDER_COPY.loadErrorNotAuthoritative;
    if (error.status === 401 || error.status === 403) return AI_LADDER_COPY.loadErrorUnauthorized;
  }
  return AI_LADDER_COPY.loadError;
};

export const useAiLadderStatus = (token?: string, enabled = true) => {
  const [status, setStatus] = useState<AiLadderStatus>({ view_state: 'loading' });
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!enabled) return;
    const requestGeneration = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setStatus({ view_state: 'loading' });
    try {
      const next = await getAiLadderStatus(token, controller.signal);
      if (!controller.signal.aborted && generation.current === requestGeneration) setStatus(next);
    } catch (error) {
      if (controller.signal.aborted || generation.current !== requestGeneration) return;
      setStatus({ view_state: 'error', message: aiLadderStatusErrorMessage(error) });
    }
  }, [enabled, token]);

  useEffect(() => {
    void load();
    return () => {
      generation.current += 1;
      activeRequest.current?.abort();
    };
  }, [load]);

  return { status, retry: load };
};
