import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { KifuAlbumDetail, KifuAlbumListResponse } from '../../types/kifu';
import { sgfToMoves } from '../../utils/sgfSerializer';
import KifuLibraryPage from './KifuLibraryPage';

const { getAlbums, getAlbum, translation } = vi.hoisted(() => ({
  getAlbums: vi.fn(), getAlbum: vi.fn(), translation: { lang: 'cn' },
}));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums, getAlbum } }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({
  lang: translation.lang, t: (key: string, fallback?: string) => fallback ?? key,
}) }));
vi.mock('../../hooks/useReplayStoneSound', () => ({ useReplayStoneSound: () => {} }));
vi.mock('../../components/live/LiveBoard', () => ({
  default: ({ moves }: { moves: string[] }) => <div data-testid="board">{JSON.stringify(moves)}</div>,
}));
vi.mock('../../components/live/PlaybackBar', () => ({ default: () => null }));
vi.mock('../components/board/BoardPageShell', () => ({
  default: ({ board, modulePlate, railBody, actions }: {
    board: React.ReactNode; modulePlate: React.ReactNode; railBody: React.ReactNode; actions: React.ReactNode;
  }) => <main>{modulePlate}{board}{railBody}{actions}</main>,
}));
vi.mock('../components/layout/ModulePlate', () => ({
  default: ({ subtitle }: { subtitle: React.ReactNode }) => <header data-testid="subtitle">{subtitle}</header>,
}));

const album = (id: number, name: string, point = 'aa'): KifuAlbumDetail => ({
  id, player_black: name, player_white: `${name}-white`, display_player_black: name,
  display_player_white: `${name}-white`, black_rank: null, white_rank: null,
  event: null, display_event: `${name}-event`, result: 'B+R', rules: 'chinese',
  date_played: null, komi: 7.5, handicap: 0, board_size: 19, round_name: null,
  move_count: 1, place: null, source: null, sgf_content: `(;GM[1]SZ[19];B[${point}])`,
});
const a = album(1, 'A');
const b = album(2, '王星昊', 'dd');
const list = (preview: KifuAlbumDetail, total = 40): KifuAlbumListResponse => ({
  items: [preview], preview, total, page: 1, page_size: 20,
});
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};
const search = (value: string) => {
  const input = screen.getByPlaceholderText('Search by player, event, date...');
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: 'Enter' });
};
const pageView = () => (
  <ThemeProvider theme={createTheme()}><MemoryRouter><KifuLibraryPage /></MemoryRouter></ThemeProvider>
);
const renderPage = () => render(pageView());
const expectBoard = (detail: KifuAlbumDetail) => {
  expect(screen.getByTestId('board')).toBeVisible();
  expect(screen.getByTestId('board')).toHaveTextContent(JSON.stringify(sgfToMoves(detail.sgf_content).moves));
  expect(screen.getByTestId('subtitle')).toHaveTextContent(`${detail.display_player_black} vs ${detail.display_player_white}`);
};

beforeEach(() => {
  translation.lang = 'cn';
  getAlbums.mockReset();
  getAlbum.mockReset();
  getAlbums.mockResolvedValue(list(a));
  getAlbum.mockImplementation((id: number) => Promise.resolve(id === b.id ? b : a));
});

