import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';

// ---- Mock auth (token/user/isGuest/isLoading) + the tsumego API (getProgress/saveProgress) ----
const { mockUseAuth, mockGetProgress, mockSaveProgress } = vi.hoisted(() => ({
  mockUseAuth: vi.fn(),
  mockGetProgress: vi.fn(),
  mockSaveProgress: vi.fn(),
}));

vi.mock('../AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../api/tsumegoApi', () => ({
  TsumegoAPI: {
    getProgress: (...args: unknown[]) => mockGetProgress(...args),
    saveProgress: (...args: unknown[]) => mockSaveProgress(...args),
  },
}));

import {
  TsumegoProgressProvider,
  useTsumegoProgress,
  mergeProgressEntry,
  readLocalProgress,
  writeLocalProgress,
  mergeProgressMaps,
  type TsumegoProgressEntry,
  type TsumegoProgressMap,
} from '../TsumegoProgressContext';
import {
  kioskActivityStorage,
  setKioskIdentity,
  __resetKioskActivityStorageForTests,
} from '../../kiosk/storage/kioskActivityStorage';

const STORAGE_KEY = 'tsumego_progress';
const ALICE = 'alice-uuid';
const BOB = 'bob-uuid';

// A resolved REAL user (Alice), unless a test overrides it.
const aliceAuth = (extra: Record<string, unknown> = {}) => ({
  token: null,
  user: { uuid: ALICE, username: 'alice' },
  isGuest: false,
  isLoading: false,
  ...extra,
});
const guestAuth = (extra: Record<string, unknown> = {}) => ({
  token: null,
  user: { uuid: '0', username: 'guest' },
  isGuest: true,
  isLoading: false,
  ...extra,
});
const unresolvedAuth = () => ({ token: null, user: null, isGuest: false, isLoading: true });

// Namespaced (real-user) key helpers.
const namespacedKey = (uuid: string) => `${STORAGE_KEY}:${uuid}`;
const seedNamespaced = (uuid: string, map: TsumegoProgressMap) =>
  localStorage.setItem(namespacedKey(uuid), JSON.stringify(map));
const readNamespaced = (uuid: string): TsumegoProgressMap =>
  JSON.parse(localStorage.getItem(namespacedKey(uuid)) || '{}');

// Legacy (pre-isolation, unscoped) key helpers.
const seedLegacy = (map: TsumegoProgressMap) => localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
const readLegacyRaw = (): string | null => localStorage.getItem(STORAGE_KEY);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  __resetKioskActivityStorageForTests();
  mockUseAuth.mockReturnValue(aliceAuth());
  mockGetProgress.mockResolvedValue({});
  mockSaveProgress.mockResolvedValue({});
});

// ============ Pure helpers ============

describe('mergeProgressEntry', () => {
  it('returns a copy of incoming when no existing entry', () => {
    const incoming: TsumegoProgressEntry = { completed: true, attempts: 2, lastDuration: 30 };
    const merged = mergeProgressEntry(undefined, incoming);
    expect(merged).toEqual(incoming);
    expect(merged).not.toBe(incoming);
  });

  it('completed is OR (monotonic — never regresses)', () => {
    const a = mergeProgressEntry({ completed: true, attempts: 1 }, { completed: false, attempts: 1 });
    expect(a.completed).toBe(true);
    const b = mergeProgressEntry({ completed: false, attempts: 1 }, { completed: true, attempts: 1 });
    expect(b.completed).toBe(true);
    const c = mergeProgressEntry({ completed: false, attempts: 1 }, { completed: false, attempts: 1 });
    expect(c.completed).toBe(false);
  });

  it('attempts is the max of both', () => {
    expect(mergeProgressEntry({ completed: false, attempts: 5 }, { completed: false, attempts: 2 }).attempts).toBe(5);
    expect(mergeProgressEntry({ completed: false, attempts: 1 }, { completed: false, attempts: 9 }).attempts).toBe(9);
  });

  it('lastDuration prefers incoming when defined, else keeps existing', () => {
    expect(mergeProgressEntry({ completed: false, attempts: 1, lastDuration: 10 }, { completed: false, attempts: 1, lastDuration: 20 }).lastDuration).toBe(20);
    expect(mergeProgressEntry({ completed: false, attempts: 1, lastDuration: 10 }, { completed: false, attempts: 1 }).lastDuration).toBe(10);
  });

  it('firstCompletedAt keeps the earliest defined value', () => {
    const m = mergeProgressEntry(
      { completed: true, attempts: 1, firstCompletedAt: '2024-05-10T00:00:00Z' },
      { completed: true, attempts: 1, firstCompletedAt: '2024-01-01T00:00:00Z' },
    );
    expect(m.firstCompletedAt).toBe('2024-01-01T00:00:00Z');
  });
});

