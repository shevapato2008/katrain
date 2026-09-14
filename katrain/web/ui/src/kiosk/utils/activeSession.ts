/** Persisted "continue where you left off" pointer for 对弈 / 死活 (contract §Active-session). */
export type ActiveSessionKind = 'game' | 'practice';

export interface ActiveSession {
  kind: ActiveSessionKind;
  label: string;
  route: string;
  ts: number;
  /**
   * 这一局下不下实体盘 —— 开局设置屏在按下「开始对局」那一刻用 `playInputState(...).onBoard`
   * 算出来写进来(设备能用 ∧ 偏好开着 ∧ 19 路)。对局路由外的 `PlayInputGuard` 和 `GamePage`
   * 都读它,不再各自判断(v2 §3.5 / P8)。**可选**:旧版本写下的记录没有它,读的一方回落偏好。
   */
  onBoard?: boolean;
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
      // onBoard 可选,不参与有效性判断 —— 见接口注释。
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
