import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

const mockLevels = [
  { level: '15k', categories: { '手筋': 139, '吃子': 630, '死活': 167 }, total: 1000 },
  { level: '14k', categories: { '对杀': 124, '吃子': 295 }, total: 419 },
];

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockLevels),
  }) as any;
});

import TsumegoPage from '../pages/TsumegoPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <TsumegoPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoPage', () => {
  it('renders title and subtitle', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('死活题')).toBeInTheDocument();
      expect(screen.getByText('选择难度级别 · 练习死活以提高计算力')).toBeInTheDocument();
    });
  });

  it('fetches and renders level cards', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('15K')).toBeInTheDocument();
      expect(screen.getByText('14K')).toBeInTheDocument();
    });
  });

  it('shows problem count', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('1000 题')).toBeInTheDocument();
      expect(screen.getByText('419 题')).toBeInTheDocument();
    });
  });

  it('shows category labels', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('手筋: 139')).toBeInTheDocument();
      expect(screen.getByText('吃子: 630')).toBeInTheDocument();
    });
  });

  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error on fetch failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 500, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/)).toBeInTheDocument();
    });
  });

  it('shows the 继续练习 resume card when an active practice session exists', async () => {
    localStorage.setItem(
      'kiosk_active_practice',
      JSON.stringify({ kind: 'practice', label: '3 段 · 死活题 · 第 12 题', route: '/kiosk/tsumego/problem/p12', ts: Date.now() })
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('继续练习')).toBeInTheDocument();
      expect(screen.getByText('3 段 · 死活题 · 第 12 题')).toBeInTheDocument();
    });
  });

  it('does not show the 继续练习 resume card when there is no active practice session', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('15K')).toBeInTheDocument();
    });
    expect(screen.queryByText('继续练习')).toBeNull();
  });

  it('highlights the last-practiced level with a 上次 tag', async () => {
    localStorage.setItem('kiosk_tsumego_last_level', '15k');
    renderPage();
    await waitFor(() => {
      const card = screen.getByTestId('tsumego-level-card-15k');
      expect(within(card).getByText('上次')).toBeInTheDocument();
    });
    expect(within(screen.getByTestId('tsumego-level-card-14k')).queryByText('上次')).toBeNull();
  });
});
