import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import LobbyPage from '../pages/LobbyPage';

const mockOnlineUsers = [
  { id: 1, username: '张三', rank: '2D', elo_points: 1200 },
  { id: 2, username: '李四', rank: '3K', elo_points: 800 },
];

const mockActiveGames = [
  { session_id: 'game-1', player_b: '张三', player_w: '李四', spectator_count: 2, move_count: 45 },
];

let mockWsInstances: any[] = [];

class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();

  constructor() {
    mockWsInstances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }
}

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/pvp/lobby']}>
        <Routes>
          <Route path="/kiosk/play/pvp/lobby" element={<LobbyPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LobbyPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockWsInstances = [];
    (global as any).WebSocket = MockWebSocket;
    mockNavigate.mockReset();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/users/online')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockOnlineUsers) });
      }
      if (url.includes('/games/active')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockActiveGames) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    }) as any;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows auth required message when not authenticated', () => {
    mockUseAuth.mockReturnValue({ user: null, token: null });
    renderPage();
    expect(screen.getByText('请先登录后使用在线大厅')).toBeInTheDocument();
  });

  it('renders lobby title when authenticated', async () => {
    mockUseAuth.mockReturnValue({ user: { id: 1, username: '张三', rank: '2D' }, token: 'mock-token' });
    renderPage();
    expect(screen.getByText('在线大厅')).toBeInTheDocument();
  });

  it('renders online users list', async () => {
    mockUseAuth.mockReturnValue({ user: { id: 1, username: '张三', rank: '2D' }, token: 'mock-token' });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('张三')).toBeInTheDocument();
      expect(screen.getByText('李四')).toBeInTheDocument();
    });
  });

  it('renders active games', async () => {
    mockUseAuth.mockReturnValue({ user: { id: 1, username: '张三', rank: '2D' }, token: 'mock-token' });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('张三 (B) vs 李四 (W)')).toBeInTheDocument();
    });
  });

  it('navigates to kiosk room on match found', async () => {
    mockUseAuth.mockReturnValue({ user: { id: 1, username: '张三', rank: '2D' }, token: 'mock-token' });
    renderPage();

    await waitFor(() => expect(mockWsInstances.length).toBeGreaterThan(0));

    const ws = mockWsInstances[0];
    ws.onmessage?.({ data: JSON.stringify({ type: 'match_found', session_id: 'match-123' }) });

    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/room/match-123');
  });

  it('navigates to kiosk room on watch click', async () => {
    mockUseAuth.mockReturnValue({ user: { id: 1, username: '张三', rank: '2D' }, token: 'mock-token' });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('观战')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText('观战'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/pvp/room/game-1');
  });
});
