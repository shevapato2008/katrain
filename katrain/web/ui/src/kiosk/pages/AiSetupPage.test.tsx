import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from './AiSetupPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { startRanked, rankedState, retryRanked, createSession, gameSetup } = vi.hoisted(() => ({
  startRanked: vi.fn().mockResolvedValue({ session_id: 'ranked-s1', game_id: 'g1' }),
  retryRanked: vi.fn(),
  createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  gameSetup: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  rankedState: { current: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 2, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: [], net_score: 0, pending_settlement: false } as any },
}));

vi.mock('../../api', () => ({
  API: {
    createSession,
    gameSetup,
  },
}));
vi.mock('../../features/aiLadder/api', () => ({ startAiLadderGame: startRanked }));
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: () => ({ status: rankedState.current, retry: retryRanked }) }));

const { writeActiveSession } = vi.hoisted(() => ({ writeActiveSession: vi.fn() }));
vi.mock('../utils/activeSession', () => ({ writeActiveSession }));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AiSetupPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    writeActiveSession.mockReset();
    startRanked.mockClear();
    createSession.mockClear();
    gameSetup.mockClear();
  });

  it('renders the board-preview console header (盘面预览)', () => {
    renderPage();
    expect(screen.getByText('盘面预览')).toBeInTheDocument();
  });

  it('writes the active session and navigates to the game route on Start (free mode)', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对弈/i }));

    await waitFor(() => {
      expect(writeActiveSession).toHaveBeenCalledWith({
        kind: 'game',
        label: '自由对弈',
        route: '/kiosk/play/ai/game/s1',
        ts: expect.any(Number),
      });
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/ai/game/s1');
    });
  });

  it('writes the ranked label on Start (ranked mode)', async () => {
    renderPage('ranked');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对弈/i }));

    await waitFor(() => {
      expect(writeActiveSession).toHaveBeenCalledWith(
        expect.objectContaining({ kind: 'game', label: '升降级对弈', route: '/kiosk/play/ai/game/ranked-s1' })
      );
      expect(startRanked).toHaveBeenCalledWith(expect.objectContaining({ board_size: 19, color: 'black' }), 'test-token');
      expect(createSession).not.toHaveBeenCalled();
      expect(gameSetup).not.toHaveBeenCalled();
    });
  });

  it('shows the server-selected ranked opponent instead of HumanSL strength', () => {
    renderPage('ranked');
    expect(screen.getByText('定级对手：9级')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'AI 棋力' })).not.toBeInTheDocument();
  });

  it('Start button is present without scrolling (rendered, not gated behind overflow)', () => {
    renderPage('free');
    expect(screen.getByRole('button', { name: /开始对弈|start game/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument();
  });

  it('rules render as a dropdown trigger, not 4 separate chips', () => {
    renderPage('free');
    // Compact form shows the current rule value as one control; the Japanese/Korean/AGA
    // options are behind the dropdown (not all visible at once).
    expect(screen.queryByText('AGA')).not.toBeInTheDocument();
  });
});
