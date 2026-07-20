import { getCurrentKioskActivityStorage } from '../storage/kioskActivityStorage';

/** Persisted "continue where you left off" pointer for 对弈 / 死活 (contract §Active-session). */
export type ActiveSessionKind = 'game' | 'practice';

export interface ActiveSession {
  kind: ActiveSessionKind;
  label: string;
  route: string;
  ts: number;
}

const KEY: Record<ActiveSessionKind, string> = {
  game: 'kiosk_active_game',
  practice: 'kiosk_active_practice',
};

// Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): routed through the
// kioskActivityStorage resolved-identity singleton — a guest (or any unresolved identity)
// reads/writes an in-memory-only namespace, never localStorage; a real user gets
// `${KEY}:${user.uuid}` in localStorage. AuthContext is the single writer of the singleton
// (see kioskActivityStorage.ts); every caller here is a plain render-time read or an
// event/effect-triggered write (never a lazy useState/useMemo first-paint snapshot), so
// relying on the singleton (rather than each page threading identity through explicitly) is
// safe — see the design note in kioskActivityStorage.ts.

export function readActiveSession(kind: ActiveSessionKind): ActiveSession | null {
  try {
    const raw = getCurrentKioskActivityStorage().getItem(KEY[kind]);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<ActiveSession>;
    if (
      p && p.kind === kind &&
      typeof p.label === 'string' &&
      typeof p.route === 'string' &&
      typeof p.ts === 'number'
    ) {
      return p as ActiveSession;
    }
    return null;
  } catch {
    return null;
  }
}

export function writeActiveSession(s: ActiveSession): void {
  try {
    getCurrentKioskActivityStorage().setItem(KEY[s.kind], JSON.stringify(s));
  } catch {
    /* best-effort */
  }
}

export function clearActiveSession(kind: ActiveSessionKind): void {
  try {
    getCurrentKioskActivityStorage().removeItem(KEY[kind]);
  } catch {
    /* best-effort */
  }
}
