import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { UserGameDetail, UserGameSummary } from '../../api/userGamesApi';
import { LedAPI } from '../../api/ledApi';
import { API } from '../../api';
import { kioskTheme } from '../theme';
import ReportsPage from './ReportsPage';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  deleteGame: vi.fn(),
  getAlbum: vi.fn(),
  getAlbums: vi.fn(),
  navigate: vi.fn(),
  createReport: vi.fn(),
  retryReport: vi.fn(),
  refreshTasks: vi.fn(),
  clearError: vi.fn(),
  hookResult: {} as Record<string, unknown>,
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true }),
}));
vi.mock('../../api/userGamesApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/userGamesApi')>();
  return { ...actual, UserGamesAPI: { ...actual.UserGamesAPI, list: mocks.list, get: mocks.get, create: mocks.create, delete: mocks.deleteGame } };
});
vi.mock('../../api/kifuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/kifuApi')>();
  return { ...actual, KifuAPI: { ...actual.KifuAPI, getAlbum: mocks.getAlbum, getAlbums: mocks.getAlbums } };
});
vi.mock('../../features/report/useReportTasks', () => ({
  useReportTasks: () => mocks.hookResult,
}));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mocks.navigate };
});
vi.mock('../../components/live/LiveBoard', () => ({
  default: (props: { boardSize: number; currentMove: number; moves: string[] }) => (
    <div data-testid="live-board" data-board-size={props.boardSize} data-current-move={props.currentMove} data-total={props.moves.length} />
  ),
}));

const game = (id: string, boardSize = 19, moveCount = 3): UserGameSummary => ({
  id, user_id: 1, title: `棋局 ${id}`, player_black: `黑${id}`, player_white: `白${id}`,
  black_rank: null, white_rank: null, result: 'B+R', board_size: boardSize, rules: 'chinese',
  komi: 7.5, move_count: moveCount, source: 'import', category: 'game', game_type: null,
  event: `赛事 ${id}`, round_name: null, game_date: '2026-07-15', created_at: '2026-07-15', updated_at: null,
});
const detail = (summary: UserGameSummary, sgf?: string): UserGameDetail => ({
  ...summary,
  sgf_content: sgf ?? `(;FF[4]GM[1]SZ[${summary.board_size}];B[aa];W[bb];B[cc])`,
});
const response = (items: UserGameSummary[], page = 1, total = items.length) => ({ items, total, page, page_size: 12 });
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

async function openActionsFor(id: string) {
  const card = await screen.findByRole('button', { name: new RegExp(`选择棋局.*赛事 ${id}`) });
  const container = card.closest('[data-testid="report-game-card"]')!;
  fireEvent.click(container.querySelector('button[aria-haspopup="menu"]')!);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue(response([game('a'), game('b')]));
  mocks.get.mockImplementation(async (_token: string, id: string) => detail(game(id)));
  mocks.create.mockResolvedValue(detail(game('new')));
  mocks.deleteGame.mockResolvedValue({ status: 'deleted' });
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
    tasks: [], queueSummary: { pending: 2, running: 1, completed: 5, failed: 1 },
    reportStatesByGame: {}, loading: false, error: null, clearError: mocks.clearError,
    refresh: mocks.refreshTasks, createReport: mocks.createReport, retryReport: mocks.retryReport,
  };
});