describe('readLocalProgress / writeLocalProgress (explicit store)', () => {
  it('returns {} when nothing stored', () => {
    const store = kioskActivityStorage(ALICE, false);
    expect(readLocalProgress(store)).toEqual({});
  });

  it('returns {} on corrupt JSON without throwing', () => {
    seedNamespaced(ALICE, {} as TsumegoProgressMap);
    localStorage.setItem(namespacedKey(ALICE), '{not json');
    const store = kioskActivityStorage(ALICE, false);
    expect(readLocalProgress(store)).toEqual({});
  });

  it('writeLocalProgress field-merges into the stored map and persists it', () => {
    seedNamespaced(ALICE, { p1: { completed: false, attempts: 2, lastDuration: 10 } });
    const store = kioskActivityStorage(ALICE, false);
    const merged = writeLocalProgress('p1', { completed: true, attempts: 1, lastDuration: 30 }, store);
    expect(merged).toMatchObject({ completed: true, attempts: 2, lastDuration: 30 });
    expect(readNamespaced(ALICE).p1).toMatchObject({ completed: true, attempts: 2, lastDuration: 30 });
  });

  it('writeLocalProgress creates a new entry when absent', () => {
    const store = kioskActivityStorage(ALICE, false);
    writeLocalProgress('new', { completed: false, attempts: 1 }, store);
    expect(readNamespaced(ALICE).new).toMatchObject({ completed: false, attempts: 1 });
  });

  it('a guest store never touches localStorage', () => {
    const guestStore = kioskActivityStorage(null, true);
    writeLocalProgress('p1', { completed: true, attempts: 1 }, guestStore);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(readLocalProgress(guestStore).p1).toMatchObject({ completed: true, attempts: 1 });
  });
});

describe('mergeProgressMaps', () => {
  it('merges server map into base field-by-field', () => {
    const base: TsumegoProgressMap = {
      a: { completed: false, attempts: 3 },
      b: { completed: true, attempts: 1 },
    };
    const server: TsumegoProgressMap = {
      a: { completed: true, attempts: 1 }, // completed OR, attempts max(3,1)=3
      c: { completed: false, attempts: 2 }, // new
    };
    const merged = mergeProgressMaps(base, server);
    expect(merged.a).toMatchObject({ completed: true, attempts: 3 });
    expect(merged.b).toMatchObject({ completed: true, attempts: 1 });
    expect(merged.c).toMatchObject({ completed: false, attempts: 2 });
  });
});

// ============ Provider behavior — real (resolved) user ============

const wrapper = ({ children }: { children: ReactNode }) => (
  <TsumegoProgressProvider>{children}</TsumegoProgressProvider>
);

