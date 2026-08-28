import { describe, it, expect, vi } from 'vitest';
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

vi.mock('../pages/ReportsPage', () => ({
  default: () => <h1>KIOSK_REPORT_PAGE</h1>,
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
  /* ⚠️ 这一条原来断言的是「游客到 /kiosk/play 会被弹到登录页」。
     **Fan 2026-08-28 亲裁改了这条边界**:「把 KioskAuthGuard 从自由对弈那几条路由上摘掉,
     其余(升降级、大厅、设置)保持。」所以它现在断言的是相反的事 ——
     而「其余仍然被挡」那几格移到了下面那个 describe 里,一格都没少。 */
  it('游客到得了自由对弈那条链的入口(不再被弹到登录页)', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      token: null,
    });
    renderApp('/kiosk/play');
    expect(screen.queryByRole('button', { name: /^登录$/ })).toBeNull();
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
    // Dock 上那一项 Task 4 起叫「课程」不叫「教程」——规范 §3 的共享词典
    // (四棋类同一份词,不是围棋能自选的)。路由 `/kiosk/tutorial` 没变。
    // 用 getAllByText:课程落地页自己也可能渲染同名标题,不止一处匹配。
    expect(screen.getAllByText('课程').length).toBeGreaterThanOrEqual(1);
  });

  it('registers the real first-level Report destination with Header and Dock', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: '张三', rank: '2D', credits: 0 },
      login: vi.fn(), logout: vi.fn(), token: 'mock-token',
    });
    renderApp('/kiosk/report');
    expect(screen.getByRole('heading', { name: 'KIOSK_REPORT_PAGE' })).toBeInTheDocument();
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    expect(screen.queryByText('智能棋盘')).not.toBeInTheDocument();
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
    // 游客也一样落到对弈页 —— index 重定向和兜底都在守卫**外面**。
    expect(screen.queryByRole('button', { name: /^登录$/ })).toBeNull();
  });

  /* 🔴 边界的另一半。摘守卫只摘了自由对弈那条链,**这几格证明其余没跟着被摘掉** ——
     少了它们,哪天有人把 `<Route element={<KioskAuthGuard />}>` 整个删掉,上面那几条
     「游客到得了」照样全绿,而设置和大厅就裸了。 */
  describe('仍然要登录的那些', () => {
    const asGuest = () => mockUseAuth.mockReturnValue({
      isAuthenticated: false, isLoading: false, user: null, login: vi.fn(), logout: vi.fn(), token: null,
    });

    it('设置', () => {
      asGuest();
      renderApp('/kiosk/settings');
      expect(screen.queryByTestId('settings-page')).toBeNull();
      expect(screen.getByRole('button', { name: /^登录$/ })).toBeInTheDocument();
    });

    it('复盘', () => {
      asGuest();
      renderApp('/kiosk/report');
      expect(screen.queryByText('KIOSK_REPORT_PAGE')).toBeNull();
      expect(screen.getByRole('button', { name: /^登录$/ })).toBeInTheDocument();
    });

    it('对战大厅', () => {
      asGuest();
      renderApp('/kiosk/play/pvp/lobby');
      expect(screen.getByRole('button', { name: /^登录$/ })).toBeInTheDocument();
    });

    it('本地两人对局屏', () => {
      asGuest();
      renderApp('/kiosk/play/pvp/local/game/s1');
      expect(screen.getByRole('button', { name: /^登录$/ })).toBeInTheDocument();
    });
  });
});
