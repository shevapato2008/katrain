import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockLevels = vi.hoisted(() => [
  { elo_score: 1300, level_name: '1段', name: '星树熊', goal_difference: 3, timing: '40|30|3' },
  { elo_score: 1100, level_name: '1级', name: '星铠虾', goal_difference: 2, timing: '30|30|3' },
  { elo_score: 1000, level_name: '2级', name: '星夜鹰', goal_difference: 2, timing: '30|30|3' },
]);

vi.mock('../../api', () => ({
  API: {
    platformEngineLevels: vi.fn().mockResolvedValue({ levels: mockLevels }),
    platformEngineStart: vi.fn().mockResolvedValue({ session_id: 's1' }),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

import PlatformEngineSetupPage from '../pages/PlatformEngineSetupPage';

const renderPage = (platform = 'golaxy') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/cross-platform/engine/${platform}`]}>
        <Routes>
          <Route path="/kiosk/play/cross-platform/engine/:platform" element={<PlatformEngineSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlatformEngineSetupPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it('renders levels fetched from API.platformEngineLevels', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/星铠虾/)).toBeInTheDocument();
    });
  });

  it('renders the fixed rules info line (read-only)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/棋盘 19 路 · 中国规则 · 不计时/)).toBeInTheDocument();
    });
  });

  it('renders the derived komi label for the default handicap (分先)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/黑贴 7\.5/)).toBeInTheDocument();
    });
  });

  it('renders first-move chips (猜先/执黑/执白)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('猜先')).toBeInTheDocument();
      expect(screen.getByText('执黑')).toBeInTheDocument();
      expect(screen.getByText('执白')).toBeInTheDocument();
    });
  });

  it('shows an error alert when level fetch fails', async () => {
    const { API } = await import('../../api');
    (API.platformEngineLevels as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('calls API.platformEngineStart with the selected level/handicap/color (defaults) and navigates to the game route', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/星铠虾/)).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对弈/i }));

    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.platformEngineStart).toHaveBeenCalledWith(
        'golaxy',
        { level: 1100, human_color: 'nigiri', handicap: 0 },
        'test-token'
      );
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/game/s1');
    });
  });

  it('includes the selected handicap and color in the start payload', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/星铠虾/)).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText('执黑'));

    // Open the handicap select and choose 让4子.
    await user.click(screen.getByLabelText('让子'));
    await user.click(await screen.findByRole('option', { name: '让4子' }));

    await user.click(screen.getByRole('button', { name: /开始对弈/i }));

    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.platformEngineStart).toHaveBeenCalledWith(
        'golaxy',
        { level: 1100, human_color: 'B', handicap: 4 },
        'test-token'
      );
    });
  });

  it('back button navigates to the platform connect page', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/星铠虾/)).toBeInTheDocument();
    });
    const user = userEvent.setup();
    const backButtons = screen.getAllByRole('button');
    // First button rendered is the back (ArrowBack) button.
    await user.click(backButtons[0]);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform');
  });
});
