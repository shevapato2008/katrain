import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { kioskTheme } from '../theme';
import KifuDetailPage from '../pages/KifuDetailPage';

const { getAlbum, baipuLoad, cacheSgf, language } = vi.hoisted(() => ({
  getAlbum: vi.fn(), baipuLoad: vi.fn(), cacheSgf: vi.fn(), language: { current: 'cn' },
}));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbum } }));
vi.mock('../../api/baipuApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/baipuApi')>();
  return { ...actual, BaipuAPI: { ...actual.BaipuAPI, load: baipuLoad }, cacheSgf };
});
vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: language.current,
    t: (key: string, fallback?: string) => ({
      'strength:dan': { cn: '段', en: 'dan', jp: '段' },
      'result:black_win': { cn: '黑胜', en: 'B+', jp: '黒勝' },
      'result:resign': { cn: '中盘', en: 'R', jp: '中押し' },
    } as Record<string, Record<string, string>>)[key]?.[language.current] ?? fallback ?? key,
  }),
}));

const RAW_SGF = '(;FF[4]GM[1]SZ[19]PB[原黑]PW[原白];B[pd])';
const detail = (lang: string) => ({
  id: 7, player_black: '原黑', player_white: '原白',
  display_player_black: `${lang}-black`, display_player_white: `${lang}-white`,
  black_rank: '9d', white_rank: '9d', event: '原赛事', display_event: `${lang}-event`,
  round_name: '原轮次', display_round_name: `${lang}-round`, sources: ['gokifu'],
  date_played: '2026-01-01', result: 'B+R', rules: 'chinese', komi: 7.5,
  handicap: 0, board_size: 19, move_count: 1, place: null, source: null, sgf_content: RAW_SGF,
});
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};
const page = () => <ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={['/kiosk/kifu/7']}><Routes><Route path="/kiosk/kifu/:kifuId" element={<KifuDetailPage />} /></Routes></MemoryRouter></ThemeProvider>;

beforeEach(() => {
  vi.clearAllMocks();
  language.current = 'cn';
  Element.prototype.scrollIntoView = vi.fn();
  getAlbum.mockImplementation((_id: number, lang: string) => Promise.resolve(detail(lang)));
  baipuLoad.mockResolvedValue({ board_size: 19, steps: [], meta: {} });
});

describe('kiosk 棋谱详情语言展示', () => {
  it('cn→en→jp 重取详情，题头和段位/结果同步变化，逐手读取原始 SGF', async () => {
    const view = render(page());
    for (const lang of ['cn', 'en', 'jp']) {
      if (lang !== 'cn') {
        language.current = lang;
        view.rerender(page());
      }
      await waitFor(() => expect(getAlbum).toHaveBeenLastCalledWith(7, lang));
      const hero = await screen.findByTestId('kifu-detail-hero');
      await waitFor(() => expect(hero).toHaveTextContent(`${lang}-black`));
      expect(hero).toHaveTextContent(`${lang}-white`);
      expect(hero).toHaveTextContent(lang === 'en' ? '9dan' : '9段');
      expect(hero).toHaveTextContent(lang === 'cn' ? '黑胜中盘' : lang === 'en' ? 'B+R' : '黒勝中押し');
      expect(screen.getByTestId('kifu-detail-pagebar')).toHaveTextContent(`${lang}-event · ${lang}-round`);
    }
    expect(baipuLoad).toHaveBeenLastCalledWith({ sgf: RAW_SGF });
    fireEvent.click(screen.getByRole('button', { name: '摆到实体盘' }));
    expect(cacheSgf).toHaveBeenCalledWith('kifu_7', expect.any(String), RAW_SGF);
  });

  it('旧语言慢响应不能覆盖新语言详情', async () => {
    const old = deferred<ReturnType<typeof detail>>();
    getAlbum.mockImplementation((_id: number, lang: string) => lang === 'cn' ? old.promise : Promise.resolve(detail(lang)));
    const view = render(page());
    language.current = 'en';
    view.rerender(page());
    expect(await screen.findByTestId('kifu-detail-hero')).toHaveTextContent('en-black');
    await act(async () => { old.resolve(detail('cn')); });
    expect(screen.getByTestId('kifu-detail-hero')).toHaveTextContent('en-black');
  });
});
