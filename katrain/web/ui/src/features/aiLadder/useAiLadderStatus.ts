import { useCallback, useEffect, useRef, useState } from 'react';
import { getAiLadderStatus } from './api';
import type { AiLadderStatus } from './types';

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
      setStatus({
        view_state: 'error',
        message: error instanceof Error ? error.message : 'Failed to load AI ladder status',
      });
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
