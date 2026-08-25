import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskMove, ReportTaskSummary } from '../../api/reportApi';
import type { UserGameDetail, UserGameSummary } from '../../api/userGamesApi';
import { LedAPI } from '../../api/ledApi';
import { API } from '../../api';
import { kioskTheme } from '../theme';
import ReportsPage from './ReportsPage';

/**
 * 屏 19 复盘 `/kiosk/report`。
 *
 * ⚠️ **这里一条几何都不断言。** jsdom 没有布局引擎 —— 「只有中间那块滚」「露一半」
 * 「右栏恒 680」判在 `tests/kiosk-shell-geometry.spec.ts`(真浏览器量 1024×600)。
 * 上一版有一个 `ReportsPage.layout.test.tsx` 在 jsdom 里断言 `flex:1` / `minHeight:0`,
 * 它断的是**声明**不是**结论**(把它原样搬进真浏览器不可能失败),而且它的断言对象
 * (`report-preview-region` / `PlaybackBar`)本轮整块没了 —— **已删**。
 *
 * 这份文件守的是「屏上说的是不是真的」:提子有没有减掉、没算过的时候写不写「未分析」、
 * 四种分析状态是不是各有各的样子、迟到的接口回包会不会盖掉新结果。
 */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  deleteGame: vi.fn(),
  getAlbum: vi.fn(),
  getAlbums: vi.fn(),
  navigate: vi.fn(),
  baipuLoad: vi.fn(),
  getMoves: vi.fn(),
  createReport: vi.fn(),
  retryReport: vi.fn(),
  refreshTasks: vi.fn(),
  clearError: vi.fn(),
  hookResult: {} as Record<string, unknown>,
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true, user: { username: '阿福' } }),
}));
vi.mock('../../api/userGamesApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/userGamesApi')>();
  return { ...actual, UserGamesAPI: { ...actual.UserGamesAPI, list: mocks.list, get: mocks.get, create: mocks.create, delete: mocks.deleteGame } };
});
vi.mock('../../api/kifuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/kifuApi')>();
  return { ...actual, KifuAPI: { ...actual.KifuAPI, getAlbum: mocks.getAlbum, getAlbums: mocks.getAlbums } };
});
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: mocks.baipuLoad } };
});
vi.mock('../../api/reportApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/reportApi')>();
  return { ...actual, ReportsAPI: { ...actual.ReportsAPI, getMoves: mocks.getMoves } };
});
vi.mock('../../features/report/useReportTasks', () => ({
  useReportTasks: () => mocks.hookResult,
}));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mocks.navigate };
});

const game = (id: string, over: Partial<UserGameSummary> = {}): UserGameSummary => ({
  id, user_id: 1, title: null, player_black: '阿福', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'W+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 187, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: '2026-08-20',
  created_at: '2026-08-20T15:12:00', updated_at: null,
  ...over,
});
const detail = (summary: UserGameSummary, sgf?: string): UserGameDetail => ({
  ...summary,
  sgf_content: sgf ?? `(;FF[4]GM[1]SZ[${summary.board_size}];B[pd];W[dd])`,
});
const response = (items: UserGameSummary[], page = 1, total = items.length) => ({ items, total, page, page_size: 12 });

const step = (over: Record<string, unknown>) => ({
  kind: 'move', move_index: 0, property: 'B', row: null, col: null, color: null,
  removed: [], board_hash: '', ...over,
});
// 第 3 步白子落 Q4 并把第 1 步那颗 Q16 提掉 —— 终局盘上不许还留着 Q16。
const STEPS = [
  step({ move_index: 0, property: 'B', row: 3, col: 15, color: 'B' }),   // Q16
  step({ move_index: 1, property: 'W', row: 3, col: 3, color: 'W' }),    // D16
  step({ move_index: 2, property: 'W', row: 15, col: 15, color: 'W', removed: [{ row: 3, col: 15 }] }), // Q4 提 Q16
];

const task = (over: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 41, user_game_id: 'a', status: 'completed', report_type: 'normal',
  total_moves: 187, analyzed_moves: 187, requested_visits: 500, ...over,
});

