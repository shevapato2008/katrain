import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';

// ---- Mock auth (token) + the tsumego API (getProgress/saveProgress) ----
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

const STORAGE_KEY = 'tsumego_progress';

const seedLocal = (map: TsumegoProgressMap) => localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
const readRaw = (): TsumegoProgressMap => JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mockUseAuth.mockReturnValue({ token: null });
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

describe('readLocalProgress / writeLocalProgress', () => {
  it('returns {} when nothing stored', () => {
    expect(readLocalProgress()).toEqual({});
  });

  it('returns {} on corrupt JSON without throwing', () => {
    localStorage.setItem(STORAGE_KEY, '{not json');
    expect(readLocalProgress()).toEqual({});
  });

  it('writeLocalProgress field-merges into the stored map and persists it', () => {
    seedLocal({ p1: { completed: false, attempts: 2, lastDuration: 10 } });
    const merged = writeLocalProgress('p1', { completed: true, attempts: 1, lastDuration: 30 });
    // completed OR -> true, attempts max -> 2, lastDuration latest -> 30
    expect(merged).toMatchObject({ completed: true, attempts: 2, lastDuration: 30 });
    expect(readRaw().p1).toMatchObject({ completed: true, attempts: 2, lastDuration: 30 });
  });

  it('writeLocalProgress creates a new entry when absent', () => {
    writeLocalProgress('new', { completed: false, attempts: 1 });
    expect(readRaw().new).toMatchObject({ completed: false, attempts: 1 });
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

// ============ Provider behavior ============

const wrapper = ({ children }: { children: ReactNode }) => (
  <TsumegoProgressProvider>{children}</TsumegoProgressProvider>
);

describe('TsumegoProgressProvider', () => {
  it('loads localStorage synchronously on mount', () => {
    seedLocal({ p1: { completed: true, attempts: 1 } });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
    expect(result.current.isCompleted('p1')).toBe(true);
  });

  it('does NOT call getProgress when there is no token', async () => {
    renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).not.toHaveBeenCalled());
  });

  it('merges the server map (localStorage ⊕ server) when a token is present', async () => {
    mockUseAuth.mockReturnValue({ token: 'tok' });
    seedLocal({ p1: { completed: false, attempts: 4 }, p2: { completed: false, attempts: 1 } });
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
    // merged map is also written back to localStorage
    expect(readRaw().p3).toMatchObject({ completed: true, attempts: 2 });
  });

  it('markProgress writes localStorage AND updates in-memory state', () => {
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 2, lastDuration: 33 });
    });
    expect(result.current.progress.p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
    expect(readRaw().p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
  });

  it('markProgress posts to the server when a token is present', () => {
    mockUseAuth.mockReturnValue({ token: 'tok' });
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
    mockUseAuth.mockReturnValue({ token: null });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 1 });
    });
    expect(mockSaveProgress).not.toHaveBeenCalled();
    // localStorage still persists.
    expect(readRaw().p9).toMatchObject({ completed: true, attempts: 1 });
  });

  it('markProgress field-merges (completed OR, attempts max) into prior progress', () => {
    seedLocal({ p1: { completed: false, attempts: 5, lastDuration: 99 } });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 2, lastDuration: 10 });
    });
    // completed OR -> true, attempts max(5,2) -> 5, lastDuration latest -> 10
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 5, lastDuration: 10 });
  });

  it('aggregates unitProgress over an id slice (completed count)', () => {
    seedLocal({
      a: { completed: true, attempts: 1 },
      b: { completed: false, attempts: 2 },
      c: { completed: true, attempts: 1 },
    });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.unitProgress(['a', 'b', 'c', 'd'])).toEqual({ completed: 2, total: 4 });
  });

  it('aggregates categoryProgress the same way', () => {
    seedLocal({
      a: { completed: true, attempts: 1 },
      b: { completed: true, attempts: 1 },
    });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    expect(result.current.categoryProgress(['a', 'b', 'x'])).toEqual({ completed: 2, total: 3 });
  });

  it('keeps localStorage-only progress when the server fetch fails', async () => {
    mockUseAuth.mockReturnValue({ token: 'tok' });
    seedLocal({ p1: { completed: true, attempts: 1 } });
    mockGetProgress.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    // local progress is intact despite the failed server fetch.
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
  });
});

// ============ Default (no Provider) safety ============

describe('useTsumegoProgress without a Provider (safe default)', () => {
  it('markProgress still persists to localStorage', () => {
    const { result } = renderHook(() => useTsumegoProgress());
    act(() => {
      result.current.markProgress('p1', { completed: true, attempts: 1, lastDuration: 12 });
    });
    expect(readRaw().p1).toMatchObject({ completed: true, attempts: 1, lastDuration: 12 });
  });

  it('isCompleted / unitProgress read live from localStorage', () => {
    seedLocal({ a: { completed: true, attempts: 1 }, b: { completed: false, attempts: 1 } });
    const { result } = renderHook(() => useTsumegoProgress());
    expect(result.current.isCompleted('a')).toBe(true);
    expect(result.current.unitProgress(['a', 'b'])).toEqual({ completed: 1, total: 2 });
  });
});