describe('kiosk ReportsPage list and preview', () => {
  it('loads URL search/page, selects the first game, and initializes its preview at the final move', async () => {
    renderPage('/kiosk/report?q=%E6%9F%AF%E6%B4%81&page=2');
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith('token', {
      page: 2, page_size: 12, q: '柯洁', sort: 'created_at_desc',
    }));
    expect(await screen.findByTestId('live-board')).toHaveAttribute('data-current-move', '3');
    expect(screen.getByDisplayValue('柯洁')).toBeInTheDocument();
    expect(screen.getByText('2 排队中')).toBeInTheDocument();
    expect(screen.getByText('1 生成中')).toBeInTheDocument();
    expect(screen.getByText('1 失败')).toBeInTheDocument();
  });

  it('preserves selection after a mutation refresh when present and switches preview when another card is tapped', async () => {
    renderPage();
    await screen.findByTestId('live-board');
    fireEvent.click(screen.getByRole('button', { name: /选择棋局.*赛事 b/ }));
    await waitFor(() => expect(mocks.get).toHaveBeenLastCalledWith('token', 'b'));
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 b/ }).closest('[data-testid="report-game-card"]')).toHaveAttribute('data-selected', 'true');
    await openActionsFor('a');
    fireEvent.click(screen.getByRole('menuitem', { name: '删除棋谱' }));
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '确认删除棋谱' })).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 b/ }).closest('[data-testid="report-game-card"]')).toHaveAttribute('data-selected', 'true');
  });

  it('keeps search in the URL while paging and resets selection to the new page first item', async () => {
    mocks.list
      .mockResolvedValueOnce(response([game('a'), game('b')], 1, 25))
      .mockResolvedValueOnce(response([game('c')], 2, 25));
    renderPage('/kiosk/report?q=%E6%A3%8B');
    await screen.findByRole('button', { name: /选择棋局.*赛事 a/ });
    fireEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('q=%E6%A3%8B&page=2'));
    expect(await screen.findByRole('button', { name: /选择棋局.*赛事 c/ })).toBeInTheDocument();
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('token', 'c'));
  });

  it('writes trimmed search to the URL, resets page and reconciles selection to the new first item', async () => {
    mocks.list.mockResolvedValueOnce(response([game('a')], 3, 30)).mockResolvedValueOnce(response([game('c')], 1, 1));
    renderPage('/kiosk/report?page=3');
    const search = await screen.findByPlaceholderText('搜索棋手、标题或赛事');
    fireEvent.change(search, { target: { value: '  新棋手  ' } });
    fireEvent.keyDown(search, { key: 'Enter' });
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/report?q=%E6%96%B0%E6%A3%8B%E6%89%8B'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('token', 'c'));
  });

  it('propagates 9×9, 13×13 and 19×19 SGFs and exposes all PlaybackBar controls', async () => {
    const games = [game('9', 9), game('13', 13), game('19', 19)];
    mocks.list.mockResolvedValue(response(games));
    mocks.get.mockImplementation(async (_token: string, id: string) => detail(games.find((item) => item.id === id)!));
    renderPage();
    expect(await screen.findByTestId('live-board')).toHaveAttribute('data-board-size', '9');
    ['live:first_move', 'live:previous', '播放', 'live:next', 'live:latest'].forEach((name) => {
      expect(screen.getByRole('button', { name })).toHaveStyle({ minWidth: '48px', minHeight: '48px' });
    });
    fireEvent.click(screen.getByRole('button', { name: /选择棋局.*赛事 13/ }));
    await waitFor(() => expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', '13'));
    fireEvent.click(screen.getByRole('button', { name: /选择棋局.*赛事 19/ }));
    await waitFor(() => expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', '19'));

    fireEvent.click(screen.getByRole('button', { name: 'live:first_move' }));
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '0');
    fireEvent.click(screen.getByRole('button', { name: 'live:next' }));
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '1');
    fireEvent.click(screen.getByRole('button', { name: 'live:latest' }));
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '3');
    fireEvent.click(screen.getByRole('button', { name: 'live:previous' }));
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '2');
    fireEvent.change(screen.getByRole('slider'), { target: { value: 1 } });
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '1');
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: '播放' }));
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId('live-board')).toHaveAttribute('data-current-move', '2');
    vi.useRealTimers();
  });

  it.each([
    ['', '棋谱缺少 SGF 内容'],
    ['not sgf', '无法解析棋谱'],
  ])('shows bounded preview recovery for invalid SGF %j', async (sgf, message) => {
    mocks.get.mockResolvedValue({ ...detail(game('a')), sgf_content: sgf });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('shows game-detail failure and retries the selected preview', async () => {
    mocks.get.mockRejectedValueOnce(new Error('detail down')).mockResolvedValueOnce(detail(game('a')));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('detail down');
    fireEvent.click(screen.getByRole('button', { name: '重试预览' }));
    expect(await screen.findByTestId('live-board')).toBeInTheDocument();
  });

  it('shows list and report polling failures without blanking the cards', async () => {
    mocks.hookResult = { ...mocks.hookResult, error: 'poll down' };
    renderPage();
    expect(await screen.findByText('poll down')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 a/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试任务' }));
    expect(mocks.refreshTasks).toHaveBeenCalled();
  });

  it('shows a list failure with a repeatable retry action', async () => {
    mocks.list.mockRejectedValueOnce(new Error('list offline')).mockResolvedValueOnce(response([game('a')]));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('list offline');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('button', { name: /选择棋局.*赛事 a/ })).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledTimes(2);
  });

  it('ignores an old list success that arrives after the latest search result', async () => {
    const oldRequest = deferred<ReturnType<typeof response>>();
    mocks.list.mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce(response([game('newest')]));
    renderPage('/kiosk/report?q=old');
    const search = screen.getByPlaceholderText('搜索棋手、标题或赛事');
    fireEvent.change(search, { target: { value: 'new' } });
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(await screen.findByRole('button', { name: /选择棋局.*赛事 newest/ })).toBeInTheDocument();

    await act(async () => oldRequest.resolve(response([game('stale')])));
    expect(screen.queryByRole('button', { name: /选择棋局.*赛事 stale/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 newest/ })).toBeInTheDocument();
  });

  it('ignores an old list rejection without clearing the latest result or exposing stale error', async () => {
    const oldRequest = deferred<ReturnType<typeof response>>();
    mocks.list.mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce(response([game('newest')]));
    renderPage('/kiosk/report?q=old');
    const search = screen.getByPlaceholderText('搜索棋手、标题或赛事');
    fireEvent.change(search, { target: { value: 'new' } });
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(await screen.findByRole('button', { name: /选择棋局.*赛事 newest/ })).toBeInTheDocument();

    await act(async () => oldRequest.reject(new Error('stale list failure')));
    expect(screen.queryByText('stale list failure')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 newest/ })).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('never invokes vision or LED APIs while previewing and playing a report game', async () => {
    const visionSpy = vi.spyOn(API, 'visionStatus');
    const ledPointSpy = vi.spyOn(LedAPI, 'point');
    const ledPointsSpy = vi.spyOn(LedAPI, 'points');
    const ledClearSpy = vi.spyOn(LedAPI, 'clear');
    renderPage();
    await screen.findByTestId('live-board');
    fireEvent.click(screen.getByRole('button', { name: 'live:first_move' }));
    fireEvent.click(screen.getByRole('button', { name: 'live:next' }));
    expect(visionSpy).not.toHaveBeenCalled();
    expect(ledPointSpy).not.toHaveBeenCalled();
    expect(ledPointsSpy).not.toHaveBeenCalled();
    expect(ledClearSpy).not.toHaveBeenCalled();
  });
});