const reportMove = (over: Partial<ReportTaskMove>): ReportTaskMove => ({
  id: over.move_number ?? 0, task_id: 41, move_number: 0, status: 'success',
  winrate: null, score_lead: null, visits: 500, top_moves: null, ownership: null,
  actual_move: null, actual_player: null, delta_score: null, delta_winrate: null,
  ...over,
});
// 黑一手掉 4 分(过失误线)、一手赚 3 分(过妙手线)。
const MOVES: ReportTaskMove[] = [
  reportMove({ move_number: 0, winrate: 0.5, score_lead: 0 }),
  reportMove({ move_number: 1, winrate: 0.3, score_lead: -4, actual_player: 'B', delta_score: -4 }),
  reportMove({ move_number: 2, winrate: 0.35, score_lead: -5, actual_player: 'W', delta_score: -1 }),
  reportMove({ move_number: 3, winrate: 0.55, score_lead: -2, actual_player: 'B', delta_score: 3 }),
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}{location.search}</div>;
}

function renderPage(route = '/kiosk/report') {
  return render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/kiosk/report" element={<><ReportsPage /><LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

const rows = () => screen.getAllByTestId('review-row');
const cellValue = (label: string) =>
  screen.getByText(label).closest('.kiosk-status__cell')!.querySelector('.kiosk-status__v')!.textContent;
const stones = () => document.querySelectorAll('.kiosk-mini-board [data-stone]');
const stoneAt = (coord: string) => document.querySelector(`.kiosk-mini-board [data-at="${coord}"]`);

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue(response([game('a'), game('b', { player_white: '柯洁', white_rank: '九段' })]));
  mocks.get.mockImplementation(async (_token: string, id: string) => detail(game(id)));
  mocks.create.mockResolvedValue(detail(game('new')));
  mocks.deleteGame.mockResolvedValue({ status: 'deleted' });
  mocks.baipuLoad.mockResolvedValue({ board_size: 19, steps: STEPS, meta: {} });
  mocks.getMoves.mockResolvedValue(MOVES);
  mocks.getAlbum.mockResolvedValue({ sgf_content: '(;SZ[13];B[aa])' });
  mocks.getAlbums.mockResolvedValue({ items: [{
    id: 10, player_black: '库黑', player_white: '库白', black_rank: '', white_rank: '',
    event: '库赛事', result: 'W+R', move_count: 1, date_played: '2026-07-15', board_size: 13,
    handicap: 0, komi: 7.5, rules: 'chinese', round_name: null,
  }], total: 1, page: 1, page_size: 10 });
  mocks.createReport.mockResolvedValue({ id: 99 });
  mocks.retryReport.mockResolvedValue({ id: 8 });
  mocks.refreshTasks.mockResolvedValue(undefined);
  mocks.hookResult = {
    tasks: [], queueSummary: null, reportStatesByGame: {}, loading: false, error: null,
    clearError: mocks.clearError, refresh: mocks.refreshTasks,
    createReport: mocks.createReport, retryReport: mocks.retryReport,
  };
});

