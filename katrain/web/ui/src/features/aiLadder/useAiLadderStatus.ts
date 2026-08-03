import { useCallback, useEffect, useState } from 'react';
import { getAiLadderStatus } from './api';
import type { AiLadderStatus } from './types';

export const useAiLadderStatus = (token?: string, enabled = true) => {
  const [status, setStatus] = useState<AiLadderStatus>({ view_state: 'loading' });

  const load = useCallback(async () => {
    if (!enabled) return;
    setStatus({ view_state: 'loading' });
    try {
      setStatus(await getAiLadderStatus(token));
    } catch (error) {
      setStatus({
        view_state: 'error',
        message: error instanceof Error ? error.message : 'Failed to load AI ladder status',
      });
    }
  }, [enabled, token]);

  useEffect(() => { void load(); }, [load]);

  return { status, retry: load };
};