describe('kiosk ReportsPage mutations', () => {
  it('opens both import choices and supports import-only plus normal/deep report creation', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '导入本地 SGF' }));
    expect(screen.getByRole('dialog', { name: '导入本地 SGF' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('SGF 内容'), { target: { value: '(;FF[4]GM[1]SZ[9];B[aa])' } });
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith('token', expect.objectContaining({ source: 'import', board_size: 9 })));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '导入本地 SGF' })).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '从棋谱库导入' }));
    await waitFor(() => expect(screen.getByRole('dialog', { name: '从棋谱库导入' })).toBeInTheDocument());
    await screen.findByRole('button', { name: /库赛事/ });
    fireEvent.click(screen.getByRole('button', { name: '导入并生成深度复盘' }));
    await waitFor(() => expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'new', reportType: 'deep', totalMoves: 3 }));
  });

  it('can import a local SGF and immediately request a normal report', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '导入本地 SGF' }));
    fireEvent.change(screen.getByLabelText('SGF 内容'), { target: { value: '(;FF[4]GM[1]SZ[13];B[aa])' } });
    fireEvent.click(screen.getByRole('button', { name: '导入并生成普通复盘' }));
    await waitFor(() => expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'new', reportType: 'normal', totalMoves: 3 }));
  });

  it('keeps local SGF input and shows submit failure inside the modal until retry succeeds', async () => {
    mocks.create.mockRejectedValueOnce(new Error('local import rejected')).mockResolvedValueOnce(detail(game('new')));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '导入本地 SGF' }));
    const dialog = screen.getByRole('dialog', { name: '导入本地 SGF' });
    const sgfInput = within(dialog).getByRole('textbox', { name: 'SGF 内容' });
    fireEvent.change(sgfInput, { target: { value: '(;FF[4]GM[1]SZ[9];B[aa])' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '仅导入' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('local import rejected');
    expect(sgfInput).toHaveValue('(;FF[4]GM[1]SZ[9];B[aa])');
    fireEvent.click(within(dialog).getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '导入本地 SGF' })).not.toBeInTheDocument());
    expect(mocks.create).toHaveBeenCalledTimes(2);
  });

  it('keeps the library selection and shows submit failure inside the modal until retry succeeds', async () => {
    mocks.getAlbum.mockRejectedValueOnce(new Error('library import rejected')).mockResolvedValueOnce({ sgf_content: '(;SZ[13];B[aa])' });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '从棋谱库导入' }));
    const dialog = await screen.findByRole('dialog', { name: '从棋谱库导入' });
    const selected = await within(dialog).findByRole('button', { name: /库赛事/ });
    expect(selected).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(within(dialog).getByRole('button', { name: '仅导入' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('library import rejected');
    expect(selected).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(within(dialog).getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '从棋谱库导入' })).not.toBeInTheDocument());
    expect(mocks.getAlbum).toHaveBeenCalledTimes(2);
  });

  it('selects an imported game when it is present after current-page reconciliation', async () => {
    const imported = detail(game('new', 13, 1), '(;SZ[13];B[aa])');
    mocks.create.mockResolvedValue(imported);
    mocks.list.mockResolvedValueOnce(response([game('a')])).mockResolvedValueOnce(response([game('new', 13, 1), game('a')]));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /导入棋谱/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '导入本地 SGF' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'SGF 内容' }), { target: { value: '(;FF[4]GM[1]SZ[13];B[aa])' } });
    fireEvent.click(screen.getByRole('button', { name: '仅导入' }));
    await waitFor(() => expect(screen.getByRole('button', { name: /选择棋局.*赛事 new/ }).closest('[data-testid="report-game-card"]')).toHaveAttribute('data-selected', 'true'));
    await waitFor(() => expect(screen.getByTestId('live-board')).toHaveAttribute('data-board-size', '13'));
  });

  it('creates normal/deep reports and displays optimistic/active progress from the shared hook', async () => {
    mocks.hookResult = {
      ...mocks.hookResult,
      reportStatesByGame: { a: { activeNormal: { id: -1, user_game_id: 'a', status: 'pending', report_type: 'normal', total_moves: 3, analyzed_moves: 0, requested_visits: 500 } } },
    };
    renderPage();
    expect(await screen.findByText('普通复盘 · 排队中')).toBeInTheDocument();
    await openActionsFor('b');
    fireEvent.click(screen.getByRole('menuitem', { name: '生成深度复盘' }));
    await waitFor(() => expect(mocks.createReport).toHaveBeenCalledWith({ userGameId: 'b', reportType: 'deep', totalMoves: 3 }));
  });

  it('opens a completed report and retries a failed report', async () => {
    mocks.hookResult = {
      ...mocks.hookResult,
      reportStatesByGame: { a: {
        completedNormal: { id: 7, user_game_id: 'a', status: 'completed', report_type: 'normal', total_moves: 3, analyzed_moves: 3, requested_visits: 500 },
        failedDeep: { id: 8, user_game_id: 'a', status: 'failed', report_type: 'deep', total_moves: 3, analyzed_moves: 1, requested_visits: 2000 },
      } },
    };
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: '打开普通复盘' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/kiosk/report/7');
    fireEvent.click(screen.getByRole('button', { name: '重试深度复盘' }));
    await waitFor(() => expect(mocks.retryReport).toHaveBeenCalledWith(8));
  });

  it('confirms deletion, refreshes after success, and preserves the page on rejection', async () => {
    renderPage('/kiosk/report?page=2');
    await openActionsFor('a');
    fireEvent.click(screen.getByRole('menuitem', { name: '删除棋谱' }));
    expect(screen.getByText('删除后将无法恢复，关联复盘数据也会一并删除。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
    await waitFor(() => expect(mocks.deleteGame).toHaveBeenCalledWith('token', 'a'));
    expect(mocks.refreshTasks).toHaveBeenCalled();

    mocks.deleteGame.mockRejectedValueOnce(new Error('server rejects delete'));
    await openActionsFor('b');
    fireEvent.click(screen.getByRole('menuitem', { name: '删除棋谱' }));
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
    expect(await screen.findByText('server rejects delete')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('page=2');
  });

  it('resets a deleted selected game to the first remaining card and its preview', async () => {
    mocks.list.mockResolvedValueOnce(response([game('a'), game('b')])).mockResolvedValueOnce(response([game('b')]));
    renderPage();
    await screen.findByRole('button', { name: /选择棋局.*赛事 a/ });
    await openActionsFor('a');
    fireEvent.click(screen.getByRole('menuitem', { name: '删除棋谱' }));
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: /选择棋局.*赛事 a/ })).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '确认删除棋谱' })).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: /选择棋局.*赛事 b/ }).closest('[data-testid="report-game-card"]')).toHaveAttribute('data-selected', 'true');
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('token', 'b'));
  });
});
