import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KifuLibraryPage from './KifuLibraryPage';

const { getAlbums, getAlbum, language } = vi.hoisted(() => ({
  getAlbums: vi.fn(), getAlbum: vi.fn(), language: { current: 'cn' },
}));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums, getAlbum } }));
vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: language.current,
    t: (key: string, fallback?: string) => ({
      'kifu:moves_unit': { cn: '手', en: 'moves', jp: '手' },
      'kifu:source': { cn: '来源', en: 'Source', jp: '出典' },
      'kifu:source_golaxy': { cn: '星阵', en: 'GoLaxy', jp: 'GoLaxy' },
      'kifu:source_unknown': { cn: '来源待核实', en: 'Source unverified', jp: '出典未確認' },
    } as Record<string, Record<string, string>>)[key]?.[language.current] ?? fallback ?? key,
  }),
}));
vi.mock('../../components/live/LiveBoard', () => ({ default: () => <div data-testid="board" /> }));
vi.mock('../../components/live/PlaybackBar', () => ({ default: () => <div /> }));
vi.mock('../components/board/BoardPageShell', () => ({
  default: ({ board, modulePlate, railBody }: { board: React.ReactNode; modulePlate: React.ReactNode; railBody: React.ReactNode }) =>
    <main>{modulePlate}{board}{railBody}</main>,
}));
vi.mock('../components/layout/ModulePlate', () => ({
  default: ({ title, subtitle, status }: { title: React.ReactNode; subtitle: React.ReactNode; status: React.ReactNode }) =>
    <header>{title}<span data-testid="subtitle">{subtitle}</span>{status}</header>,
}));

const record = (lang: string) => ({
  id: 9, player_black: '原黑', player_white: '原白',
  display_player_black: `${lang}-black`, display_player_white: `${lang}-white`,
  black_rank: '9d', white_rank: '9d', event: '原赛事', display_event: `${lang}-event`,
  round_name: '原轮次', display_round_name: `${lang}-round`, sources: ['golaxy', 'cwi', '19x19', 'unknown'],
  date_played: '2026-01-01', result: 'B+R', rules: 'chinese', komi: 7.5,
  handicap: 0, board_size: 19, move_count: 101,
});
const detail = (lang: string) => ({ ...record(lang), place: null, source: null, sgf_content: '(;GM[1]FF[4]SZ[19];B[aa])' });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};
const page = () => <ThemeProvider theme={createTheme()}><MemoryRouter initialEntries={['/galaxy/kifu?q=原黑&page=2']}><KifuLibraryPage /></MemoryRouter></ThemeProvider>;

beforeEach(() => {
  vi.clearAllMocks();
  language.current = 'cn';
  getAlbums.mockImplementation(({ lang }: { lang: string }) => Promise.resolve({ items: [record(lang)], total: 40, page: 2, page_size: 20 }));
  getAlbum.mockImplementation((_id: number, lang: string) => Promise.resolve(detail(lang)));
});

