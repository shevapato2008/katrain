import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReportTaskSummary } from '../../api/reportApi';
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
const setImmersive = vi.fn();
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
vi.mock('../context/ImmersiveContext', () => ({ useImmersive: () => ({ setImmersive }) }));
vi.mock('../../components/live/LiveBoard', () => ({
  default: (props: Record<string, unknown>) => {
    boardProps = props;
    return (
      <div data-testid="live-board" data-board-size={String(props.boardSize)} data-current-move={String(props.currentMove)}>
        <button onClick={() => (props.onTryMove as ((move: string) => void) | undefined)?.('D4')}>place try</button>
        <button onClick={() => (props.onIntersectionClick as (() => void) | undefined)?.()}>board tap</button>
      </div>
    );
  },
}));
vi.mock('../../components/live/AiAnalysis', () => ({
  default: (props: Record<string, unknown>) => (
    <div data-testid="ai-analysis">
      <button onClick={() => (props.onMoveSelect as (move: string | null) => void)('Q10')}>PV Q10</button>
    </div>
  ),
}));
vi.mock('../../components/live/TrendChart', () => ({
  default: (props: Record<string, unknown>) => (
    <button data-testid="trend-chart" onClick={() => (props.onMoveClick as (move: number) => void)(1)}>trend 1</button>
  ),
}));
vi.mock('../../components/live/PlaybackBar', () => ({
  default: (props: Record<string, unknown>) => (
    <button
      data-testid="playback"
      data-touch-sized={String(props.touchSized)}
      onClick={() => (props.onMoveChange as (move: number) => void)(2)}
    >playback 2</button>
  ),
}));

