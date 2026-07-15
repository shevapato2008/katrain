import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { useEffect } from 'react';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';
import { useImmersive } from '../context/ImmersiveContext';

const renderLayout = (route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<KioskLayout username="张三" />}>
            <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
            <Route path="/kiosk/report" element={<div>REPORT_CONTENT</div>} />
            <Route path="/kiosk/settings" element={<div>SETTINGS_CONTENT</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** Outlet child that flips the real ImmersiveContext (mounted by KioskLayout) to
 * immersive mode on mount — proves the A6→A10 immersive mechanism end to end. */
const ImmersiveTrigger = () => {
  const { setImmersive } = useImmersive();
  useEffect(() => {
    setImmersive(true);
  }, [setImmersive]);
  return <div>IMMERSIVE_CONTENT</div>;
};

describe('KioskLayout', () => {
  it('renders header, dock, console, and outlet on /kiosk/play', () => {
    renderLayout('/kiosk/play');
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    expect(screen.getByText('智能棋盘')).toBeInTheDocument();
  });

  it('shows Header and Dock on Report but Header without Dock on Settings', () => {
    const report = renderLayout('/kiosk/report');
    expect(screen.getByText('REPORT_CONTENT')).toBeInTheDocument();
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    report.unmount();

    renderLayout('/kiosk/settings');
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.queryByText('复盘')).not.toBeInTheDocument();
  });

  it('gates the SmartBoardConsole to CONSOLE_ROUTES — hidden on /kiosk/settings', () => {
    renderLayout('/kiosk/settings');
    expect(screen.getByText('SETTINGS_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('智能棋盘')).toBeNull();
  });

  it('collapses Header and Dock when a descendant sets immersive mode', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/play']}>
          <Routes>
            <Route element={<KioskLayout username="张三" />}>
              <Route path="/kiosk/play" element={<ImmersiveTrigger />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText('IMMERSIVE_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('智星盒')).toBeNull();
    expect(screen.queryByText('对弈')).toBeNull();
  });
});
