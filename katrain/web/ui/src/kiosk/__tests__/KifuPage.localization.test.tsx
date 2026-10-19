import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { Link, MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
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
      'review:tag_analyzed': { cn: '已分析', en: 'Analysed', jp: '解析済み' },
      'kifu:view_analysis_report': { cn: '查看分析报告', en: 'View analysis report', jp: '解析レポートを見る' },
      'kifu:view_kifu': { cn: '查看棋谱', en: 'View game record', jp: '棋譜を見る' },
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
  black_rank: '9d', white_rank: '9d', display_black_rank: '9d', display_white_rank: '9d', event: '原赛事', display_event: `${lang}-event`,
  round_name: '原轮次', display_round_name: `${lang}-round`, sources: ['golaxy', 'cwi', '19x19', 'unknown'],
  date_played: '2026-01-01', result: 'B+R', rules: 'chinese', komi: 7.5,
  handicap: 0, board_size: 19, move_count: 101, has_analysis: true,
});
const response = (lang: string, total = 25) => ({ items: [record(lang)], total, page: 1, page_size: 20 });
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};
const renderPage = () => render(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
const TestSettings = () => {
  const navigate = useNavigate();
  return <button onClick={() => { language.current = 'en'; navigate('/kiosk/kifu'); }}>English</button>;
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  language.current = 'cn';
  getAlbums.mockImplementation(({ lang }: { lang: string }) => Promise.resolve(response(lang)));
});

describe('棋谱 kiosk 语言展示', () => {
  it('keeps the searched page through Settings and reloads it in English', async () => {
    getAlbums.mockImplementation(({ lang, page }: { lang: string; page: number }) =>
      Promise.resolve(response(`${lang}-page${page}`)));
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/kifu']}>
          <Link to="/kiosk/settings">Settings</Link>
          <Routes>
            <Route path="/kiosk/kifu" element={<KifuPage />} />
            <Route path="/kiosk/settings" element={<TestSettings />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '吴清源' } });
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: '吴清源', page: 1, lang: 'cn' }),
    ));
    await screen.findByRole('button', { name: /cn-page1-event.*cn-page1-black/ });
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await screen.findByRole('button', { name: /cn-page2-event.*cn-page2-black/ });
    fireEvent.click(screen.getByRole('link', { name: 'Settings' }));
    fireEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('searchbox')).toHaveValue('吴清源');
    expect(await screen.findByRole('button', { name: /en-page2-event.*en-page2-black/ })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '跳转页码' })).toHaveValue('2');
    expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ q: '吴清源', page: 2, lang: 'en' }));
  });

  it('cn→en→jp 重取同页并同步显示译名、结果、段位，隐藏来源', async () => {
    const view = renderPage();
    const row = await screen.findByRole('button', { name: /cn-event.*cn-black.*cn-white/ });
    expect(row).toHaveTextContent('9段');
    expect(row).toHaveTextContent('黑胜中盘');
    expect(within(row).getByRole('img', { name: '查看分析报告' })).toBeInTheDocument();
    expect(within(row).queryByText('来源')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, lang: 'cn' })));
    language.current = 'en';
    view.rerender(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, lang: 'en' })));
    const enRow = await screen.findByRole('button', { name: /en-event.*en-black.*en-white/ });
    expect(enRow).toHaveTextContent('en-round');
    expect(enRow).toHaveTextContent('9dan');
    expect(enRow).toHaveTextContent('B+R');
    expect(within(enRow).getByRole('img', { name: 'View analysis report' })).toBeInTheDocument();
    expect(enRow).not.toHaveTextContent('Source');
    expect(enRow).not.toHaveTextContent('GoLaxy');
    expect(enRow).not.toHaveTextContent('Source unverified');

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '原黑' } });
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ q: '原黑', page: 1, lang: 'en' })), { timeout: 1500 });
    language.current = 'jp';
    view.rerender(<ThemeProvider theme={kioskTheme}><MemoryRouter><KifuPage /></MemoryRouter></ThemeProvider>);
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith(expect.objectContaining({ q: '原黑', page: 1, lang: 'jp' })));
    const jpRow = await screen.findByRole('button', { name: /jp-event.*jp-black.*jp-white/ });
    expect(jpRow).toHaveTextContent('jp-round');
    expect(jpRow).toHaveTextContent('9段');
    expect(jpRow).toHaveTextContent('黒勝中押し');
    expect(within(jpRow).getByRole('img', { name: '解析レポートを見る' })).toBeInTheDocument();
    expect(jpRow).not.toHaveTextContent('出典');
    expect(jpRow).not.toHaveTextContent('GoLaxy');
    expect(jpRow).not.toHaveTextContent('出典未確認');
    expect(screen.getByRole('searchbox')).toHaveValue('原黑');
  });

  it('译名为空时不回退原始 SGF 字段', async () => {
    getAlbums.mockResolvedValue({ items: [{ ...record('cn'), display_player_black: null, display_player_white: null, display_event: null, display_round_name: null }], total: 1, page: 1, page_size: 20 });
    renderPage();
    const row = await screen.findByRole('button', { name: /黑方.*白方/ });
    expect(row).not.toHaveTextContent(/原赛事|原轮次|原黑|原白/);
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
