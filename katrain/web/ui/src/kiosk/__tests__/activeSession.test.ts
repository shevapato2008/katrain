import { describe, it, expect, beforeEach } from 'vitest';
import { readActiveSession, writeActiveSession, clearActiveSession, type ActiveSession } from '../utils/activeSession';

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

describe('activeSession', () => {
  beforeEach(() => localStorage.clear());

  it('returns null when nothing is stored', () => {
    expect(readActiveSession('game')).toBeNull();
    expect(readActiveSession('practice')).toBeNull();
  });

  it('round-trips a game session under kiosk_active_game', () => {
    writeActiveSession(sample);
    expect(localStorage.getItem('kiosk_active_game')).toContain('/kiosk/play/ai/game/abc');
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
    localStorage.setItem('kiosk_active_game', '{not json');
    expect(readActiveSession('game')).toBeNull();
  });

  it('rejects a blob whose kind mismatches the slot', () => {
    localStorage.setItem('kiosk_active_practice', JSON.stringify({ ...sample, kind: 'game' }));
    expect(readActiveSession('practice')).toBeNull();
  });
});
