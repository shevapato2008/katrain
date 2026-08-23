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
vi.mock('../../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: () => ({ match: detail, loading: false, currentMove: 194, setCurrentMove: vi.fn() }),
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
