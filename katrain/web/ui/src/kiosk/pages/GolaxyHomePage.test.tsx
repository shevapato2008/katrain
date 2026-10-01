import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import GolaxyHomePage from './GolaxyHomePage';

const { platformStatus, navigate, vision } = vi.hoisted(() => ({
  platformStatus: vi.fn(),
  navigate: vi.fn(),
  vision: { enabled: true },
}));
vi.mock('../../api', () => ({ API: { platformStatus } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true }),
}));
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ isVisionEnabled: vision.enabled }),
}));
vi.mock('react-router-dom', async () => ({
  ...await vi.importActual('react-router-dom'),
  useNavigate: () => navigate,
}));

const connected = (saved_username?: string) => ({
  platforms: [{ platform: 'golaxy', connected: true, saved_username }],
});
const renderPage = () => render(<MemoryRouter><GolaxyHomePage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  vision.enabled = true;
  localStorage.clear();
  platformStatus.mockResolvedValue(connected('真实账号'));
});

describe('Golaxy home', () => {
  it('shows loading, then the real connected account and the engine entry', async () => {
    let finish!: (value: unknown) => void;
    platformStatus.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderPage();
    expect(screen.getByText('正在读取星阵连接')).toBeInTheDocument();
    finish(connected('真实账号'));
    expect(await screen.findByText(/真实账号/)).toBeInTheDocument();
    expect(screen.queryByText('秋水长天')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /人机对弈/ }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });

  it('shows a login route when the account is disconnected', async () => {
    platformStatus.mockResolvedValue({ platforms: [{ platform: 'golaxy', connected: false }] });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '连接星阵' }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');
    expect(screen.queryByRole('button', { name: /人机对弈/ })).not.toBeInTheDocument();
  });

  it('offers retry after a status request fails', async () => {
    platformStatus.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: '重试' }));
    expect(await screen.findByText(/真实账号/)).toBeInTheDocument();
    expect(platformStatus).toHaveBeenCalledTimes(2);
  });

  it('keeps unverified player modes unavailable', async () => {
    renderPage();
    await screen.findByText(/真实账号/);
    expect(screen.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /房间/ })).toBeDisabled();
    expect(screen.getAllByText('人人对弈还没接通')).toHaveLength(3);
    expect(screen.queryByText('秋水长天')).not.toBeInTheDocument();
  });

  it('switches between screen and board only when vision is available', async () => {
    const page = renderPage();
    await screen.findByText(/真实账号/);
    const board = screen.getByRole('button', { name: '实体盘' });
    const screenButton = screen.getByRole('button', { name: '屏幕' });
    expect(board).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(screenButton);
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('false');
    await userEvent.click(board);
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('true');
    page.unmount();
    vision.enabled = false;
    renderPage();
    await screen.findByText(/真实账号/);
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '屏幕' })).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem('kiosk_play_on_board')).toBe('true');
  });
});
