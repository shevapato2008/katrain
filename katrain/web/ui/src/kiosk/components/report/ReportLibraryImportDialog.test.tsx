import { ThemeProvider } from '@mui/material/styles';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { KifuAPI } from '../../../api/kifuApi';
import type { KifuAlbumSummary } from '../../../types/kifu';
import { kioskTheme } from '../../theme';
import ReportLibraryImportDialog from './ReportLibraryImportDialog';

vi.mock('../../../api/kifuApi', () => ({ KifuAPI: { getAlbums: vi.fn() } }));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: 'zh-CN',
    t: (key: string, fallback?: string) => (
      key === 'report:library_players_title' ? '{black} against {white}' :
      key === 'report:library_game_accessible' ? '{title} / {black} versus {white}' : (fallback ?? key)
    ),
  }),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const album = (id: number, event = `赛事 ${id}`): KifuAlbumSummary => ({
  id, player_black: `黑棋 ${id}`, player_white: `白棋 ${id}`, black_rank: '2D', white_rank: '3D',
  event, result: 'B+R', rules: 'chinese', date_played: '2026-07-15', komi: 7.5,
  handicap: 0, board_size: 19, round_name: '决赛', move_count: 188,
});

function response(items: KifuAlbumSummary[], total = items.length) {
  return { items, total, page: 1, page_size: 10 };
}

function renderDialog(options: { loading?: boolean; open?: boolean } = {}) {
  const onClose = vi.fn();
  const onImport = vi.fn();
  const view = render(
    <ThemeProvider theme={kioskTheme}>
      <ReportLibraryImportDialog
        open={options.open ?? true}
        loading={options.loading}
        onClose={onClose}
        onImport={onImport}
      />
    </ThemeProvider>,
  );
  return { ...view, onClose, onImport };
}

beforeEach(() => {
  vi.mocked(KifuAPI.getAlbums).mockReset();
  vi.mocked(KifuAPI.getAlbums).mockResolvedValue(response([album(1), album(2)]));
});

