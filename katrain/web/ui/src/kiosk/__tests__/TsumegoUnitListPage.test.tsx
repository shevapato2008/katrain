import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { sequenceKey, UNIT_SIZE } from '../pages/tsumegoUnits';

const { mockNavigate, mockUnitProgress, mockProgress } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockUnitProgress: vi.fn(() => ({ completed: 0, total: 0 })),
  mockProgress: {} as Record<string, any>,
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: mockProgress,
    markProgress: vi.fn(),
    isCompleted: () => false,
    unitProgress: mockUnitProgress,
    categoryProgress: () => ({ completed: 0, total: 0 }),
    refresh: vi.fn(),
  }),
}));

// Unit slice of UNIT_SIZE problems, each with board stones for the MiniBoard thumbnail.
const unitProblems = Array.from({ length: UNIT_SIZE }, (_, i) => ({
  id: `u${i}`,
  level: '15k',
  category: 'tesuji',
  hint: '',
  initialBlack: ['pd'],
  initialWhite: ['dp'],
}));

const fullList = Array.from({ length: 40 }, (_, i) => ({ id: `u${i}` }));

// URL-routed fetch: the unit slice uses ?offset=&limit=20; the full sequence uses ?limit=1000.
const installFetch = () => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (/limit=1000/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve(fullList) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve(unitProblems) });
  }) as any;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUnitProgress.mockReturnValue({ completed: 0, total: UNIT_SIZE });
  for (const k of Object.keys(mockProgress)) delete mockProgress[k];
  sessionStorage.clear();
  installFetch();
});

import TsumegoUnitListPage from '../pages/TsumegoUnitListPage';

const renderPage = (level = '15k', category = 'tesuji', unit = '1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}/${unit}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoUnitListPage', () => {
  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches the unit slice with offset=0 for unit 1', async () => {
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        `/api/v1/tsumego/levels/15k/categories/tesuji?offset=0&limit=${UNIT_SIZE}`,
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  it('fetches with offset=(unit-1)*20 for unit 2', async () => {
    renderPage('15k', 'tesuji', '2');
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        `/api/v1/tsumego/levels/15k/categories/tesuji?offset=${UNIT_SIZE}&limit=${UNIT_SIZE}`,
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  it('renders the unit heading and problem range', async () => {
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => {
      expect(screen.getByText((_, el) => el?.textContent === '单元 1')).toBeInTheDocument();
      // range 1–20
      expect(screen.getByText('1–20')).toBeInTheDocument();
    });
  });

  it('renders a ProblemCard per problem', async () => {
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => {
      // One CardActionArea per ProblemCard (header back-arrow is a plain Button, not a card).
      expect(document.querySelectorAll('.MuiCardActionArea-root').length).toBe(UNIT_SIZE);
    });
  });

  it('navigates to the problem page when a card is clicked', async () => {
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => expect(document.querySelectorAll('.MuiCardActionArea-root').length).toBe(UNIT_SIZE));
    // Click the first problem card's action area.
    const firstCard = document.querySelector('.MuiCardActionArea-root') as HTMLElement;
    fireEvent.click(firstCard);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/u0');
  });

  it('populates the sessionStorage sequence when missing (deep-link)', async () => {
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories/tesuji?limit=1000',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
    await waitFor(() => {
      const raw = sessionStorage.getItem(sequenceKey('15k', 'tesuji'));
      expect(raw).not.toBeNull();
      expect(JSON.parse(raw!)).toHaveLength(40);
    });
  });

  it('does NOT refetch the full sequence when already cached', async () => {
    sessionStorage.setItem(sequenceKey('15k', 'tesuji'), JSON.stringify(['u0', 'u1']));
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => expect(document.querySelectorAll('.MuiCardActionArea-root').length).toBe(UNIT_SIZE));
    const calls = (global.fetch as any).mock.calls.map((c: any[]) => String(c[0]));
    expect(calls.some((u: string) => /limit=1000/.test(u))).toBe(false);
    // Cached sequence is left intact.
    expect(JSON.parse(sessionStorage.getItem(sequenceKey('15k', 'tesuji'))!)).toEqual(['u0', 'u1']);
  });

  it('shows the completion chip from unitProgress', async () => {
    mockUnitProgress.mockReturnValue({ completed: 7, total: UNIT_SIZE });
    renderPage('15k', 'tesuji', '1');
    await waitFor(() => {
      expect(screen.getByText('7/20')).toBeInTheDocument();
    });
  });

  it('shows error and a back button on fetch failure', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (/limit=1000/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve(fullList) });
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
    }) as any;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/)).toBeInTheDocument();
      expect(screen.getByText('返回')).toBeInTheDocument();
    });
  });
});
