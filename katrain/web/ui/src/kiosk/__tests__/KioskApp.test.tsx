import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../context/OrientationContext', () => ({
  OrientationProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

vi.mock('../components/layout/RotationWrapper', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockSetLanguage = vi.fn();
vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: mockSetLanguage, languages: [] }),
}));

// Keep the tutorial landing page deterministic (no real network) when we render
// the /kiosk/tutorial route.
vi.mock('../../api/tutorialApi', () => ({
  TutorialReadAPI: {
    getCategories: () => Promise.resolve([]),
    assetUrl: (p: string) => `/api/v1/tutorials/assets/${p}`,
  },
}));

import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk/play') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/kiosk/*" element={<KioskApp />} />
      </Routes>
    </MemoryRouter>
  );

describe('KioskApp', () => {
  it('renders login page when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      token: null,
    });
    renderApp('/kiosk/play');
    // Auth guard redirects to login
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('defaults the kiosk language to Chinese when no preference is saved', () => {
    localStorage.removeItem('katrain_language');
    mockSetLanguage.mockClear();
    mockUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login: vi.fn(), logout: vi.fn(), token: null });
    renderApp('/kiosk/play');
    expect(mockSetLanguage).toHaveBeenCalledWith('cn');
  });

  it('respects an explicitly saved language and does not override it', () => {
    localStorage.setItem('katrain_language', 'en');
    mockSetLanguage.mockClear();
    mockUseAuth.mockReturnValue({ isAuthenticated: false, user: null, login: vi.fn(), logout: vi.fn(), token: null });
    renderApp('/kiosk/play');
    expect(mockSetLanguage).not.toHaveBeenCalled();
    localStorage.removeItem('katrain_language');
  });

  it('renders nav rail on authenticated route', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      login: vi.fn(),
      logout: vi.fn(),
      token: 'mock-token',
    });
    renderApp('/kiosk/play');
    // After auth, nav rail visible
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('智星盒')).toBeInTheDocument();
  });

  it('renders the tutorial entry on /kiosk/tutorial when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      login: vi.fn(),
      logout: vi.fn(),
      token: 'mock-token',
    });
    renderApp('/kiosk/tutorial');
    // The 教程 nav tab is present within the kiosk layout (route is reachable).
    // Use getAllByText: the tutorial landing page may also render a 教程 title
    // once its (mocked) data resolves, so there can be more than one match.
    expect(screen.getAllByText('教程').length).toBeGreaterThanOrEqual(1);
  });

  it('redirects /kiosk to /kiosk/play', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      token: null,
    });
    renderApp('/kiosk');
    // Should redirect to login (which then redirects to play after auth)
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });
});
