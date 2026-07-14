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

// Vite replaces this with the build mode selected by VITE_KIOSK_2D_ONLY.
// The focused test command is run once per build mode below so the shared
// context cannot accidentally regain browser-storage access in the kiosk.
const isKioskBuild = __KIOSK_2D_ONLY__;
const kioskIt = isKioskBuild ? it : it.skip;
const galaxyIt = isKioskBuild ? it.skip : it;

describe('AuthContext', () => {
  beforeEach(() => {
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

  galaxyIt('restores the session from a stored localStorage token on mount', async () => {
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

  kioskIt('bootstraps from the SSO cookie without reading or writing localStorage', async () => {
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
    mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) {
        expect(init?.headers).toBeUndefined();
        return okJson(meResponse);
      }
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.username).toBe('testuser');
    expect(result.current.isLoading).toBe(false);
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
  });

  kioskIt('settles unauthenticated after /me rejects the cookie without localStorage access', async () => {
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/me')) return notOk();
      return okJson({});
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
  });

  galaxyIt('recovers via the shared SSO cookie when the stored token is stale', async () => {
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

  kioskIt('uses the fresh login token in memory without persisting it in localStorage', async () => {
    const setItem = vi.spyOn(window.localStorage, 'setItem');
    const getItem = vi.spyOn(window.localStorage, 'getItem');
    const removeItem = vi.spyOn(window.localStorage, 'removeItem');
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
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
  });

  kioskIt('logs out a cookie-only session without an Authorization header or localStorage', async () => {
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
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();
  });
});
