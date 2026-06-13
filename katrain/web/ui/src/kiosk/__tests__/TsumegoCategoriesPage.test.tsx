import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const { mockNavigate, mockCategoryProgress } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockCategoryProgress: vi.fn(() => ({ completed: 0, total: 0 })),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: {},
    markProgress: vi.fn(),
    isCompleted: () => false,
    unitProgress: () => ({ completed: 0, total: 0 }),
    categoryProgress: mockCategoryProgress,
    refresh: vi.fn(),
  }),
}));

const mockCategories = [
  { category: 'tesuji', name: '手筋', count: 40 },
  { category: 'life-death', name: '死活', count: 25 },
];

// Per-category id lists fetched non-blocking (?limit=1000) for completed counts.
const tesujiIds = Array.from({ length: 40 }, (_, i) => ({ id: `t${i}` }));
const lifeDeathIds = Array.from({ length: 25 }, (_, i) => ({ id: `ld${i}` }));

// URL-routed fetch: the per-category ?limit=1000 branch MUST be checked before the bare
// categories list branch, or the list shadows it.
const installFetch = () => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (/\/categories\/tesuji\?/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve(tesujiIds) });
    if (/\/categories\/life-death\?/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve(lifeDeathIds) });
    if (/\/categories$/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve(mockCategories) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  }) as any;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockCategoryProgress.mockReturnValue({ completed: 0, total: 0 });
  installFetch();
});

import TsumegoCategoriesPage from '../pages/TsumegoCategoriesPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/tsumego/15k']}>
        <Routes>
          <Route path="/kiosk/tsumego/:level" element={<TsumegoCategoriesPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoCategoriesPage', () => {
  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches the categories endpoint for the level', async () => {
    renderPage();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  it('renders the level heading and total problem count', async () => {
    renderPage();
    await waitFor(() => {
      // total = 40 + 25 = 65. MUI splits "{count} {label}" into sibling text nodes,
      // so match on the element's combined textContent (appears in header + all-card).
      expect(screen.getByText(/15K/)).toBeInTheDocument();
      expect(screen.getAllByText((_, el) => el?.textContent === '65 题').length).toBeGreaterThan(0);
    });
  });

  it('renders a category card per category with its name and count', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('手筋')).toBeInTheDocument();
      expect(screen.getByText('死活')).toBeInTheDocument();
    });
  });

  it('renders the "全部题目" all-problems shortcut card', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('全部题目')).toBeInTheDocument();
    });
  });

  it('navigates to the all-problems list when the shortcut is clicked', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('全部题目')).toBeInTheDocument());
    fireEvent.click(screen.getByText('全部题目'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/all');
  });

  it('navigates to a category units page when a category card is clicked', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('手筋')).toBeInTheDocument());
    fireEvent.click(screen.getByText('手筋'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/tesuji');
  });

  it('fetches each category id list non-blocking and shows completed/total once resolved', async () => {
    // tesuji: 10/40 completed -> shows "10/40"
    mockCategoryProgress.mockImplementation((ids: string[]) => ({
      completed: ids.length === 40 ? 10 : 0,
      total: ids.length,
    }));
    renderPage();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories/tesuji?limit=1000',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
    await waitFor(() => {
      // "{completed}/{total} 题" is split across sibling text nodes — match on textContent.
      // The matcher hits both the <p> and its text-wrapper, so just assert ≥1 match.
      expect(
        screen.getAllByText((_, el) => el?.textContent === '10/40 题').length
      ).toBeGreaterThan(0);
    });
  });

  it('shows error and a back button on fetch failure', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (/\/categories$/.test(url)) return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }) as any;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/)).toBeInTheDocument();
      expect(screen.getByText('返回')).toBeInTheDocument();
    });
  });
});
