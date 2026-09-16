import { describe, it, expect, beforeEach } from 'vitest';
import {
  kioskActivityStorage,
  migrateLegacyActivityKey,
  setKioskIdentity,
  getCurrentKioskActivityStorage,
  __resetKioskActivityStorageForTests,
} from './kioskActivityStorage';

beforeEach(() => {
  localStorage.clear();
  __resetKioskActivityStorageForTests();
});

describe('kioskActivityStorage — guest / unresolved (in-memory only)', () => {
  it('a guest never touches localStorage', () => {
    const store = kioskActivityStorage(null, true);
    store.setItem('tsumego_progress', JSON.stringify({ p1: { completed: true } }));
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
    expect(store.getItem('tsumego_progress')).toBe(JSON.stringify({ p1: { completed: true } }));
  });

  it('an unresolved identity (identityKey=null, isGuest=false) also never touches localStorage', () => {
    const store = kioskActivityStorage(null, false);
    store.setItem('tsumego_progress', 'x');
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
  });

  it('a guest does not read a prior real user data seeded under the raw key', () => {
    localStorage.setItem('tsumego_progress', JSON.stringify({ p1: { completed: true } }));
    localStorage.setItem('tsumego_progress:alice-uuid', JSON.stringify({ p2: { completed: true } }));
    const store = kioskActivityStorage(null, true);
    expect(store.getItem('tsumego_progress')).toBeNull();
  });

  it('removeItem on the guest store never removes a real localStorage key', () => {
    localStorage.setItem('tsumego_progress', 'real-data');
    const store = kioskActivityStorage(null, true);
    store.removeItem('tsumego_progress');
    expect(localStorage.getItem('tsumego_progress')).toBe('real-data');
  });
});

describe('kioskActivityStorage — real user (namespaced localStorage)', () => {
  it('writes under `${key}:${identityKey}`, not the raw key', () => {
    const store = kioskActivityStorage('alice-uuid', false);
    store.setItem('tsumego_progress', 'alice-data');
    expect(localStorage.getItem('tsumego_progress:alice-uuid')).toBe('alice-data');
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
  });

  it('a different uuid reads empty', () => {
    const alice = kioskActivityStorage('alice-uuid', false);
    alice.setItem('tsumego_progress', 'alice-data');
    const bob = kioskActivityStorage('bob-uuid', false);
    expect(bob.getItem('tsumego_progress')).toBeNull();
  });

  it('isGuest=true always wins over a non-null identityKey (defense in depth)', () => {
    const store = kioskActivityStorage('alice-uuid', true);
    store.setItem('tsumego_progress', 'x');
    expect(localStorage.getItem('tsumego_progress:alice-uuid')).toBeNull();
  });
});

describe('migrateLegacyActivityKey', () => {
  it('copies the legacy unscoped key under the namespace, then deletes the legacy key', () => {
    localStorage.setItem('tsumego_progress', 'legacy-data');
    const store = kioskActivityStorage('alice-uuid', false);
    migrateLegacyActivityKey(store, 'tsumego_progress');
    expect(store.getItem('tsumego_progress')).toBe('legacy-data');
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
  });

  it('is a no-op when there is no legacy key', () => {
    const store = kioskActivityStorage('alice-uuid', false);
    migrateLegacyActivityKey(store, 'tsumego_progress');
    expect(store.getItem('tsumego_progress')).toBeNull();
  });

  it('does not overwrite existing namespaced data, but still deletes the legacy key', () => {
    localStorage.setItem('tsumego_progress', 'legacy-data');
    localStorage.setItem('tsumego_progress:alice-uuid', 'already-migrated');
    const store = kioskActivityStorage('alice-uuid', false);
    migrateLegacyActivityKey(store, 'tsumego_progress');
    expect(store.getItem('tsumego_progress')).toBe('already-migrated');
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
  });
});

describe('resolved-identity singleton', () => {
  it('defaults to the ephemeral store before setKioskIdentity is ever called', () => {
    localStorage.setItem('tsumego_progress', 'real-data');
    expect(getCurrentKioskActivityStorage().getItem('tsumego_progress')).toBeNull();
  });

  it('setKioskIdentity(uuid, false) switches the singleton to namespaced localStorage', () => {
    setKioskIdentity('alice-uuid', false);
    getCurrentKioskActivityStorage().setItem('tsumego_progress', 'alice-data');
    expect(localStorage.getItem('tsumego_progress:alice-uuid')).toBe('alice-data');
  });

  it('setKioskIdentity(null, true) (guest) switches the singleton to the ephemeral store', () => {
    setKioskIdentity('alice-uuid', false);
    setKioskIdentity(null, true);
    getCurrentKioskActivityStorage().setItem('tsumego_progress', 'guest-data');
    expect(localStorage.getItem('tsumego_progress')).toBeNull();
    expect(localStorage.getItem('tsumego_progress:alice-uuid')).toBeNull();
  });

  it('re-resolving the same identity does not rebuild the store (idempotent)', () => {
    setKioskIdentity('alice-uuid', false);
    const first = getCurrentKioskActivityStorage();
    setKioskIdentity('alice-uuid', false);
    expect(getCurrentKioskActivityStorage()).toBe(first);
  });
});
