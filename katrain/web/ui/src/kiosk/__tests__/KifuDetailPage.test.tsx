import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuDetailPage from '../pages/KifuDetailPage';
import type { BaipuStep } from '../../api/baipuApi';

/**
 * 屏 16 · 棋谱详情 `/kiosk/kifu/:kifuId`(计划外补的一屏,记作 Task 15b)。
 *
 * **这份文件里最要紧的一条是提子那条。** 这一屏的盘不自己算气、不自己判提 ——
 * 它把 `/api/v1/baipu/load` 每一步给的 `removed[]` 原样执行。所以造的数据里有一步带
 * `removed`,断言的是「那颗子从盘上没了」:如果哪天有人在前端补一份提子实现、
 * 或者把 `removed` 忘了播,这条就红。
 *
 * ⚠️ **jsdom 没有布局引擎**,所以这里一条几何都不断言。盘线和刻度带对不对齐、右栏装不装得下,
 * 判据在 `tests/kiosk-shell-geometry.spec.ts`(真浏览器量)。这里只管「哪颗子在盘上」。
 */

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { getAlbum } = vi.hoisted(() => ({ getAlbum: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum } }));

const { baipuLoad, cacheSgfMock } = vi.hoisted(() => ({ baipuLoad: vi.fn(), cacheSgfMock: vi.fn() }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: baipuLoad }, cacheSgf: cacheSgfMock };
});

const step = (over: Partial<BaipuStep>): BaipuStep => ({
  kind: 'move', move_index: 0, property: 'B',
  row: null, col: null, color: null, removed: [], board_hash: '',
  ...over,
});

// 坐标全是 canonical(row=0 在**上**)。19 路:row 3 → 16 线,col 15 → Q。
// 第 4 手白子落 Q4,同时把第 1 手那颗 Q16 提掉 —— 提子那条断言就靠它。
const STEPS: BaipuStep[] = [
  step({ move_index: 0, property: 'B', row: 3, col: 15, color: 'B' }),   // Q16
  step({ move_index: 1, property: 'W', row: 3, col: 3, color: 'W' }),    // D16
  step({ move_index: 2, property: 'B', row: 15, col: 3, color: 'B' }),   // D4
  step({ move_index: 3, property: 'W', row: 15, col: 15, color: 'W', removed: [{ row: 3, col: 15 }] }), // Q4 提 Q16
];

const ALBUM = {
  id: 7,
  player_black: '申真谞', player_white: '柯洁',
  black_rank: '九段', white_rank: '九段',
  event: '第 29 届三星杯', round_name: '半决赛',
  result: 'B+R', move_count: 241,
  date_played: '2026-06-30', board_size: 19, handicap: 0,
  komi: 7.5, rules: 'chinese',
  place: null, source: null,
  sgf_content: '(;FF[4]GM[1]SZ[19];B[pd])',
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
  baipuLoad.mockResolvedValue({ board_size: 19, steps: STEPS, meta: {} });
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

  it('题头写的是两位棋手、段位和这一局的元数据', async () => {
    const hero = await (renderPage(), waitLoaded());
    expect(hero.textContent).toContain('申真谞');
    expect(hero.textContent).toContain('柯洁');
    expect(hero.textContent).toContain('九段');
    expect(hero.textContent).toContain('2026-06-30');
    expect(hero.textContent).toContain('19 路');
    expect(hero.textContent).toContain('中国规则');
    expect(hero.textContent).toContain('黑贴 7.5 目');
    expect(hero.textContent).toContain('241 手');
  });
});