describe('ReportLibraryImportDialog data flow', () => {
  it('fetches only when opened, searches on Enter, and paginates', async () => {
    const user = userEvent.setup();
    const view = renderDialog({ open: false });
    expect(KifuAPI.getAlbums).not.toHaveBeenCalled();
    view.rerender(
      <ThemeProvider theme={kioskTheme}>
        <ReportLibraryImportDialog open onClose={view.onClose} onImport={view.onImport} />
      </ThemeProvider>,
    );
    await waitFor(() => expect(KifuAPI.getAlbums).toHaveBeenCalledWith({ page: 1, page_size: 10 }));

    vi.mocked(KifuAPI.getAlbums).mockResolvedValueOnce(response([album(11)], 21));
    await user.type(screen.getByRole('textbox', { name: '搜索棋谱库' }), '春兰杯{Enter}');
    await waitFor(() => expect(KifuAPI.getAlbums).toHaveBeenLastCalledWith({ q: '春兰杯', page: 1, page_size: 10 }));

    await waitFor(() => expect(screen.getByRole('navigation')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await waitFor(() => expect(KifuAPI.getAlbums).toHaveBeenLastCalledWith({ q: '春兰杯', page: 2, page_size: 10 }));
  });

  it('resets selection to the first result whenever the fetched result set changes', async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(await screen.findByRole('button', { name: /赛事 2/ }));
    expect(screen.getByRole('button', { name: /赛事 2/ })).toHaveAttribute('aria-pressed', 'true');

    vi.mocked(KifuAPI.getAlbums).mockResolvedValueOnce(response([album(3), album(4)]));
    await user.type(screen.getByRole('textbox', { name: '搜索棋谱库' }), '新结果{Enter}');
    expect(await screen.findByRole('button', { name: /赛事 3/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('button', { name: /赛事 2/ })).not.toBeInTheDocument();
  });

  it('clears selection during fetch and ignores stale responses and errors after a newer search wins', async () => {
    const user = userEvent.setup();
    const stale = deferred<ReturnType<typeof response>>();
    const newest = deferred<ReturnType<typeof response>>();
    vi.mocked(KifuAPI.getAlbums)
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(newest.promise);
    renderDialog();

    await user.type(screen.getByRole('textbox', { name: '搜索棋谱库' }), '新棋谱{Enter}');
    expect(screen.getByRole('button', { name: '仅导入' })).toBeDisabled();
    await act(async () => { newest.resolve(response([album(9, '最新结果')])); });
    expect(await screen.findByRole('button', { name: /最新结果/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '仅导入' })).toBeEnabled();

    await act(async () => { stale.reject(new Error('stale failure')); });
    expect(screen.getByRole('button', { name: /最新结果/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText('棋谱加载失败，请重试。')).not.toBeInTheDocument();
  });

  it('builds the result accessible name entirely through translation', async () => {
    renderDialog();
    expect(await screen.findByRole('button', { name: '赛事 1 / 黑棋 1 versus 白棋 1' })).toBeInTheDocument();
  });

  it('translates the visible player fallback title', async () => {
    vi.mocked(KifuAPI.getAlbums).mockResolvedValue(response([album(5, '')]));
    renderDialog();
    expect(await screen.findByText('黑棋 5 against 白棋 5')).toBeInTheDocument();
  });

  it('shows a retryable fetch failure', async () => {
    const user = userEvent.setup();
    vi.mocked(KifuAPI.getAlbums).mockRejectedValueOnce(new Error('offline'));
    renderDialog();
    expect(await screen.findByText('棋谱加载失败，请重试。')).toBeInTheDocument();
    const retry = screen.getByRole('button', { name: '重试' });
    expect(retry).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    await user.click(retry);
    expect(await screen.findByRole('button', { name: /赛事 1/ })).toBeInTheDocument();
    expect(KifuAPI.getAlbums).toHaveBeenCalledTimes(2);
  });

  it('submits import-only, normal, and deep for the selected album', async () => {
    const user = userEvent.setup();
    const { onImport } = renderDialog();
    await user.click(await screen.findByRole('button', { name: /赛事 2/ }));
    await user.click(screen.getByRole('button', { name: '仅导入' }));
    await user.click(screen.getByRole('button', { name: '导入并生成普通报告' }));
    await user.click(screen.getByRole('button', { name: '导入并生成深度报告' }));
    expect(onImport).toHaveBeenNthCalledWith(1, album(2));
    expect(onImport).toHaveBeenNthCalledWith(2, album(2), 'normal');
    expect(onImport).toHaveBeenNthCalledWith(3, album(2), 'deep');
  });

  it('locks close, selection, search, and submission while importing', async () => {
    vi.mocked(KifuAPI.getAlbums).mockResolvedValue(response([album(1), album(2)], 21));
    const { onClose, onImport } = renderDialog({ loading: true });
    expect(screen.getByRole('textbox', { name: '搜索棋谱库' })).toBeDisabled();
    expect(await screen.findByRole('button', { name: /赛事 1/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Go to page 2' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    fireEvent.click(screen.getByRole('button', { name: '导入中...' }));
    expect(onClose).not.toHaveBeenCalled();
    expect(onImport).not.toHaveBeenCalled();
  });
});

describe('ReportLibraryImportDialog 1024×600 layout', () => {
  it('keeps bounded paper, independently scrolling content, fixed actions, and 48px wrapped controls', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 });
    renderDialog();
    await screen.findByRole('button', { name: /赛事 1/ });

    const paper = screen.getByRole('dialog', { name: '从棋谱库导入' });
    const content = screen.getByTestId('report-library-import-content');
    const actions = screen.getByTestId('report-library-import-actions');
    expect(paper).toHaveStyle({
      width: 'calc(100vw - 24px)',
      maxWidth: '960px',
      height: 'calc(100dvh - 24px)',
      maxHeight: '576px',
      overflow: 'hidden',
    });
    expect(content).toHaveStyle({ minWidth: '0', minHeight: '0', overflowY: 'auto', overflowX: 'hidden' });
    expect(actions).toHaveStyle({
      flexShrink: '0',
      overflowX: 'hidden',
      gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    });
    for (const label of ['取消', '仅导入', '导入并生成普通报告', '导入并生成深度报告']) {
      expect(screen.getByRole('button', { name: label })).toHaveStyle({
        minHeight: '48px', minWidth: '48px', whiteSpace: 'normal',
      });
    }
    expect(within(content).getByRole('textbox', { name: '搜索棋谱库' })).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    expect(screen.getByRole('button', { name: '搜索' })).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    for (const result of screen.getAllByRole('button', { name: /赛事 [12]/ })) {
      expect(result).toHaveStyle({ minHeight: '56px', minWidth: '48px' });
    }

    vi.mocked(KifuAPI.getAlbums).mockResolvedValue(response([album(1), album(2)], 21));
    fireEvent.keyDown(within(content).getByRole('textbox', { name: '搜索棋谱库' }), { key: 'Enter' });
    return waitFor(() => {
      const pageButton = screen.getByRole('button', { name: 'Go to page 2' });
      expect(pageButton).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    });
  });
});
