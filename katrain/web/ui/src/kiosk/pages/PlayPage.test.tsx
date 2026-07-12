import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// PlayPage reads the username for the greeting and the token to fetch platform status;
// stub AuthContext (no provider in tests). Overridable per-test via mockReturnValue.
const { useAuthMock } = vi.hoisted(() => ({ useAuthMock: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: useAuthMock }));

// 跨平台对弈 section fetches API.platformStatus(token); stub it per-test.
const { platformStatusMock } = vi.hoisted(() => ({ platformStatusMock: vi.fn() }));
vi.mock('../../api', () => ({ API: { platformStatus: platformStatusMock } }));

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
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({ user: { username: 'fan' }, isAuthenticated: true, token: null });
    platformStatusMock.mockReset();
    platformStatusMock.mockResolvedValue({ platforms: [] });
  });

  it('renders four equal ModeCards with exactly one primary (jade) card', () => {
    renderPage();
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(4);

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

  it('renders three sibling sections including 跨平台对弈', async () => {
    useAuthMock.mockReturnValue({ user: { username: '友' }, isAuthenticated: true, token: 't' });
    platformStatusMock.mockResolvedValue({
      platforms: [{ platform: 'golaxy', connected: true, saved_username: '13800000000', supports_engine_play: true }],
    });
    renderPage();
    expect(screen.getByText('人机对弈')).toBeInTheDocument();
    expect(screen.getByText('人人对弈')).toBeInTheDocument();
    expect(screen.getByText('跨平台对弈')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('星阵围棋')).toBeInTheDocument());
  });

  it('does not render a duplicate 跨平台 mode card under 人机/人人', () => {
    renderPage();
    // The old duplicate ModeCard title. Platform cards use platform names, not this.
    expect(screen.queryByText('连接 OGS、野狐等平台')).not.toBeInTheDocument();
  });
});
