import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

const mockUseOrientation = vi.fn();
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => mockUseOrientation(),
}));

const renderLayout = (route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<KioskLayout username="张三" />}>
            <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('KioskLayout', () => {
  it('renders status bar, navigation rail, and outlet in landscape', () => {
    mockUseOrientation.mockReturnValue({ isPortrait: false });
    renderLayout();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    // NavigationRail renders as vertical nav (72px wide)
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('renders status bar, top tab bar, and outlet in portrait', () => {
    mockUseOrientation.mockReturnValue({ isPortrait: true });
    renderLayout();
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    // TopTabBar renders as horizontal nav (48px tall)
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
});
