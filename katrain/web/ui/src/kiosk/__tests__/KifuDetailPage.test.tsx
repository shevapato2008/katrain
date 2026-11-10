import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuDetailPage from '../pages/KifuDetailPage';
import { ApiError } from '../../api';

/**
 * 屏 16 · 棋谱详情 `/kiosk/kifu/:kifuId`(计划外补的一屏,记作 Task 15b)。
 *
 * 用真实 SGF 着手验证共享的屏幕回放，包括提子、退回、初始摆子和虚手。
 *
 * ⚠️ **jsdom 没有布局引擎**,所以这里一条几何都不断言。盘线和刻度带对不对齐、右栏装不装得下,
 * 判据在 `tests/kiosk-shell-geometry.spec.ts`(真浏览器量)。这里只管「哪颗子在盘上」。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { getAlbum, play } = vi.hoisted(() => ({ getAlbum: vi.fn(), play: vi.fn() }));
vi.mock('../../hooks/useSound', () => ({ useSound: () => ({ play }) }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ isLoading: false, isGuest: false, identityKey: 'kifu-detail-owner', token: 'test-token', isAuthenticated: true }) }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum } }));

const { baipuLoad, cacheSgfMock } = vi.hoisted(() => ({ baipuLoad: vi.fn(), cacheSgfMock: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: baipuLoad }, cacheSgf: cacheSgfMock };
});

// 第 4 手白 A18 与白 B19 围住黑 A19，真实提掉角上的黑子。
const MOVES = ';B[aa];W[ba];B[dd];W[ab]';

const ALBUM = {
  id: 7,
  player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', round_name: '半决赛',
  // 页面展示 API 按当前语言返回的 display_* 字段，原始 SGF 字段仅保留为源数据。
  display_player_black: '申真谞', display_player_white: '柯洁',
  display_black_rank: '九段', display_white_rank: '九段',
  display_event: '第 29 届三星杯', display_round_name: '半决赛',
  result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese',
  place: null, source: null,
  sgf_content: `(;FF[4]GM[1]SZ[19]${MOVES})`,
};

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/kifu/7']}>
        <Routes>
          <Route path="/kiosk/kifu/:kifuId" element={<KifuDetailPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

const stoneAt = (coord: string) => document.querySelector(`[data-at="${coord}"]`);
const board = () => screen.getByTestId('kifu-detail-board');
const waitLoaded = () => screen.findByTestId('kifu-detail-hero');

beforeEach(() => {
  vi.clearAllMocks();
  // jsdom 里 `scrollIntoView` 不存在。这是**测试环境的缺口**,不是产品要绕的东西 ——
  // 补在这里,不在页面里加 `if (typeof ... === 'function')`。
  Element.prototype.scrollIntoView = vi.fn();
  getAlbum.mockResolvedValue(ALBUM);
  baipuLoad.mockRejectedValue(new Error('screen replay must not load physical steps'));
});

describe('屏 16 棋谱详情 · 三种状态', () => {
  it('还在读的时候说的是「正在读这一局」', () => {
    getAlbum.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByTestId('kifu-detail-loading')).toBeInTheDocument();
  });

  it('读不到就报错,并且重试真的会再拉一次', async () => {
    getAlbum.mockRejectedValueOnce(new Error('404'));
    renderPage();
    expect(await screen.findByTestId('kifu-detail-error')).toBeInTheDocument();
    expect(screen.getByText('404')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(2));
    await waitLoaded();
  });

  it('连不上云端时提示检查连接或重试，不断言盒子离线', async () => {
    getAlbum.mockRejectedValueOnce(new ApiError(503, 'Request failed 503', { code: 'kifu_cloud_unreachable' }));
    renderPage();
    expect(await screen.findByText('无法连接棋谱库')).toBeInTheDocument();
    expect(screen.getByText('请检查网络连接或稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitLoaded();
  });

  it('云端服务报错时提示暂不可用，不误报断网', async () => {
    getAlbum.mockRejectedValueOnce(new ApiError(503, 'Request failed 503', { code: 'kifu_cloud_error' }));
    renderPage();
    expect(await screen.findByText('棋谱库暂时不可用')).toBeInTheDocument();
    expect(screen.getByText('云端服务暂时出了问题，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText('无法连接棋谱库')).toBeNull();
    expect(screen.queryByText(/Request failed/)).toBeNull();
  });

  it('题头写的是两位棋手、段位和这一局的元数据', async () => {
    const hero = await (renderPage(), waitLoaded());
    expect(hero.textContent).toContain('申真谞');
    expect(hero.textContent).toContain('柯洁');
    expect(hero.textContent).toContain('九段');
    expect(hero.textContent).toContain('2026-06-30');
    expect(hero).toHaveAttribute('title', expect.stringContaining('19 路'));
    expect(hero).toHaveAttribute('title', expect.stringContaining('中国规则'));
    expect(hero).toHaveAttribute('title', expect.stringContaining('SGF 贴目 7.5 目'));
    expect(hero.textContent).toContain('4 手');
  });
});

it('棋局详情触控入口显示规则、路数和贴目', async () => {
  renderPage(); await waitLoaded();
  fireEvent.click(screen.getByRole('button', { name: '棋局详情' }));
  const dialog = screen.getByRole('dialog', { name: '棋局详情' });
  expect(dialog).toHaveTextContent('19 路');
  expect(dialog).toHaveTextContent('中国规则');
  expect(dialog).toHaveTextContent('SGF 贴目 7.5 目');
  fireEvent.click(within(dialog).getByRole('button', { name: '关闭' }));
  expect(screen.queryByRole('dialog')).toBeNull();
});

describe('屏 16 棋谱详情 · 逐手回放', () => {
  it('一进来显示终局盘和真实回放手数 4 / 4', async () => {
    renderPage();
    await waitLoaded();
    expect(board().querySelectorAll('[data-stone]')).toHaveLength(3);
    expect(screen.getByTestId('kifu-detail-moves').textContent).toContain('第 4 / 4 手');
    expect(baipuLoad).not.toHaveBeenCalled();
  });

  it('下一手走一步,第一手那颗黑子出现在 A19', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '回到开局' }));
    fireEvent.click(screen.getByRole('button', { name: '下一手' }));
    expect(stoneAt('A19')).toHaveAttribute('data-stone', 'b');
    expect(screen.getByTestId('kifu-detail-moves').textContent).toContain('第 1 / 4 手');
  });

  it('走到围住角上黑子的那一手时,被提的子从盘上消失', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(stoneAt('A19')).toBeNull();
    expect(stoneAt('A18')).toHaveAttribute('data-stone', 'w');
    expect(stoneAt('B19')).toHaveAttribute('data-stone', 'w');
    expect(stoneAt('D16')).toHaveAttribute('data-stone', 'b');
  });

  it('退回去那颗被提的子要回来 —— 回放是可逆的,不是一路盖上去', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(stoneAt('A19')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(stoneAt('A19')).toHaveAttribute('data-stone', 'b');
    expect(stoneAt('A18')).toBeNull();
  });

  it('开局时前两个键灰、末手时后两个键灰', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '回到开局' }));
    expect(screen.getByRole('button', { name: '回到开局' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '上一手' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '下一手' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(screen.getByRole('button', { name: '下一手' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '跳到最后' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '回到开局' })).not.toBeDisabled();
  });

  it('谱上一行两手,黑一格白一格;点哪一手就跳到哪一手', async () => {
    renderPage();
    await waitLoaded();
    const moves = screen.getByTestId('kifu-detail-moves');
    expect([...moves.querySelectorAll('.kifu-replay-move-grid button')].map(button => button.textContent))
      .toEqual(['1A19', '2B19', '3D16', '4A18']);
    fireEvent.click(moves.querySelectorAll('.kifu-replay-move-grid button')[2]);
    expect(screen.getByTestId('kifu-detail-moves').textContent).toContain('第 3 / 4 手');
    expect(stoneAt('D16')).toHaveAttribute('data-stone', 'b');
    expect(stoneAt('A18')).toBeNull();
  });

  it('让子的 setup 不算一手 —— 它在开局就在盘上,但手数还是 0', async () => {
    getAlbum.mockResolvedValue({ ...ALBUM, sgf_content: `(;SZ[19]AB[jj]${MOVES})` });
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '回到开局' }));
    expect(stoneAt('K10')).toHaveAttribute('data-stone', 'b');
    expect(screen.getByTestId('kifu-detail-moves').textContent).toContain('第 0 / 4 手');
  });
});

describe('屏 16 棋谱详情 · 两个出口', () => {
  // 稿子画了三个键,第三个是「送去复盘」。**不做,但不是因为做不到**(2026-08-22 更正措辞):
  // `POST /api/v1/reports/` 收 `user_game_id`,服务端拿它去 `UserGame` 表里查这局是不是你下的 ——
  // 名局棋谱在那张表里没有行,得先复制一份进去,而**复盘屏的「从棋谱库导入」就是干这个的**。
  // 在这儿再开一个入口 = 同一条路两个口;galaxy 的棋谱库也只有「在研究中打开」一个出口。
  // 这条断言把那个裁定钉住:**多出第三个键就红**。
  it('回放提供实体盘出口，不混入分析操作', async () => {
    renderPage();
    await waitLoaded();
    const actions = screen.getByTestId('kifu-detail-actions');
    expect([...actions.querySelectorAll('button')].map((b) => b.textContent))
      .toEqual(['实体盘']);
    expect(screen.queryByText('送去复盘')).not.toBeInTheDocument();
  });

  it('「摆到实体盘」先把整份谱缓存到本地,再进摆谱屏', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '实体盘' }));
    expect(cacheSgfMock).toHaveBeenCalledWith('kifu_7', '第 29 届三星杯 · 半决赛', ALBUM.sgf_content, expect.objectContaining({ getItem: expect.any(Function), setItem: expect.any(Function), removeItem: expect.any(Function) }));
    expect(mockNavigate).toHaveBeenCalledWith(
      '/kiosk/baipu/session/kifu_7',
      // backTo:摆谱会话的返回键回这一局的详情页(2026-09-22),不是一律回摆谱列表
      expect.objectContaining({ state: expect.objectContaining({ sgf: ALBUM.sgf_content, backTo: '/kiosk/kifu/7' }) }),
    );
  });

  it('未分析状态说明不会伪造 AI 数据', async () => {
    renderPage(); await waitLoaded();
    expect(screen.getByText('尚未分析')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: '着手评价' })).not.toBeInTheDocument();
  });

  it('返回键回棋谱屏', async () => {
    renderPage();
    await waitLoaded();
    // 限定在页控条里找 —— 「棋谱」两个字在折叠块标题(「棋谱 · 交叉点坐标」)里也有一份。
    fireEvent.click(within(screen.getByTestId('kifu-detail-pagebar')).getByRole('button', { name: /棋谱/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('13 路的谱「摆到实体盘」灰着,并说明实体盘只摆得了 19 路', async () => {
    getAlbum.mockResolvedValue({ ...ALBUM, board_size: 13, sgf_content: '(;SZ[13];B[dd])' });
    renderPage();
    await waitLoaded();
    const btn = screen.getByRole('button', { name: '实体盘' });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('title', expect.stringContaining('13 路'));
  });
});

it('keeps archive load, pass and start silent while explicit forward/backward/jump replay sounds once', async () => {
  getAlbum.mockResolvedValue({ ...ALBUM, sgf_content: `(;SZ[19]${MOVES};B[])` });
  renderPage(); await waitLoaded();
  expect(play).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '回到开局' }));
  expect(play).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '下一手' }));
  expect(play).toHaveBeenCalledExactlyOnceWith('stone');
  fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
  expect(play).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '上一手' }));
  expect(play).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole('button', { name: '回到开局' }));
  expect(play).toHaveBeenCalledTimes(2);
});
