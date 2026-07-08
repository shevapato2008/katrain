import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SettingsPage from '../pages/SettingsPage';

const mockSetRotation = vi.fn();
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: mockSetRotation }),
}));

// B6: SettingsPage now also pulls in useSettings/useAuth/useGeometry (via
// AccountSection + PhysicalBoardStatus). Mock each context module directly —
// same idiom as src/kiosk/__tests__/KioskAuth.test.tsx (AuthContext) and
// src/kiosk/__tests__/PhysicalBoardStatus.test.tsx (GeometryContext) — rather
// than mounting the real providers, which would require faking network calls
// (SettingsProvider's i18n.loadTranslations, GeometryProvider's status poll).
const mockSetLanguage = vi.fn();
vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: mockSetLanguage, languages: [] }),
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

describe('SettingsPage', () => {
  it('renders without crashing and shows key elements', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /设置/i })).toBeInTheDocument();
    expect(screen.getByText(/语言/)).toBeInTheDocument();
    expect(screen.getByText(/外部平台/)).toBeInTheDocument();
    expect(screen.getByText(/野狐围棋/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新标定棋盘' })).toBeInTheDocument();
  });

  it('renders rotation chips with both landscape options', () => {
    renderPage();
    expect(screen.getByText('屏幕旋转')).toBeInTheDocument();
    expect(screen.getByText('0° 横屏')).toBeInTheDocument();
    expect(screen.getByText('180° 横屏翻转')).toBeInTheDocument();
  });

  it('calls setRotation when a rotation chip is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('180° 横屏翻转'));
    expect(mockSetRotation).toHaveBeenCalledWith(180);
  });
});
