import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockProblems手筋 = [
  { id: 'p1', level: '15k', category: '手筋', hint: '找到关键点', initialBlack: [], initialWhite: [] },
];
const mockProblems死活 = [
  { id: 'p2', level: '15k', category: '死活', hint: '', initialBlack: [], initialWhite: [] },
];
const mockCategories = [
  { category: '手筋' },
  { category: '死活' },
];

function mockFetchTwoStep(categories = mockCategories, problemsByCategory: Record<string, any[]> = { '手筋': mockProblems手筋, '死活': mockProblems死活 }) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/categories/')) {
      // Problem fetch for a specific category
      const cat = decodeURIComponent(url.split('/categories/')[1].split('?')[0]);
      const problems = problemsByCategory[cat] ?? [];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(problems) });
    }
    if (url.includes('/categories')) {
      // Categories list
      return Promise.resolve({ ok: true, json: () => Promise.resolve(categories) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  }) as any;
}

beforeEach(() => {
  vi.restoreAllMocks();
  mockFetchTwoStep();
});

import TsumegoLevelPage from '../pages/TsumegoLevelPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/tsumego/15k']}>
        <Routes>
          <Route path="/kiosk/tsumego/:levelId" element={<TsumegoLevelPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoLevelPage', () => {
  it('renders level title', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('15K 级题目')).toBeInTheDocument();
    });
  });

  it('renders problem cards from multiple categories', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
    });
  });

  it('shows category chips on cards', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('手筋')).toBeInTheDocument();
      expect(screen.getByText('死活')).toBeInTheDocument();
    });
  });

  it('shows hint text when available', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('找到关键点')).toBeInTheDocument();
    });
  });

  it('shows problem count', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('2 道题目')).toBeInTheDocument();
    });
  });

  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error on categories fetch failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, json: () => Promise.resolve({}) }) as any;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no categories', async () => {
    mockFetchTwoStep([], {});
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('该难度暂无题目')).toBeInTheDocument();
    });
  });

  it('handles partial category failure gracefully', async () => {
    // One category succeeds, one fails
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/categories/')) {
        const cat = decodeURIComponent(url.split('/categories/')[1].split('?')[0]);
        if (cat === '手筋') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(mockProblems手筋) });
        }
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      }
      if (url.includes('/categories')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockCategories) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    }) as any;

    renderPage();
    await waitFor(() => {
      // Should still show the problems from the successful category
      expect(screen.getByText('#1')).toBeInTheDocument();
      expect(screen.getByText('手筋')).toBeInTheDocument();
    });
  });

  it('shows retry button on error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) }) as any;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('重试')).toBeInTheDocument();
    });
  });
});
