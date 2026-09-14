import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
  localIsAhead,
  type TsumegoProgressEntry,
  type TsumegoProgressMap,
} from '../TsumegoProgressContext';
import type { TsumegoProgressAnswer } from '../../api/tsumegoApi';

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

/** `getProgress` 的回答(2026-09-15 起带 `degraded`)。云端 / 服务端模式那一份 = `degraded: false`。 */
const served = (progress: TsumegoProgressMap, degraded = false): TsumegoProgressAnswer => ({ progress, degraded });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  // 作用域是模块级的 ⇒ 每条用例都要归零,否则上一条的账号会漏到下一条。
  setProgressScope(null);
  mockUseAuth.mockReturnValue(auth());
  mockGetProgress.mockResolvedValue(served({}));
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
    mockGetProgress.mockResolvedValue(served({
      p1: { completed: true, attempts: 1 }, // completed OR -> true, attempts max(4,1) -> 4
      p3: { completed: true, attempts: 2 }, // server-only
    }));

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

  it('读失败之后重读:回来之前仍算「没读到」,读成功才清掉 —— 重读途中不许看起来像「读到了、是空的」', async () => {
    // 盒上的样子:token=null,身份在 user 上。
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(result.current.serverLoadFailed).toBe(true));

    let resolve!: (answer: TsumegoProgressAnswer) => void;
    mockGetProgress.mockReturnValueOnce(new Promise<TsumegoProgressAnswer>((r) => { resolve = r; }));
    act(() => result.current.refresh());
    expect(mockGetProgress).toHaveBeenCalledTimes(2);
    // 请求发出去了、还没回来:本机进度仍是空的,标志若在这时清掉,下游看到的就是「读到了,一道错题都没有」。
    expect(result.current.serverLoadFailed).toBe(true);

    await act(async () => { resolve(served({ p1: { completed: false, attempts: 2 } })); });
    expect(result.current.serverLoadFailed).toBe(false);
    expect(result.current.progress.p1).toMatchObject({ completed: false, attempts: 2 });
  });

  it('重试还在路上时换了账号:甲那份回来作废 —— 不并进乙的进度、不写乙的钥匙、不拿乙的本机进度去回推(Codex 第 2 轮 #1)', async () => {
    // 非严格 kiosk / galaxy:登出 → 登录都在同一棵树里,这个 Provider 不卸载。
    mockUseAuth.mockReturnValue(auth({ token: 'tok-a', user: { id: 7 } }));
    mockGetProgress.mockRejectedValueOnce(new Error('offline'));
    const { result, rerender } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(result.current.serverLoadFailed).toBe(true));

    // 甲按「重试」,请求挂在路上。
    let resolveA!: (answer: TsumegoProgressAnswer) => void;
    mockGetProgress.mockReturnValueOnce(new Promise<TsumegoProgressAnswer>((r) => { resolveA = r; }));
    act(() => result.current.refresh());

    // 甲登出、乙登录;乙自己那次读成功了。
    mockGetProgress.mockResolvedValueOnce(served({ b1: { completed: false, attempts: 1 } }));
    mockUseAuth.mockReturnValue(auth({ token: 'tok-b', user: { id: 8 } }));
    rerender();
    await waitFor(() => expect(result.current.progress.b1).toMatchObject({ completed: false, attempts: 1 }));

    // 甲那份这时才回来。`completed` 按 OR 合并是单调的 —— 并进去就再也退不回来。
    await act(async () => { resolveA(served({ a1: { completed: true, attempts: 1 } })); });
    expect(result.current.progress.a1).toBeUndefined();
    expect(readRaw(8).a1).toBeUndefined();
    // 并进去的话 `pushLocalAhead(乙的进度, 甲的回答, 'tok-a')` 会把乙的 b1 推进甲的云端账。
    expect(mockSaveProgress).not.toHaveBeenCalled();
  });

  it('连按两次「重试」、先发的那次后回来:以后发的为准,旧的失败不许把状态翻回「没读到」(Codex 第 2 轮 #1)', async () => {
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useTsumegoProgress(), { wrapper });
    await waitFor(() => expect(result.current.serverLoadFailed).toBe(true));

    let rejectFirst!: (err: Error) => void;
    mockGetProgress.mockReturnValueOnce(new Promise<TsumegoProgressAnswer>((_resolve, reject) => { rejectFirst = reject; }));
    act(() => result.current.refresh());
    mockGetProgress.mockResolvedValueOnce(served({ p1: { completed: false, attempts: 2 } }));
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.progress.p1).toMatchObject({ completed: false, attempts: 2 }));
    expect(result.current.serverLoadFailed).toBe(false);

    await act(async () => { rejectFirst(new Error('timeout')); });
    expect(result.current.serverLoadFailed).toBe(false);
  });

  describe('盒子退回本机缓存(契约另一半:tests/web_ui/test_tsumego_board_unavailable.py)', () => {
    afterEach(() => vi.unstubAllGlobals());

    // 走**真的** `getProgress` + stub 的 `fetch`:响应头字面量在这里钉死,和后端那条 pytest 各钉一次。
    it.each([
      ['local_cache', true, 0],
      ['cloud', false, 1],
    ] as const)('200 + X-Data-Authority: %s ⇒ serverLoadFailed=%s,回推 %i 次', async (authority, failed, pushes) => {
      const real = await vi.importActual<typeof import('../../api/tsumegoApi')>('../../api/tsumegoApi');
      mockGetProgress.mockImplementation(real.TsumegoAPI.getProgress);
      vi.stubGlobal('fetch', vi.fn(async () => new Response(
        JSON.stringify({ p1: { completed: false, attempts: 2 } }),
        { status: 200, headers: { 'Content-Type': 'application/json', 'X-Data-Authority': authority } },
      )));
      // 本机有一条比回答多的:只有云端那份才拿它去回推。拿本机缓存比,几乎每一条都会被判成「本机更多」。
      seedLocal({ p9: { completed: true, attempts: 1 } }, 7);
      mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));

      const { result } = renderHook(() => useTsumegoProgress(), { wrapper });

      // 本机缓存那份是真的下界,照样并进来;但它不是这个人的全部进度 ⇒ 仍算没读到(错题页据此给重试)。
      await waitFor(() => expect(result.current.progress.p1).toMatchObject({ completed: false, attempts: 2 }));
      expect(result.current.serverLoadFailed).toBe(failed);
      expect(mockSaveProgress).toHaveBeenCalledTimes(pushes);
    });
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
    mockGetProgress.mockResolvedValue(served({ s1: { completed: true, attempts: 1 } }));
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