describe('屏 19 · 列表与选中', () => {
  it('从 URL 读搜索词和页码,并默认选中第一行', async () => {
    renderPage('/kiosk/report?q=柯洁&page=2');
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith('token', {
      page: 2, page_size: 12, q: '柯洁', sort: 'created_at_desc',
    }));
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-selected', 'true'));
    expect(rows()[1]).toHaveAttribute('data-selected', 'false');
  });

  it('点另一行换选中,左栏跟着换那一局', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(within(rows()[1]).getByRole('button', { name: /vs 柯洁/ }));
    await waitFor(() => expect(rows()[1]).toHaveAttribute('data-selected', 'true'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('token', 'b'));
  });

  it('刷新后仍在的那一局保持选中,不跳回第一行', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(within(rows()[1]).getByRole('button', { name: /vs 柯洁/ }));
    await waitFor(() => expect(rows()[1]).toHaveAttribute('data-selected', 'true'));
    mocks.list.mockResolvedValue(response([game('a'), game('b', { player_white: '柯洁', white_rank: '九段' })]));
    fireEvent.click(screen.getByRole('button', { name: '筛选和搜索历史对局' }));
    await waitFor(() => expect(rows()[1]).toHaveAttribute('data-selected', 'true'));
  });

  it('搜索写进 URL、页码归 1;翻页把搜索词留着', async () => {
    renderPage('/kiosk/report?page=3');
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: '筛选和搜索历史对局' }));
    const box = screen.getByTestId('review-search');
    fireEvent.change(box, { target: { value: '  柯洁  ' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/report?q=%E6%9F%AF%E6%B4%81'));
  });

  it('收起搜索会把搜索词一起撤掉 —— 不留一条看不见的过滤条件', async () => {
    renderPage('/kiosk/report?q=柯洁');
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(screen.getByTestId('review-search')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '筛选和搜索历史对局' }));
    await waitFor(() => expect(screen.queryByTestId('review-search')).toBeNull());
    expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/report');
    expect(screen.getByTestId('location')).not.toHaveTextContent('q=');
  });

  it('迟到的成功不覆盖最新那批结果', async () => {
    const stale = deferred<ReturnType<typeof response>>();
    mocks.list.mockReturnValueOnce(stale.promise);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: '筛选和搜索历史对局' }));
    const box = screen.getByTestId('review-search');
    fireEvent.change(box, { target: { value: '柯洁' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(rows()).toHaveLength(2));
    await act(async () => { stale.resolve(response([game('stale')])); });
    expect(rows()).toHaveLength(2);
  });

  it('迟到的失败不清掉最新结果,也不冒出一条过期的错', async () => {
    const stale = deferred<ReturnType<typeof response>>();
    mocks.list.mockReturnValueOnce(stale.promise);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: '筛选和搜索历史对局' }));
    const box = screen.getByTestId('review-search');
    fireEvent.change(box, { target: { value: '柯洁' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(rows()).toHaveLength(2));
    await act(async () => { stale.reject(new Error('过期')); });
    expect(rows()).toHaveLength(2);
    expect(screen.queryByText('过期')).toBeNull();
  });

  it('列表读不到时报错,重试能反复点', async () => {
    mocks.list.mockRejectedValueOnce(new Error('断网了'));
    renderPage();
    expect(await screen.findByText('断网了')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(rows()).toHaveLength(2));
  });

  it('一局都没有时说的是「还没有下过的棋」,不是一片空白', async () => {
    mocks.list.mockResolvedValue(response([], 1, 0));
    renderPage();
    expect(await screen.findByText('还没有下过的棋')).toBeInTheDocument();
    expect(screen.queryAllByTestId('review-row')).toHaveLength(0);
  });
});

/**
 * 来源筛选(Fan 2026-08-26 裁定要补)。它是 27 屏改造前那一屏「对局历史」有、
 * 屏 19 没有的唯一一件东西 —— 那一屏这一轮删了(全仓没有任何入口)。
 *
 * 几何在 `tests/kiosk-shell-scroll.spec.ts`(真浏览器 1024×600 量:展开那条带子
 * 正好从列表里扣 54,和 `.has-search::before` 那个 +54 是同一个数)。
 * 这里守的是**口径**:筛出来的空不许说成「一局没下过」、看不见的筛选不许留着。
 */
/**
 * 组标题右端那个数**是谁数的**。
 *
 * 「本机 N 局」以前是句假话:盒子在线时列表和 `total` 来自云端(跨设备),
 * 只有断网那一档它才碰巧是真的 —— 而用户没有任何办法分辨自己看的是哪一档。
 * 后端那三档在 `tests/web_ui/test_user_games_authority.py`。
 */
describe('屏 19 · 这个数是谁数的', () => {
  it('云端那份说「共 N 局」—— 它是跨设备的总数,不是这台盒子的', async () => {
    mocks.list.mockResolvedValue({ ...response([game('a')], 1, 37), authority: 'cloud' });
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(1));
    const label = document.querySelector('.kiosk-section--grow .secval') as HTMLElement;
    expect(label).toHaveTextContent('共 37 局');
    expect(label).not.toHaveTextContent('本机');
  });

  it.each(['this_node', 'local_cache'] as const)('%s 说「本机 N 局」', async (authority) => {
    mocks.list.mockResolvedValue({ ...response([game('a')], 1, 3), authority });
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(document.querySelector('.kiosk-section--grow .secval')).toHaveTextContent('本机 3 局');
  });

  it('老服务端不带这一格时退回「本机」——**不知道就说小的那个**', async () => {
    // 反过来(默认当成 cloud)的代价是不对称的:说小了用户会去找,说大了他不会。
    mocks.list.mockResolvedValue(response([game('a')], 1, 3));
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(1));
    const label = document.querySelector('.kiosk-section--grow .secval') as HTMLElement;
    expect(label).toHaveTextContent('本机 3 局');
    expect(label).not.toHaveTextContent('共');
  });

  it('搜到 / 面对面 那两句不声称完整,云端与否都不改口', async () => {
    mocks.list.mockResolvedValue({ ...response([game('a')], 1, 2), authority: 'cloud' });
    renderPage('/kiosk/report?q=柯洁');
    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(document.querySelector('.kiosk-section--grow .secval')).toHaveTextContent('搜到 2 局');
  });
});

