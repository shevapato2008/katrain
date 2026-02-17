import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

describe('KioskLayout', () => {
  it('renders status bar, navigation rail, and outlet content', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/play']}>
          <Routes>
            <Route element={<KioskLayout username="张三" />}>
              <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );
    // StatusBar
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
    // NavigationRail
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('设置')).toBeInTheDocument();
    // Outlet
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
  });
});
