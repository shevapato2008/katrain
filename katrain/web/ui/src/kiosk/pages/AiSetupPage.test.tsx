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

vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    gameSetup: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  },
}));

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
        expect.objectContaining({ kind: 'game', label: '升降级对弈', route: '/kiosk/play/ai/game/s1' })
      );
    });
  });
});
