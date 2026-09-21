import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LivePage from '../pages/LivePage';
import { LiveAPI } from '../../api/live';
import type { MatchSummary, UpcomingMatch } from '../../types/live';

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_k: string, d: string) => d, lang: 'cn' }),
}));

const match = (id: string, status: 'live' | 'finished', winrate = 0.5): MatchSummary => ({
  id, source: 'xingzhen', tournament: `${id} 杯`, round_name: '第 1 轮',
  date: '2026-09-20T03:00:00Z', player_black: '黑方', player_white: '白方',
  black_rank: '9p', white_rank: '9p', status, result: status === 'finished' ? 'B+R' : null,
  move_count: 120, current_winrate: winrate, current_score: 0, last_updated: '2026-09-20T05:00:00Z',
  board_size: 19, komi: 7.5, rules: 'chinese',
});

const upcoming = (id: string): UpcomingMatch => ({
  id, tournament: '名人战', round_name: '第 3 局', scheduled_time: '2026-09-21T11:00:00Z',
  player_black: '申真谞', player_white: '柯洁', source: 'foxwq', source_url: 'https://example.com/x',
});

/** 观战屏的桩:把收到的导航 state 摆出来,好断言「打开它的这一页写了 backTo」。 */
const WatchStub = () => {
  const { state } = useLocation();
  return <div data-testid="watch-page">{JSON.stringify(state)}</div>;
};

const renderPage = () => render(
  <MemoryRouter initialEntries={['/kiosk/live']}>
    <Routes>
      <Route path="/kiosk/live" element={<LivePage />} />
      <Route path="/kiosk/kifu" element={<div data-testid="kifu-page" />} />
      <Route path="/kiosk/live/:matchId" element={<WatchStub />} />
    </Routes>
  </MemoryRouter>,
);

describe('屏 直播列表 /kiosk/live', () => {
  beforeEach(() => {
    vi.spyOn(LiveAPI, 'getMatches').mockResolvedValue({
      matches: [...Array(8)].map((_, i) => match(`m${i}`, i < 5 ? 'live' : 'finished')),
      total: 8, live_count: 5,
    });
    vi.spyOn(LiveAPI, 'getUpcoming').mockResolvedValue({ matches: [upcoming('u1')] });
  });
  afterEach(() => vi.restoreAllMocks());

  it('有返回键,点它回棋谱', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /棋谱/ }));
    expect(screen.getByTestId('kifu-page')).toBeInTheDocument();
  });

  // 棋谱屏只画 4 行;这一屏是「更多」的去处 ⇒ 8 条要全在(直播中 5 + 已结束 3)。
  it('8 条比赛全部上屏:直播中 5 条,切到「已结束」是另外 3 条', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('live-row')).toHaveLength(5));
    await userEvent.click(screen.getByRole('radio', { name: '已结束' }));
    await waitFor(() => expect(screen.getAllByTestId('live-row')).toHaveLength(3));
  });

  it('切到「即将开始」看到赛程行,且整页没有一个 target="_blank"', async () => {
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    await userEvent.click(screen.getByRole('radio', { name: '即将开始' }));
    expect(await screen.findByTestId('upcoming-row')).toHaveTextContent('名人战');
    expect(container.querySelectorAll('[target="_blank"]')).toHaveLength(0);
    expect(container.querySelectorAll('a[href]')).toHaveLength(0);
  });

  it('点一行进观战,并把自己写进 backTo(观战屏返回回这里)', async () => {
    renderPage();
    await userEvent.click((await screen.findAllByTestId('live-row'))[0]);
    expect(JSON.parse(screen.getByTestId('watch-page').textContent ?? 'null')).toEqual({ backTo: '/kiosk/live' });
  });

  // `current_winrate` 在 pandanet 源里恒为写死的 0.5、xingzhen 取不到时也退回 0.5 ——
  // 屏上画它就是编。屏 18 已经为同一件事裁过一次。
  it('不画 current_winrate', async () => {
    vi.spyOn(LiveAPI, 'getMatches').mockResolvedValue({
      matches: [match('m0', 'live', 0.5), match('m1', 'live', 0.73)], total: 2, live_count: 2,
    });
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    expect(container.textContent).not.toMatch(/%|50|73/);
  });

  it('整页没有 MUI 组件', async () => {
    const { container } = renderPage();
    await screen.findAllByTestId('live-row');
    expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
  });

  it('拉不到直播时说「读不到」,不说「现在没有比赛在下」;点重试再拉一次', async () => {
    const get = vi.spyOn(LiveAPI, 'getMatches').mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByTestId('live-list-error')).toBeInTheDocument();
    expect(screen.queryByText('现在没有比赛在下')).toBeNull();
    const before = get.mock.calls.length;
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(before));
  });

  it('拉不到赛程时说「读不到」,不说「没有赛事预告」', async () => {
    vi.spyOn(LiveAPI, 'getUpcoming').mockRejectedValue(new Error('boom'));
    renderPage();
    await screen.findAllByTestId('live-row');
    await userEvent.click(screen.getByRole('radio', { name: '即将开始' }));
    expect(await screen.findByTestId('upcoming-error')).toBeInTheDocument();
    expect(screen.queryByText('暂无赛事预告')).toBeNull();
  });
});
