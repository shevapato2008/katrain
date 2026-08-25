import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskMove, ReportTaskSummary } from '../../api/reportApi';
import type { UserGameDetail } from '../../api/userGamesApi';
import type { MoveAnalysis } from '../../types/live';
import { kioskTheme } from '../theme';

const navigate = vi.fn();
const refresh = vi.fn().mockResolvedValue(undefined);
const retry = vi.fn().mockResolvedValue(undefined);
const getReport = vi.fn();
const getMoves = vi.fn();
const getGame = vi.fn();
const setCurrentMove = vi.fn();
const playSound = vi.fn();
let auth = { token: 'token', isAuthenticated: true };
let detail: ReturnType<typeof baseDetail>;
let boardProps: Record<string, unknown> = {};
const realHook = vi.hoisted(() => ({ enabled: false }));

vi.mock('react-router-dom', async (original) => ({
  ...(await original<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../features/report/useReportDetail', async (original) => {
  const actual = await original<typeof import('../../features/report/useReportDetail')>();
  return { useReportDetail: (...args: Parameters<typeof actual.useReportDetail>) => (
    realHook.enabled ? actual.useReportDetail(...args) : detail
  ) };
});
vi.mock('../../api/reportApi', async (original) => ({
  ...(await original<typeof import('../../api/reportApi')>()),
  ReportsAPI: {
    get: (...args: unknown[]) => getReport(...args),
    getMoves: (...args: unknown[]) => getMoves(...args),
    retry: (...args: unknown[]) => retry(...args),
  },
}));
vi.mock('../../api/userGamesApi', async (original) => ({
  ...(await original<typeof import('../../api/userGamesApi')>()),
  UserGamesAPI: { get: (...args: unknown[]) => getGame(...args) },
}));
vi.mock('../../hooks/useSound', () => ({ useSound: () => ({ play: playSound }) }));
// 盘是 canvas,jsdom 里画不出来 —— 换成一块能替它发出「点了哪一格」的桩。
// `Q10` 在 `ABCDEFGHJKLMNOPQRSTUVWXYZ`(跳 I)里 x=15、y=10−1=9;`A1` 是 (0,0)。
vi.mock('../../components/live/LiveBoard', () => ({
  default: (props: Record<string, unknown>) => {
    boardProps = props;
    const click = props.onIntersectionClick as ((x: number, y: number) => void) | undefined;
    return (
      <div data-testid="live-board" data-board-size={String(props.boardSize)} data-current-move={String(props.currentMove)}>
        <button onClick={() => (props.onTryMove as ((move: string) => void) | undefined)?.('D4')}>place try</button>
        <button onClick={() => click?.(15, 9)}>tap Q10</button>
        <button onClick={() => click?.(0, 0)}>tap A1</button>
      </div>
    );
  },
}));

const task: ReportTaskSummary = {
  id: 42,
  user_game_id: 'game id/汉字',
  status: 'running',
  report_type: 'deep',
  total_moves: 3,
  analyzed_moves: 2,
  requested_visits: 1000,
  started_at: null,
  completed_at: null,
};

const game: UserGameDetail = {
  id: 'game id/汉字', user_id: 1, title: '一场特别特别长的棋局标题',
  player_black: '黑方', player_white: '白方', black_rank: '9D', white_rank: '9D', result: null,
  board_size: 19, rules: 'chinese', komi: 7.5, move_count: 3, source: 'import', category: 'all',
  game_type: null, event: '测试赛事', round_name: '第一轮', game_date: null, created_at: null, updated_at: null,
  sgf_content: '(;GM[1]FF[4]SZ[19];B[pd];W[dd];B[qp])',
};

const analysis: MoveAnalysis = {
  id: 1, match_id: 'game id/汉字', move_number: 2, winrate: 0.62, score_lead: 3.2,
  visits: 1000, top_moves: [{ move: 'Q10', visits: 800, winrate: 0.64, score_lead: 4.1, prior: 0.5, pv: ['Q10', 'D10'], psv: 1 }],
  ownership: [[0.2]], move: 'D4', actual_player: 'B', delta_score: 0, delta_winrate: 0,
  is_brilliant: false, is_mistake: false, is_questionable: false,
};

/**
 * 逐手数据。**曲线和「重点手」都从它来** —— 传空数组的话曲线是空态、重点手是空态,
 * 那两块的断言就全成了空的。
 * 第 2 手黑掉 5 目(过失误线 −3),胜率 62% → 30%;第 1 行存着候选 Q10 ⇒「该走 Q10」。
 */
const reportMoves: ReportTaskMove[] = [
  {
    id: 0, task_id: 42, move_number: 0, status: 'success', winrate: 0.5, score_lead: 0,
    visits: 500, top_moves: null, ownership: null, actual_move: null, actual_player: null,
    delta_score: null, delta_winrate: null,
  },
  {
    id: 1, task_id: 42, move_number: 1, status: 'success', winrate: 0.62, score_lead: 3.2,
    visits: 500,
    top_moves: [{ move: 'Q10', visits: 800, winrate: 0.64, score_lead: 4.1, prior: 0.5, pv: ['Q10'], psv: 1 }],
    ownership: null, actual_move: 'D4', actual_player: 'W', delta_score: -0.2, delta_winrate: 0,
  },
  {
    id: 2, task_id: 42, move_number: 2, status: 'success', winrate: 0.30, score_lead: -1.8,
    visits: 500, top_moves: null, ownership: null, actual_move: 'C3', actual_player: 'B',
    delta_score: -5, delta_winrate: -0.32,
  },
];

function baseDetail() {
  return {
    task, game, moves: reportMoves, analysisByMove: { 2: analysis }, currentMove: 2,
    setCurrentMove, loading: false, error: null as string | null, refresh,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function renderPage(taskId = '42') {
  return render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/report/${taskId}`]}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

import ReportDetailPage from './ReportDetailPage';


/**
 * 屏 20 复盘 · 报告 `/kiosk/report/:taskId`(L2 布局 A)。
 *
 * ⚠️ **这里一条几何都不断言。** 上一版有三处在 jsdom 里断言 `minWidth:48px` /
 * `aspectRatio:1` / `overflowY:auto` —— 那些数今天由 CSS 类给,jsdom 看不见类;
 * 而按钮的触摸靶、盘的方形、右栏 460 的纵向账,判据全在
 * `tests/kiosk-shell-geometry.spec.ts`(真浏览器量 1024×600)。
 *
 * 这份文件守的是「屏上说的是不是真的、点了之后发生了什么」。
 */
describe('屏 20 · 题头与状态', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    detail = baseDetail();
    boardProps = {};
    realHook.enabled = false;
    retry.mockReset().mockResolvedValue(undefined);
    getReport.mockReset();
    getMoves.mockReset();
    getGame.mockReset();
  });

  afterEach(() => vi.useRealTimers());

  // 顶栏在不在**不再是这一屏能决定的事**:2026-08-26 删掉了 `ImmersiveContext`,
  // `KioskLayout` 无条件渲染顶栏,判据搬到 `KioskLayout.test.tsx` 和真浏览器几何闸。
  // 这一条只留下它自己的部分 —— 盘按谱的路数画、题头念的是这一局是什么。
  it('盘按谱的路数画,题头念的是这一局是什么', () => {
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', '19');
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent('生成中 · 深度复盘');
    // 页控条的标题走的是复盘列表那套说法(同一局在两屏之间不许改口)
    expect(screen.getByTestId('report-detail-pagebar').textContent).toContain('导入的棋谱');
  });

  it('还在跑的时候写进度 —— 那会儿「一共多少手」说的是将来', () => {
    renderPage();
    expect(screen.getByTestId('report-detail-progress')).toHaveTextContent('已分析 2 / 3 手');
    // 排队/生成中不可能有耗时:completed_at 要到跑完才写。
    expect(screen.queryByText(/秒/)).toBeNull();
  });

  // 稿子这行写「每手算 2000 次 · 用了 6 分 12 秒」。耗时 2026-08-23 才接上
  // (`ReportTaskStatus` 补了 started_at / completed_at),**接不到时不许编**。
  it('跑完了照稿子写耗时', () => {
    detail = {
      ...baseDetail(),
      task: {
        ...task,
        status: 'completed',
        analyzed_moves: 3,
        started_at: '2026-08-23T01:00:00+08:00',
        completed_at: '2026-08-23T01:06:12+08:00',
      },
    };
    renderPage();
    expect(screen.getByTestId('report-detail-progress')).toHaveTextContent('每手算 1000 次 · 用了 6分12秒');
  });

  // 这三条守的是同一件事:**耗时说不出来时,退回那句本来就真的话,不写「用了 0 秒」。**
  // 没有它,①云端还没补字段的盒子、②失败的任务、③两个章的时钟对不上的行,
  // 屏上都会出现一个编出来的耗时。
  it.each([
    ['云端还没补字段 —— 两个章都是 null', { status: 'completed', started_at: null, completed_at: null }],
    ['失败的任务 —— completed_at 被回队列的那条路清掉了', { status: 'failed', started_at: '2026-08-23T01:00:00+08:00', completed_at: null }],
    ['时钟对不上 —— 完成早于开始', { status: 'completed', started_at: '2026-08-23T01:06:12+08:00', completed_at: '2026-08-23T01:00:00+08:00' }],
  ] as const)('耗时拿不到就退回「一共多少手」:%s', (_name, patch) => {
    detail = {
      ...baseDetail(),
      task: { ...task, analyzed_moves: 3, ...patch } as ReportTaskSummary,
    };
    renderPage();
    expect(screen.getByTestId('report-detail-progress')).toHaveTextContent('每手算 1000 次 · 3 手');
    expect(screen.getByTestId('report-detail-progress').textContent).not.toContain('用了');
  });

  it('状态和档位只认识那几个,别的照实说「未知」', () => {
    detail = {
      ...baseDetail(),
      task: { ...task, status: 'mystery', report_type: 'mystery' as unknown as ReportTaskSummary['report_type'] },
    };
    renderPage();
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent('状态未知 · 类型未知');
    expect(screen.queryByText(/失败/)).toBeNull();
  });

  it.each([
    ['pending', '排队中'],
    ['completed', '已完成'],
  ] as const)('%s 也照样把盘画出来 —— 轮询归共享钩子管', (status, label) => {
    detail = { ...baseDetail(), task: { ...task, status } };
    renderPage();
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent(label);
    expect(screen.getByTestId('live-board')).toBeVisible();
  });

  it.each([9, 13, 19])('%i 路盘照样接得住', (size) => {
    detail = { ...baseDetail(), game: { ...game, board_size: size, sgf_content: `(;SZ[${size}];B[aa])` } };
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', String(size));
  });

  // 盘那一圈坐标交给外壳画,盘自己那圈必须关掉 —— 两边都画就是两套坐标。
  // ⚠️ 关掉之后 `calculateBoardLayout` 的边距要跟着从 1.5 收回 0.5,
  // 那条对不对只有真浏览器量得出来(几何闸里那条「头尾两条线正对刻度带头尾两个字」)。
  it('盘自己那圈坐标是关掉的,四条刻度带由外壳画', () => {
    renderPage();
    expect(boardProps.showCoordinates).toBe(false);
    expect(document.querySelectorAll('.kiosk-board__ruler')).toHaveLength(4);
    expect(document.querySelectorAll('.kiosk-board__ruler--top span')).toHaveLength(19);
  });

});

describe('屏 20 · 胜率曲线与重点手', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    detail = baseDetail();
    boardProps = {};
    realHook.enabled = false;
  });

  it('曲线按逐手数据画,折叠块右端写的是掉得最狠那一手', () => {
    renderPage();
    expect(screen.getByTestId('review-winrate-plot')).toHaveAttribute('data-state', 'plotted');
    expect(screen.getByTestId('report-detail-curve').textContent).toContain('第 2 手掉 32 点');
  });

  // 稿子把滑块拿掉了,而 187 手的谱靠四个翻手键挪不到第 120 手 ——
  // 原来 `TrendChart` 的「点哪儿跳哪一手」落到曲线上,不能跟着控件一起丢。
  it('点曲线跳到那一手,并且画一条竖游标标出现在在哪', () => {
    renderPage();
    expect(screen.getByTestId('review-winrate-cursor')).toBeInTheDocument();
    const plot = screen.getByTestId('review-winrate-plot');
    plot.getBoundingClientRect = () => ({ left: 0, width: 100, top: 0, height: 96, right: 100, bottom: 96, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.click(plot, { clientX: 0 });
    expect(setCurrentMove).toHaveBeenCalledWith(0);
  });

  it('重点手列的是掉得最多的,「该走 X」取的是**上一行**的首选', () => {
    renderPage();
    const rows = screen.getAllByTestId('report-detail-key-row');
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain('2 手');
    expect(rows[0].textContent).toContain('该走 Q10');
    expect(rows[0].textContent).toContain('黑 62% → 30%');
    expect(rows[0].textContent).toContain('掉 32 点');
  });

  it('点「看这手」跳到那一手', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '看这手' }));
    expect(setCurrentMove).toHaveBeenCalledWith(2);
  });

  it('一手都没掉过的局照实说,不摆一张空表', () => {
    detail = { ...baseDetail(), moves: reportMoves.map((m) => ({ ...m, delta_score: 0 })) };
    renderPage();
    expect(screen.queryAllByTestId('report-detail-key-row')).toHaveLength(0);
    expect(screen.getByText('没有掉得明显的手')).toBeInTheDocument();
    expect(screen.getByTestId('report-detail-curve').textContent).toContain('没有明显失误');
  });

  it('一手都没算出来时曲线不画线,写明为什么空', () => {
    detail = { ...baseDetail(), moves: [] };
    renderPage();
    const plot = screen.getByTestId('review-winrate-plot');
    expect(plot).toHaveAttribute('data-state', 'empty');
    expect(plot.querySelector('polyline')).toBeNull();
  });
});

describe('屏 20 · 盘上的交互', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    detail = baseDetail();
    boardProps = {};
    realHook.enabled = false;
  });

  it('四个开关都在,没有形势数据时「形势」按不了', () => {
    detail = { ...baseDetail(), analysisByMove: { 2: { ...analysis, ownership: null } } };
    renderPage();
    for (const name of ['形势', '手数', 'AI 推荐', '试下']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: '形势' })).toBeDisabled();
  });

  it('三个显示开关真的传到盘上', () => {
    renderPage();
    expect(boardProps.showMoveNumbers).toBe(true);
    expect(boardProps.showTerritory).toBe(true);
    expect(boardProps.ownership).toEqual([[0.2]]);
    expect(boardProps.showAiMarkers).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    expect(boardProps.showAiMarkers).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '手数' }));
    expect(boardProps.showMoveNumbers).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '形势' }));
    expect(boardProps.showTerritory).toBe(false);
    expect(boardProps.ownership).toBeNull();
  });

  // 稿子这一屏**没有候选着法表**(那张表在研究屏)。可「点一条推荐看它的后续」
  // 不能跟着表一起没 —— 打开「AI 推荐」之后点盘上那个标记就是选它。
  it('点盘上的 AI 标记打开它的后续,点别处收起', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    fireEvent.click(screen.getByText('tap Q10'));
    expect(boardProps.pvMoves).toEqual(['Q10', 'D10']);
    fireEvent.click(screen.getByText('tap A1'));
    expect(boardProps.pvMoves).toBeNull();
  });

  it('没打开「AI 推荐」时点盘不会凭空冒出一条变化', () => {
    renderPage();
    fireEvent.click(screen.getByText('tap Q10'));
    expect(boardProps.pvMoves).toBeNull();
  });

  it('翻手之后变化收起', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    fireEvent.click(screen.getByText('tap Q10'));
    fireEvent.click(screen.getByRole('button', { name: '上一手' }));
    expect(setCurrentMove).toHaveBeenCalledWith(1);
    expect(boardProps.pvMoves).toBeNull();
  });

  it('外部把游标挪走时变化收起', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    fireEvent.click(screen.getByText('tap Q10'));
    expect(boardProps.pvMoves).toEqual(['Q10', 'D10']);
    detail = { ...baseDetail(), currentMove: 1, analysisByMove: { 1: { ...analysis, move_number: 1 } } };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(boardProps.pvMoves).toBeNull();
  });

  it('同一手的推荐被换掉时,选中的那条变化收起', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    fireEvent.click(screen.getByText('tap Q10'));
    detail = {
      ...baseDetail(),
      analysisByMove: { 2: { ...analysis, top_moves: [{ ...analysis.top_moves![0], move: 'R6', pv: ['R6'] }] } },
    };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(boardProps.pvMoves).toBeNull();
    expect(screen.queryByTestId('report-detail-variation')).toBeNull();
    detail = baseDetail();
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(boardProps.pvMoves).toBeNull();
  });

  it('试下能落子、能清空,退出试下时一并清掉', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    expect(screen.getByTestId('report-detail-try').textContent).toContain('D4');
    fireEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(screen.queryByTestId('report-detail-try')).toBeNull();
    fireEvent.click(screen.getByText('place try'));
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    expect(boardProps.tryMoves).toBeUndefined();
  });

  it('基准手一变,试下的子就不再属于这一手了', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    expect(screen.getByTestId('report-detail-try')).toBeVisible();
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(screen.queryByTestId('report-detail-try')).toBeNull();
    expect(boardProps.tryMoves).toEqual([]);
  });

  it('StrictMode 重放不会把已经丢掉的本地交互复活', () => {
    const view = (key: string) => (
      <StrictMode>
        <ThemeProvider theme={kioskTheme}><MemoryRouter key={key} initialEntries={['/kiosk/report/42']}>
          <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
        </MemoryRouter></ThemeProvider>
      </StrictMode>
    );
    const rendered = render(view('stable'));
    fireEvent.click(screen.getByRole('button', { name: 'AI 推荐' }));
    fireEvent.click(screen.getByText('tap Q10'));
    detail = {
      ...baseDetail(),
      analysisByMove: { 2: { ...analysis, top_moves: [{ ...analysis.top_moves![0], move: 'R6', pv: ['R6'] }] } },
    };
    rendered.rerender(view('stable'));
    detail = baseDetail();
    rendered.rerender(view('stable'));
    expect(screen.queryByTestId('report-detail-variation')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(view('stable'));
    detail = baseDetail();
    rendered.rerender(view('stable'));
    expect(screen.queryByTestId('report-detail-try')).toBeNull();
  });
});

describe('屏 20 · 翻手、出口与出错', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    detail = baseDetail();
    boardProps = {};
    realHook.enabled = false;
    retry.mockReset().mockResolvedValue(undefined);
  });

  afterEach(() => vi.useRealTimers());

  it('四个翻手键各跳各的,开局和末手各自灰掉一半', () => {
    detail = { ...baseDetail(), currentMove: 0 };
    renderPage();
    expect(screen.getByRole('button', { name: '回到开局' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '上一手' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '跳到最后' }));
    expect(setCurrentMove).toHaveBeenCalledWith(3);
  });

  it('翻过手之后落一声子响,第一次加载那一帧不响', () => {
    detail = { ...baseDetail(), task: null, game: null, currentMove: 0, loading: true };
    const rendered = renderPage();
    detail = baseDetail();
    const again = () => rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    again();
    expect(playSound).not.toHaveBeenCalled();
    detail = { ...baseDetail(), currentMove: 1 };
    again();
    expect(playSound).toHaveBeenCalledWith('stone');
  });

  /**
   * `&from=report&task=42` 是 2026-08-24 屏 21 加的:研究屏有四个入口、回去的地方各不
   * 相同,而这一条和对局历史那一条的 URL 形状**一模一样**(都是 `?user_game_id=`)、
   * 反推不出来。`task` 让返回键回得到**这一份报告**,而不是报告列表。
   */
  it('「去研究」带着这一局的编号和出处过去,编号照原样编码', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '去研究' }));
    expect(navigate).toHaveBeenCalledWith(
      '/kiosk/research?user_game_id=game+id%2F%E6%B1%89%E5%AD%97&from=report&task=42',
    );
  });

  // 稿子把「重算」和「去研究」并排画在题头,不是只在失败时才出现 ——
  // 它的用处正是「跑完了但想换个深度再跑一遍」。
  it('「重算」常驻,点了先刷新再重跑', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '重算' }));
    await waitFor(() => expect(retry).toHaveBeenCalledWith('token', 42));
    expect(refresh).toHaveBeenCalled();
  });

  it('重算失败时话说出来,盘和数据还在;重试加载能把那条错清掉', async () => {
    retry.mockRejectedValueOnce(new Error('重试服务不可用'));
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '重算' }));
    expect(await screen.findByText(/重试服务不可用/)).toBeInTheDocument();
    expect(screen.getByTestId('live-board')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    await waitFor(() => expect(screen.queryByText(/重试服务不可用/)).toBeNull());
  });

  it('没登录时只给一条路:回复盘列表', () => {
    auth = { token: null, isAuthenticated: false };
    renderPage();
    expect(screen.getByText('请登录后查看复盘详情。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /复盘/ }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/report');
  });

  it('谱缺了的时候说清楚,并给一条重新加载', () => {
    detail = { ...baseDetail(), game: { ...game, sgf_content: '' } };
    renderPage();
    expect(screen.getByText('暂无棋谱数据，无法复盘。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }));
    expect(refresh).toHaveBeenCalled();
  });

  it('整局读不到时报错并给重试', () => {
    detail = { ...baseDetail(), game: null, error: 'Request failed 404: Not found' };
    renderPage();
    expect(screen.getByText(/Not found/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    expect(refresh).toHaveBeenCalled();
  });

  it('一时的错不许把已经在屏上的东西清掉', () => {
    detail = { ...baseDetail(), error: '网络暂时不可用' };
    renderPage();
    expect(screen.getByTestId('live-board')).toBeVisible();
    expect(screen.getByText(/网络暂时不可用/)).toBeInTheDocument();
  });

  it('换一份报告时,上一份的变化、试下和错都不许跟过来', async () => {
    retry.mockRejectedValueOnce(new Error('旧任务重试失败'));
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/report/42']}>
          <Link to="/kiosk/report/43">change report</Link>
          <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    fireEvent.click(screen.getByRole('button', { name: '重算' }));
    expect(await screen.findByText(/旧任务重试失败/)).toBeVisible();

    detail = {
      ...baseDetail(),
      task: { ...task, id: 43, user_game_id: 'game-43' },
      game: { ...game, id: 'game-43', title: '新报告' },
    };
    fireEvent.click(screen.getByRole('link', { name: 'change report' }));
    expect(screen.queryByTestId('report-detail-variation')).toBeNull();
    expect(screen.queryByTestId('report-detail-try')).toBeNull();
    expect(screen.queryByText(/旧任务重试失败/)).toBeNull();
  });
});

describe('屏 20 · 接真钩子的轮询', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    detail = baseDetail();
    realHook.enabled = true;
    retry.mockReset().mockResolvedValue(undefined);
    getReport.mockReset();
    getMoves.mockReset().mockResolvedValue([]);
    getGame.mockReset().mockResolvedValue(game);
  });

  afterEach(() => vi.useRealTimers());

  it('先等过期那张快照,再重跑,拿到新快照后接着轮询', async () => {
    vi.useFakeTimers();
    const oldSnapshot = deferred<ReportTaskSummary>();
    getReport
      .mockResolvedValueOnce({ ...task, status: 'failed' })
      .mockImplementationOnce(() => oldSnapshot.promise)
      .mockResolvedValueOnce({ ...task, status: 'running' })
      .mockResolvedValueOnce({ ...task, status: 'completed', analyzed_moves: 3 });

    renderPage();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: '重算' }));
    expect(getReport).toHaveBeenCalledTimes(2);
    expect(retry).not.toHaveBeenCalled();

    await act(async () => {
      oldSnapshot.resolve({ ...task, status: 'failed' });
      await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    });
    expect(retry).toHaveBeenCalledWith('token', 42);
    expect(getReport).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent('生成中');

    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(getReport).toHaveBeenCalledTimes(4);
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent('已完成');
  });

  it('两秒一轮,拿到终态就停', async () => {
    vi.useFakeTimers();
    getReport
      .mockResolvedValueOnce({ ...task, status: 'running' })
      .mockResolvedValueOnce({ ...task, status: 'completed', analyzed_moves: 3 });

    renderPage();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(getReport).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(getReport).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(getReport).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(getReport).toHaveBeenCalledTimes(2);
  });
});

/**
 * 让子局的两套下标。**盘上的 `moves` 里前几个是摆上去的让子石,而报告的 `move_number`
 * 只数真正的着手**(后端 `katrain/cron/sgf.py` 把摆子单独走 `initialStones`)。
 * 不把这个偏移加回去,让子局滑到第 k 手时盘面是对的、右边的分析却是第 k+让子数 手的 ——
 * 而**屏上没有任何东西会说它错位了**:胜率有、曲线有、推荐也有,只是都不属于这一手。
 */
describe('屏 20 · 让子局的下标要对得上', () => {
  const handicapGame = {
    ...game,
    move_count: 2,
    sgf_content: '(;GM[1]FF[4]SZ[19]HA[2]AB[dd][pp];W[qq];B[cc])',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    auth = { token: 'token', isAuthenticated: true };
    boardProps = {};
    realHook.enabled = false;
  });

  it('第 0 手:盘上是两颗让子石,不是空盘', () => {
    detail = { ...baseDetail(), game: handicapGame, currentMove: 0, analysisByMove: {} };
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '2');
    expect(boardProps.moves).toEqual(['D16', 'Q4', 'R3', 'C17']);
  });

  it('第 1 手:盘上是让子石加白第一手', () => {
    detail = { ...baseDetail(), game: handicapGame, currentMove: 1, analysisByMove: {} };
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '3');
  });

  it('走到最后一手就走不动了 —— 上限数的是着手,不数让子石', () => {
    // 上限要是把两颗让子石也算进去,「下一手 / 跳到最后」在真正的末手之后还是亮的,
    // 点下去停在两个根本不存在的手数上,那两格永远不会有分析。
    detail = {
      ...baseDetail(),
      game: handicapGame,
      currentMove: 2,
      analysisByMove: {},
      task: { ...task, status: 'completed', total_moves: 2, analyzed_moves: 2 },
    };
    renderPage();
    const nav = screen.getByTestId('report-detail-movenav');
    for (const label of ['下一手', '跳到最后']) {
      expect(within(nav).getByLabelText(label)).toBeDisabled();
    }
  });

  it('还没到末手时该亮着 —— 一律禁掉也叫「过」', () => {
    detail = {
      ...baseDetail(), game: handicapGame, currentMove: 1, analysisByMove: {},
      task: { ...task, status: 'completed', total_moves: 2, analyzed_moves: 2 },
    };
    renderPage();
    const nav = screen.getByTestId('report-detail-movenav');
    expect(within(nav).getByLabelText('下一手')).toBeEnabled();
  });

  it('分先局没有偏移 —— 加错方向比不加还坏', () => {
    detail = { ...baseDetail(), currentMove: 2 };
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '2');
  });
});
