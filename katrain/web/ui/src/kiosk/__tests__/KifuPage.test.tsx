import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';
import type { KifuAlbumSummary } from '../../types/kifu';
import type { MatchSummary } from '../../types/live';

/**
 * 屏 15 · 棋谱 `/kiosk/kifu`。
 *
 * 这份文件是**整份重写**的:上一版断言的是 MUI 的两栏「列表 + 预览」(`variant="h4"` 标题、
 * `CardActionArea`、`Pagination`、右栏那块 `LiveBoard` 预览)。那套界面本轮整个换掉了 ——
 * 预览和「在研究中打开」搬进了屏 16(`KifuDetailPage`),这一屏变成三条路的汇合点。
 *
 * 几条**判据落在哪儿**值得写明:
 *  · 「收起时不拉列表」断言的是 `getAlbums` **被调用时的参数形状**(`page_size: 1` 只够拿
 *    组标题右端那个「共 N 局」),不是屏上有没有搜索框 —— 把整页拉回来先不渲染,后者一样绿。
 *  · 「已摆完」那三条(有 total / 没 total / k < total)是**同一条口径的三个方向**:
 *    旧进度里没有 `total`,读到 `undefined` 的正确反应是不下结论。
 *  · 直播那块断网时整块不渲染 —— 断言的是 `queryByTestId` 为空,并且**同一批数据在
 *    不报错时是渲染的**,否则「一直不渲染」也能骗过这条。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { getAlbums } = vi.hoisted(() => ({ getAlbums: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums } }));

const { useLiveMatchesMock } = vi.hoisted(() => ({ useLiveMatchesMock: vi.fn() }));
vi.mock('../../hooks/live/useLiveMatches', () => ({ useLiveMatches: useLiveMatchesMock }));

const album = (id: number, over: Partial<KifuAlbumSummary> = {}): KifuAlbumSummary => ({
  id,
  player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese', round_name: '半决赛',
  ...over,
});

const match = (id: string, over: Partial<MatchSummary> = {}): MatchSummary => ({
  id,
  source: 'xingzhen',
  tournament: '第 29 届三星杯',
  round_name: '八强',
  date: '2026-08-22T06:00:00Z',
  player_black: '柯洁', player_white: '申真谞',
  black_rank: '九段', white_rank: '九段',
  status: 'live', result: null, move_count: 118,
  current_winrate: 0.5, current_score: 0, last_updated: '',
  board_size: 19, komi: 7.5, rules: 'chinese',
  ...over,
});

const liveResult = (over: Partial<ReturnType<typeof useLiveMatchesMock>> = {}) => ({
  matches: [] as MatchSummary[], liveCount: 0, total: 0,
  loading: false, error: null, refresh: vi.fn(),
  ...over,
});

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <KifuPage />
      </MemoryRouter>
    </ThemeProvider>,
  );

/** 往 localStorage 里造一条「最近摆过」。**造的是真的存储键**,不是 mock 的模块。 */
const seedRecent = (
  entries: { id: string; name: string; savedAt: number }[],
  progress: Record<string, { k: number; frames: number; updatedAt: number; total?: number }> = {},
  sgfFor: string[] = [],
) => {
  localStorage.setItem('baipu:recent', JSON.stringify(entries));
  for (const [id, p] of Object.entries(progress)) {
    localStorage.setItem(`baipu:progress:${id}`, JSON.stringify(p));
  }
  for (const id of sgfFor) {
    localStorage.setItem(`baipu:sgf:${id}`, JSON.stringify({
      id, name: id, sgf: '(;FF[4]GM[1]SZ[19];B[pd])', savedAt: 1,
    }));
  }
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getAlbums.mockResolvedValue({ items: [album(1), album(2)], total: 2, page: 1, page_size: 6 });
  useLiveMatchesMock.mockReturnValue(liveResult());
});

