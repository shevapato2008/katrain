import { useEffect, useState, type ReactNode } from 'react';
import { API } from '../../api';
import {
  EngineReadinessContext,
  type EngineReadiness,
} from './EngineReadinessContext';

const POLL_MS = 2_000;
const UNAVAILABLE_AFTER_MS = 120_000;

export function EngineReadinessProvider({ children }: { children: ReactNode }) {
  const [readiness, setReadiness] = useState<EngineReadiness>('warming');

  useEffect(() => {
    const mountedAt = Date.now();
    let active = true;
    let timer: ReturnType<typeof window.setTimeout> | undefined;

    const poll = async () => {
      let reachable = false;
      try {
        const health = await API.engineHealth();
        reachable = health?.engines?.local === 'reachable';
      } catch {
        reachable = false;
      }

      if (!active) return;
      if (reachable) {
        setReadiness('ready');
        return;
      }

      setReadiness(Date.now() - mountedAt >= UNAVAILABLE_AFTER_MS ? 'unavailable' : 'warming');
      timer = window.setTimeout(poll, POLL_MS);
    };

    void poll();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  return (
    <EngineReadinessContext.Provider value={readiness}>
      {children}
    </EngineReadinessContext.Provider>
  );
}
