/* 直播列表页迁 `BoardPageShell` 之后的三条守卫。
 *
 * 只断言**渲染结构与行为**，不断言布局结论 —— 判据是「把它原样搬进真浏览器，
 * 还有可能失败吗」：这三条都会。盒子的高度/宽度/能不能滚一律不在这里写，
 * 那些归 `superpowers/tracks/galaxy-ui-redesign/loadbearing_live_list.js`
 * （真浏览器，四档视口 × 两个页签）。
 *
 * 变异实跑（改坏 → 变红，还原 → 变绿），三条逐条真跑过：
 *   1. 去掉 `showBack={false}`                        → 「不画返回键」那条红
 *   2. 「进入直播」挪回 `rightTab === 0 &&` 条件里      → 「切页签仍在」那条红
 *   3. 整页换回 12a3d3fe 的改动前版本（真实树，不是变异） → 「三段齐全」那条红
 *
 * 变异 2 **第一次没红**，值得记：断言原来写的是
 * `getByTestId('board-rail-actions').querySelector('button') !== null`，
 * 而动作区里还挂着播放条、它自带六个走子键 —— 按钮整个消失也照样绿。
 * 判据落在容器上而不是落在**这一个控件**上，就是量错了操作数
 * （同族 [[reference_gate_measures_wrong_operand]]）。改成对 `live-enter-match`
 * 这个 testid 断言之后才真的红。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MatchDetail, MatchSummary } from '../../../types/live';
import { GameNavigationProvider } from '../../context/GameNavigationContext';
import LivePage from './LivePage';

const summary: MatchSummary = {
  id: 'm1', source: 'yike', tournament: 'Galaxy Cup', round_name: null,
  date: '2026-08-23T12:00:00Z', player_black: 'Alpha', player_white: 'Beta',
  black_rank: null, white_rank: null, status: 'live', result: null, move_count: 194,
  current_winrate: 0.5, current_score: 0, last_updated: '2026-08-23T12:01:00Z',
  board_size: 19, komi: 7.5,
} as MatchSummary;

const detail: MatchDetail = {
  ...summary, rules: 'chinese', sgf: null, moves: ['D4', 'Q16'],
} as MatchDetail;

vi.mock('../../../hooks/live/useLiveMatches', () => ({
  useLiveMatches: () => ({ matches: [summary], liveCount: 1, loading: false }),
}));
/* useLiveMatch 的 mock 要能**记下调用参数**、也能被单条用例改返回值：
   「列表页不该拉分析」这条判据落在传进去的 options 上，不在渲染出来的 DOM 上；
   「切换中不该画上一局」这条要能造出「hook 返回的还是上一局」那个中间态。 */
const liveMatch = vi.hoisted(() => ({
  spy: vi.fn(),
  result: { current: null as unknown as ReturnType<typeof Object> },
}));
vi.mock('../../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: (id: string | undefined, opts?: Record<string, unknown>) => {
    liveMatch.spy(id, opts);
    return liveMatch.result.current;
  },
}));
vi.mock('../../../components/live/LiveBoard', () => ({
  default: () => <div data-testid="mock-live-board" />,
}));
vi.mock('../../../components/live/UpcomingList', () => ({
  default: () => <div data-testid="mock-upcoming-list" />,
}));

class ResizeObserverMock {
  constructor(_cb: ResizeObserverCallback) {}
  observe() {}
  unobserve() {}
  disconnect() {}
}

const renderPage = () => render(
  <MemoryRouter>
    <GameNavigationProvider>
      <LivePage />
    </GameNavigationProvider>
  </MemoryRouter>,
);

