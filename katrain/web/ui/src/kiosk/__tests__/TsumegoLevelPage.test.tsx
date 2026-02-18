import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockProblems = [
  { id: 'p1', level: '15k', category: '手筋', hint: '找到关键点', initialBlack: [], initialWhite: [] },
  { id: 'p2', level: '15k', category: '死活', hint: '', initialBlack: [], initialWhite: [] },
];

beforeEach(() => {
  vi.restoreAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ problems: mockProblems, total: 2, page: 1, per_page: 50 }),
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

  it('shows error on fetch failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
    });
  });
});
