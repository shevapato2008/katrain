import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation, type InitialEntry } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SettingsPage from '../pages/SettingsPage';

// B6: SettingsPage pulls in useSettings/useAuth/useGeometry (via AccountSection +
// PhysicalBoardStatus). Mock each context module directly — same idiom as
// src/kiosk/__tests__/KioskAuth.test.tsx (AuthContext) and
// src/kiosk/__tests__/PhysicalBoardStatus.test.tsx (GeometryContext) — rather
// than mounting the real providers, which would require faking network calls
// (SettingsProvider's i18n.loadTranslations, GeometryProvider's status poll).
const mockSetLanguage = vi.fn();
vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({
    language: 'cn',
    setLanguage: mockSetLanguage,
    // Shares galaxy's full catalog; a small subset is enough to exercise the Select.
    languages: [
      { code: 'en', name: 'English' },
      { code: 'cn', name: '中文' },
      { code: 'jp', name: '日本語' },
    ],
  }),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: '张三', rank: '2D', credits: 0 },
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    token: 'mock-token',
  }),
}));

vi.mock('../context/GeometryContext', () => ({
  useGeometry: () => ({
    status: {
      phase: 'required',
      session_calibrated: false,
      last_valid: false,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
    },
  }),
}));

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </ThemeProvider>
  );

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
};

const renderNavigationPage = (entry: InitialEntry) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/kiosk/settings" element={<SettingsPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

describe('SettingsPage', () => {
  it('renders without crashing and shows key elements', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /设置/i })).toBeInTheDocument();
    expect(screen.getByText(/语言/)).toBeInTheDocument();
    expect(screen.getByText(/外部平台/)).toBeInTheDocument();
    expect(screen.getByText(/野狐围棋/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新标定棋盘' })).toBeInTheDocument();
  });

  it('keeps both 1024x600 columns reachable by placing external platforms in the shorter left column', () => {
    renderPage();
    const left = screen.getByTestId('settings-left-column');
    const right = screen.getByTestId('settings-right-column');
    expect(within(left).getByText('外部平台')).toBeVisible();
    expect(within(right).getByText('账户')).toBeVisible();
    expect(left).toHaveStyle({ overflow: 'hidden' });
    expect(right).toHaveStyle({ overflow: 'hidden' });
    expect(screen.getByText('野狐围棋')).toBeVisible();
  });

  it('switches language via the persisted setter through the shared catalog', () => {
    mockSetLanguage.mockClear();
    renderPage();
    // Open the language Select (renders the current value 中文) and pick English.
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(screen.getByRole('option', { name: 'English' }));
    expect(mockSetLanguage).toHaveBeenCalledWith('en');
  });

  it('renders a translated page-owned back button —— §11 页控条那个 36 高带字的返回键', () => {
    renderPage();

    const back = screen.getByRole('button', { name: '返回' });
    // 48 见方的圆钮是**上一版页面自己手写**的返回条。§11 把返回统一下放到页控条,
    // 尺寸由共享 `--pagebar-back-h`(36)给,四棋类同一个数 —— 这里不再逐像素断言,
    // 那是布局结论,归 `tests/kiosk-shell-geometry.spec.ts` 的真浏览器闸。
    expect(back).toHaveClass('kiosk-pagebar__back');
  });

  it('returns to a validated internal kiosk route from location state', () => {
    renderNavigationPage({
      pathname: '/kiosk/settings',
      state: { from: '/kiosk/kifu?page=3&q=%E6%A3%8B' },
    });

    fireEvent.click(screen.getByRole('button', { name: '返回' }));

    expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/kifu?page=3&q=%E6%A3%8B');
  });

  it.each([
    ['absent state', undefined],
    ['an external origin', 'https://example.com/kiosk/kifu'],
    ['the Settings route with query and hash', '/kiosk/settings?from=kifu#top'],
    ['a Settings descendant', '/kiosk/settings/account?tab=profile#top'],
    ['a non-kiosk route', '/galaxy/report'],
  ])('falls back to play for %s', (_case, from) => {
    renderNavigationPage({ pathname: '/kiosk/settings', state: from === undefined ? null : { from } });

    fireEvent.click(screen.getByRole('button', { name: '返回' }));

    expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/play');
  });
});
