import { renderHook, act, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { describe, it, expect, vi, beforeEach } from 'vitest';

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

const meResponse = { id: 1, username: 'testuser', rank: '1d', credits: 100 };

const okJson = (body: unknown): Promise<Response> =>
  Promise.resolve({ ok: true, json: async () => body } as Response);
const notOk = (): Promise<Response> =>
  Promise.resolve({ ok: false, json: async () => ({}) } as Response);
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
});