const task: ReportTaskSummary = {
  id: 42,
  user_game_id: 'game id/汉字',
  status: 'running',
  report_type: 'deep',
  total_moves: 3,
  analyzed_moves: 2,
  requested_visits: 1000,
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

function baseDetail() {
  return {
    task, game, moves: [], analysisByMove: { 2: analysis }, currentMove: 2,
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

describe('ReportDetailPage (kiosk)', () => {
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

  it('renders the immersive split report with progressive state and touch-safe actions', () => {
    renderPage();
    expect(setImmersive).toHaveBeenCalledWith(true);
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', '19');
    expect(screen.getByText('生成中')).toBeInTheDocument();
    expect(screen.getByText('深度复盘')).toBeInTheDocument();
    expect(screen.getByText('已分析 2 / 3 手')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '在研究中打开' })).toHaveStyle({ minHeight: '48px' });
    expect(screen.getByTestId('playback')).toHaveAttribute('data-touch-sized', 'true');
    expect(screen.getByTestId('report-detail-right')).toHaveStyle({ minWidth: '0' });
  });

  it('uses the game title in the ellipsized bar and falls back to the player matchup', () => {
    const rendered = renderPage();
    // 原来断言的是 `title=` 原生提示 —— 那是**悬停**才出得来的东西,而这是台触摸屏,
    // 手指没有悬停态。§11 换成页控条之后不再带它;标题被截断时该看见的是省略号,
    // 那是布局结论,归真浏览器闸(「长标题不许把返回键挤成两行」那条)。
    expect(screen.getByText(game.title!)).toBeInTheDocument();
    detail = { ...baseDetail(), game: { ...game, title: null } };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(screen.getByText('黑方 vs 白方')).toBeVisible();
  });

  it('keeps every critical touch action at least 48 by 48 pixels', () => {
    renderPage();
    for (const name of ['试下', '形势', '手数', 'AI', '在研究中打开']) {
      expect(screen.getByRole('button', { name })).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    }
    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    expect(screen.getByRole('button', { name: '清空' })).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    fireEvent.click(screen.getByText('PV Q10'));
    expect(screen.getByRole('button', { name: '清除变化' })).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
  });

  it('keeps playback fixed while analysis, chart, and recovery remain in the 1024x600 scroll region', () => {
    detail = { ...baseDetail(), error: '暂时断网' };
    const rendered = render(
      <div data-testid="viewport" style={{ width: 1024, height: 600 }}>
        <ThemeProvider theme={kioskTheme}>
          <MemoryRouter initialEntries={['/kiosk/report/42']}>
            <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
          </MemoryRouter>
        </ThemeProvider>
      </div>,
    );
    const viewport = screen.getByTestId('viewport');
    const scroll = screen.getByTestId('report-detail-analysis-scroll');
    const playback = screen.getByTestId('playback');
    const playbackShell = screen.getByTestId('report-detail-playback-fixed');
    expect(viewport).toHaveStyle({ width: '1024px', height: '600px' });
    expect(scroll).toHaveStyle({ minHeight: '0', overflowY: 'auto' });
    expect(scroll).toContainElement(screen.getByTestId('trend-chart'));
    expect(scroll).toContainElement(screen.getByText('暂时断网'));
    expect(scroll).not.toContainElement(playback);
    expect(playbackShell).toContainElement(playback);
    expect(screen.getByTestId('report-detail-right').lastElementChild).toBe(playbackShell);
    rendered.unmount();
  });

  it('maps only known report statuses and types and shows translated unknown fallbacks', () => {
    detail = {
      ...baseDetail(),
      task: { ...task, status: 'mystery', report_type: 'mystery' as unknown as ReportTaskSummary['report_type'] },
    };
    renderPage();
    expect(screen.getByTestId('report-detail-status')).toHaveTextContent('状态未知 · 类型未知');
    expect(screen.getAllByText('状态未知').length).toBeGreaterThan(0);
    expect(screen.getAllByText('类型未知').length).toBeGreaterThan(0);
    expect(screen.queryByText('失败')).not.toBeInTheDocument();
    expect(screen.queryByText('普通复盘')).not.toBeInTheDocument();
  });

  it.each([
    ['pending', '排队中'],
    ['completed', '已完成'],
  ] as const)('renders the %s lifecycle state while polling remains owned by the shared hook', (status, label) => {
    detail = { ...baseDetail(), task: { ...task, status } };
    renderPage();
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByTestId('live-board')).toBeVisible();
  });

  it('does not override a historical cursor when progressive analysis grows', () => {
    const rendered = renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '2');
    detail = {
      ...baseDetail(),
      task: { ...task, analyzed_moves: 3 },
      analysisByMove: { 1: analysis, 2: analysis, 3: analysis },
      currentMove: 1,
    };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '1');
    expect(setCurrentMove).not.toHaveBeenCalledWith(3);
  });

  it.each([9, 13, 19])('supports a square %i-line board', (size) => {
    detail = { ...baseDetail(), game: { ...game, board_size: size, sgf_content: `(;SZ[${size}];B[aa])` } };
    renderPage();
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', String(size));
    expect(screen.getByTestId('report-detail-board')).toHaveStyle({ aspectRatio: '1' });
  });

  it('keeps four persistent toggles and disables territory without ownership', () => {
    detail = { ...baseDetail(), analysisByMove: { 2: { ...analysis, ownership: null } } };
    renderPage();
    expect(screen.getByRole('button', { name: /试下/ })).toBeVisible();
    expect(screen.getByRole('button', { name: /形势/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /手数/ })).toBeVisible();
    expect(screen.getByRole('button', { name: /AI/ })).toBeVisible();
  });

  it('toggles AI markers, numbers and territory on the board', () => {
    renderPage();
    expect(boardProps.showAiMarkers).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /AI/ }));
    expect(boardProps.showAiMarkers).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /手数/ }));
    expect(boardProps.showMoveNumbers).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /形势/ }));
    expect(boardProps.showTerritory).toBe(true);
    expect(boardProps.ownership).toEqual([[0.2]]);
  });

  it('opens and clears a tapped PV, and navigation resets it', () => {
    renderPage();
    fireEvent.click(screen.getByText('PV Q10'));
    expect(boardProps.pvMoves).toEqual(['Q10', 'D10']);
    fireEvent.click(screen.getByText('board tap'));
    expect(boardProps.pvMoves).toBeNull();
    fireEvent.click(screen.getByText('PV Q10'));
    fireEvent.click(screen.getByTestId('trend-chart'));
    expect(setCurrentMove).toHaveBeenCalledWith(1);
    expect(boardProps.pvMoves).toBeNull();
  });

  it('clears PV when progressive refresh changes the cursor externally', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByText('PV Q10'));
    expect(boardProps.pvMoves).toEqual(['Q10', 'D10']);
    detail = { ...baseDetail(), currentMove: 1, analysisByMove: { 1: { ...analysis, move_number: 1 } } };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(boardProps.pvMoves).toBeNull();
  });

  it('clears the selected PV when same-cursor recommendations are replaced', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByText('PV Q10'));
    expect(boardProps.pvMoves).toEqual(['Q10', 'D10']);
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
    expect(screen.queryByRole('button', { name: '清除变化' })).not.toBeInTheDocument();
    detail = baseDetail();
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(boardProps.pvMoves).toBeNull();
    expect(screen.queryByRole('button', { name: '清除变化' })).not.toBeInTheDocument();
  });

  it('supports local try moves and clears them explicitly or on exit', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /试下/ }));
    fireEvent.click(screen.getByText('place try'));
    expect(screen.getByText(/D4/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(screen.queryByText(/D4/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('place try'));
    fireEvent.click(screen.getByRole('button', { name: /试下/ }));
    expect(boardProps.tryMoves).toBeUndefined();
  });

  it('resets try moves when the base cursor changes', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByRole('button', { name: /试下/ }));
    fireEvent.click(screen.getByText('place try'));
    expect(screen.getByText(/D4/)).toBeVisible();
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(screen.queryByText(/D4/)).not.toBeInTheDocument();
    expect(boardProps.tryMoves).toEqual([]);
    detail = baseDetail();
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(screen.queryByText(/D4/)).not.toBeInTheDocument();
    expect(boardProps.tryMoves).toEqual([]);
  });

  it('does not resurrect committed local interactions under StrictMode replay', () => {
    const view = (key: string) => (
      <StrictMode>
        <ThemeProvider theme={kioskTheme}><MemoryRouter key={key} initialEntries={['/kiosk/report/42']}>
          <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
        </MemoryRouter></ThemeProvider>
      </StrictMode>
    );
    const rendered = render(view('stable'));
    fireEvent.click(screen.getByText('PV Q10'));
    detail = {
      ...baseDetail(),
      analysisByMove: { 2: { ...analysis, top_moves: [{ ...analysis.top_moves![0], move: 'R6', pv: ['R6'] }] } },
    };
    rendered.rerender(view('stable'));
    detail = baseDetail();
    rendered.rerender(view('stable'));
    expect(screen.queryByRole('button', { name: '清除变化' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '试下' }));
    fireEvent.click(screen.getByText('place try'));
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(view('stable'));
    detail = baseDetail();
    rendered.rerender(view('stable'));
    expect(screen.queryByText(/D4/)).not.toBeInTheDocument();
  });

  it('wires trend and playback navigation and plays stone sound after a move changes', () => {
    const rendered = renderPage();
    fireEvent.click(screen.getByTestId('playback'));
    expect(setCurrentMove).toHaveBeenCalledWith(2);
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(playSound).toHaveBeenCalledWith('stone');
  });

  it('does not play a stone sound for the first loaded snapshot, only later movement', () => {
    detail = { ...baseDetail(), task: null, game: null, currentMove: 0, loading: true };
    const rendered = renderPage();
    detail = baseDetail();
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(playSound).not.toHaveBeenCalled();
    detail = { ...baseDetail(), currentMove: 1 };
    rendered.rerender(
      <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/report/42']}>
        <Routes><Route path="/kiosk/report/:taskId" element={<ReportDetailPage />} /></Routes>
      </MemoryRouter></ThemeProvider>,
    );
    expect(playSound).toHaveBeenCalledWith('stone');
  });

  it('opens Research using the encoded user_game_id', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '在研究中打开' }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/research?user_game_id=game+id%2F%E6%B1%89%E5%AD%97');
  });

  it('offers back recovery when unauthenticated without calling detail services', () => {
    auth = { token: null, isAuthenticated: false };
    renderPage();
    expect(screen.getByText('请登录后查看复盘详情。')).toBeInTheDocument();
    const back = screen.getByRole('button', { name: /返回/ });
    expect(back).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    fireEvent.click(back);
    expect(navigate).toHaveBeenCalledWith('/kiosk/report');
  });

  it('offers back and reload recovery when SGF is missing', async () => {
    detail = { ...baseDetail(), game: { ...game, sgf_content: '' } };
    renderPage();
    expect(screen.getByText('暂无棋谱数据，无法复盘。')).toBeInTheDocument();
    const reload = screen.getByRole('button', { name: '重新加载' });
    expect(reload).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    fireEvent.click(reload);
    expect(refresh).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /返回/ }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/report');
  });

  it('retries not-found or network errors using refresh', () => {
    detail = { ...baseDetail(), game: null, error: 'Request failed 404: Not found' };
    renderPage();
    expect(screen.getByText(/Not found/)).toBeInTheDocument();
    const refreshButton = screen.getByRole('button', { name: '重试加载' });
    expect(refreshButton).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    fireEvent.click(refreshButton);
    expect(refresh).toHaveBeenCalled();
  });

  it('keeps prior data visible on transient errors while offering refresh', () => {
    detail = { ...baseDetail(), error: '网络暂时不可用' };
    renderPage();
    expect(screen.getByTestId('live-board')).toBeVisible();
    expect(screen.getByText('网络暂时不可用')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    expect(refresh).toHaveBeenCalled();
  });

  it('retries a failed report then refreshes it', async () => {
    detail = { ...baseDetail(), task: { ...task, status: 'failed' } };
    renderPage();
    const retryButton = screen.getByRole('button', { name: '重试复盘' });
    expect(retryButton).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    fireEvent.click(retryButton);
    await waitFor(() => expect(retry).toHaveBeenCalledWith('token', 42));
    expect(refresh).toHaveBeenCalled();
  });

  it('keeps failed retry feedback and prior data visible', async () => {
    retry.mockRejectedValueOnce(new Error('重试服务不可用'));
    detail = { ...baseDetail(), task: { ...task, status: 'failed' } };
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '重试复盘' }));
    expect(await screen.findByText('重试服务不可用')).toBeInTheDocument();
    expect(screen.getByTestId('live-board')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重试加载' }));
    await waitFor(() => expect(screen.queryByText('重试服务不可用')).not.toBeInTheDocument());
  });

  it('resets PV, try moves, and retry feedback when route params reuse the page', async () => {
    retry.mockRejectedValueOnce(new Error('旧任务重试失败'));
    detail = { ...baseDetail(), task: { ...task, status: 'failed' } };
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
    fireEvent.click(screen.getByText('PV Q10'));
    fireEvent.click(screen.getByRole('button', { name: '重试复盘' }));
    expect(await screen.findByText('旧任务重试失败')).toBeVisible();

    detail = {
      ...baseDetail(),
      task: { ...task, id: 43, user_game_id: 'game-43' },
      game: { ...game, id: 'game-43', title: '新报告' },
    };
    fireEvent.click(screen.getByRole('link', { name: 'change report' }));
    expect(screen.queryByRole('button', { name: '清除变化' })).not.toBeInTheDocument();
    expect(screen.queryByText(/D4/)).not.toBeInTheDocument();
    expect(screen.queryByText('旧任务重试失败')).not.toBeInTheDocument();
  });

  it('waits out an old snapshot, retries, forces a fresh snapshot, and resumes polling', async () => {
    vi.useFakeTimers();
    realHook.enabled = true;
    const oldSnapshot = deferred<ReportTaskSummary>();
    getReport
      .mockResolvedValueOnce({ ...task, status: 'failed' })
      .mockImplementationOnce(() => oldSnapshot.promise)
      .mockResolvedValueOnce({ ...task, status: 'running' })
      .mockResolvedValueOnce({ ...task, status: 'completed', analyzed_moves: 3 });
    getMoves.mockResolvedValue([]);
    getGame.mockResolvedValue(game);

    renderPage();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    fireEvent.click(screen.getByRole('button', { name: '重试复盘' }));
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

  it('enters immersive mode on mount and restores the shell on cleanup', () => {
    const rendered = renderPage();
    expect(setImmersive).toHaveBeenCalledWith(true);
    rendered.unmount();
    expect(setImmersive).toHaveBeenLastCalledWith(false);
  });

  it('polls active reports every two seconds and stops after the terminal snapshot', async () => {
    vi.useFakeTimers();
    realHook.enabled = true;
    getReport
      .mockResolvedValueOnce({ ...task, status: 'running' })
      .mockResolvedValueOnce({ ...task, status: 'completed', analyzed_moves: 3 });
    getMoves.mockResolvedValue([]);
    getGame.mockResolvedValue(game);

    renderPage();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(getReport).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(getReport).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(getReport).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(getReport).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
