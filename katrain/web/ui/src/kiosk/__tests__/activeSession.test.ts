import { describe, it, expect, beforeEach } from 'vitest';
import { readActiveSession, writeActiveSession, clearActiveSession, type ActiveSession } from '../utils/activeSession';
import { setKioskIdentity, __resetKioskActivityStorageForTests } from '../storage/kioskActivityStorage';

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = String(v); },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

const sample: ActiveSession = {
  kind: 'game', label: '自由对弈 · 执黑', route: '/kiosk/play/ai/game/abc', ts: 1_720_000_000_000,
};

const ALICE = 'alice-uuid';

describe('activeSession — real, resolved identity (namespaced localStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
    __resetKioskActivityStorageForTests();
    setKioskIdentity(ALICE, false);
  });

  it('returns null when nothing is stored', () => {
    expect(readActiveSession('game')).toBeNull();
    expect(readActiveSession('practice')).toBeNull();
  });

  it('round-trips a game session under kiosk_active_game:{uuid}, not the raw key', () => {
    writeActiveSession(sample);
    expect(localStorage.getItem(`kiosk_active_game:${ALICE}`)).toContain('/kiosk/play/ai/game/abc');
    expect(localStorage.getItem('kiosk_active_game')).toBeNull();
    expect(readActiveSession('game')).toEqual(sample);
  });

  it('keeps game and practice slots independent', () => {
    writeActiveSession(sample);
    expect(readActiveSession('practice')).toBeNull();
  });

  it('clearActiveSession removes only its slot', () => {
    writeActiveSession(sample);
    writeActiveSession({ ...sample, kind: 'practice', route: '/kiosk/tsumego/problem/9' });
    clearActiveSession('game');
    expect(readActiveSession('game')).toBeNull();
    expect(readActiveSession('practice')).not.toBeNull();
  });

  it('returns null on corrupt JSON', () => {
    localStorage.setItem(`kiosk_active_game:${ALICE}`, '{not json');
    expect(readActiveSession('game')).toBeNull();
  });

  it('rejects a blob whose kind mismatches the slot', () => {
    localStorage.setItem(`kiosk_active_practice:${ALICE}`, JSON.stringify({ ...sample, kind: 'game' }));
    expect(readActiveSession('practice')).toBeNull();
  });

  it('a different uuid reads empty even though Alice has an active session', () => {
    writeActiveSession(sample);
    setKioskIdentity('bob-uuid', false);
    expect(readActiveSession('game')).toBeNull();
  });
});

describe('activeSession — guest / unresolved identity (in-memory only)', () => {
  beforeEach(() => {
    localStorage.clear();
    __resetKioskActivityStorageForTests();
  });

  it('a guest never persists an active session to localStorage', () => {
    setKioskIdentity(null, true);
    writeActiveSession(sample);
    expect(readActiveSession('game')).toEqual(sample); // in-memory round-trip still works
    expect(localStorage.getItem('kiosk_active_game')).toBeNull();
    for (let i = 0; i < localStorage.length; i++) {
      expect(localStorage.key(i)!.startsWith('kiosk_active_')).toBe(false);
    }
  });

  it('a guest does not read a prior real user active session', () => {
    setKioskIdentity(ALICE, false);
    writeActiveSession(sample);
    setKioskIdentity(null, true);
    expect(readActiveSession('game')).toBeNull();
  });

  it('before setKioskIdentity is ever called (unresolved), reads/writes stay in-memory only', () => {
    writeActiveSession(sample); // identity never resolved in this test
    expect(readActiveSession('game')).toEqual(sample);
    expect(localStorage.getItem('kiosk_active_game')).toBeNull();
  });
});
