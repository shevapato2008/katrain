import { renderHook, act, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fetch
global.fetch = vi.fn();

// Mock localStorage
const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

const meResponse = { id: 1, uuid: 'test-uuid-1234', username: 'testuser', rank: '1d', credits: 100 };

const okJson = (body: unknown): Promise<Response> =>
  Promise.resolve({ ok: true, json: async () => body } as Response);
const notOk = (status = 401): Promise<Response> =>
  Promise.resolve({ ok: false, status, json: async () => ({}) } as Response);
const mockFetch = vi.mocked(global.fetch);

const hasAuthHeader = (init?: RequestInit) => {
  const h = (init?.headers ?? {}) as Record<string, string>;
  return Boolean(h.Authorization);
};

// Run this focused suite in Galaxy, legacy-kiosk, and strict-box-kiosk modes.
const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';
const strictKioskIt = isStrictBoxKiosk ? it : it.skip;
const legacyKioskIt = isKioskBuild && !isStrictBoxKiosk ? it : it.skip;
const nonStrictIt = isStrictBoxKiosk ? it.skip : it;
const galaxyIt = isKioskBuild ? it.skip : it;

describe('AuthContext', () => {
  afterEach(() => vi.useRealTimers());
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    window.localStorage.clear();
  });

  it('bootstraps to no user when there is no token and cookie /me fails', async () => {
    // On mount it always probes /me (so a shared SSO cookie can restore the
    // session); with no header and no cookie the server returns 401.
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        // With neither cookie nor Bearer credentials, the server rejects the
        // cold bootstrap. A real cookie-backed cold start is covered below.
        expect(init?.headers).toBeUndefined();
        return notOk();
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    // Loading while the mount probe is in flight — the guard must not redirect yet.
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  nonStrictIt('restores the session from a stored localStorage token on mount', async () => {
    // REGRESSION: fresh mount (i.e. re-entering 围棋) with a valid persisted
    // token must end authenticated, not bounce to the login page.
    window.localStorage.setItem('token', 'stored-token');
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return hasAuthHeader(init) ? okJson(meResponse) : notOk();
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('testuser');
    expect(result.current.isLoading).toBe(false);
  });

  it('restores the session from the shared SSO cookie on mount (no localStorage token)', async () => {
    // Cookie-only path: browser auto-sends the 127.0.0.1 cookie; the server
    // accepts it even though the client sent no Authorization header.
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return okJson(meResponse);
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('testuser');
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(result.current.isGuest).toBe(false);
  });

  it('exposes the backend-assigned uuid on the resolved user (the kiosk storage-isolation identity key)', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return okJson(meResponse);
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.uuid).toBe('test-uuid-1234');
  });

  it('marks the shared zero-persistence guest account as isGuest', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        return okJson({ id: 0, username: 'guest', rank: '', credits: 0 });
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('guest');
    expect(result.current.isGuest).toBe(true);
  });

  strictKioskIt('removes the legacy token before the cookie-only bootstrap request', async () => {
    window.localStorage.setItem('token', 'must-not-leak');
    window.localStorage.setItem('sb_go_token', 'must-never-be-read');
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        expect(window.localStorage.getItem('token')).toBeNull();
        expect(init?.headers).toBeUndefined();
        return okJson(meResponse);
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('testuser');
    expect(result.current.isLoading).toBe(false);
    expect(getItem).not.toHaveBeenCalledWith('sb_go_token');
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).toHaveBeenCalledTimes(1);
    expect(removeItem).toHaveBeenCalledWith('token');
    expect(window.localStorage.getItem('sb_go_token')).toBe('must-never-be-read');
  });

  strictKioskIt('settles unauthenticated after /me rejects the cookie', async () => {
    window.localStorage.setItem('token', 'must-not-leak');
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        expect(window.localStorage.getItem('token')).toBeNull();
        expect(init?.headers).toBeUndefined();
        return notOk();
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(getItem).not.toHaveBeenCalledWith('sb_go_token');
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).toHaveBeenCalledTimes(1);
    expect(removeItem).toHaveBeenCalledWith('token');
  });

  nonStrictIt('recovers via the shared SSO cookie when the stored token is stale', async () => {
    // REGRESSION: a >7d-expired localStorage token must NOT defeat a valid box
    // cookie. The Bearer probe 401s; we drop the stale token and retry /me
    // cookie-only (no auth header), which the server accepts.
    window.localStorage.setItem('token', 'stale-token');
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        // Stale Bearer token rejected; cookie-only retry (no header) succeeds.
        return hasAuthHeader(init) ? notOk() : okJson(meResponse);
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('testuser');
    // The stale token was cleared; the session is now cookie-backed (no JS token).
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(result.current.token).toBeNull();
  });

  galaxyIt('should login successfully', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/login')) {
        return okJson({ access_token: 'fake-token', token_type: 'bearer' });
      }
      if (url.includes('/api/v1/auth/me')) {
        // Anonymous mount probe (no header) stays logged out; the header'd
        // call inside login() succeeds.
        return hasAuthHeader(init) ? okJson(meResponse) : notOk();
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login('testuser', 'password');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe('testuser');
    expect(localStorage.getItem('token')).toBe('fake-token');
  });

  legacyKioskIt('retains the historical login token in localStorage', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/login')) {
        return okJson({ access_token: 'fake-token', token_type: 'bearer' });
      }
      if (url.includes('/api/v1/auth/me')) {
        // A cold request with no cookie and no Bearer is rejected. Direct login
        // must verify its fresh token in memory; only a later cold start uses
        // the HttpOnly cookie as the identity channel.
        if (init?.headers === undefined) return notOk();
        expect(init?.headers).toEqual({ Authorization: 'Bearer fake-token' });
        return okJson(meResponse);
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);

    await act(async () => {
      await result.current.login('testuser', 'password');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.token).toBe('fake-token');
    expect(window.localStorage.getItem('token')).toBe('fake-token');
  });

  strictKioskIt('rejects direct login without making a credential request', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return notOk();
      throw new Error(`unexpected request: ${url}`);
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(result.current.login('testuser', 'password')).rejects.toThrow(
      'Direct login is disabled in strict box mode',
    );
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  strictKioskIt('logs out a cookie-only session without an Authorization header', async () => {
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
    let logoutInit: RequestInit | undefined;
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return okJson(meResponse);
      if (url.includes('/api/v1/auth/logout')) {
        logoutInit = init;
        return okJson({ status: 'ok' });
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.token).toBeNull();

    await act(async () => {
      await result.current.logout();
    });

    expect(logoutInit).toEqual({ method: 'POST' });
    expect(result.current.isAuthenticated).toBe(false);
    expect(getItem).not.toHaveBeenCalledWith('sb_go_token');
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).toHaveBeenCalledWith('token');
  });

  nonStrictIt.each([503, 403])('retains Bearer credentials on /me %s and restores through retry', async (status) => {
    localStorage.setItem('token', 'saved-token');
    mockFetch.mockImplementationOnce(() => notOk(status));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.status).toBe('unavailable'));
    expect(localStorage.getItem('token')).toBe('saved-token');
    expect(result.current.token).toBe('saved-token');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    mockFetch.mockImplementation(() => okJson(meResponse));
    await act(async () => { await result.current.retry(); });
    expect(result.current.status).toBe('authenticated');
    expect(mockFetch.mock.calls[1][1]?.headers).toEqual({ Authorization: 'Bearer saved-token' });
  });

  nonStrictIt('retains Bearer credentials after a network failure', async () => {
    localStorage.setItem('token', 'saved-token');
    mockFetch.mockRejectedValue(new TypeError('offline'));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.status).toBe('unavailable'));
    expect(localStorage.getItem('token')).toBe('saved-token');
    expect(result.current.token).toBe('saved-token');
  });

  it('bounds a hung probe and serializes concurrent retry clicks', async () => {
    vi.useFakeTimers();
    mockFetch.mockImplementation(() => new Promise(() => {}));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    expect(result.current.status).toBe('checking');
    await act(async () => { await vi.advanceTimersByTimeAsync(8000); });
    expect(result.current.status).toBe('unavailable');
    let retryOne: Promise<void>;
    let retryTwo: Promise<void>;
    act(() => { retryOne = result.current.retry(); retryTwo = result.current.retry(); });
    expect(mockFetch).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(8000); await Promise.all([retryOne!, retryTwo!]); });
    expect(result.current.status).toBe('unavailable');
  });

  nonStrictIt('only a rejected saved credential establishes expiry', async () => {
    localStorage.setItem('token', 'expired-token');
    mockFetch.mockImplementation(() => notOk(401));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.status).toBe('expired'));
    expect(localStorage.getItem('token')).toBeNull();
    expect(result.current.token).toBeNull();
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  nonStrictIt('ignores a late bootstrap after successful login', async () => {
    let resolveBootstrap: (value: Response) => void = () => {};
    mockFetch.mockImplementationOnce(() => new Promise((resolve) => { resolveBootstrap = resolve; }));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    mockFetch.mockImplementation((input) => String(input).endsWith('/login')
      ? okJson({ access_token: 'new-token' }) : okJson(meResponse));
    await act(async () => { await result.current.login('testuser', 'password'); });
    await act(async () => { resolveBootstrap(await notOk(401)); });
    expect(result.current.status).toBe('authenticated');
    expect(result.current.token).toBe('new-token');
    expect(localStorage.getItem('token')).toBe('new-token');
  });

  it('unmounts identity immediately on logout and ignores a late probe', async () => {
    let resolveBootstrap: (value: Response) => void = () => {};
    mockFetch.mockImplementationOnce(() => new Promise((resolve) => { resolveBootstrap = resolve; }));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    mockFetch.mockImplementation(() => okJson({}));
    await act(async () => { await result.current.logout(); });
    await act(async () => { resolveBootstrap(await okJson(meResponse)); });
    expect(result.current.status).toBe('guest');
    expect(result.current.user).toBeNull();
  });

  nonStrictIt('failed login during bootstrap leaves a retryable state', async () => {
    mockFetch.mockImplementationOnce(() => new Promise(() => {}));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    mockFetch.mockImplementation(() => notOk(401));
    await act(async () => { await expect(result.current.login('bad', 'bad')).rejects.toThrow('Login failed'); });
    expect(result.current.status).toBe('unavailable');
    expect(result.current.isLoading).toBe(false);
  });

  nonStrictIt.each([200, 401])('a retry started during login cannot replace the new account after late /me %s', async (lateStatus) => {
    localStorage.setItem('token', 'old-token');
    mockFetch.mockImplementationOnce(() => notOk(503));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.status).toBe('unavailable'));
    let finishLogin: (value: Response) => void = () => {};
    let finishRetry: (value: Response) => void = () => {};
    mockFetch.mockImplementation((input, init) => {
      if (String(input).endsWith('/login')) return new Promise((resolve) => { finishLogin = resolve; });
      const headers = init?.headers as Record<string, string> | undefined;
      if (headers?.Authorization === 'Bearer new-token') return okJson(meResponse);
      if (headers?.Authorization === 'Bearer old-token') return new Promise((resolve) => { finishRetry = resolve; });
      return notOk(401);
    });
    let loginPending: Promise<void>;
    let retryPending: Promise<void>;
    act(() => { loginPending = result.current.login('testuser', 'password'); });
    act(() => { retryPending = result.current.retry(); });
    await act(async () => { finishLogin(await okJson({ access_token: 'new-token' })); await loginPending!; });
    expect(result.current.status).toBe('authenticated');
    await act(async () => {
      finishRetry(await (lateStatus === 401 ? notOk(401) : okJson({ ...meResponse, id: 99, uuid: 'old', username: 'old' })));
      await retryPending!;
    });
    expect(result.current.status).toBe('authenticated');
    expect(result.current.user?.username).toBe('testuser');
    expect(result.current.token).toBe('new-token');
    expect(localStorage.getItem('token')).toBe('new-token');
    expect(mockFetch).toHaveBeenCalledTimes(4);
  });

});