describe('屏 19 · 按来源筛', () => {
  it('筛「面对面」把 source 发给后端,并写进 URL', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: '筛选和搜索历史对局' }));
    fireEvent.click(screen.getByRole('button', { name: '面对面' }));
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith('token', {
      page: 1, page_size: 12, q: undefined, sort: 'created_at_desc', source: 'play_local',
    }));
    expect(screen.getByTestId('location')).toHaveTextContent('source=play_local');
  });

  it('「全部」不往后端发 source —— 别把默认值也当成一个筛选条件', async () => {
    renderPage('/kiosk/report?source=play_local');
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: '全部' }));
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith('token', {
      page: 1, page_size: 12, q: undefined, sort: 'created_at_desc', source: undefined,
    }));
    expect(screen.getByTestId('location')).not.toHaveTextContent('source=');
  });

  it('URL 上带着筛选进来时,那条带子是**开着**的', async () => {
    renderPage('/kiosk/report?source=play_local');
    await waitFor(() => expect(rows()).toHaveLength(2));
    // 收着的话列表短了,而屏上没有任何控件说得出为什么。
    expect(screen.getByTestId('review-source')).toBeInTheDocument();
    expect(within(screen.getByTestId('review-source')).getByRole('button', { name: '面对面' }))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('收起那条带子会把筛选一起撤掉,不是只撤搜索词', async () => {
    renderPage('/kiosk/report?source=play_local');
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: '筛选和搜索历史对局' }));
    await waitFor(() => expect(screen.queryByTestId('review-source')).toBeNull());
    expect(screen.getByTestId('location')).not.toHaveTextContent('source=');
  });

  it('计数写的是筛出来那一档,不是「本机 N 局」', async () => {
    mocks.list.mockResolvedValue(response([game('a')], 1, 1));
    renderPage('/kiosk/report?source=play_local');
    await waitFor(() => expect(rows()).toHaveLength(1));
    const label = document.querySelector('.kiosk-section--grow .secval') as HTMLElement;
    expect(label).toHaveTextContent('面对面 1 局');
    expect(label).not.toHaveTextContent('本机');
  });

  it('筛出来是空的,说的是「还没有面对面下过」——**不是**「还没有下过的棋」', async () => {
    // 把筛选的后果栽到用户头上是这一族最常见的谎:他可能下过一百局人机。
    mocks.list.mockResolvedValue(response([], 1, 0));
    renderPage('/kiosk/report?source=play_local');
    expect(await screen.findByText('还没有面对面下过')).toBeInTheDocument();
    expect(screen.queryByText('还没有下过的棋')).toBeNull();
  });

  it('认不得的 source 退回全部 —— URL 是手输得到的,不该让列表空着还怪用户', async () => {
    renderPage('/kiosk/report?source=乱写的');
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith('token', {
      page: 1, page_size: 12, q: undefined, sort: 'created_at_desc', source: undefined,
    }));
    expect(document.querySelector('.kiosk-section--grow .secval')).toHaveTextContent('本机');
  });

  it('导入一局之后筛选收回全部 —— 导进来的是 import,筛在面对面上它根本不在结果里', async () => {
    mocks.create.mockResolvedValue({ ...game('imported'), sgf_content: '(;FF[4]SZ[19];B[pd])' });
    renderPage('/kiosk/report?source=play_local');
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: /导入棋谱复盘/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '导入本地 SGF' }));
    const box = await screen.findByLabelText('SGF 内容');
    fireEvent.change(box, { target: { value: '(;FF[4]GM[1]SZ[19];B[pd];W[dd])' } });
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('source='));
  });
});

