/**
 * Tsumego unit-grouping constants + the Phase 4 prev/next sequence contract.
 * Kept in a non-component module so the unit pages stay react-refresh clean.
 */

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
 */
export const AUTO_ADVANCE_KEY = 'kiosk_tsumego_autoadvance';

/** Read the auto-advance preference. Defaults to true when unset / unparseable. */
export function readAutoAdvance(): boolean {
  try {
    const v = localStorage.getItem(AUTO_ADVANCE_KEY);
    if (v === null) return true; // default ON
    return v === 'true';
  } catch {
    return true;
  }
}

/** Persist the auto-advance preference. */
export function writeAutoAdvance(enabled: boolean): void {
  try {
    localStorage.setItem(AUTO_ADVANCE_KEY, enabled ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}
