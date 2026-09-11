/**
 * AuthContext 的手机验证码登录（P3 / Task 13）。
 *
 * 夹具形状照 `AuthContext.test.tsx:1-48`（fetch 假体 + localStorage 假体 + 门控），
 * 但 localStorage 那句加了 `configurable: true`（原文 :25-27 没有，它在模块顶层只跑一次）。
 *
 * ⚠️ **两种 fetch 假体模型不要混**：本文件用模块级 `global.fetch = vi.fn()` + `vi.mocked`，
 * 与 `api.phone.test.ts` 的「每条用例内 `vi.spyOn(globalThis,'fetch')`」是两套。
 * 缝在一起时 `restoreAllMocks` 会把 fetch 还原成那个 vi.fn 而不是原生，断言会落到错的对象上。
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

global.fetch = vi.fn();
const store: Record<string, string> = {};
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { for (const k of Object.keys(store)) delete store[k]; },
  },
});
const mockFetch = vi.mocked(global.fetch);

const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';
const nonStrictIt = isStrictBoxKiosk ? it.skip : it;
const strictKioskIt = isStrictBoxKiosk ? it : it.skip;

const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body } as Response);
const notOk = (status = 401) => Promise.resolve({ ok: false, status, json: async () => ({}) } as Response);

const mountAuth = async () => {
  const hook = renderHook(() => useAuth(), { wrapper: AuthProvider });
  await waitFor(() => expect(hook.result.current.isLoading).toBe(false));
  return hook;
};

describe('AuthContext 手机验证码登录', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
  });

  nonStrictIt('loginByPhone 成功后：存 token、拉到 user、isAuthenticated 为 true', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/auth/phone/login')) return ok({ access_token: 'tok', token_type: 'bearer' });
      if (url.includes('/auth/me')) return ok({ id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: true });
      return notOk();
    });
    const { result } = await mountAuth();
    await act(async () => { await result.current.loginByPhone('c1', '123456'); });
    expect(window.localStorage.getItem('token')).toBe('tok');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.phone_bound).toBe(true);
  });

  nonStrictIt('/auth/me 失败时不写 token、不置 user —— 半截登录不许伪装成成功', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/auth/phone/login')) return ok({ access_token: 'tok', token_type: 'bearer' });
      return notOk();          // 含挂载时那次 /auth/me 与登录后那次
    });
    const { result } = await mountAuth();
    await act(async () => {
      await expect(result.current.loginByPhone('c1', '123456')).rejects.toThrow();
    });
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  nonStrictIt('refreshUser 重新拉 /auth/me，把 phone_bound 的新值带进来', async () => {
    // 绑定成功后免费额度文案要当场翻面（Task 16），靠的就是这一步。
    window.localStorage.setItem('token', 'tok');
    let bound = false;
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/me')) {
        return ok({ id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: bound });
      }
      return notOk();
    });
    const { result } = await mountAuth();
    expect(result.current.user?.phone_bound).toBe(false);
    bound = true;
    await act(async () => { await result.current.refreshUser(); });
    expect(result.current.user?.phone_bound).toBe(true);
  });

  nonStrictIt('refreshUser 失败时抛错，不把旧 user 原样留着当成刷新成功', async () => {
    // 计划原稿写的是 `if (res.ok) setUser(...)` —— 失败时**什么都不做、也不说**。
    // 那样 Task 16 的「绑定成功后文案翻面」在刷新失败时会静默不翻,用户看到的是
    // 「绑定成功了但还是提示我去绑定」,而没有任何一处告诉他刷新没成功。
    // 这正是生产代码底线里「加载/错误不得伪装成成功」那条。抛出去,让调用方决定。
    window.localStorage.setItem('token', 'tok');
    let failing = false;
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/me')) {
        return failing ? notOk(500) : ok({ id: 1, username: 'u', rank: '5k', credits: 0, phone_bound: false });
      }
      return notOk();
    });
    const { result } = await mountAuth();
    expect(result.current.user?.username).toBe('u');
    failing = true;
    await act(async () => {
      await expect(result.current.refreshUser()).rejects.toThrow();
    });
    // 旧 user 还在（我们没有把人踢下线），但调用方**知道**这次刷新失败了。
    expect(result.current.user?.username).toBe('u');
  });

  strictKioskIt('严格盒端不允许直接登录 —— loginByPhone 与 login 同一条口径', async () => {
    // D-U3「盒子什么都不改」：盒端身份是云端账号经 box_sso_bootstrap 交下来的，
    // 本地再开一条发码登录会造出第二个身份来源。
    mockFetch.mockImplementation(() => notOk());
    const { result } = await mountAuth();
    await expect(result.current.loginByPhone('c1', '123456')).rejects.toThrow(/strict box/i);
  });
});
