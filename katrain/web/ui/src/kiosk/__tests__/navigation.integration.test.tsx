import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// localStorage mock (jsdom doesn't provide full implementation)
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value); },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Must be before importing KioskApp
const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/kiosk/*" element={<KioskApp />} />
      </Routes>
    </MemoryRouter>
  );

describe('Kiosk navigation integration', () => {
  describe('unauthenticated', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: false,
        user: null,
        login: vi.fn(),
        logout: vi.fn(),
        token: null,
      });
    });

    it('unauthenticated user is redirected to login for any route', () => {
      renderApp('/kiosk/tsumego');
      expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
    });
  });

  describe('authenticated', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        user: { id: 1, username: '张三', rank: '2D', credits: 0 },
        login: vi.fn(),
        logout: vi.fn(),
        token: 'mock-token',
      });
      // Mock fetch for pages that use API calls (e.g., TsumegoPage)
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          { level: '15k', categories: { '手筋': 139 }, total: 1000 },
        ]),
      }) as any;
    });

    it('shows play page with nav rail', () => {
      renderApp('/kiosk/play');
      expect(screen.getByText('对弈')).toBeInTheDocument();
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });

    it('nav rail items navigate correctly', async () => {
      renderApp('/kiosk/play');
      fireEvent.click(screen.getByText('死活'));
      await waitFor(() => {
        expect(screen.getByText('选择难度级别')).toBeInTheDocument();
      });
    });

    it('/kiosk redirects to /kiosk/play', () => {
      renderApp('/kiosk');
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });

    it('unknown kiosk routes redirect to play', () => {
      renderApp('/kiosk/nonexistent');
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });
  });
});