describe('屏 19 · 左栏(选中这一局)', () => {
  // ⚠️ **提子不在前端算。** 盘面是把 `/baipu/load` 每一步的 `removed[]` 原样播一遍得到的。
  // 哪天有人在前端补一份提子实现、或者把 `removed` 忘了播,这条就红。
  it('左栏那块盘是终局盘,被提的子不在上面', async () => {
    renderPage();
    await waitFor(() => expect(stones()).toHaveLength(2));
    expect(stoneAt('Q16')).toBeNull();
    expect(stoneAt('Q4')).toHaveAttribute('data-stone', 'w');
    expect(stoneAt('D16')).toHaveAttribute('data-stone', 'w');
  });

  it('谱铺不开时画空盘并说明,不摆一盘不是这一局的子当装饰', async () => {
    mocks.baipuLoad.mockRejectedValue(new Error('SGF 坏了'));
    renderPage();
    expect(await screen.findByText('这一局的谱读不出来')).toBeInTheDocument();
    expect(stones()).toHaveLength(0);
  });

  // 「没算过」和「算过了,准确率 0%」是两件事。三格拿 `未分析` 分开它们。
  it('没有报告时三格写「未分析」,不写 0%', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(cellValue('准确率')).toBe('未分析');
    expect(cellValue('失误')).toBe('未分析');
    expect(cellValue('妙手')).toBe('未分析');
    expect(mocks.getMoves).not.toHaveBeenCalled();
  });

  it('有报告时三格是真数字 —— 妙手那一格数的是 delta_score ≥ 2 的手', async () => {
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    renderPage();
    await waitFor(() => expect(mocks.getMoves).toHaveBeenCalledWith('token', 41));
    await waitFor(() => expect(cellValue('失误')).toBe('1 手'));
    expect(cellValue('妙手')).toBe('1 手');
    expect(cellValue('准确率')).toMatch(/^\d+%$/);
  });

  // 判不出「你」的局(两人面对面下的、导进来的谱)不许挑一方冒充你。
  it('本地两人对局判不出「你」,同步行写明是按谁的视角算的', async () => {
    mocks.list.mockResolvedValue(response([game('a', {
      source: 'play_local', player_black: '小明', player_white: '小红', result: 'B+R',
    })]));
    renderPage();
    expect(await screen.findByText(/本地对局 · 两人 · 黑方视角/)).toBeInTheDocument();
    expect(screen.queryByText(/你\(/)).toBeNull();
  });
});

describe('屏 19 · 这一局的胜率', () => {
  it('没算过的时候不画线,写明为什么空', async () => {
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-selected', 'true'));
    const plot = screen.getByTestId('review-winrate-plot');
    expect(plot).toHaveAttribute('data-state', 'empty');
    expect(plot.textContent).toContain('这一局还没分析');
    expect(plot.querySelector('polyline')).toBeNull();
  });

  it('算过了就按黑方胜率画,掉分最狠的那一手单独一段红', async () => {
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'plotted'));
    expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-points', '4');
    expect(screen.getByTestId('review-winrate-drop')).toBeInTheDocument();
  });

  it('报告读不出来时那句话就是错误本身,不是一条假曲线', async () => {
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    mocks.getMoves.mockRejectedValue(new Error('报告没了'));
    renderPage();
    expect(await screen.findByText('报告没了')).toBeInTheDocument();
    expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'empty');
  });
});

