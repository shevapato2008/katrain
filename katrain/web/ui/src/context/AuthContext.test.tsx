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

describe('AuthContext', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
  });

  it('should initialize with no user', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('should login successfully', async () => {
    // login() makes two fetches (POST /login then GET /me), and setToken()
    // then triggers AuthProvider's useEffect which fires a THIRD fetch
    // (GET /me again). A call-count-based mock only covers the first two, so
    // the third resolves to undefined and login's effect aborts. Branch on the
    // request URL instead so every fetch the provider makes is answered.
    const meResponse = {
      id: 1,
      username: 'testuser',
      rank: '1d',
      credits: 100,
    };
    (global.fetch as any).mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/v1/auth/login')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ access_token: 'fake-token', token_type: 'bearer' }),
        });
      }
      if (url.includes('/api/v1/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: async () => meResponse,
        });
      }
      // Fallback for any other endpoint (e.g. logout) so .ok never throws.
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await act(async () => {
      await result.current.login('testuser', 'password');
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe('testuser');
    expect(localStorage.getItem('token')).toBe('fake-token');
  });
});
