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

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, username: '甲' }, isAuthenticated: true, token: null }),
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
  localStorage.clear();
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
  it('加载态也使用 kiosk 外壳，不退回旧 MUI 转圈页', () => {
    renderPage();
    expect(screen.getByTestId('categories-loading')).toBeInTheDocument();
    expect(document.querySelector('.kiosk-layout-b')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).toBeNull();
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
      expect(screen.getByText('15 级 · 选择题型')).toBeInTheDocument();
      expect(screen.getByText('65 题 · 2 类')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /难度/ })).toBeInTheDocument();
  });

  it('题型按题库元数据的稳定顺序排列，并使用 kiosk 卡片', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('手筋')).toBeInTheDocument();
      expect(screen.getByText('死活')).toBeInTheDocument();
    });
    const titles = Array.from(document.querySelectorAll('.tsumego-category-grid .kiosk-card__t > b'))
      .map((node) => node.textContent);
    expect(titles).toEqual(['死活', '手筋']);
    expect(document.querySelectorAll('.tsumego-category-grid .kiosk-card')).toHaveLength(2);
    expect(document.querySelector('.MuiCard-root')).toBeNull();
  });

  it('题型图标来自 kiosk Phosphor 素材，不用 emoji 或 MUI 图标', async () => {
    const { container } = renderPage();
    await waitFor(() => {
      expect(screen.getByText('手筋')).toBeInTheDocument();
    });
    // Built from code points (not literal glyphs) so this source file stays free of the
    // tofu-rendering characters — the whole point of the T9 fix (Gate E scans src/kiosk).
    // U+2694+FE0F crossed-swords (old life-death icon), U+2728 sparkles (old tesuji icon),
    // U+1F3AF direct-hit (old endgame icon), U+1F4CB clipboard (old default/tofu icon).
    const staleCategoryGlyphs = [
      String.fromCodePoint(0x2694, 0xfe0f),
      String.fromCodePoint(0x2728),
      String.fromCodePoint(0x1f3af),
      String.fromCodePoint(0x1f4cb),
    ];
    staleCategoryGlyphs.forEach((glyph) => {
      expect(container.textContent).not.toContain(glyph);
    });
    expect(document.querySelectorAll('.tsumego-category-grid .kiosk-icon')).toHaveLength(2);
    expect(document.querySelector('.MuiSvgIcon-root')).toBeNull();
  });

  it('把全部题目收成「综合训练」，明确也按 20 题分单元', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('综合训练')).toBeInTheDocument();
    });
    expect(screen.getByText('混合当前难度全部题型，也按每 20 题分成单元')).toBeInTheDocument();
    expect(screen.queryByText('全部题目')).toBeNull();
  });

  it('综合训练进入同一条单元路径', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('综合训练')).toBeInTheDocument());
    fireEvent.click(screen.getByText('综合训练'));
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
      expect(screen.getByText('10 / 40 题')).toBeInTheDocument();
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
      expect(screen.getByRole('button', { name: '难度' })).toBeInTheDocument();
    });
  });

  // 连不上云端(503)这一屏有自己的 loadCategories,能干净地再调一次 —— 补一个真的重试键(选项 A),
  // 不能只把话说成「点重试」却没有按钮。
  it('连不上云端(HTTP 503)时说「连不上云端题库」,并有一个能用的重试按钮', async () => {
    let categoriesCalls = 0;
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (/\/categories$/.test(url)) {
        categoriesCalls += 1;
        return categoriesCalls === 1
          ? Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) })
          : Promise.resolve({ ok: true, json: () => Promise.resolve(mockCategories) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }) as any;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/连不上云端题库/)).toBeInTheDocument();
    });
    const retryButton = screen.getByRole('button', { name: '重试' });
    fireEvent.click(retryButton);
    await waitFor(() => {
      expect(screen.getByText('手筋')).toBeInTheDocument();
    });
    expect(categoriesCalls).toBe(2);
  });
});
