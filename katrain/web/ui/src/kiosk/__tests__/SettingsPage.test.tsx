import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SettingsPage from '../pages/SettingsPage';

const mockSetRotation = vi.fn();
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: mockSetRotation }),
}));

// SettingsPage now reads the real language system via useSettings; stub it (mirrors the
// OrientationContext mock) so the page renders without a full SettingsProvider.
vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
  languages: [
    { code: 'cn', name: '中文' },
    { code: 'en', name: 'English' },
  ],
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

  it('renders rotation chips with all 4 options', () => {
    renderPage();
    expect(screen.getByText('屏幕旋转')).toBeInTheDocument();
    expect(screen.getByText('0° 横屏')).toBeInTheDocument();
    expect(screen.getByText('90° 竖屏')).toBeInTheDocument();
    expect(screen.getByText('180° 横屏翻转')).toBeInTheDocument();
    expect(screen.getByText('270° 竖屏翻转')).toBeInTheDocument();
  });

  it('calls setRotation when a rotation chip is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('90° 竖屏'));
    expect(mockSetRotation).toHaveBeenCalledWith(90);
  });
});
