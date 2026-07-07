import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';
import { translateResult } from '../../utils/resultTranslation';

// Hoisted spies referenced by the mock factories below.
const { mockCreateSession, mockNavigate } = vi.hoisted(() => ({
  mockCreateSession: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({ createSession: mockCreateSession }),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Translation can't be exercised in the empty-i18n test harness (fallbacks always win),
// so we mock it to identity and assert the WIRING (called with result/t/rules) instead.
vi.mock('../../utils/resultTranslation', () => ({
  translateResult: vi.fn((result: string) => result),
}));

const mockAlbums = [
  {
    id: 1, player_black: '柯洁', player_white: '申真谞',
    black_rank: '九段', white_rank: '九段',
    event: '2024 LG杯决赛', result: 'W+R', move_count: 211,
    date_played: '2024-12-15', board_size: 19, handicap: 0,
    komi: 6.5, rules: 'chinese', round_name: '决赛',
  },
  {
    id: 2, player_black: '张三', player_white: 'KataGo',
    black_rank: '2D', white_rank: '5D',
    event: '自由对弈', result: 'W+12.5', move_count: 184,
    date_played: '2025-01-05', board_size: 19, handicap: 0,
    komi: 6.5, rules: 'chinese', round_name: null,
  },
];

// 3-move SGF → previewCurrentMove initializes to 3 (deterministic counter/boundary tests).
const DETAIL_SGF = '(;FF[4]GM[1]SZ[19];B[pd];W[dp];B[pp])';

const listResponse = (total = 2, page = 1) => ({
  ok: true,
  json: () => Promise.resolve({ items: mockAlbums, total, page, page_size: 20 }),
});

const detailResponse = () => ({
  ok: true,
  json: () => Promise.resolve({ ...mockAlbums[0], place: null, source: null, sgf_content: DETAIL_SGF }),
});

// URL-routed mock: the /albums/:id branch MUST be checked before the bare /albums list
// branch, or the list shadows the detail and previewSgf never loads.
const installFetch = (total = 2) => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (/\/albums\/\d+/.test(url)) return Promise.resolve(detailResponse());
    const page = Number(new URL(url, 'http://x').searchParams.get('page')) || 1;
    return Promise.resolve(listResponse(total, page));
  }) as unknown as typeof fetch;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockCreateSession.mockResolvedValue('sess-1');
  vi.mocked(translateResult).mockImplementation((result: string) => result);
  installFetch();
});

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <KifuPage />
      </MemoryRouter>
    </ThemeProvider>
  );

// Selects the first card and waits for the detail SGF to load (button enabled).
const selectFirstKifu = async () => {
  await waitFor(() => expect(screen.getByText('柯洁')).toBeInTheDocument());
  fireEvent.click(screen.getByText('柯洁'));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /在研究中打开/ })).not.toBeDisabled()
  );
};