describe('屏 15 棋谱 · 问候与三张卡', () => {
  it('问候行照稿子写「看别人的棋」', () => {
    renderPage();
    expect(screen.getByText('看别人的')).toBeInTheDocument();
    expect(screen.getByText('棋')).toBeInTheDocument();
    expect(screen.getByText('名局、职业直播，以及把谱摆到实体盘上')).toBeInTheDocument();
  });

  it('三张卡在,顺序是 搜棋谱 / 摆到实体盘 / 导入 SGF', () => {
    renderPage();
    const cards = [...document.querySelectorAll('.kiosk-card')].map((c) => c.querySelector('b')?.textContent);
    expect(cards).toEqual(['搜棋谱', '摆到实体盘', '导入 SGF']);
  });

  it('「摆到实体盘」进 /kiosk/baipu —— Task 4 把摆谱下了 Dock,入口就是这张卡', () => {
    renderPage();
    fireEvent.click(screen.getByText('摆到实体盘').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/baipu');
  });

  it('「导入 SGF」按下去开的是本地文件选择框', () => {
    renderPage();
    const input = screen.getByTestId('kifu-sgf-input') as HTMLInputElement;
    const clicked = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByText('导入 SGF').closest('button')!);
    expect(clicked).toHaveBeenCalled();
  });
});

describe('屏 15 棋谱 · 搜棋谱是开关不是跳转', () => {
  it('收起时只探一个数,不取列表、不渲染行', async () => {
    renderPage();
    expect(screen.queryByTestId('kifu-search')).not.toBeInTheDocument();
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(1));
    // 判据落在**请求的形状**上:`page_size: 1` 只够拿 `total`。
    // 断言「有没有搜索框」是不够的 —— 把整页拉回来但先不渲染,那条一样绿。
    expect(getAlbums).toHaveBeenCalledWith({ page: 1, page_size: 1 });
    expect(document.querySelectorAll('.kiosk-rows .kiosk-row')).toHaveLength(0);
  });

  it('收起时那句「共 N 局」照样是真数据', async () => {
    getAlbums.mockResolvedValue({ items: [], total: 1234, page: 1, page_size: 1 });
    renderPage();
    expect(await screen.findByText('共 1,234 局')).toBeInTheDocument();
  });

  it('按下去才展开搜索框、才发请求,结果行铺出来', async () => {
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(
      { q: undefined, page: 1, page_size: 6 },
    ));
    expect(screen.getByTestId('kifu-search')).toBeInTheDocument();
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    expect(rows).toHaveLength(2);
  });

  it('组标题右端写的是真数据「共 N 局」,不是稿子那句「按棋手 / 赛事 / 日期搜」', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 1234, page: 1, page_size: 6 });
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    expect(await screen.findByText('共 1,234 局')).toBeInTheDocument();
    // 稿子写在这个位置的是一句解释(「按棋手 / 赛事 / 日期搜」),规范说这里放数据。
    expect(screen.queryByText('按棋手 / 赛事 / 日期搜')).not.toBeInTheDocument();
  });

  it('点一行进屏 16 的详情', async () => {
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    fireEvent.click(rows[0].closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu/1');
  });

  it('搜不到东西时说的是「没有对得上的谱」,不是空着', async () => {
    getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 6 });
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    expect(await screen.findByText('没有对得上的谱')).toBeInTheDocument();
  });

  it('库读不到时如实报错并给重试 —— 重试真的会再发一次请求', async () => {
    // 只让**列表**那一发失败:探数那一发(page_size 1)在挂载时就走掉了,
    // 用 `mockRejectedValueOnce` 会被它吃掉,列表反而成功。
    getAlbums.mockImplementation((o: { page_size?: number }) => (o?.page_size === 6
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({ items: [], total: 1234, page: 1, page_size: 1 })));
    renderPage();
    fireEvent.click(screen.getByText('搜棋谱').closest('button')!);
    expect(await screen.findByText('棋谱库读不到')).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
    const before = getAlbums.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(getAlbums.mock.calls.length).toBe(before + 1));
  });
});