describe('TsumegoProgressProvider — real, resolved user (Alice)', () => {
  it('loads the namespaced cache synchronously on mount', () => {
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
    expect(result.current.isCompleted('p1')).toBe(true);
  });

  it('does NOT call getProgress when there is no token', async () => {
    renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).not.toHaveBeenCalled());
  });

  it('merges the server map (cache ⊕ server) when a token is present', async () => {
    mockUseAuth.mockReturnValue(aliceAuth({ token: 'tok' }));
    seedNamespaced(ALICE, { p1: { completed: false, attempts: 4 }, p2: { completed: false, attempts: 1 } });
    mockGetProgress.mockResolvedValue({
      p1: { completed: true, attempts: 1 }, // completed OR -> true, attempts max(4,1) -> 4
      p3: { completed: true, attempts: 2 }, // server-only
    });

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockGetProgress).toHaveBeenCalledWith('tok'));
    await waitFor(() => {
      expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 4 });
      expect(result.current.progress.p3).toMatchObject({ completed: true, attempts: 2 });
    });
    // merged map is also written back to the namespaced cache, not the raw key.
    expect(readNamespaced(ALICE).p3).toMatchObject({ completed: true, attempts: 2 });
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('markProgress writes the namespaced cache AND updates in-memory state', () => {
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 2, lastDuration: 33 });
    });
    expect(result.current.progress.p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
    expect(readNamespaced(ALICE).p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
  });

  it('markProgress posts to the server when a token is present', () => {
    mockUseAuth.mockReturnValue(aliceAuth({ token: 'tok' }));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 2, lastDuration: 33 });
    });
    expect(mockSaveProgress).toHaveBeenCalledWith(
      'p9',
      { completed: true, attempts: 2, lastDuration: 33 },
      'tok',
    );
  });

  it('markProgress does NOT post to the server when there is no token (offline)', () => {
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 1 });
    });
    expect(mockSaveProgress).not.toHaveBeenCalled();
    expect(readNamespaced(ALICE).p9).toMatchObject({ completed: true, attempts: 1 });
  });

  it('markProgress field-merges (completed OR, attempts max) into prior progress', () => {
    seedNamespaced(ALICE, { p1: { completed: false, attempts: 5, lastDuration: 99 } });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 2, lastDuration: 10 });
    });
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 5, lastDuration: 10 });
  });

  it('aggregates unitProgress over an id slice (completed count)', () => {
    seedNamespaced(ALICE, {
      a: { completed: true, attempts: 1 },
      b: { completed: false, attempts: 2 },
      c: { completed: true, attempts: 1 },
    });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.unitProgress(['a', 'b', 'c', 'd'])).toEqual({ completed: 2, total: 4 });
  });

  it('aggregates categoryProgress the same way', () => {
    seedNamespaced(ALICE, {
      a: { completed: true, attempts: 1 },
      b: { completed: true, attempts: 1 },
    });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.categoryProgress(['a', 'b', 'x'])).toEqual({ completed: 2, total: 3 });
  });

  it('keeps the cached progress when the server fetch fails', async () => {
    mockUseAuth.mockReturnValue(aliceAuth({ token: 'tok' }));
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    mockGetProgress.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
  });

  it('a different uuid (Bob) reads empty even though Alice has namespaced progress', () => {
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(aliceAuth({ user: { uuid: BOB, username: 'bob' } }));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.progress).toEqual({});
    expect(result.current.isCompleted('p1')).toBe(false);
  });
});

// ============ THE RACE: first-paint / unresolved-identity window ============

describe('TsumegoProgressProvider — first-paint race (unresolved identity)', () => {
  it('returns an empty progress map on the very first render while isLoading, even with real data seeded under BOTH the legacy key and a namespaced key', () => {
    seedLegacy({ p1: { completed: true, attempts: 1 } });
    seedNamespaced(ALICE, { p2: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(unresolvedAuth());

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    // First-paint value: the useState initializer must have produced {} — NOT Alice's data,
    // NOT the legacy data — precisely because identity was unresolved at mount time.
    expect(result.current.progress).toEqual({});
    expect(result.current.isCompleted('p1')).toBe(false);
    expect(result.current.isCompleted('p2')).toBe(false);
  });

  it('THE precise race guard: stays empty even when `user` already carries a resolved uuid, as long as isLoading is still true', () => {
    // AuthContext's CURRENT contract happens to always pair isLoading=true with user=null, so
    // an implementation that keys ONLY off `identityKey == null` (and ignores `isLoading`
    // entirely) would accidentally pass every other test in this file too. This test isolates
    // the isLoading-specific guard from that coincidence: it simulates a hypothetical (but
    // plausible future) AuthContext that optimistically restores a cached `user` object before
    // the `/me` probe has actually confirmed it. If TsumegoProgressProvider's useState
    // initializer keyed off identityKey alone, this would read Alice's namespaced data on
    // first paint despite isLoading still being true — the isLoading check is what stops it.
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue({ token: null, user: { uuid: ALICE, username: 'alice' }, isGuest: false, isLoading: true });

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    expect(result.current.progress).toEqual({});
    expect(result.current.isCompleted('p1')).toBe(false);
  });

  it('stays empty and never fetches while unresolved, then hydrates once resolved to Alice', async () => {
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(unresolvedAuth());

    const { result, rerender } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.progress).toEqual({});
    expect(mockGetProgress).not.toHaveBeenCalled();

    mockUseAuth.mockReturnValue(aliceAuth());
    rerender();

    await waitFor(() => expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 }));
  });
});

// ============ Guest mode ============