describe('屏 19 · 行的五种状态', () => {
  const withState = (state: Record<string, unknown>) => {
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: state } };
  };

  it('只跑了一档:标 + 一个「查看报告」,点了进报告屏', async () => {
    withState({ completedNormal: task() });
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'analyzed'));
    expect(within(rows()[0]).getByText('已分析')).toBeInTheDocument();
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '查看报告' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/report/41');
  });

  // ⚠️ **报告按档发** —— 两档都跑完时一个「查看报告」指不了两个 id。
  // 上一版的 `ReportGameCard` 本来就是两个键,收成一个等于丢了一条路。
  it('两档都跑完:拆成「标准」「精读」两个键,各自只有一个宾语', async () => {
    withState({ completedNormal: task(), completedDeep: task({ id: 88, report_type: 'deep' }) });
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'analyzed'));
    expect(within(rows()[0]).queryByRole('button', { name: '查看报告' })).toBeNull();
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '标准' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/report/41');
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '精读' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/report/88');
  });

  it('正在分析:写到第几手了,没有按钮 —— 算完自己会变', async () => {
    withState({ activeNormal: task({ status: 'running', analyzed_moves: 31 }) });
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'running'));
    expect(within(rows()[0]).getByText('正在分析 31/187')).toBeInTheDocument();
    expect(within(rows()[0]).queryByRole('button', { name: '查看报告' })).toBeNull();
    expect(within(rows()[0]).queryByRole('button', { name: '继续分析' })).toBeNull();
  });

  // **「算了一半」既不是成功也不是失败**,它必须自己一档。后端没有「暂停」这个状态:
  // 跑了一半断掉的任务落在 failed 上、`analyzed_moves` 还留着,重试会从断点续算。
  it('只算到一半:自己一档,行尾说的是「继续分析」而不是「重试」', async () => {
    withState({ failedNormal: task({ status: 'failed', analyzed_moves: 96 }) });
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'partial'));
    expect(within(rows()[0]).getByText('只算到 96/187')).toBeInTheDocument();
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '继续分析' }));
    expect(mocks.retryReport).toHaveBeenCalledWith(41);
    expect(mocks.navigate).not.toHaveBeenCalled();       // 就地干活,不跳页
  });

  it('一手都没算成:说的是失败,给的是重试', async () => {
    withState({ failedNormal: task({ status: 'failed', analyzed_moves: 0 }) });
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'failed'));
    expect(within(rows()[0]).getByText('分析失败')).toBeInTheDocument();
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '重试' }));
    expect(mocks.retryReport).toHaveBeenCalledWith(41);
  });

  // **判别位是「这局结束了没有」,不是「算不算分」** —— 半局的报告没意义,
  // 而且离线 KataGo 把残局算完再回去接着下是一条真作弊通道。
  // 计分局下完了照样该有报告(国象稿子明写两者进的是同一条复盘线)。
  it('没下完的局标「未终局」,而且两张档位卡按不了', async () => {
    mocks.list.mockResolvedValue(response([game('a', { result: null, move_count: 22 })]));
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'unfinished'));
    expect(within(rows()[0]).getByText('未终局')).toBeInTheDocument();
    // 那句话自己带着手数,后面不许再挂一段「22 手」—— 同一个数说两遍。
    expect(within(rows()[0]).getByText(/^下到第 22 手就退出了 · /)).toBeInTheDocument();
    expect(within(rows()[0]).queryByText(/就退出了 · 22 手/)).toBeNull();
    expect(screen.getByRole('button', { name: /标准/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /精读/ })).toBeDisabled();
  });

  it('计分局下完了照样能分析 —— 挡的是没下完,不是算不算分', async () => {
    mocks.list.mockResolvedValue(response([game('a', { game_type: 'ai_ladder_ranked', result: 'W+R' })]));
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-state', 'unanalyzed'));
    expect(screen.getByRole('button', { name: /标准/ })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /标准/ }));
    expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'a', reportType: 'normal', totalMoves: 187 });
  });

  it('行里念的是「你(黑)…」,而且计分局认得出来', async () => {
    mocks.list.mockResolvedValue(response([
      game('a', { result: 'B+R' }),
      game('b', { game_type: 'ai_ladder_ranked', result: 'W+2.5' }),
    ]));
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(within(rows()[0]).getByText(/你\(黑\)中盘胜/)).toBeInTheDocument();
    expect(within(rows()[1]).getByText(/升降级对弈/)).toBeInTheDocument();
    expect(within(rows()[1]).getByText(/你\(黑\)负 2.5/)).toBeInTheDocument();
  });
});