/**
 * **对账,不是队列。**
 *
 * `markProgress` 的服务端写是 fire-and-forget,`.catch` 里原来的注释写着
 * 「offline/queued server-side」—— 那句话**只在盒子上成立**:盒子的浏览器打的是
 * 本机 127.0.0.1,请求必到,后端离线时会写本机库 + 入同步队列。
 * 而 galaxy 网页版的浏览器打的是云端,网一断这条 POST 就没了,
 * 本机 localStorage 却记着「解出来了」—— **坏了和好着在用户那儿长得一模一样**,
 * 直到他换台设备才发现少了几题。
 *
 * 补法是在每次**拉取成功**之后对一次账(拉得回来 = 服务端此刻够得着),
 * 把本机比服务端多的补上去。不用重发队列:队列活在内存里,刷新页面就没了,
 * 而丢掉的正是「那次 POST 失败了」这唯一的记录。
 */
describe('做题进度:拉得回来就把本机多出来的补上去', () => {
  const entry = (over: Partial<TsumegoProgressEntry> = {}): TsumegoProgressEntry => ({
    completed: false, attempts: 1, ...over,
  });

  it('本机解出来了而服务端没有 ⇒ 补一次', async () => {
    seedLocal({ p1: entry({ completed: true, attempts: 2 }) }, 7);
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockResolvedValue(served({ p1: entry({ completed: false, attempts: 1 }) }));

    renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockSaveProgress).toHaveBeenCalledWith(
      'p1', { completed: true, attempts: 2, lastDuration: undefined }, undefined,
    ));
  });

  it('服务端根本没有这一条 ⇒ 也补', async () => {
    seedLocal({ p9: entry({ completed: true, attempts: 1 }) }, 7);
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockResolvedValue(served({}));

    renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockSaveProgress).toHaveBeenCalled());
    expect(mockSaveProgress.mock.calls[0][0]).toBe('p9');
  });

  it('两边一样时**一次请求都不发** —— 每次开屏回推整库是另一种错', async () => {
    const same = entry({ completed: true, attempts: 3 });
    seedLocal({ p1: same }, 7);
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockResolvedValue(served({ p1: { ...same } }));

    renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    expect(mockSaveProgress).not.toHaveBeenCalled();
  });

  it('服务端比本机靠前时不回推 —— 那会把服务端的数往回按', async () => {
    seedLocal({ p1: entry({ completed: false, attempts: 1 }) }, 7);
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockResolvedValue(served({ p1: entry({ completed: true, attempts: 5 }) }));

    renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    expect(mockSaveProgress).not.toHaveBeenCalled();
  });

  it('拉取失败时不对账 —— 服务端此刻够不着,补也补不上去', async () => {
    seedLocal({ p1: entry({ completed: true }) }, 7);
    mockUseAuth.mockReturnValue(auth({ user: { id: 7 } }));
    mockGetProgress.mockRejectedValue(new Error('offline'));

    renderHook(() => useTsumegoProgress(), { wrapper });

    await waitFor(() => expect(mockGetProgress).toHaveBeenCalled());
    expect(mockSaveProgress).not.toHaveBeenCalled();
  });

  it('没有账号时既不拉也不对账 —— 匿名那份进度不许挂到任何人头上', async () => {
    seedLocal({ p1: entry({ completed: true }) }, null);
    renderHook(() => useTsumegoProgress(), { wrapper });
    await Promise.resolve();
    expect(mockGetProgress).not.toHaveBeenCalled();
    expect(mockSaveProgress).not.toHaveBeenCalled();
  });

  describe('localIsAhead:只看 completed 和 attempts', () => {
    it.each([
      ['本机解出来了、服务端没有', entry({ completed: true }), entry({ completed: false }), true],
      ['本机试得更多', entry({ attempts: 5 }), entry({ attempts: 2 }), true],
      ['服务端没有这一条', entry({ completed: true }), undefined, true],
      ['服务端没有而本机也是空的', entry({ attempts: 0 }), undefined, false],
      ['一模一样', entry({ completed: true, attempts: 2 }), entry({ completed: true, attempts: 2 }), false],
      ['服务端更靠前', entry({ attempts: 1 }), entry({ attempts: 9 }), false],
      ['本机没有这一条', undefined, entry({ completed: true }), false],
    ])('%s', (_name, local, server, expected) => {
      expect(localIsAhead(local, server)).toBe(expected);
    });

    it('时间戳不作判据 —— 拿它比会把每一条都判成「本机更新」,于是每次开屏回推整库', () => {
      const local = entry({ completed: true, attempts: 2, lastAttemptAt: '2026-08-26T10:00:00Z' });
      const server = entry({ completed: true, attempts: 2, lastAttemptAt: '2026-01-01T00:00:00Z' });
      expect(localIsAhead(local, server)).toBe(false);
    });
  });
});

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
