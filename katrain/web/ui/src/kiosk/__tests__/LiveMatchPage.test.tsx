import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import type { MatchDetail } from '../../types/live';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

vi.mock('../../hooks/live/useLiveMatch', () => ({
  useLiveMatch: vi.fn(),
}));

// Stub the sound hook so jsdom doesn't try to construct Audio.
vi.mock('../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
}));

import { useLiveMatch } from '../../hooks/live/useLiveMatch';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});
import LiveMatchPage from '../pages/LiveMatchPage';

const mockUseLiveMatch = useLiveMatch as ReturnType<typeof vi.fn>;

const mockMatch: MatchDetail = {
  id: 'match-1',
  source: 'xingzhen',
  tournament: 'LG杯决赛',
  round_name: '第一局',
  date: '2025-06-15',
  player_black: '柯洁',
  player_white: '申真谞',
  black_rank: '九段',
  white_rank: '九段',
  status: 'live',
  result: null,
  move_count: 156,
  current_winrate: 0.62,
  current_score: 3.8,
  last_updated: '2025-06-15T10:00:00Z',
  board_size: 19,
  komi: 7.5,
  rules: 'chinese',
  sgf: null,
  // 着法表是这一屏唯一的翻手界面(进度条删了),所以夹具得真有几手。
  moves: ['Q16', 'D4', 'Q10', 'C14'],
};

/** 跟随那台状态机是这一屏自己在驱动的,所以 `setCurrentMove` 要能被查。 */
const mockSetCurrentMove = vi.fn();

function setMatch(over: Partial<ReturnType<typeof useLiveMatch>> = {}) {
  mockUseLiveMatch.mockReturnValue({
    match: mockMatch,
    loading: false,
    error: null,
    currentMove: 156,
    setCurrentMove: mockSetCurrentMove,
    analysis: {},
    refresh: vi.fn(),
    ...over,
  });
}

const renderPage = (matchId = 'match-1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/live/${matchId}`]}>
        <Routes>
          <Route path="/kiosk/live/:matchId" element={<LiveMatchPage />} />
          <Route path="/kiosk/live" element={<div>LIVE_LIST</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('LiveMatchPage (kiosk)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 2026-08-24 屏 18 重画:三态换成外壳的 `.empty` 三句话(那个 `CircularProgress`
  // 和 `Alert` 走的是 MUI,而这一屏整块进了共享外壳)。**被测的意图一字未改**:
  // 还在读 / 读不到(要说出服务端那句话)/ 空手而归,三种各说各的,且都给得出返回。
  it('还在读的时候说「正在读这一局」,不是一个转圈', () => {
    setMatch({ match: null, loading: true });
    renderPage();
    expect(screen.getByTestId('live-loading')).toHaveTextContent('正在读这一局');
  });

  it('读不到:说出服务端那句话,并且给得出返回', () => {
    setMatch({ match: null, loading: false, error: new Error('Match not found') });
    renderPage();
    expect(screen.getByTestId('live-error')).toHaveTextContent('Match not found');
    expect(screen.getByRole('button', { name: /棋谱/ })).toBeInTheDocument();
  });

  it('renders tournament, players, and live status', () => {
    setMatch();
    renderPage();
    expect(screen.getByText(/LG杯决赛/)).toBeInTheDocument(); // MatchInfo (tournament · round)
    expect(screen.getAllByText(/柯洁/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/申真谞/).length).toBeGreaterThan(0);
    expect(screen.getByText('直播中')).toBeInTheDocument(); // header status chip
  });

  it('renders the board canvas', () => {
    setMatch();
    const { container } = renderPage();
    expect(container.querySelector('canvas')).toBeInTheDocument();
  });

  // 稿子那排是**五个**:试下 / 形势 / 手数 / AI 推荐 / 跟到最新。
  // 「跟到最新」是这一轮新加的 —— 删掉 `PlaybackBar` 之后,它是回到直播最新手的唯一入口。
  it('底下那排是五个开关,不是动作 —— 这一屏没有动作区', () => {
    setMatch();
    renderPage();
    const bar = screen.getByTestId('live-toggles');
    ['试下', '形势', '手数', 'AI 推荐', '跟到最新'].forEach((label) => {
      expect(within(bar).getByRole('button', { name: label })).toBeInTheDocument();
    });
    // 开关就该有按下态(`aria-pressed`),不是按一下弹回来的动作键
    expect(within(bar).getByRole('button', { name: 'AI 推荐' })).toHaveAttribute('aria-pressed', 'true');
  });

  /**
   * 🔴 这条守的是删 `PlaybackBar` 时差点丢掉的那件事:`useLiveMatch` 只在 `prev === null`
   * 时设过一次 `currentMove`,让直播盘跟着长的是那个组件里的 effect。
   * 状态机搬到本页之后,**「跟着长」和「往回翻就松开跟随」这两半都要还在**。
   */
  it('跟随:落到最新手;点着法表往回翻就松开,不再被拽回来', () => {
    setMatch({ currentMove: 100 });
    renderPage();
    // 跟随开着 ⇒ effect 把它推到 move_count
    expect(mockSetCurrentMove).toHaveBeenCalledWith(mockMatch.move_count);

    mockSetCurrentMove.mockClear();
    // ⚠️ 折叠块自己那个标题行也是 `<button>`,所以不能取 `getAllByRole('button')[0]`
    // —— 那是「展开/收起」,不是第 1 手。取着法格本身。
    const cells = screen.getByTestId('live-moves-fold').querySelectorAll('.mv[role="button"]');
    fireEvent.click(cells[0]);
    expect(mockSetCurrentMove).toHaveBeenCalledWith(1);
    expect(within(screen.getByTestId('live-toggles')).getByRole('button', { name: '跟到最新' }))
      .toHaveAttribute('aria-pressed', 'false');
  });

  // 钟不画:三个源客户端、数据库、类型三层都没有这个字段(见页面头注)。
  // `current_winrate` 同理不上屏 —— 它在源头被写死成 0.5,「真的 50%」和「没有这个数」同值。
  it('两张玩家卡上没有钟,也没有那个源头硬编码的 50%', () => {
    setMatch();
    renderPage();
    const b = screen.getByTestId('live-player-B');
    expect(b.querySelector('.clock')).toBeNull();
    expect(screen.queryByText(/50\.0%/)).toBeNull();
  });

  it('shows finished status chip for a finished match', () => {
    setMatch({ match: { ...mockMatch, status: 'finished', result: 'B+2.5' }, currentMove: 280 });
    renderPage();
    expect(screen.getByText('已结束')).toBeInTheDocument();
  });

  it('空手而归(没 match 也没 error):照样是那一块,不是一张白屏', () => {
    setMatch({ match: null, loading: false, error: null });
    renderPage();
    expect(screen.getByTestId('live-error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /棋谱/ })).toBeInTheDocument();
  });

  /**
   * 返回去的是**棋谱**不是 `/kiosk/live`。后者是个孤儿路由 —— 全仓唯一入口是
   * 棋谱屏那几行(`KifuPage.tsx:397`),它自己既不在 Dock 上、也没有返回键。
   * 上一版把人从这儿扔到那块屏上,是个走得进出不来的死角。
   */
  it('返回去棋谱,不是那块没有入口的 /kiosk/live', () => {
    setMatch();
    renderPage();
    // 「棋谱」在这一屏出现两次:页控条那颗返回键,和着法折叠块的标题「棋谱 · 跟着直播长」。
    // 要的是前者 —— 从页控条里取,别用全局名字查。
    const pagebar = screen.getByTestId('live-pagebar');
    fireEvent.click(within(pagebar).getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });
});
