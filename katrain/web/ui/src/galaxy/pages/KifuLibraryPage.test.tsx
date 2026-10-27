import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { KifuAlbumDetail, KifuAlbumListResponse } from '../../types/kifu';
import { sgfToMoves } from '../../utils/sgfSerializer';
import KifuLibraryPage from './KifuLibraryPage';

const { getAlbums, getAlbum } = vi.hoisted(() => ({ getAlbums: vi.fn(), getAlbum: vi.fn() }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums, getAlbum } }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({
  lang: 'cn', t: (key: string, fallback?: string) => fallback ?? key,
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
const renderPage = () => render(
  <ThemeProvider theme={createTheme()}><MemoryRouter><KifuLibraryPage /></MemoryRouter></ThemeProvider>,
);
const expectBoard = (detail: KifuAlbumDetail) => {
  expect(screen.getByTestId('board')).toHaveTextContent(JSON.stringify(sgfToMoves(detail.sgf_content).moves));
  expect(screen.getByTestId('subtitle')).toHaveTextContent(`${detail.display_player_black} vs ${detail.display_player_white}`);
};

beforeEach(() => {
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
    await screen.findByTestId('board');
    expectBoard(a);
    expect(getAlbum).not.toHaveBeenCalled();

    search('王星昊');
    await waitFor(() => expect(getAlbums).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('40 records · 第 1 / 2 页')).not.toBeInTheDocument();
    expect(screen.queryByTestId('board')).not.toBeInTheDocument();
    await act(async () => { next.resolve({ ...list(b, 504), items: [b, a] }); });

    expect(await screen.findByText('王星昊-event')).toBeInTheDocument();
    expect(screen.getByText('504 records · 第 1 / 26 页')).toBeInTheDocument();
    expectBoard(b);
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
