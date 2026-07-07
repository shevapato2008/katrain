import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
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
    renderLayout();
    expect(screen.getByText('弈航')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    // NavigationRail renders as vertical nav (72px wide)
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
});
