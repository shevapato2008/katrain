import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { sequenceKey, UNIT_SIZE } from '../pages/tsumegoUnits';

const { mockNavigate, mockUnitProgress } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockUnitProgress: vi.fn(() => ({ completed: 0, total: 0 })),
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
    unitProgress: mockUnitProgress,
    categoryProgress: () => ({ completed: 0, total: 0 }),
    refresh: vi.fn(),
  }),
}));

// 45 problems → ceil(45/20) = 3 units (20, 20, 5).
const TOTAL = 45;
const allIds = Array.from({ length: TOTAL }, (_, i) => ({ id: `q${i}` }));

const installFetch = (data: { id: string }[] = allIds) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
  }) as any;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUnitProgress.mockReturnValue({ completed: 0, total: 0 });
  sessionStorage.clear();
  installFetch();
});

import TsumegoUnitsPage from '../pages/TsumegoUnitsPage';

const renderPage = (level = '15k', category = 'tesuji') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/:level/:category" element={<TsumegoUnitsPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoUnitsPage', () => {
  it('shows loading spinner initially', () => {
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('fetches the full category id list with limit=1000', async () => {
    renderPage();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories/tesuji?limit=1000',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  it('groups problems into ceil(total/20) units', async () => {
    renderPage();
    await waitFor(() => {
      // 45 problems → units 1, 2, 3.
      expect(screen.getByText((_, el) => el?.textContent === '单元 1')).toBeInTheDocument();
      expect(screen.getByText((_, el) => el?.textContent === '单元 2')).toBeInTheDocument();
      expect(screen.getByText((_, el) => el?.textContent === '单元 3')).toBeInTheDocument();
    });
    // No 4th unit.
    expect(screen.queryByText((_, el) => el?.textContent === '单元 4')).not.toBeInTheDocument();
  });

  it('shows each unit problem range (1–20, 21–40, 41–45)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('1–20')).toBeInTheDocument();
      expect(screen.getByText('21–40')).toBeInTheDocument();
      expect(screen.getByText('41–45')).toBeInTheDocument();
    });
  });

  it('writes the ordered id sequence to sessionStorage (Phase 4 contract)', async () => {
    renderPage('15k', 'tesuji');
    await waitFor(() => {
      const raw = sessionStorage.getItem(sequenceKey('15k', 'tesuji'));
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      expect(parsed).toHaveLength(TOTAL);
      expect(parsed[0]).toBe('q0');
      expect(parsed[TOTAL - 1]).toBe('q44');
    });
  });

  it('navigates to a unit list page when a unit card is clicked', async () => {
    renderPage('15k', 'tesuji');
    await waitFor(() => expect(screen.getByText('1–20')).toBeInTheDocument());
    fireEvent.click(screen.getByText('1–20'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/tesuji/1');
  });

  it('clicking unit 3 navigates with the correct unit number', async () => {
    renderPage('15k', 'tesuji');
    await waitFor(() => expect(screen.getByText('41–45')).toBeInTheDocument());
    fireEvent.click(screen.getByText('41–45'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/tesuji/3');
  });

  it('computes unit completion via unitProgress per 20-id slice', async () => {
    // unitProgress is called once per unit with that unit's ids.
    renderPage('15k', 'tesuji');
    await waitFor(() => expect(screen.getByText('1–20')).toBeInTheDocument());
    const calls = mockUnitProgress.mock.calls as unknown as string[][][];
    // first unit slice has UNIT_SIZE ids
    expect(calls.some((c) => Array.isArray(c[0]) && (c[0] as string[]).length === UNIT_SIZE)).toBe(true);
    // last unit slice has the remainder (5)
    expect(calls.some((c) => Array.isArray(c[0]) && (c[0] as string[]).length === TOTAL % UNIT_SIZE)).toBe(true);
  });

  it('marks a unit complete (green count) when all problems solved', async () => {
    // Make every unitProgress call report fully complete.
    mockUnitProgress.mockImplementation((ids: string[]) => ({ completed: ids.length, total: ids.length }));
    renderPage('15k', 'tesuji');
    await waitFor(() => {
      // "20/20" appears for full units.
      expect(screen.getAllByText('20/20').length).toBeGreaterThan(0);
    });
  });

  it('shows error and a back button on fetch failure', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/HTTP 404/)).toBeInTheDocument();
      expect(screen.getByText('返回')).toBeInTheDocument();
    });
  });
});