describe('Galaxy 棋谱搜索请求一致性', () => {
  it('搜索成功一起接受新列表、总数和首盘preview，即使旧选择仍在新结果内', async () => {
    const next = deferred<KifuAlbumListResponse>();
    getAlbums.mockResolvedValueOnce(list(a)).mockReturnValueOnce(next.promise);
    // The list preview must draw without waiting for a second detail request.
    getAlbum.mockReturnValue(new Promise(() => {}));
    renderPage();
    const board = await screen.findByTestId('board');
    expectBoard(a);
    expect(getAlbum).not.toHaveBeenCalled();

    search('王星昊');
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('40 records · 第 1 / 2 页')).not.toBeInTheDocument();
    expect(screen.getByTestId('board')).toBe(board);
    expect(board).not.toBeVisible();
    expect(board.closest('[aria-hidden]')).toHaveAttribute('aria-hidden', 'true');
    expect(board.closest('[inert]')).toBeInTheDocument();
    expect(screen.getByTestId('subtitle')).not.toHaveTextContent('A vs A-white');
    expect(screen.queryByText('A-event')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看棋谱' })).toBeDisabled();
    expect(screen.getByTestId('kifu-preview-spinner')).toBeVisible();
    await act(async () => { next.resolve({ ...list(b, 504), items: [b, a] }); });

    expect(await screen.findByText('王星昊-event')).toBeInTheDocument();
    expect(screen.getByText('504 records · 第 1 / 26 页')).toBeInTheDocument();
    expectBoard(b);
    expect(screen.getByTestId('board')).toBe(board);
    expect(board.closest('[aria-hidden]')).toHaveAttribute('aria-hidden', 'false');
    expect(board.closest('[inert]')).toBeNull();
    expect(getAlbum).not.toHaveBeenCalled();
  });

  it('旧列表被取消且晚到成功不会替换新搜索的列表、总数和棋盘', async () => {
    const old = deferred<KifuAlbumListResponse>();
    getAlbums.mockReturnValueOnce(old.promise).mockResolvedValueOnce(list(b, 504));
    renderPage();
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(1));
    const oldSignal = getAlbums.mock.calls[0][0].signal as AbortSignal;
    search('王星昊');
    await screen.findByText('王星昊-event');
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { old.resolve(list(a)); });
    expect(screen.queryByText('A-event')).not.toBeInTheDocument();
    expect(screen.getByText('504 records · 第 1 / 26 页')).toBeInTheDocument();
    expectBoard(b);
  });

  it('旧详情被取消且晚到不会覆盖新搜索首盘', async () => {
    const old = deferred<KifuAlbumDetail>();
    getAlbums.mockResolvedValueOnce({ ...list(a), preview: null }).mockResolvedValueOnce(list(b, 504));
    getAlbum.mockReturnValueOnce(old.promise);
    renderPage();
    await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(1));
    const oldSignal = getAlbum.mock.calls[0][2] as AbortSignal;
    search('王星昊');
    await screen.findByText('王星昊-event');
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { old.resolve(a); });
    expectBoard(b);
  });

  it('切换卡片后旧详情晚到不会覆盖当前选择', async () => {
    const old = deferred<KifuAlbumDetail>();
    getAlbums.mockResolvedValue({ ...list(a), items: [a, b], preview: null });
    getAlbum.mockReturnValueOnce(old.promise).mockResolvedValueOnce(b);
    renderPage();
    await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(1));
    const oldSignal = getAlbum.mock.calls[0][2] as AbortSignal;
    fireEvent.click(screen.getByText('王星昊-event'));
    await screen.findByTestId('board');
    expectBoard(b);
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { old.resolve(a); });
    expectBoard(b);
  });

  it('已有棋盘在详情加载期间保留实例但不可见，失败可重试', async () => {
    const pending = deferred<KifuAlbumDetail>();
    getAlbums.mockResolvedValue({ ...list(a), items: [a, b] });
    getAlbum.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(b);
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      renderPage();
      const board = await screen.findByTestId('board');
      fireEvent.click(screen.getByText('王星昊-event'));
      await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(1));
      expect(screen.getByTestId('board')).toBe(board);
      expect(board).not.toBeVisible();
      expect(board.closest('[aria-hidden]')).toHaveAttribute('aria-hidden', 'true');
      expect(board.closest('[inert]')).toBeInTheDocument();
      await act(async () => { pending.reject(new Error('offline')); });
      expect(await screen.findByText('棋谱预览加载失败')).toBeVisible();
      expect(board).not.toBeVisible();
      fireEvent.click(screen.getByRole('button', { name: '重试' }));
      await waitFor(() => expectBoard(b));
      expect(screen.getByTestId('board')).toBe(board);
    } finally {
      error.mockRestore();
    }
  });

  it('连续搜索保留同一棋盘，取消中间请求且只显示最后一组结果', async () => {
    const middle = deferred<KifuAlbumListResponse>();
    const last = deferred<KifuAlbumListResponse>();
    const c = album(3, 'C', 'pp');
    getAlbums.mockResolvedValueOnce(list(a)).mockReturnValueOnce(middle.promise).mockReturnValueOnce(last.promise);
    renderPage();
    const board = await screen.findByTestId('board');
    search('王星昊');
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(2));
    const middleSignal = getAlbums.mock.calls[1][0].signal as AbortSignal;
    search('C');
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(3));
    expect(middleSignal.aborted).toBe(true);
    expect(screen.getByTestId('board')).toBe(board);
    expect(board).not.toBeVisible();
    await act(async () => { last.resolve(list(c, 1)); });
    expectBoard(c);
    expect(screen.getByTestId('board')).toBe(board);
    await act(async () => { middle.resolve(list(b, 504)); });
    expectBoard(c);
    expect(screen.queryByText('王星昊-event')).not.toBeInTheDocument();
  });

  it('从其它卡片返回首条时仍复用本次列表preview', async () => {
    getAlbums.mockResolvedValue({ ...list(a), items: [a, b] });
    renderPage();
    await screen.findByTestId('board');
    fireEvent.click(screen.getByText('王星昊-event'));
    await waitFor(() => expectBoard(b));
    fireEvent.click(screen.getByText('A-event'));
    await waitFor(() => expectBoard(a));
    expect(getAlbum).toHaveBeenCalledTimes(1);
  });

  it('同页刷新保留仍在结果中的手动选择并刷新详情', async () => {
    getAlbums.mockResolvedValue({ ...list(a), items: [a, b] });
    renderPage();
    await screen.findByTestId('board');
    fireEvent.click(screen.getByText('王星昊-event'));
    await waitFor(() => expectBoard(b));
    search('');
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(2));
    expect(getAlbum).toHaveBeenLastCalledWith(b.id, 'cn', expect.any(AbortSignal));
    expectBoard(b);
  });

  it('语言切换保留手动选择并从新语言详情更新原棋盘', async () => {
    const translated = { ...b, display_player_black: 'Wang', display_player_white: 'White' };
    const next = deferred<KifuAlbumListResponse>();
    getAlbums.mockResolvedValueOnce({ ...list(a), items: [a, b] }).mockReturnValueOnce(next.promise);
    getAlbum.mockResolvedValueOnce(b).mockResolvedValueOnce(translated);
    const view = renderPage();
    await screen.findByTestId('board');
    fireEvent.click(screen.getByText('王星昊-event'));
    await waitFor(() => expectBoard(b));
    const board = screen.getByTestId('board');
    translation.lang = 'en';
    view.rerender(pageView());
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('board')).toBe(board);
    expect(board).not.toBeVisible();
    await act(async () => { next.resolve({ ...list(a), items: [a, translated] }); });
    await waitFor(() => expectBoard(translated));
    expect(getAlbum).toHaveBeenLastCalledWith(b.id, 'en', expect.any(AbortSignal));
    expect(screen.getByTestId('board')).toBe(board);
  });

  it('无结果清空旧选择和棋盘，入口不可用', async () => {
    getAlbums.mockResolvedValueOnce(list(a)).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20, preview: null });
    renderPage();
    await screen.findByTestId('board');
    search('不存在');
    expect(await screen.findByText('No records found')).toBeInTheDocument();
    expect(screen.queryByTestId('board')).not.toBeInTheDocument();
    expect(screen.getByTestId('subtitle')).toHaveTextContent('0 records');
    expect(screen.getByRole('button', { name: '查看棋谱' })).toBeDisabled();
  });

  it('失败显示重试而非旧结果或空成功，同词Enter和重试按钮均发起新请求', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      getAlbums.mockResolvedValueOnce(list(a))
        .mockRejectedValueOnce(new Error('offline'))
        .mockRejectedValueOnce(new Error('offline again'))
        .mockResolvedValueOnce(list(b, 504));
      renderPage();
      await screen.findByTestId('board');
      search('王星昊');
      expect(await screen.findByRole('alert')).toHaveTextContent('棋谱库读不到');
      expect(screen.queryByText('A-event')).not.toBeInTheDocument();
      expect(screen.queryByTestId('board')).not.toBeInTheDocument();
      expect(screen.queryByText('No records found')).not.toBeInTheDocument();
      search('王星昊');
      await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(3));
      fireEvent.click(await screen.findByRole('button', { name: '重试' }));
      await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(4));
      expect(await screen.findByText('王星昊-event')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expectBoard(b);
    } finally {
      error.mockRestore();
    }
  });
});