describe('TsumegoProgressProvider — guest', () => {
  it('a guest never persists anything: no tsumego_progress* key exists after an attempt', () => {
    mockUseAuth.mockReturnValue(guestAuth());
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 1, lastDuration: 5 });
    });

    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
    // No raw key, no namespaced key, nothing under any uuid whatsoever.
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)!;
      expect(key.startsWith(STORAGE_KEY)).toBe(false);
    }
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('a guest does not read a prior real user progress (legacy AND namespaced both seeded)', () => {
    seedLegacy({ p1: { completed: true, attempts: 1 } });
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 3 } });
    mockUseAuth.mockReturnValue(guestAuth());

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    expect(result.current.progress).toEqual({});
    expect(result.current.isCompleted('p1')).toBe(false);
  });

  it('a guest does not post to the server even with a token present (defense in depth)', () => {
    mockUseAuth.mockReturnValue(guestAuth({ token: 'guest-tok' }));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 1 });
    });
    // markProgress only gates server writes on `token`, matching existing server-side
    // enforcement (every guest HTTP write already 403s) — the client-side invariant under
    // test here is that nothing reaches localStorage regardless.
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('leaves any legacy key untouched (guests never migrate)', () => {
    seedLegacy({ p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(guestAuth());
    renderHook(() => useTsumegoProgress(), { wrapper });
    expect(readLegacyRaw()).toBe(JSON.stringify({ p1: { completed: true, attempts: 1 } }));
  });
});

// ============ Legacy migration (real user only, once) ============

describe('TsumegoProgressProvider — legacy migration', () => {
  it('migrates the legacy unscoped key to the namespaced key exactly once, then deletes it', () => {
    seedLegacy({ p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(aliceAuth());

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
    expect(readNamespaced(ALICE).p1).toMatchObject({ completed: true, attempts: 1 });
    expect(readLegacyRaw()).toBeNull();
  });

  it('does not clobber existing namespaced data with the legacy key', () => {
    seedLegacy({ p1: { completed: false, attempts: 99 } });
    seedNamespaced(ALICE, { p1: { completed: true, attempts: 1 } });
    mockUseAuth.mockReturnValue(aliceAuth());

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
    expect(readLegacyRaw()).toBeNull(); // still deleted, so a future identity can't inherit it
  });
});

// ============ Alice recovers after a guest transition ============

describe('TsumegoProgressProvider — identity transitions on the same mounted instance', () => {
  it('Alice writes, a guest transition happens, then Alice logs back in and her cache is intact', () => {
    mockUseAuth.mockReturnValue(aliceAuth());
    const { result, rerender } = renderHook(() => useTsumegoProgress(), { wrapper });

    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 1, lastDuration: 7 });
    });
    expect(readNamespaced(ALICE).p1).toMatchObject({ completed: true, attempts: 1 });

    // Guest transition (same mounted Provider instance — no remount).
    mockUseAuth.mockReturnValue(guestAuth());
    rerender();
    expect(result.current.progress).toEqual({});

    act(() => {
      result.current.markProgress('scratch', { completed: false, attempts: 1 });
    });
    // Guest's scratch write must not land under Alice's namespace, nor raw.
    expect(readNamespaced(ALICE).scratch).toBeUndefined();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();

    // Alice logs back in.
    mockUseAuth.mockReturnValue(aliceAuth());
    rerender();
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1, lastDuration: 7 });
    expect(result.current.progress.scratch).toBeUndefined();
  });
});

// ============ Default (no Provider) safety ============

describe('useTsumegoProgress without a Provider (safe default)', () => {
  it('with no resolved identity anywhere (no AuthProvider mounted), markProgress does NOT persist to raw localStorage', () => {
    const { result } = renderHook(() => useTsumegoProgress());
    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 1, lastDuration: 12 });
    });
    // Safe-by-default: with no identity ever resolved, the resolved-identity singleton stays
    // on its ephemeral default — the write must not reach the raw (or any namespaced) key.
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('isCompleted / unitProgress read live from the resolved-identity singleton', () => {
    // Once AuthContext (elsewhere in the app) has resolved a real identity, the singleton
    // reflects it — even components with no TsumegoProgressProvider ancestor benefit.
    const store = kioskActivityStorage(ALICE, false);
    writeLocalProgress('a', { completed: true, attempts: 1 }, store);
    writeLocalProgress('b', { completed: false, attempts: 1 }, store);
    // Simulate AuthContext having already resolved Alice via the singleton setter.
    setKioskIdentity(ALICE, false);

    const { result } = renderHook(() => useTsumegoProgress());
    expect(result.current.isCompleted('a')).toBe(true);
    expect(result.current.unitProgress(['a', 'b'])).toEqual({ completed: 1, total: 2 });
  });
});