describe('Galaxy 棋谱库语言展示', () => {
  it('将姓名中的段位放进独立的小号段位元素', async () => {
    getAlbums.mockResolvedValue({
      items: [{
        ...record('cn'),
        player_black: '吴清源六段',
        display_player_black: '吴清源',
        black_rank: null,
        display_black_rank: '六段',
      }],
      total: 1, page: 2, page_size: 20,
    });
    render(page());
    const name = await screen.findByText('吴清源');
    const rank = screen.getByText('六段');
    expect(name).not.toContainElement(rank);
    expect(rank.tagName).toBe('SPAN');
  });

  it('切语言保留搜索、页码和选中卡，并更新卡片及页头译名', async () => {
    const view = render(page());
    fireEvent.click(await screen.findByText('cn-black'));
    await waitFor(() => expect(getAlbum).toHaveBeenCalledWith(9, 'cn'));
    expect(screen.getByText(/cn-black vs cn-white/)).toBeInTheDocument();
    expect(screen.getByText('星阵')).toBeInTheDocument();
    expect(screen.getByText('CWI')).toBeInTheDocument();
    expect(screen.getByText('19x19')).toBeInTheDocument();
    expect(screen.getByText('来源待核实')).toBeInTheDocument();

    for (const lang of ['en', 'jp']) {
      language.current = lang;
      view.rerender(page());
      await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: '原黑', page: 2, page_size: 20, lang }));
      await waitFor(() => expect(getAlbum).toHaveBeenLastCalledWith(9, lang));
      expect(await screen.findByText(`${lang}-black`)).toBeInTheDocument();
      expect(screen.getByText(new RegExp(`${lang}-black vs ${lang}-white`))).toBeInTheDocument();
      expect(screen.getByText('GoLaxy')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toHaveValue('原黑');
    }
  });

  it('旧语言详情迟到时不会盖掉新语言', async () => {
    const oldList = deferred<{ items: ReturnType<typeof record>[]; total: number; page: number; page_size: number }>();
    const oldDetail = deferred<ReturnType<typeof detail>>();
    getAlbums.mockImplementation(({ lang }: { lang: string }) => lang === 'cn'
      ? oldList.promise : Promise.resolve({ items: [record(lang)], total: 40, page: 2, page_size: 20 }));
    getAlbum.mockImplementation((_id: number, lang: string) => lang === 'cn' ? oldDetail.promise : Promise.resolve(detail(lang)));
    const view = render(page());
    // Resolve the first list so that the card can be selected; the stale detail remains pending.
    await act(async () => { oldList.resolve({ items: [record('cn')], total: 40, page: 2, page_size: 20 }); });
    fireEvent.click(await screen.findByText('cn-black'));
    language.current = 'en';
    view.rerender(page());
    expect(await screen.findByText('en-black')).toBeInTheDocument();
    expect(await screen.findByText(/en-black vs en-white/)).toBeInTheDocument();
    await act(async () => { oldDetail.resolve(detail('cn')); });
    expect(screen.getByText(/en-black vs en-white/)).toBeInTheDocument();
  });

  it('旧语言列表迟到时不会盖掉新语言', async () => {
    const old = deferred<{ items: ReturnType<typeof record>[]; total: number; page: number; page_size: number }>();
    getAlbums.mockImplementation(({ lang }: { lang: string }) => lang === 'cn'
      ? old.promise : Promise.resolve({ items: [record(lang)], total: 40, page: 2, page_size: 20 }));
    const view = render(page());
    language.current = 'en';
    view.rerender(page());
    expect(await screen.findByText('en-black')).toBeInTheDocument();
    await act(async () => { old.resolve({ items: [record('cn')], total: 40, page: 2, page_size: 20 }); });
    expect(screen.getByText('en-black')).toBeInTheDocument();
    expect(screen.queryByText('cn-black')).not.toBeInTheDocument();
  });

  it('重复点击已选卡仍保留棋盘预览', async () => {
    render(page());
    fireEvent.click(await screen.findByText('cn-black'));
    expect(await screen.findByTestId('board')).toBeInTheDocument();
    fireEvent.click(screen.getByText('cn-black'));
    expect(screen.getByTestId('board')).toBeInTheDocument();
    expect(getAlbum).toHaveBeenCalledTimes(1);
  });

  it('详情失败后再次点击同卡会重试并恢复棋盘预览', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      getAlbum.mockRejectedValueOnce(new Error('offline'));
      render(page());
      fireEvent.click(await screen.findByText('cn-black'));
      await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(1));
      await screen.findByText('选择一局棋谱预览');

      fireEvent.click(screen.getByText('cn-black'));
      await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(2));
      expect(await screen.findByTestId('board')).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });

  it('切语言重取详情失败后再次点击同卡也能重试', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const view = render(page());
      fireEvent.click(await screen.findByText('cn-black'));
      expect(await screen.findByTestId('board')).toBeInTheDocument();
      getAlbum.mockRejectedValueOnce(new Error('offline'));
      language.current = 'en';
      view.rerender(page());
      await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(2));
      await screen.findByText('选择一局棋谱预览');

      fireEvent.click(await screen.findByText('en-black'));
      await waitFor(() => expect(getAlbum).toHaveBeenCalledTimes(3));
      expect(await screen.findByTestId('board')).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });
});
