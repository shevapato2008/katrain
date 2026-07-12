import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformEngineSetupPage from './PlatformEngineSetupPage';

const { mockLevels } = vi.hoisted(() => ({
  mockLevels: [
    { elo_score: 100, level_name: '1级', name: '星铠虾', goal_difference: 0, timing: '' },
    { elo_score: 200, level_name: '2级', name: '星铠龙', goal_difference: 0, timing: '' },
  ],
}));

vi.mock('../../api', () => ({
  API: {
    platformEngineLevels: vi.fn().mockResolvedValue({ levels: mockLevels }),
    platformEngineStart: vi.fn().mockResolvedValue({ session_id: 's1' }),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/cross-platform/golaxy/engine/setup']}>
        <Routes>
          <Route path="/kiosk/play/cross-platform/:platform/engine/setup" element={<PlatformEngineSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlatformEngineSetupPage (compact, no-scroll)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Start button is present without scrolling (rendered, not gated behind overflow)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /开始对弈|start game/i })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument();
  });

  it('settings panel is structurally non-scrolling (overflow:hidden, not auto)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /开始对弈|start game/i })).toBeInTheDocument();
    });
    const panel = screen.getByTestId('engine-setup-noscroll-root');
    expect(getComputedStyle(panel).overflowY).not.toBe('auto');
  });
});
