import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// localStorage mock (jsdom doesn't provide full implementation)
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value); },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Must be before importing KioskApp
const mockUseAuth = vi.fn();
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
}));

import KioskApp from '../KioskApp';

const renderApp = (route = '/kiosk') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/kiosk/*" element={<KioskApp />} />
      </Routes>
    </MemoryRouter>
  );

describe('Kiosk navigation integration', () => {
  describe('unauthenticated', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: false,
        user: null,
        login: vi.fn(),
        logout: vi.fn(),
        token: null,
      });
    });

    it('unauthenticated user is redirected to login for any route', () => {
      renderApp('/kiosk/tsumego');
      expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
    });
  });

  describe('authenticated', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        user: { id: 1, username: '张三', rank: '2D', credits: 0 },
        login: vi.fn(),
        logout: vi.fn(),
        token: 'mock-token',
      });
      // Mock fetch for pages that use API calls (e.g., TsumegoPage)
      global.fetch = vi.fn().mockImplementation(async (url: string) => ({
        ok: true,
        json: () => Promise.resolve(
          String(url).includes('/api/v1/platforms/status')
            ? { platforms: [] }
            // 分类键是后端真的会给的 slug(`TsumegoProblem.category`),不是中文名。
            : [{ level: '15k', categories: { tesuji: 139 }, total: 1000 }],
        ),
      })) as unknown as typeof fetch;
    });

    it('shows play page with nav rail', () => {
      renderApp('/kiosk/play');
      expect(screen.getByText('对弈')).toBeInTheDocument();
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });

    it('nav rail items navigate correctly', async () => {
      renderApp('/kiosk/play');
      // Task 4:Dock 上这一项改叫「训练营」(规范 §3 共享词典),路由 `/kiosk/tsumego` 不变。
      fireEvent.click(screen.getByText('训练营'));
      // Task 12 把这一屏按稿子整屏换了(`shots/11-training.png`):原来那条
      // 「选择难度级别 · 练习死活以提高计算力」的标题栏没有了,问候行取而代之。
      await waitFor(() => {
        expect(screen.getByText('题在实体盘上摆好，落子即判')).toBeInTheDocument();
      });
    });

    it('/kiosk redirects to /kiosk/play', () => {
      renderApp('/kiosk');
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });

    it('unknown kiosk routes redirect to play', () => {
      renderApp('/kiosk/nonexistent');
      expect(screen.getByText('人机对弈')).toBeInTheDocument();
    });

    // Task 3(D9)把顶栏齿轮拆了,Task 4 把「设置」放进 Dock(规范 §1)——
    // 入口换了地方,不是没有了。这里点的就是 Dock 上那一格。
    //
    // 不写成 `renderApp('/kiosk/settings')` 直接跳:那样测的是「从我这层往里通」,
    // 而堵点按定义在更外面 —— 断路照样发通行证。入口在不在,只有从入口点进去才算数。
    //
    // 返回落到 `/kiosk/play`:Dock 不带 `location.state.from`,SettingsPage 的
    // `handleBack` 因此走安全兜底(SettingsPage.tsx:73)。旧齿轮那条路会带上原路由,
    // Task 18 重做设置屏时再决定 Dock 要不要带 —— 这条测试锁的是现状。
    it('opens Settings from the Dock and its back action lands on the safe fallback', async () => {
      renderApp('/kiosk/play');

      fireEvent.click(screen.getByRole('button', { name: '设置' }));
      await waitFor(() => expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument());

      fireEvent.click(screen.getByRole('button', { name: '返回' }));
      await waitFor(() => expect(screen.getByText('人机对弈')).toBeInTheDocument());
    });

    it('opens the Report list from the Dock without mounting physical-board UI', async () => {
      global.fetch = vi.fn().mockImplementation(async (url: string) => {
        const path = String(url);
        const data = path.includes('/reports/summary')
          ? { pending: 0, running: 0, completed: 0, failed: 0 }
          : path.includes('/reports/')
            ? []
            : path.includes('/user-games/')
              ? { items: [], total: 0, page: 1, page_size: 12 }
              : [];
        return { ok: true, json: async () => data, text: async () => '' };
      }) as unknown as typeof fetch;
      renderApp('/kiosk/play');
      fireEvent.click(screen.getByText('复盘'));
      await waitFor(() => expect(screen.getAllByText('复盘').length).toBeGreaterThanOrEqual(2));
      expect(screen.queryByText('智能棋盘')).not.toBeInTheDocument();
    });

    it('navigates to lobby from play/pvp/lobby route', async () => {
      renderApp('/kiosk/play/pvp/lobby');
      await waitFor(() => {
        expect(screen.getByText('在线大厅')).toBeInTheDocument();
      });
    });
  });

  // Phase 3: the tsumego flow is now 5 levels deep:
  //   tsumego (levels) → :level (categories) → :level/:category (units)
  //   → :level/:category/:unit (unit list) → problem/:id (problem page).
  describe('5-level tsumego navigation (authenticated)', () => {
    // 25 problems → 2 units (20 + 5).
    const problemIds = Array.from({ length: 25 }, (_, i) => ({
      id: `prob${i}`,
      level: '15k',
      category: 'tesuji',
      hint: '',
      initialBlack: ['pd'],
      initialWhite: ['dp'],
    }));

    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        user: { id: 1, username: '张三', rank: '2D', credits: 0 },
        login: vi.fn(),
        logout: vi.fn(),
        token: 'mock-token',
      });
      localStorageMock.clear();

      // URL-routed mock covering every endpoint along the 5-level path. Most-specific
      // patterns are matched first so they aren't shadowed by the generic ones.
      global.fetch = vi.fn().mockImplementation((url: string) => {
        const u = String(url);
        const json = (data: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
        if (/\/tsumego\/progress$/.test(u)) return json({});
        if (/\/tsumego\/problems\/prob\d+/.test(u)) {
          return json({ id: 'prob0', level: '15k', category: 'tesuji', hint: '', boardSize: 9, initialBlack: [], initialWhite: [], sgfContent: '' });
        }
        if (/\/categories\/tesuji\?offset=/.test(u)) {
          // unit slice (offset/limit=20) — return up to 20 problems.
          return json(problemIds.slice(0, 20));
        }
        if (/\/categories\/tesuji\?limit=1000/.test(u)) return json(problemIds);
        if (/\/levels\/15k\/categories$/.test(u)) return json([{ category: 'tesuji', name: '手筋', count: 25 }]);
        if (/\/tsumego\/levels$/.test(u)) return json([{ level: '15k', categories: { tesuji: 25 }, total: 25 }]);
        return json([]);
      }) as unknown as typeof fetch;
    });

    it('drills from levels → categories → units → unit list → problem', async () => {
      renderApp('/kiosk/tsumego');

      // Level 1: 训练营「按级别」那一排 → 点 15 级。(Task 12 起卡上写的是中文档名,
      // 不是 `15K` —— `levelChinese('15k')`。)
      // 只有一档时「按级别」右端那个值也是「15 级」,所以按卡的可及名取,别按裸文本取。
      const levelCard = await screen.findByRole('button', { name: /^15 级，/ });
      fireEvent.click(levelCard);

      // Level 2: categories page → "选择分类" subtitle + 手筋 category card.
      await waitFor(() => expect(screen.getByText('手筋')).toBeInTheDocument());
      fireEvent.click(screen.getByText('手筋'));

      // Level 3: 单元列表 → 2 个单元。(Task 13 起卡上写的是「第 1-20 题」,不是「1–20」。)
      await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
      expect(screen.getByText('第 21-25 题')).toBeInTheDocument();
      fireEvent.click(screen.getByText('第 1-20 题').closest('button')!);

      // Level 4: 题目列表 → 一格一题的 `.qgrid`。(屏 13 起不再是带缩略棋盘的 MUI 卡,
      // 格子里只有题号和「试了几次」。)
      await waitFor(() => {
        expect(document.querySelectorAll('.qgrid button').length).toBe(20);
      });

      // The units page wrote the prev/next sequence to sessionStorage.
      const seq = sessionStorage.getItem('kiosk_problems_15k_tesuji');
      expect(seq).not.toBeNull();
      expect(JSON.parse(seq!)).toHaveLength(25);

      // Level 5: 点第一格 → 做题屏(盘渲出来)。
      const firstCard = document.querySelector('.qgrid button') as HTMLElement;
      fireEvent.click(firstCard);
      await waitFor(() => expect(screen.getByTestId('tsumego-board')).toBeInTheDocument());
    });
  });
});
