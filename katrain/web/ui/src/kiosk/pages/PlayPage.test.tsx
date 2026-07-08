import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { ActiveSession } from '../utils/activeSession';
import PlayPage from './PlayPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { readActiveSession } = vi.hoisted(() => ({ readActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ readActiveSession }));

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
  beforeEach(() => {
    mockNavigate.mockReset();
    readActiveSession.mockReset();
    readActiveSession.mockReturnValue(null);
  });

  it('renders six equal ModeCards with exactly one primary (jade) card', () => {
    renderPage();
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(6);

    const primaryCards = screen.getAllByTestId('mode-card-primary');
    expect(primaryCards).toHaveLength(1);
    expect(primaryCards[0]).toHaveTextContent('自由对弈');
  });

  it('hides the resume bar when there is no active session', () => {
    readActiveSession.mockReturnValue(null);
    renderPage();

    expect(screen.queryByTestId('resume-game-bar')).toBeNull();
  });

  it('shows the resume bar and navigates to the session route on click', () => {
    const session: ActiveSession = {
      kind: 'game',
      label: '自由对弈 · 执黑',
      route: '/kiosk/play/ai/game/abc',
      ts: 1_720_000_000_000,
    };
    readActiveSession.mockReturnValue(session);
    renderPage();

    const bar = screen.getByTestId('resume-game-bar');
    expect(bar).toHaveTextContent('自由对弈 · 执黑');

    fireEvent.click(bar);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/abc');
  });
});
