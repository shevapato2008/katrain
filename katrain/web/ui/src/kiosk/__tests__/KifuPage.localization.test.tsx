import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KifuPage from '../pages/KifuPage';
import { kioskTheme } from '../theme';

const { getAlbums, language } = vi.hoisted(() => ({ getAlbums: vi.fn(), language: { current: 'cn' } }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums } }));
vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: language.current,
    t: (key: string, fallback?: string) => ({
      'strength:dan': { cn: '段', en: 'dan', jp: '段' },
      'result:black_win': { cn: '黑胜', en: 'B+', jp: '黒勝' },
      'result:resign': { cn: '中盘', en: 'R', jp: '中押し' },
      'kifu:moves_unit': { cn: '手', en: 'moves', jp: '手' },
      'kifu:source': { cn: '来源', en: 'Source', jp: '出典' },
      'kifu:source_golaxy': { cn: '星阵', en: 'GoLaxy', jp: 'GoLaxy' },
      'kifu:source_unknown': { cn: '来源待核实', en: 'Source unverified', jp: '出典未確認' },
    } as Record<string, Record<string, string>>)[key]?.[language.current] ?? fallback ?? key,
  }),
}));

const record = (lang: string) => ({
  id: 9, player_black: '原黑', player_white: '原白',
  display_player_black: `${lang}-black`, display_player_white: `${lang}-white`,
  black_rank: '9d', white_rank: '9d', event: '原赛事', display_event: `${lang}-event`,
  round_name: '原轮次', display_round_name: `${lang}-round`, sources: ['golaxy', 'cwi', '19x19', 'unknown'],
  date_played: '2026-01-01', result: 'B+R', rules: 'chinese', komi: 7.5,
  handicap: 0, board_size: 19, move_count: 101,
});
const response = (lang: string, total = 25) => ({ items: [record(lang)], total, page: 1, page_size: 20 });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};
const renderPage = () => render(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  language.current = 'cn';
  getAlbums.mockImplementation(({ lang }: { lang: string }) => Promise.resolve(response(lang)));
});

describe('棋谱 kiosk 语言展示', () => {
  it('cn→en→jp 重取同页并同步显示译名、结果、段位与全部来源', async () => {
    const view = renderPage();
    const row = await screen.findByRole('button', { name: /cn-event.*cn-black.*cn-white/ });
    expect(row).toHaveTextContent('9段');
    expect(row).toHaveTextContent('黑胜中盘');
    expect(within(row).getByText('星阵')).toBeInTheDocument();
    expect(within(row).getByText('CWI')).toBeInTheDocument();
    expect(within(row).getByText('19x19')).toBeInTheDocument();
    expect(within(row).getByText('来源待核实')).toBeInTheDocument();
    expect(row).toHaveTextContent('来源');
    expect(row).toHaveStyle({ height: 'auto', gridTemplateRows: '18px 25px auto' });

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, lang: 'cn' })));
    language.current = 'en';
    view.rerender(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, lang: 'en' })));
    const enRow = await screen.findByRole('button', { name: /en-event.*en-black.*en-white/ });
    expect(enRow).toHaveTextContent('en-round');
    expect(enRow).toHaveTextContent('9dan');
    expect(enRow).toHaveTextContent('B+R');
    expect(enRow).toHaveTextContent('Source');
    expect(enRow).toHaveTextContent('GoLaxy');
    expect(enRow).toHaveTextContent('Source unverified');

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '原黑' } });
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ q: '原黑', page: 1, lang: 'en' })), { timeout: 1500 });
    language.current = 'jp';
    view.rerender(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ q: '原黑', page: 1, lang: 'jp' })));
    const jpRow = await screen.findByRole('button', { name: /jp-event.*jp-black.*jp-white/ });
    expect(jpRow).toHaveTextContent('jp-round');
    expect(jpRow).toHaveTextContent('9段');
    expect(jpRow).toHaveTextContent('黒勝中押し');
    expect(jpRow).toHaveTextContent('出典');
    expect(jpRow).toHaveTextContent('GoLaxy');
    expect(jpRow).toHaveTextContent('出典未確認');
    expect(screen.getByRole('searchbox')).toHaveValue('原黑');
  });

  it('译名为空时显示原文', async () => {
    getAlbums.mockResolvedValue({ items: [{ ...record('cn'), display_player_black: null, display_player_white: null, display_event: null, display_round_name: null }], total: 1, page: 1, page_size: 20 });
    renderPage();
    const row = await screen.findByRole('button', { name: /原赛事.*原轮次.*原黑.*原白/ });
    expect(row).toBeInTheDocument();
  });

  it('迟到的旧语言响应不能覆盖新语言', async () => {
    const old = deferred<ReturnType<typeof response>>();
    getAlbums.mockImplementation(({ lang }: { lang: string }) => lang === 'cn' ? old.promise : Promise.resolve(response(lang)));
    const view = renderPage();
    language.current = 'en';
    view.rerender(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
    expect(await screen.findByRole('button', { name: /en-event.*en-black.*en-white/ })).toBeInTheDocument();
    await act(async () => { old.resolve(response('cn')); });
    expect(screen.getByRole('button', { name: /en-event.*en-black.*en-white/ })).toBeInTheDocument();
  });
});
