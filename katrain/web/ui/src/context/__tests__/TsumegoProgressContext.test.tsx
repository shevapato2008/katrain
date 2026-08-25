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
  progressStorageKey,
  setProgressScope,
  type TsumegoProgressEntry,
  type TsumegoProgressMap,
} from '../TsumegoProgressContext';

/** 2026-08-25 之前那把**不分人**的钥匙。只出现在「它该被删掉」那条用例里。 */
const LEGACY_KEY = 'tsumego_progress';

const seedLocal = (map: TsumegoProgressMap, userId: number | null = null) =>
  localStorage.setItem(progressStorageKey(userId), JSON.stringify(map));
const readRaw = (userId: number | null = null): TsumegoProgressMap =>
  JSON.parse(localStorage.getItem(progressStorageKey(userId)) || '{}');

const auth = (over: { token?: string | null; user?: { id: number } | null } = {}) => ({
  token: null,
  user: null,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  // 作用域是模块级的 ⇒ 每条用例都要归零,否则上一条的账号会漏到下一条。
  setProgressScope(null);
  mockUseAuth.mockReturnValue(auth());
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
    localStorage.setItem(progressStorageKey(null), '{not json');
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

  it('没有账号时不拉服务端', async () => {
    renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).not.toHaveBeenCalled());
  });

  it('merges the server map (localStorage ⊕ server) when signed in', async () => {
    mockUseAuth.mockReturnValue(auth({ token: 'tok', user: { id: 7 } }));
    seedLocal({ p1: { completed: false, attempts: 4 }, p2: { completed: false, attempts: 1 } }, 7);
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
    expect(readRaw(7).p3).toMatchObject({ completed: true, attempts: 2 });
  });

  it('markProgress writes localStorage AND updates in-memory state', () => {
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => {
      result.current.markProgress('p9', { completed: true, attempts: 2, lastDuration: 33 });
    });
    expect(result.current.progress.p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
    expect(readRaw().p9).toMatchObject({ completed: true, attempts: 2, lastDuration: 33 });
  });

  it('markProgress posts to the server when signed in', () => {
    mockUseAuth.mockReturnValue(auth({ token: 'tok', user: { id: 7 } }));
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

  it('markProgress does NOT post to the server when there is no account', () => {
    mockUseAuth.mockReturnValue(auth());
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
    mockUseAuth.mockReturnValue(auth({ token: 'tok', user: { id: 7 } }));
    seedLocal({ p1: { completed: true, attempts: 1 } }, 7);
    mockGetProgress.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    // local progress is intact despite the failed server fetch.
    expect(result.current.progress.p1).toMatchObject({ completed: true, attempts: 1 });
  });
});

// ============ 共享设备:钥匙分人(2026-08-25) ============

/**
 * 盒子是**多人轮流用的共享设备**。这一组守的是三件在真机上才会出事、
 * 而在开发机上一律看不出来的事。三条都做过变异实测(把修复改回去,确认会红)。
 */
describe('共享设备:进度按账号隔离', () => {
  it('甲解过的题不算进乙的账 —— **这就是修之前的缺陷**', async () => {
    // 甲(id 1)解了 p1。
    mockUseAuth.mockReturnValue(auth({ token: 'tok-a', user: { id: 1 } }));
    const a = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => { a.result.current.markProgress('p1', { completed: true, attempts: 1 }); });
    expect(a.result.current.isCompleted('p1')).toBe(true);
    a.unmount();

    // 乙(id 2)上机。同一台设备、同一个 localStorage。
    setProgressScope(null);
    mockUseAuth.mockReturnValue(auth({ token: 'tok-b', user: { id: 2 } }));
    const b = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(mockGetProgress).toHaveBeenCalledWith('tok-b'));

    // 变异:把 progressStorageKey 改回不带 userId ⇒ 这一条当场红。
    expect(b.result.current.isCompleted('p1')).toBe(false);
    expect(b.result.current.progress).toEqual({});
    // 甲的那份还在自己钥匙下,没被乙覆盖掉。
    expect(readRaw(1).p1).toMatchObject({ completed: true });
  });

  it('旧的不分人 blob **被删掉,不迁移给任何人**', () => {
    // 它没有主人 —— 记到「下一个登录的人」头上正是这次要修的那个缺陷。
    localStorage.setItem(LEGACY_KEY, JSON.stringify({ ghost: { completed: true, attempts: 9 } }));
    mockUseAuth.mockReturnValue(auth({ token: 'tok', user: { id: 3 } }));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
    expect(result.current.isCompleted('ghost')).toBe(false);
    expect(readRaw(3).ghost).toBeUndefined();
  });

  it('登出之后屏上不留上一个人的进度', () => {
    mockUseAuth.mockReturnValue(auth({ token: 'tok', user: { id: 1 } }));
    const { result, rerender } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => { result.current.markProgress('p1', { completed: true, attempts: 1 }); });
    expect(result.current.isCompleted('p1')).toBe(true);

    mockUseAuth.mockReturnValue(auth());   // 登出
    rerender();
    expect(result.current.isCompleted('p1')).toBe(false);
  });
});

/**
 * 出厂盒子(严格 box SSO)里 `token` **恒为 `null`** 而 `user` 有值 —— 身份走
 * 127.0.0.1 上的共享 cookie,后端 `resolve_http_token` 在严格模式下只认 cookie。
 * 修之前判别位是 `token` ⇒ **盒子上从不拉、也从不写**,而本机开发一切正常。
 * 这两条就是那个「盒子上坏、开发机上好」的分界线。
 */
describe('出厂盒子:token 恒为 null,身份靠 cookie', () => {
  it('token 是 null 但有账号时,照样去拉服务端进度', async () => {
    mockUseAuth.mockReturnValue(auth({ token: null, user: { id: 5 } }));
    mockGetProgress.mockResolvedValue({ s1: { completed: true, attempts: 1 } });
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

    // 变异:把闸改回 `if (!token) return` ⇒ 这一条当场红。
    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    // **不带 token 调用** —— 让 authHeaders 去决定用 Bearer 还是 cookie。
    expect(mockGetProgress).toHaveBeenCalledWith(undefined);
    await waitFor(() => expect(result.current.isCompleted('s1')).toBe(true));
  });

  it('token 是 null 但有账号时,markProgress 照样落服务端', () => {
    mockUseAuth.mockReturnValue(auth({ token: null, user: { id: 5 } }));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    act(() => { result.current.markProgress('p9', { completed: true, attempts: 2 }); });

    // 变异:把闸改回 `if (token)` ⇒ 这一条当场红,而屏上没有任何变化 ——
    // 用户解的题在盒子重装/换机之后就没了,当时一个字都不会说。
    expect(mockSaveProgress).toHaveBeenCalledWith(
      'p9',
      { completed: true, attempts: 2, lastDuration: undefined },
      undefined,
    );
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
