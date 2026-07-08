import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlayPage from '../pages/PlayPage';

// PlayPage reads the username for the greeting; stub AuthContext (no provider in tests).
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'fan' }, isAuthenticated: true }),
}));

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <PlayPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlayPage', () => {
  it('renders all 4 play mode cards', () => {
    renderPage();
    expect(screen.getByText('自由对弈')).toBeInTheDocument();
    expect(screen.getByText('升降级对弈')).toBeInTheDocument();
    expect(screen.getByText('本地对局')).toBeInTheDocument();
    expect(screen.getByText('在线大厅')).toBeInTheDocument();
  });

  it('separates AI and PvP sections with headers', () => {
    renderPage();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
    expect(screen.getByText('人人对弈')).toBeInTheDocument();
  });
});