describe('屏 16 棋谱详情 · 逐手回放', () => {
  it('一进来停在开局:盘上一颗子都没有,页控条写 0 / 4', async () => {
    renderPage();
    await waitLoaded();
    expect(board().querySelectorAll('[data-stone]')).toHaveLength(0);
    expect(screen.getByTestId('kifu-detail-pagebar').textContent).toContain('第 0 / 4 手');
  });

  it('下一手走一步,第一手那颗黑子出现在 Q16', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '下一手' }));
    expect(stoneAt('Q16')).toHaveAttribute('data-stone', 'b');
    expect(screen.getByTestId('kifu-detail-pagebar').textContent).toContain('第 1 / 4 手');
  });

  // ⚠️ 本文件的重点:提子**不在前端算**,播的是后端给的 `removed[]`。
  // 走到第 4 手,Q16 必须从盘上消失 —— 而 Q4 的白子在。
  it('走到带提子的那一手时,被提的子从盘上消失', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(stoneAt('Q16')).toBeNull();
    expect(stoneAt('Q4')).toHaveAttribute('data-stone', 'w');
    expect(stoneAt('D16')).toHaveAttribute('data-stone', 'w');
    expect(stoneAt('D4')).toHaveAttribute('data-stone', 'b');
  });

  it('退回去那颗被提的子要回来 —— 回放是可逆的,不是一路盖上去', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(stoneAt('Q16')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(stoneAt('Q16')).toHaveAttribute('data-stone', 'b');
    expect(stoneAt('Q4')).toBeNull();
  });

  it('开局时前两个键灰、末手时后两个键灰', async () => {
    renderPage();
    await waitLoaded();
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
    expect([...moves.querySelectorAll('.mv')].map((s) => s.textContent))
      .toEqual(['Q16', 'D16', 'D4', 'Q4']);
    fireEvent.click(within(moves).getByText('D4'));
    expect(screen.getByTestId('kifu-detail-pagebar').textContent).toContain('第 3 / 4 手');
    expect(stoneAt('D4')).toHaveAttribute('data-stone', 'b');
    expect(stoneAt('Q4')).toBeNull();
  });

  it('让子的 setup 不算一手 —— 它在开局就在盘上,但手数还是 0', async () => {
    baipuLoad.mockResolvedValue({
      board_size: 19,
      steps: [step({ kind: 'setup', property: 'AB', row: 9, col: 9, color: 'B' }), ...STEPS],
      meta: {},
    });
    renderPage();
    await waitLoaded();
    expect(stoneAt('K10')).toHaveAttribute('data-stone', 'b');
    expect(screen.getByTestId('kifu-detail-pagebar').textContent).toContain('第 0 / 4 手');
  });
});

describe('屏 16 棋谱详情 · 两个出口', () => {
  // 稿子画了三个键,第三个是「送去复盘」。**不做,但不是因为做不到**(2026-08-22 更正措辞):
  // `POST /api/v1/reports/` 收 `user_game_id`,服务端拿它去 `UserGame` 表里查这局是不是你下的 ——
  // 名局棋谱在那张表里没有行,得先复制一份进去,而**复盘屏的「从棋谱库导入」就是干这个的**。
  // 在这儿再开一个入口 = 同一条路两个口;galaxy 的棋谱库也只有「在研究中打开」一个出口。
  // 这条断言把那个裁定钉住:**多出第三个键就红**。
  it('只有两个动作键,没有「送去复盘」', async () => {
    renderPage();
    await waitLoaded();
    const actions = screen.getByTestId('kifu-detail-actions');
    expect([...actions.querySelectorAll('button')].map((b) => b.textContent))
      .toEqual(['摆到实体盘', '去研究']);
    expect(screen.queryByText('送去复盘')).not.toBeInTheDocument();
  });

  it('「摆到实体盘」先把整份谱缓存到本地,再进摆谱屏', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '摆到实体盘' }));
    expect(cacheSgfMock).toHaveBeenCalledWith('kifu_7', '第 29 届三星杯 · 半决赛', ALBUM.sgf_content);
    expect(mockNavigate).toHaveBeenCalledWith(
      '/kiosk/baipu/session/kifu_7',
      expect.objectContaining({ state: expect.objectContaining({ sgf: ALBUM.sgf_content }) }),
    );
  });

  it('「去研究」带着 kifu_id 进研究屏', async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole('button', { name: '去研究' }));
    // `&from=kifu` 是 2026-08-24 屏 21 加的:研究屏有四个入口、回去的地方各不相同,
    // 而屏 20 和对局历史两条的 URL 形状一模一样(都是 `?user_game_id=`)、反推不出来。
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research?kifu_id=7&analyze=1&from=kifu');
  });

  it('返回键回棋谱屏', async () => {
    renderPage();
    await waitLoaded();
    // 限定在页控条里找 —— 「棋谱」两个字在折叠块标题(「棋谱 · 交叉点坐标」)里也有一份。
    fireEvent.click(within(screen.getByTestId('kifu-detail-pagebar')).getByRole('button'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });
});
