import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import GameLibraryModal from './CloudSGFPanel';
import { vi, describe, it, expect, Mock, beforeEach } from 'vitest';
import { useAuth } from '../../../context/AuthContext';

// Mock fetch
global.fetch = vi.fn();

// Mock useAuth
vi.mock('../../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// Mock KifuAPI
vi.mock('../../../api/kifuApi', () => ({
  KifuAPI: {
    getAlbums: vi.fn(),
    getAlbum: vi.fn(),
  },
}));

// Mock UserGamesAPI
vi.mock('../../api/userGamesApi', () => ({
  UserGamesAPI: {
    list: vi.fn(),
    get: vi.fn(),
  },
}));

import { KifuAPI } from '../../../api/kifuApi';
import { UserGamesAPI } from '../../api/userGamesApi';

describe('GameLibraryModal', () => {
  const mockOnClose = vi.fn();
  const mockOnLoadGame = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    (useAuth as Mock).mockReturnValue({ token: 'mock-token' });
  });

  it('renders when open', () => {
    (UserGamesAPI.list as Mock).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 15,
    });

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);
    expect(screen.getByText('棋谱库')).toBeInTheDocument();
  });

  it('shows category tabs', () => {
    (UserGamesAPI.list as Mock).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 15,
    });

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);
    expect(screen.getByText('我的棋谱')).toBeInTheDocument();
    expect(screen.getByText('我的盘面')).toBeInTheDocument();
    expect(screen.getByText('大赛棋谱')).toBeInTheDocument();
  });

  it('fetches personal games on open', async () => {
    const mockGames = {
      items: [
        {
          id: 'abc123',
          title: 'Test Game',
          player_black: 'Alice',
          player_white: 'Bob',
          result: 'B+R',
          move_count: 120,
          source: 'research',
          category: 'game',
          board_size: 19,
          rules: 'chinese',
          komi: 7.5,
          game_type: null,
          event: null,
          game_date: '2026-01-15',
          created_at: '2026-01-15T10:00:00',
          updated_at: null,
          user_id: 1,
        },
      ],
      total: 1,
      page: 1,
      page_size: 15,
    };
    (UserGamesAPI.list as Mock).mockResolvedValueOnce(mockGames);

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);

    await waitFor(() => {
      expect(UserGamesAPI.list).toHaveBeenCalledWith('mock-token', expect.objectContaining({
        category: 'game',
        page: 1,
        page_size: 15,
      }));
    });

    await waitFor(() => {
      expect(screen.getByText('Test Game')).toBeInTheDocument();
    });
  });

  it('switches to public kifu category', async () => {
    (UserGamesAPI.list as Mock).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 15,
    });
    (KifuAPI.getAlbums as Mock).mockResolvedValueOnce({
      items: [
        { id: 1, title: 'Tournament Game', player_black: 'Lee', player_white: 'Ke', result: 'W+2.5', move_count: 250, sgf_content: '(;FF[4];B[pd])' },
      ],
      total: 1,
    });

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);

    // Wait for initial load
    await waitFor(() => {
      expect(UserGamesAPI.list).toHaveBeenCalled();
    });

    // Click on public kifu tab
    fireEvent.click(screen.getByText('大赛棋谱'));

    await waitFor(() => {
      expect(KifuAPI.getAlbums).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText('Tournament Game')).toBeInTheDocument();
    });
  });

  it('loads a game and closes modal', async () => {
    (UserGamesAPI.list as Mock).mockResolvedValueOnce({
      items: [
        {
          id: 'abc123',
          title: 'My Game',
          player_black: 'A',
          player_white: 'B',
          result: '',
          move_count: 50,
          source: 'research',
          category: 'game',
          board_size: 19,
          rules: 'chinese',
          komi: 7.5,
          game_type: null,
          event: null,
          game_date: null,
          created_at: '2026-01-15T10:00:00',
          updated_at: null,
          user_id: 1,
        },
      ],
      total: 1,
      page: 1,
      page_size: 15,
    });
    (UserGamesAPI.get as Mock).mockResolvedValueOnce({
      id: 'abc123',
      sgf_content: '(;FF[4]SZ[19];B[pd];W[dp])',
    });

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);

    await waitFor(() => {
      expect(screen.getByText('My Game')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('My Game'));

    await waitFor(() => {
      expect(UserGamesAPI.get).toHaveBeenCalledWith('mock-token', 'abc123');
    });

    await waitFor(() => {
      expect(mockOnLoadGame).toHaveBeenCalledWith('(;FF[4]SZ[19];B[pd];W[dp])');
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('shows login prompt when not authenticated', () => {
    (useAuth as Mock).mockReturnValue({ token: null });

    render(<GameLibraryModal open={true} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);

    expect(screen.getByText('登录后可查看个人棋谱')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    const { container } = render(<GameLibraryModal open={false} onClose={mockOnClose} onLoadGame={mockOnLoadGame} />);
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });
});
