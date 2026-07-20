import { describe, it, expect, beforeEach } from 'vitest';
import {
  AUTO_ADVANCE_KEY,
  LAST_LEVEL_KEY,
  readAutoAdvance,
  writeAutoAdvance,
  readLastLevel,
  writeLastLevel,
} from '../pages/tsumegoUnits';
import { setKioskIdentity, __resetKioskActivityStorageForTests } from '../storage/kioskActivityStorage';

// Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): AUTO_ADVANCE_KEY and
// LAST_LEVEL_KEY are per-user activity/workflow residue (which level someone was practicing,
// whether they like auto-advance), not device properties — unlike PHYSICAL_MODE_KEY (still
// global; see PhysicalModeToggle.test.tsx) and kioskPlaySound (still global; see
// PvpLocalSetupPage.tsx). Both are routed through kioskActivityStorage via the
// resolved-identity singleton, exactly like activeSession.ts.

const ALICE = 'alice-uuid';
const BOB = 'bob-uuid';

beforeEach(() => {
  localStorage.clear();
  __resetKioskActivityStorageForTests();
});

describe('readAutoAdvance / writeAutoAdvance — real, resolved identity', () => {
  beforeEach(() => setKioskIdentity(ALICE, false));

  it('defaults to true (ON) when unset', () => {
    expect(readAutoAdvance()).toBe(true);
  });

  it('round-trips under kiosk_tsumego_autoadvance:{uuid}, not the raw key', () => {
    writeAutoAdvance(false);
    expect(readAutoAdvance()).toBe(false);
    expect(localStorage.getItem(`${AUTO_ADVANCE_KEY}:${ALICE}`)).toBe('false');
    expect(localStorage.getItem(AUTO_ADVANCE_KEY)).toBeNull();
  });

  it('a different uuid (Bob) does not see Alice\'s preference', () => {
    writeAutoAdvance(false);
    setKioskIdentity(BOB, false);
    expect(readAutoAdvance()).toBe(true); // Bob's default, not Alice's `false`
  });
});

describe('readLastLevel / writeLastLevel — real, resolved identity', () => {
  beforeEach(() => setKioskIdentity(ALICE, false));

  it('returns null when unset', () => {
    expect(readLastLevel()).toBeNull();
  });

  it('round-trips under kiosk_tsumego_last_level:{uuid}, not the raw key', () => {
    writeLastLevel('5d');
    expect(readLastLevel()).toBe('5d');
    expect(localStorage.getItem(`${LAST_LEVEL_KEY}:${ALICE}`)).toBe('5d');
    expect(localStorage.getItem(LAST_LEVEL_KEY)).toBeNull();
  });

  it('a different uuid (Bob) reads null even though Alice has a last-practiced level', () => {
    writeLastLevel('5d');
    setKioskIdentity(BOB, false);
    expect(readLastLevel()).toBeNull();
  });
});

describe('guest / unresolved identity — in-memory only, never leaks prior real user data', () => {
  it('a guest writing autoadvance leaves no kiosk_tsumego_autoadvance key in localStorage', () => {
    setKioskIdentity(null, true);
    writeAutoAdvance(false);
    expect(readAutoAdvance()).toBe(false); // in-memory round-trip still works
    for (let i = 0; i < localStorage.length; i++) {
      expect(localStorage.key(i)!.startsWith(AUTO_ADVANCE_KEY)).toBe(false);
    }
    expect(localStorage.getItem(AUTO_ADVANCE_KEY)).toBeNull();
  });

  it('a guest writing last_level leaves no kiosk_tsumego_last_level key in localStorage', () => {
    setKioskIdentity(null, true);
    writeLastLevel('5d');
    expect(readLastLevel()).toBe('5d'); // in-memory round-trip still works
    for (let i = 0; i < localStorage.length; i++) {
      expect(localStorage.key(i)!.startsWith(LAST_LEVEL_KEY)).toBe(false);
    }
    expect(localStorage.getItem(LAST_LEVEL_KEY)).toBeNull();
  });

  it('a guest does not read a prior real user autoadvance preference', () => {
    setKioskIdentity(ALICE, false);
    writeAutoAdvance(false);
    setKioskIdentity(null, true);
    expect(readAutoAdvance()).toBe(true); // guest's default, not Alice's `false`
  });

  it('a guest does not read a prior real user last-practiced level', () => {
    setKioskIdentity(ALICE, false);
    writeLastLevel('5d');
    setKioskIdentity(null, true);
    expect(readLastLevel()).toBeNull();
  });

  it('before setKioskIdentity is ever called (unresolved), reads/writes stay in-memory only', () => {
    writeAutoAdvance(false); // identity never resolved in this test
    writeLastLevel('3k');
    expect(readAutoAdvance()).toBe(false);
    expect(readLastLevel()).toBe('3k');
    expect(localStorage.getItem(AUTO_ADVANCE_KEY)).toBeNull();
    expect(localStorage.getItem(LAST_LEVEL_KEY)).toBeNull();
  });
});
