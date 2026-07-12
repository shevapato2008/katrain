import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';

vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'new-session-123', state: {} }),
    gameSetup: vi.fn().mockResolvedValue({ session_id: 'new-session-123', state: {} }),
  },
}));

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
  it('renders board preview canvas', () => {
    renderPage();
    const canvas = document.querySelector('canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('renders board size options', () => {
    renderPage();
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('renders ruleset selector', async () => {
    renderPage();
    expect(screen.getByRole('combobox', { name: '规则' })).toBeInTheDocument();
    expect(screen.getByText('中国')).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: '规则' }));
    expect(screen.getByRole('option', { name: '日本' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '韩国' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'AGA' })).toBeInTheDocument();
  });

  it('renders color selection', () => {
    renderPage();
    expect(screen.getByText(/黑/)).toBeInTheDocument();
    expect(screen.getByText(/白/)).toBeInTheDocument();
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对弈/i })).toBeInTheDocument();
  });

  it('shows AI strategy selector for free mode', async () => {
    renderPage('free');
    expect(screen.getByRole('combobox', { name: 'AI 策略' })).toBeInTheDocument();
    expect(screen.getByText('拟人')).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: 'AI 策略' }));
    expect(screen.getByRole('option', { name: 'KataGo' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '实地' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '厚势' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '策略' })).toBeInTheDocument();
  });

  it('shows AI strength selector in free mode when human strategy selected', () => {
    renderPage('free');
    // Default strategy is ai:human, so the strength dropdown should be visible
    expect(screen.getByRole('combobox', { name: 'AI 棋力' })).toBeInTheDocument();
  });

  it('hides AI strength selector in free mode for non-human strategy', async () => {
    renderPage('free');
    const user = userEvent.setup();
    // Switch AI 策略 away from ai:human (拟人)
    await user.click(screen.getByRole('combobox', { name: 'AI 策略' }));
    await user.click(screen.getByRole('option', { name: 'KataGo' }));
    expect(screen.queryByRole('combobox', { name: 'AI 棋力' })).not.toBeInTheDocument();
  });

  it('hides AI strategy selector for ranked mode', () => {
    renderPage('ranked');
    expect(screen.queryByRole('combobox', { name: 'AI 策略' })).not.toBeInTheDocument();
  });

  it('shows AI strength selector for ranked mode', () => {
    renderPage('ranked');
    expect(screen.getByRole('combobox', { name: 'AI 棋力' })).toBeInTheDocument();
  });

  it('renders handicap selector defaulting to none', () => {
    renderPage();
    expect(screen.getByRole('combobox', { name: '让子' })).toBeInTheDocument();
    expect(screen.getByText('无')).toBeInTheDocument();
  });

  it('shows komi selector in free mode with no handicap', () => {
    renderPage('free');
    expect(screen.getByRole('combobox', { name: '贴目' })).toBeInTheDocument();
  });

  it('hides komi selector when handicap is set', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: '让子' }));
    await user.click(screen.getByRole('option', { name: '2子' }));
    expect(screen.queryByRole('combobox', { name: '贴目' })).not.toBeInTheDocument();
  });

  it('shows time control selector', () => {
    renderPage();
    expect(screen.getByRole('combobox', { name: '用时' })).toBeInTheDocument();
  });

  it('time selector defaults to untimed in free mode', () => {
    renderPage('free');
    expect(screen.getByText('不限时')).toBeInTheDocument();
  });

  it('offers timed presets that map onto the existing main-time/byoyomi state', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: '用时' }));
    expect(screen.getByRole('option', { name: /5分.*3.*30秒/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /10分.*3.*30秒/ })).toBeInTheDocument();
  });

  it('time selector excludes the untimed preset for ranked mode (time is forced on)', async () => {
    renderPage('ranked');
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: '用时' }));
    expect(screen.queryByRole('option', { name: '不限时' })).not.toBeInTheDocument();
  });

  it('ranked mode defaults to a byoyomi-only preset (30s x3), same as prior slider defaults', () => {
    renderPage('ranked');
    expect(screen.getByText(/仅读秒.*30秒.*3/)).toBeInTheDocument();
  });

  it('calls API.createSession and gameSetup on start', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对弈/i }));
    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.createSession).toHaveBeenCalled();
      expect(API.gameSetup).toHaveBeenCalledWith('new-session-123', 'free', expect.objectContaining({
        board_size: 19,
        rules: 'chinese',
        color: 'black',
      }));
    });
  });

  it('shows error alert when API call fails', async () => {
    const { API } = await import('../../api');
    (API.createSession as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始对弈/i }));
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });
});