describe('屏 19 · 生成报告那一组', () => {
  it('两张档位卡对**选中的那一局**建任务', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    fireEvent.click(within(rows()[1]).getByRole('button', { name: /vs 柯洁/ }));
    await waitFor(() => expect(rows()[1]).toHaveAttribute('data-selected', 'true'));
    fireEvent.click(screen.getByRole('button', { name: /标准/ }));
    expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'b', reportType: 'normal', totalMoves: 187 });
    fireEvent.click(screen.getByRole('button', { name: /精读/ }));
    expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'b', reportType: 'deep', totalMoves: 187 });
  });

  it('一局都没有时两张档位卡按不了 —— 按了没有作用对象', async () => {
    mocks.list.mockResolvedValue(response([], 1, 0));
    renderPage();
    await screen.findByText('还没有下过的棋');
    expect(screen.getByRole('button', { name: /标准/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /精读/ })).toBeDisabled();
  });

  // ⚠️ 稿子把第三张卡画成「接口还没有 · 即将上线」,那是稿子写错了:两条导入路都在跑。
  // 这条断言把那个裁定钉住 —— 谁把它改回 `is-soon` 就红。
  it('第三张卡是能用的,点开有本地 SGF 和棋谱库两条路', async () => {
    renderPage();
    const card = await screen.findByRole('button', { name: /导入棋谱复盘/ });
    expect(card).not.toBeDisabled();
    expect(screen.queryByText('即将上线')).toBeNull();
    fireEvent.click(card);
    expect(await screen.findByRole('menuitem', { name: '导入本地 SGF' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: '从棋谱库导入' })).toBeInTheDocument();
  });

  it('本地导入可以只存不分析,也可以存完直接建报告', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱复盘/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '导入本地 SGF' }));
    fireEvent.change(await screen.findByLabelText('SGF 内容'), { target: { value: '(;SZ[19];B[aa])' } });
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalled());
    expect(mocks.createReport).not.toHaveBeenCalled();
  });

  it('导入失败时错留在对话框里,输入不丢', async () => {
    mocks.create.mockRejectedValueOnce(new Error('SGF 不合法'));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱复盘/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '导入本地 SGF' }));
    const box = await screen.findByLabelText('SGF 内容');
    fireEvent.change(box, { target: { value: '(;SZ[19];B[aa])' } });
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    expect(await screen.findByText('SGF 不合法')).toBeInTheDocument();
    expect(box).toHaveValue('(;SZ[19];B[aa])');
  });

  it('从棋谱库导入走的是同一条路 —— 把那一局复制进你自己的对局表', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱复盘/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '从棋谱库导入' }));
    fireEvent.click(await screen.findByText('库赛事'));
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(mocks.getAlbum).toHaveBeenCalledWith(10));
    await waitFor(() => expect(mocks.create).toHaveBeenCalled());
  });
});

describe('屏 19 · 删除', () => {
  // 五十二高的行上并排三个可点的东西,误触的是最不能误触的那个 ——
  // 所以删除只挂在**选中**的那一行上。
  it('删除只出现在选中的那一行上', async () => {
    renderPage();
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-selected', 'true'));
    expect(within(rows()[0]).getByRole('button', { name: '删除' })).toBeInTheDocument();
    expect(within(rows()[1]).queryByRole('button', { name: '删除' })).toBeNull();
  });

  it('确认之后才删,删完重新拉列表', async () => {
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-selected', 'true'));
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '删除' }));
    expect(mocks.deleteGame).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', { name: '确认删除' }));
    await waitFor(() => expect(mocks.deleteGame).toHaveBeenCalledWith('token', 'a'));
    await waitFor(() => expect(mocks.refreshTasks).toHaveBeenCalled());
  });

  it('删除失败时说出来,并且留在原地', async () => {
    mocks.deleteGame.mockRejectedValueOnce(new Error('删不掉'));
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    await waitFor(() => expect(rows()[0]).toHaveAttribute('data-selected', 'true'));
    fireEvent.click(within(rows()[0]).getByRole('button', { name: '删除' }));
    fireEvent.click(await screen.findByRole('button', { name: '确认删除' }));
    expect(await screen.findByText('删不掉')).toBeInTheDocument();
    expect(rows()).toHaveLength(2);
  });
});

describe('屏 19 · 不碰实体盘', () => {
  // 复盘看的是存下来的谱,和摄像头、灯没有任何关系。这条守的是「别顺手把硬件叫醒」——
  // 2G 内存的盒子上,视觉一起来服务就开始换页。
  it('整屏跑一遍,视觉和 LED 的接口一次都没调过', async () => {
    const vision = vi.spyOn(API, 'visionStatus');
    const ledPoint = vi.spyOn(LedAPI, 'point');
    const ledPoints = vi.spyOn(LedAPI, 'points');
    const ledClear = vi.spyOn(LedAPI, 'clear');
    mocks.hookResult = { ...mocks.hookResult, reportStatesByGame: { a: { completedNormal: task() } } };
    renderPage();
    await waitFor(() => expect(rows()).toHaveLength(2));
    await waitFor(() => expect(mocks.getMoves).toHaveBeenCalled());
    fireEvent.click(within(rows()[1]).getByRole('button', { name: /vs 柯洁/ }));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('token', 'b'));
    expect(vision).not.toHaveBeenCalled();
    expect(ledPoint).not.toHaveBeenCalled();
    expect(ledPoints).not.toHaveBeenCalled();
    expect(ledClear).not.toHaveBeenCalled();
  });
});