describe('LivePage（迁 BoardPageShell 之后）', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    liveMatch.spy.mockClear();
    liveMatch.result.current = {
      match: detail, loading: false, currentMove: 194, setCurrentMove: vi.fn(),
    };
  });

  it('挂的是统一的棋盘页外壳，右栏三段齐全', () => {
    renderPage();
    expect(screen.getByTestId('board-page-shell')).toBeInTheDocument();
    expect(screen.getByTestId('board-rail-module')).toBeInTheDocument();
    expect(screen.getByTestId('board-rail-scroll')).toBeInTheDocument();
    expect(screen.getByTestId('board-rail-actions')).toBeInTheDocument();
  });

  it('直播是一级导航页 —— 模块牌不画返回键', () => {
    renderPage();
    const plate = screen.getByTestId('module-plate');
    expect(plate.querySelector('button[aria-label^="返回"], button[aria-label^="Back"]')).toBeNull();
  });

  /* ---- 2026-09-01 Fan 报的两个问题，各一条守卫 ---- */

  it('列表页的棋盘只用 moves —— 不许顺手把分析数据也拉下来', () => {
    /* 实测（测试环境，服务端自量）：一盘棋的盘面是 816B–2.3KB，
       而 `analysis/preload` 是 326KB–1.64MB，差 400–700 倍。
       这一页 `analysis` 零引用（LiveBoard 只收 moves/currentMove），
       所以那份下载**整份都是白拉的**，还要和盘面抢同一条链路的带宽。
       判据落在传给 hook 的 options 上：hook 的默认档是 'poll'，
       不显式传 'none' 就会发这个请求。 */
    renderPage();
    const opts = liveMatch.spy.mock.calls.at(-1)?.[1] as { analysisMode?: string } | undefined;
    expect(opts?.analysisMode).toBe('none');
  });

  it('换一局的等待期里，棋盘位置显示加载态 —— 不是上一局的盘面', () => {
    /* 造的是真实的中间态：用户已经点了 m1，hook 手里还是上一局 m0。
       原来的判据是 `loading && !selectedMatch`，而那个 `loading` 是**列表**的，
       列表早就加载完了 ⇒ 分支落到「有 selectedMatch」上，把上一局照常画出来，
       整个等待期一个提示都没有。同族：[[reference_gate_measures_wrong_operand]]。 */
    liveMatch.result.current = {
      match: { ...detail, id: 'm0', move_count: 63 },
      loading: true, currentMove: 194, setCurrentMove: vi.fn(),
    };
    renderPage();
    expect(screen.getByTestId('live-board-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('mock-live-board')).toBeNull();
  });

  it('等待期里播放条不能显示上一局的手数', () => {
    /* Fan 的截图里是「181 / 63 手」：181 来自更早选中的那局，63 是上一局的总手数，
       而他刚点的是 272 手那局 —— 三个数分属三局。 */
    liveMatch.result.current = {
      match: { ...detail, id: 'm0', move_count: 63 },
      loading: true, currentMove: 194, setCurrentMove: vi.fn(),
    };
    renderPage();
    expect(screen.queryByTestId('playback-move-counter')).toBeNull();
  });

  it('「进入直播」在赛事预告页签下**仍然渲染** —— 它作用于选中的那局，与页签无关', async () => {
    renderPage();
    /* 断言落在**这个按钮**上，不落在「动作区里有没有 button」上 ——
       动作区里还挂着播放条，它自带六个走子键，`querySelector('button')` 永远非空，
       按钮整个消失也照样绿（第一版就是这么假绿的）。
       同族：[[reference_gate_measures_wrong_operand]]。 */
    expect(screen.getByTestId('live-enter-match')).toBeInTheDocument();

    /* 按序号取第二个页签，不按名字 —— 测试环境没装 i18n 词表，
       标签回落成原始 key，按名字取会因为翻译而假红。 */
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(2);
    fireEvent.click(tabs[1]);
    await waitFor(() => expect(screen.getByTestId('mock-upcoming-list')).toBeInTheDocument());

    // 迁移前这里是 `rightTab === 0 && (...)`，切到第二个页签整块消失。
    expect(screen.getByTestId('live-enter-match')).toBeInTheDocument();
  });
});