describe('屏 15 棋谱 · 继续摆谱与最近摆过', () => {
  it('有没摆完的谱就出「继续摆谱」,写的是第几手', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '第 29 届三星杯 · 半决赛', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    const bar = screen.getByTestId('resume-baipu-bar');
    expect(within(bar).getByText('继续摆谱')).toBeInTheDocument();
    expect(bar.textContent).toContain('上次摆到第 47 手');
  });

  it('摆完了的那份不会再被当成「继续摆谱」', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '名人战 · 第七局', savedAt: Date.now() }],
      { kifu_1: { k: 241, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    expect(screen.queryByTestId('resume-baipu-bar')).not.toBeInTheDocument();
    expect(screen.getByText('已摆完')).toBeInTheDocument();
  });

  // ⚠️ 这一条守的是 `BaipuProgress.total` 那段注释:2026-08-22 之前存下的进度里**没有**
  // 这个字段。把 `undefined` 当成「没摆完」和当成「摆完了」都是在替用户下结论 ——
  // 这里要的是**不下结论**:不出「已摆完」的标,也不出「继续摆谱」那条横幅。
  it('旧进度没有 total 时,既不说「已摆完」也不当成能继续', () => {
    seedRecent(
      [{ id: 'kifu_9', name: '老进度', savedAt: Date.now() }],
      { kifu_9: { k: 12, frames: 0, updatedAt: Date.now() } },
      ['kifu_9'],
    );
    renderPage();
    expect(screen.queryByText('已摆完')).not.toBeInTheDocument();
    // k > 0 且不能证明摆完了 ⇒ 仍然可以接着摆(那是安全的一侧:再摆一遍不会丢东西)
    expect(screen.getByTestId('resume-baipu-bar').textContent).toContain('上次摆到第 12 手');
  });

  it('「接着摆」带着本地缓存的谱进摆谱屏', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '三星杯', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      ['kifu_1'],
    );
    renderPage();
    fireEvent.click(within(screen.getByTestId('kifu-recent-rows')).getByRole('button', { name: '接着摆' }));
    expect(mockNavigate).toHaveBeenCalledWith(
      '/kiosk/baipu/session/kifu_1',
      expect.objectContaining({ state: expect.objectContaining({ name: 'kifu_1' }) }),
    );
  });

  it('缓存没了就说清楚,不假装还能摆', () => {
    seedRecent(
      [{ id: 'kifu_1', name: '三星杯', savedAt: Date.now() }],
      { kifu_1: { k: 47, frames: 0, updatedAt: Date.now(), total: 241 } },
      [],   // 谱的缓存被清掉了
    );
    renderPage();
    fireEvent.click(within(screen.getByTestId('kifu-recent-rows')).getByRole('button', { name: '接着摆' }));
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByTestId('kifu-action-error').textContent).toContain('本地缓存没了');
  });

  it('一次都没摆过时写的是空态,不是一排假行', () => {
    renderPage();
    expect(screen.getByTestId('kifu-recent-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('kifu-recent-rows')).not.toBeInTheDocument();
  });
});

describe('屏 15 棋谱 · 职业直播', () => {
  it('有直播就铺出来,来源按这一批真的来自哪几家算', () => {
    useLiveMatchesMock.mockReturnValue(liveResult({
      matches: [match('m1'), match('m2', { source: 'yike', status: 'scheduled' as MatchSummary['status'] })],
    }));
    renderPage();
    expect(screen.getByTestId('kifu-live')).toBeInTheDocument();
    expect(screen.getByText('来源：星阵 · 弈客')).toBeInTheDocument();
    expect(screen.getAllByText('直播中').length).toBeGreaterThan(0);
    expect(screen.getByText('未开始')).toBeInTheDocument();
  });

  it('点一场进 /kiosk/live/:id —— Task 4 把直播下了 Dock,入口就是这儿', () => {
    useLiveMatchesMock.mockReturnValue(liveResult({ matches: [match('m1')] }));
    renderPage();
    fireEvent.click(screen.getByText('第 29 届三星杯 · 八强').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/live/m1');
  });

  // 稿子的口径:断网时**整块不渲染**,不摆一排「加载中」骗人在等。
  // 同一批数据在不报错时是渲染的(上面那条),所以这条不是「一直没有」也能过。
  it('拉不到直播时整块不渲染', () => {
    useLiveMatchesMock.mockReturnValue(liveResult({
      matches: [match('m1')], error: new Error('offline'),
    }));
    renderPage();
    expect(screen.queryByTestId('kifu-live')).not.toBeInTheDocument();
  });
});
