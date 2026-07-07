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

export function readActiveSession(kind: ActiveSessionKind): ActiveSession | null {
  try {
    const raw = localStorage.getItem(KEY[kind]);
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
    localStorage.setItem(KEY[s.kind], JSON.stringify(s));
  } catch {
    /* best-effort */
  }
}

export function clearActiveSession(kind: ActiveSessionKind): void {
  try {
    localStorage.removeItem(KEY[kind]);
  } catch {
    /* best-effort */
  }
}
