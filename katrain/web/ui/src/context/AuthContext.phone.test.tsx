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

  /* --- 手机功能开关（`GET /auth/features`）---------------------------------
     这四条守的是同一件事的两面：**服务端说有才有，其余一切情况都当没有。**
     开关是 false 时那四个手机端点一律 404，所以"多画一个入口"= 给用户一个点了必然
     报错的按钮。这几条用 `it` 不用 `nonStrictIt`：这个探针在严格盒端也照跑
     （盒子也要问得出"这里没有手机功能"）。 */

  const featuresReturning = (body: unknown, ok = true) =>
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/features')) {
        return ok ? Promise.resolve({ ok: true, status: 200, json: async () => body } as Response) : notOk(500);
      }
      return notOk();
    });

  it('服务端说 true ⇒ 入口可以画', async () => {
    featuresReturning({ phone_login: true });
    const { result } = await mountAuth();
    await waitFor(() => expect(result.current.phoneLoginEnabled).toBe(true));
  });

  it('服务端说 false ⇒ 关着', async () => {
    featuresReturning({ phone_login: false });
    const { result } = await mountAuth();
    expect(result.current.phoneLoginEnabled).toBe(false);
  });

  it('请求失败 ⇒ 当关着，不是当开着（fail-closed）', async () => {
    // 默认开着的话，服务端一抖动就会冒出一个点下去必然报错的按钮。
    featuresReturning(null, false);
    const { result } = await mountAuth();
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.phoneLoginEnabled).toBe(false);
  });

  it('fetch 直接抛（断网）⇒ 当关着', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/features')) return Promise.reject(new Error('offline'));
      return notOk();
    });
    const { result } = await mountAuth();
    expect(result.current.phoneLoginEnabled).toBe(false);
  });

  it('后端漏发 phone_login 这一格 ⇒ 当关着，不是"有个对象就算开着"', async () => {
    featuresReturning({});
    const { result } = await mountAuth();
    expect(result.current.phoneLoginEnabled).toBe(false);
  });

  it('初值就是 false —— 加载中的那一帧不许先把入口画出来再撤掉', async () => {
    /* 探针挂着不回（真实的慢网络）。这一帧 `phoneLoginEnabled` 必须已经是 false，
       否则用户会看见入口闪一下再消失。 */
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/features')) return new Promise<Response>(() => {});
      return notOk();
    });
    const hook = renderHook(() => useAuth(), { wrapper: AuthProvider });
    expect(hook.result.current.phoneLoginEnabled).toBe(false);
    await waitFor(() => expect(hook.result.current.isLoading).toBe(false));
    expect(hook.result.current.phoneLoginEnabled).toBe(false);
  });

  strictKioskIt('严格盒端不允许直接登录 —— loginByPhone 与 login 同一条口径', async () => {
    // D-U3「盒子什么都不改」：盒端身份是云端账号经 box_sso_bootstrap 交下来的，
    // 本地再开一条发码登录会造出第二个身份来源。
    mockFetch.mockImplementation(() => notOk());
    const { result } = await mountAuth();
    await expect(result.current.loginByPhone('c1', '123456')).rejects.toThrow(/strict box/i);
  });
});
