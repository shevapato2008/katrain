import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockItems = [
  { id: 'p1', category: '手筋', hint: '找到关键点' },
  { id: 'p2', category: '死活', hint: '' },
];

const mockResponse = { items: mockItems, total: 100, page: 1, page_size: 50 };

beforeEach(() => {
  vi.restoreAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockResponse),
  }) as any;
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

  it('calls paginated problems endpoint', async () => {
    renderPage();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/problems?page=1&page_size=50',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  it('renders problem cards', async () => {
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

  it('shows loaded / total count', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('2 / 100 道题目')).toBeInTheDocument();
    });
  });

  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error on fetch failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no problems', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 }),
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('该难度暂无题目')).toBeInTheDocument();
    });
  });

  it('shows retry button on error', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 500, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('重试')).toBeInTheDocument();
    });
  });

  it('shows load more button when there are more problems', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('加载更多')).toBeInTheDocument();
    });
  });

  it('hides load more when all problems loaded', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: mockItems, total: 2, page: 1, page_size: 50 }),
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });
    expect(screen.queryByText('加载更多')).not.toBeInTheDocument();
  });

  it('fetches next page on load more click', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('加载更多')).toBeInTheDocument();
    });

    // Mock page 2 response
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [{ id: 'p3', category: '官子', hint: '' }], total: 100, page: 2, page_size: 50 }),
    });

    const user = userEvent.setup();
    await user.click(screen.getByText('加载更多'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/problems?page=2&page_size=50',
        expect.any(Object)
      );
    });
  });
});