describe('KifuPage', () => {
  it('renders the title "棋谱库"', () => {
    renderPage();
    expect(screen.getByText('棋谱库')).toBeInTheDocument();
  });

  it('renders the search box', () => {
    renderPage();
    expect(screen.getByPlaceholderText('搜索棋手、赛事...')).toBeInTheDocument();
  });

  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches and renders kifu cards with player names and events', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('柯洁')).toBeInTheDocument();
      expect(screen.getByText('申真谞')).toBeInTheDocument();
      expect(screen.getByText('张三')).toBeInTheDocument();
      expect(screen.getByText(/LG杯/)).toBeInTheDocument();
    });
  });

  it('renders ResultBadge for each kifu', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByTestId('result-badge').length).toBe(2);
    });
  });

  it('renders round_name when present', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('决赛')).toBeInTheDocument());
  });

  it('wires translateResult with (result, t, rules)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('result-badge').length).toBe(2));
    expect(translateResult).toHaveBeenCalledWith('W+R', expect.any(Function), 'chinese');
  });

  it('shows total count from API response', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('2 局')).toBeInTheDocument();
    });
  });

  it('shows preview area with navigation when a card is selected', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('柯洁')).toBeInTheDocument());
    expect(screen.getByText('选择一局棋谱预览')).toBeInTheDocument();

    fireEvent.click(screen.getByText('柯洁'));

    expect(screen.queryByText('选择一局棋谱预览')).not.toBeInTheDocument();
    expect(screen.getByTestId('kifu-preview-nav')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /在研究中打开/ })).toBeInTheDocument();
  });

  it('disables "Open in Research" until the SGF detail loads', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('柯洁')).toBeInTheDocument());
    fireEvent.click(screen.getByText('柯洁'));
    // Immediately after selection (before getAlbum resolves) the button is disabled.
    expect(screen.getByRole('button', { name: /在研究中打开/ })).toBeDisabled();
    // After the detail resolves it becomes enabled.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /在研究中打开/ })).not.toBeDisabled()
    );
  });

  it('opens in research: creates a session with the SGF and navigates', async () => {
    renderPage();
    await selectFirstKifu();

    fireEvent.click(screen.getByRole('button', { name: /在研究中打开/ }));

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledWith(
        DETAIL_SGF,
        expect.objectContaining({ initialMove: 3, skipAnalysis: true })
      );
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research/session/sess-1');
    });
  });

  it('shows an error toast and does not navigate when session creation fails', async () => {
    mockCreateSession.mockResolvedValue(null);
    renderPage();
    await selectFirstKifu();

    fireEvent.click(screen.getByRole('button', { name: /在研究中打开/ }));

    await waitFor(() => expect(screen.getByText('打开研究失败，请重试')).toBeInTheDocument());
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('navigates the preview move-by-move with correct boundary states', async () => {
    renderPage();
    await selectFirstKifu();

    // Default load = final position (3/3): next/last disabled, first/prev enabled.
    expect(screen.getByText('3 / 3 手')).toBeInTheDocument();
    expect(screen.getByLabelText('next')).toBeDisabled();
    expect(screen.getByLabelText('last')).toBeDisabled();
    expect(screen.getByLabelText('prev')).not.toBeDisabled();

    fireEvent.click(screen.getByLabelText('prev'));
    expect(screen.getByText('2 / 3 手')).toBeInTheDocument();
    expect(screen.getByLabelText('next')).not.toBeDisabled();

    fireEvent.click(screen.getByLabelText('first'));
    expect(screen.getByText('0 / 3 手')).toBeInTheDocument();
    expect(screen.getByLabelText('first')).toBeDisabled();
    expect(screen.getByLabelText('prev')).toBeDisabled();
    expect(screen.getByLabelText('next')).not.toBeDisabled();
  });

  it('paginates: clicking page 2 refetches with page=2', async () => {
    installFetch(40); // totalPages = 2
    renderPage();
    await waitFor(() => expect(screen.getByText('柯洁')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /page 2/i }));

    await waitFor(() => {
      const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
      const lastUrl = String(calls[calls.length - 1][0]);
      expect(lastUrl).toContain('page=2');
    });
  });

  it('resets to page 1 when the search query changes', async () => {
    installFetch(40);
    renderPage();
    await waitFor(() => expect(screen.getByText('柯洁')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /page 2/i }));
    await waitFor(() => {
      const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
      expect(String(calls[calls.length - 1][0])).toContain('page=2');
    });

    fireEvent.change(screen.getByPlaceholderText('搜索棋手、赛事...'), { target: { value: '柯洁' } });

    await waitFor(() => {
      const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
      const lastUrl = String(calls[calls.length - 1][0]);
      expect(lastUrl).toContain('page=1');
      expect(lastUrl).not.toContain('page=2');
      expect(lastUrl).toContain('q=');
    });
  });

  it('shows error message on fetch failure', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementationOnce(() =>
      Promise.resolve({ ok: false, status: 500, text: () => Promise.resolve('Internal Server Error') })
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Request failed 500/)).toBeInTheDocument();
    });
  });
});
