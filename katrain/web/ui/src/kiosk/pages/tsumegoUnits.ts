/**
 * Tsumego unit-grouping constants + the Phase 4 prev/next sequence contract.
 * Kept in a non-component module so the unit pages stay react-refresh clean.
 */

import { getCurrentKioskActivityStorage } from '../storage/kioskActivityStorage';

/** Problems per unit (matches galaxy D5). */
export const UNIT_SIZE = 20;

/**
 * sessionStorage key for the ordered full-category problem-id sequence.
 * Value = JSON.stringify(string[]) — problem ids in display order.
 * Phase 4 (TsumegoProblemPage) reads this to compute prev/next + boundaries.
 *
 * NOTE: the `kiosk_` prefix deliberately differs from galaxy's `problems_${level}_${category}`
 * key (galaxy stores ProblemListItem[] objects, kiosk stores string[]). Keeping them distinct
 * prevents the two build outputs from corrupting each other's cache if ever loaded in the same
 * browser (e.g. during dev), since the shared-zone hook is used by both.
 */
export const sequenceKey = (level: string, category: string) => `kiosk_problems_${level}_${category}`;

/**
 * localStorage key for the "auto-advance to next problem after solving" preference (D4).
 * Default is ON (true) when unset.
 *
 * Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): a per-user workflow
 * toggle, not a device property — routed through kioskActivityStorage (guest/unresolved ->
 * in-memory only; real user -> namespaced `${key}:${uuid}`), via the resolved-identity
 * singleton (same pattern as activeSession.ts — these are read post-mount, never a
 * synchronous first-paint snapshot, so the singleton's own empty-until-resolved default is
 * sufficient without per-page useAuth() gating).
 */
export const AUTO_ADVANCE_KEY = 'kiosk_tsumego_autoadvance';

/** Read the auto-advance preference. Defaults to true when unset / unparseable. */
export function readAutoAdvance(): boolean {
  try {
    const v = getCurrentKioskActivityStorage().getItem(AUTO_ADVANCE_KEY);
    if (v === null) return true; // default ON
    return v === 'true';
  } catch {
    return true;
  }
}

/** Persist the auto-advance preference. */
export function writeAutoAdvance(enabled: boolean): void {
  try {
    getCurrentKioskActivityStorage().setItem(AUTO_ADVANCE_KEY, enabled ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}

/** True when `level` (e.g. '3d') is a dan level, as opposed to a kyu level (e.g. '15k'). */
export function isDanLevel(level: string): boolean {
  return level.trim().toLowerCase().endsWith('d');
}

/** Chinese label for a level string, e.g. '15k' → '15 级', '3d' → '3 段'. */
export function levelChinese(level: string): string {
  const n = level.replace(/[^0-9]/g, '');
  return isDanLevel(level) ? `${n} 段` : `${n} 级`;
}

/**
 * localStorage key for the last difficulty level the user browsed into (hub 上次 highlight).
 * Single string, cheap to store — does NOT reintroduce the deliberately-omitted per-level
 * completion stat (R2 / §3.5): it's just a pointer, not progress data.
 *
 * Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): still prior-identity
 * ACTIVITY residue (which level a specific person was practicing), not a device property — so
 * it is routed through kioskActivityStorage exactly like AUTO_ADVANCE_KEY above (guest/
 * unresolved -> in-memory only; real user -> namespaced `${key}:${uuid}`).
 */
export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';

/** Read the last-practiced level, or null if never set / unavailable. */
export function readLastLevel(): string | null {
  try {
    return getCurrentKioskActivityStorage().getItem(LAST_LEVEL_KEY);
  } catch {
    return null;
  }
}

/** Persist the last-practiced level. */
export function writeLastLevel(level: string): void {
  try {
    getCurrentKioskActivityStorage().setItem(LAST_LEVEL_KEY, level);
  } catch {
    /* best-effort */
  }
}

/**
 * localStorage key for the "use physical board" preference (Phase B / Phase D).
 * Default is OFF (false) — opt-in for physical mode.
 *
 * Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): deliberately LEFT
 * GLOBAL, unlike AUTO_ADVANCE_KEY/LAST_LEVEL_KEY above — this reflects whether a physical
 * sensor board is actually wired to THIS kiosk unit (a hardware fact of the device), not a
 * per-account preference or activity residue, so identity-scoping it would be actively wrong
 * (every identity on this kiosk shares the same physical hardware).
 */
export const PHYSICAL_MODE_KEY = 'kiosk_tsumego_physical';

/** Read the "use physical board" preference. Defaults to FALSE (opt-in, T1). */
export function readPhysicalMode(): boolean {
  try {
    return localStorage.getItem(PHYSICAL_MODE_KEY) === 'true';
  } catch {
    return false;
  }
}

/** Persist the "use physical board" preference. */
export function writePhysicalMode(v: boolean): void {
  try {
    localStorage.setItem(PHYSICAL_MODE_KEY, v ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}
