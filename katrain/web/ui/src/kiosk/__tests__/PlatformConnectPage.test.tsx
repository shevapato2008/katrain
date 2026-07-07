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

const mockPlatformStatus = vi.fn();
vi.mock('../../api', () => ({
  API: {
    platformStatus: (...args: any[]) => mockPlatformStatus(...args),
    platformLogin: vi.fn().mockResolvedValue({ status: 'connected' }),
    platformLogout: vi.fn().mockResolvedValue({ status: 'disconnected' }),
    platformSmsRequest: vi.fn().mockResolvedValue({ status: 'sent' }),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

import PlatformConnectPage from '../pages/PlatformConnectPage';

const golaxyConnected = {
  platform: 'golaxy',
  connected: true,
  supports_live_play: true,
  supports_automatch: false,
  supports_rooms: false,
  supports_seek_graph: false,
  supports_engine_play: true,
  saved_username: '13800000000',
};

const golaxyDisconnected = {
  platform: 'golaxy',
  connected: false,
  supports_live_play: true,
  supports_automatch: false,
  supports_rooms: false,
  supports_seek_graph: false,
  supports_engine_play: true,
};

const ogsConnected = {
  platform: 'ogs',
  connected: true,
  supports_live_play: true,
  supports_automatch: true,
  supports_rooms: true,
  supports_seek_graph: true,
  supports_engine_play: false,
  saved_username: 'testuser',
};

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/cross-platform']}>
        <Routes>
          <Route path="/kiosk/play/cross-platform" element={<PlatformConnectPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('PlatformConnectPage', () => {
  beforeEach(async () => {
    mockNavigate.mockReset();
    mockPlatformStatus.mockReset();
    const { API } = await import('../../api');
    (API.platformLogin as ReturnType<typeof vi.fn>).mockClear();
    (API.platformLogout as ReturnType<typeof vi.fn>).mockClear();
    (API.platformSmsRequest as ReturnType<typeof vi.fn>).mockClear();
    vi.useRealTimers();
  });

  it('a connected golaxy platform (engine play) navigates to the engine setup route', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [golaxyConnected] });
    renderPage();

    const button = await screen.findByRole('button', { name: '人机对弈' });
    const user = userEvent.setup();
    await user.click(button);

    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });

  it('a connected OGS platform (no engine play) navigates to the lobby', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [ogsConnected] });
    renderPage();

    const button = await screen.findByRole('button', { name: '进入大厅' });
    const user = userEvent.setup();
    await user.click(button);

    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/lobby?platform=ogs');
  });

  it('golaxy card is no longer gated as coming soon', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [golaxyDisconnected] });
    renderPage();

    await screen.findByText('星阵围棋');
    expect(screen.queryByText('即将支持')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('SMS get-code button calls API.platformSmsRequest with the entered phone', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [golaxyDisconnected] });
    renderPage();
    const user = userEvent.setup();

    const loginButton = await screen.findByRole('button', { name: /登录/i });
    await user.click(loginButton);

    const phoneField = await screen.findByLabelText('手机号');
    await user.type(phoneField, '13900001111');

    const smsButton = screen.getByRole('button', { name: '获取验证码' });
    await user.click(smsButton);

    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.platformSmsRequest).toHaveBeenCalledWith('golaxy', '13900001111', 'test-token');
    });
  });

  it('SMS button shows inline error and does not call the API when phone is empty', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [golaxyDisconnected] });
    renderPage();
    const user = userEvent.setup();

    const loginButton = await screen.findByRole('button', { name: /登录/i });
    await user.click(loginButton);

    const smsButton = await screen.findByRole('button', { name: '获取验证码' });
    await user.click(smsButton);

    const { API } = await import('../../api');
    expect(API.platformSmsRequest).not.toHaveBeenCalled();
    expect(screen.getByText('请先输入手机号')).toBeInTheDocument();
  });

  it('login submit for golaxy sends sms_code instead of password', async () => {
    mockPlatformStatus.mockResolvedValue({ platforms: [golaxyDisconnected] });
    renderPage();
    const user = userEvent.setup();

    const loginButton = await screen.findByRole('button', { name: /登录/i });
    await user.click(loginButton);

    const phoneField = await screen.findByLabelText('手机号');
    await user.type(phoneField, '13900001111');
    const codeField = screen.getByLabelText('验证码');
    await user.type(codeField, '123456');

    const submitButtons = screen.getAllByRole('button', { name: '登录' });
    await user.click(submitButtons[submitButtons.length - 1]);

    const { API } = await import('../../api');
    await waitFor(() => {
      expect(API.platformLogin).toHaveBeenCalledWith(
        'golaxy',
        { username: '13900001111', sms_code: '123456' },
        'test-token'
      );
    });
  });
});
