import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

/**
 * 屏 11 · 训练营。**文案在 2026-08-22 按稿子整屏换过**(Task 12),所以这一份的断言
 * 和上一版对不上是预期的 —— 上一版断的是 `死活题 / 选择难度级别 / 15K / 手筋: 139`,
 * 那是 MUI 卡片时代的标题栏 + 分类计数条,稿子上没有这两样。
 *
 * 分类 key 用的是**题库真的会返回的那六个**(`life-death` / `capturing` / …)。
 * 上一版 fixture 里写的是中文键(`{ '手筋': 139 }`)—— 后端 `TsumegoProblem.category`
 * 存的是英文 slug,那份 fixture 描述的是一个不存在的后端。
 */

const mockLevels = [
  { level: '15k', categories: { capturing: 630, 'life-death': 167, tesuji: 139 }, total: 936 },
  { level: '14k', categories: { capturing: 295, semeai: 124 }, total: 419 },
];

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockLevels),
  }) as any;
});

import TsumegoPage from '../pages/TsumegoPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/tsumego']}>
        <Routes>
          <Route path="/kiosk/tsumego" element={<TsumegoPage />} />
          <Route path="*" element={<Landed />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** 落点探针:断言**落在哪条路由上**,不是「落在别处了」—— 后者对「进错了一屏」免疫。 */
const Landed = () => <div data-testid="landed">{useLocation().pathname}</div>;

/** 一张卡的可读身份 = 标题 + 副标(`KioskCard` 把它们放在 `.kiosk-card__t` 里)。 */
const cardTitles = () =>
  Array.from(document.querySelectorAll('.kiosk-card__t > b')).map(n => n.textContent);

describe('TsumegoPage · 屏 11 训练营', () => {
  it('问候行和副标照稿子', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.querySelector('.kiosk-greet b')?.textContent).toBe('今天练点什么');
    });
    expect(screen.getByText('题在实体盘上摆好，落子即判')).toBeInTheDocument();
  });

  it('按分类:题库返回哪几类就画哪几类，顺序照稿子那六张', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('死活')).toBeInTheDocument());
    // fixture 给的是 capturing / life-death / tesuji,后端返回顺序是乱的;
    // 屏上必须是稿子那六张的相对次序 —— 死活 → 手筋 → 吃子。
    expect(cardTitles().slice(0, 3)).toEqual(['死活', '手筋', '吃子']);
    expect(screen.getByText('怎么把子吃下来')).toBeInTheDocument();
  });

  it('分类那一排写明它属于哪一档 —— 不让人对着卡猜作用域', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级 · 3 类')).toBeInTheDocument());
  });

  it('上次做的那一档决定分类的作用域，不是恒取最弱那档', async () => {
    localStorage.setItem('kiosk_tsumego_last_level', '14k');
    renderPage();
    await waitFor(() => expect(screen.getByText('14 级 · 2 类')).toBeInTheDocument());
    // 14 级只有 capturing / semeai 两类 —— 15 级才有的「死活」不许出现在这一排。
    // 次序照稿子那六张(死活 / 手筋 / 对杀 / 吃子 / 官子 / 布局),对杀在吃子前面。
    expect(cardTitles().slice(0, 2)).toEqual(['对杀', '吃子']);
  });

  it('按级别:每档一张环卡，环里写「—」不写 0%', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    const rings = Array.from(document.querySelectorAll('.kiosk-card__tile.is-ring'));
    expect(rings).toHaveLength(2);
    // 「—」= 这一层算不出;`0%` 是一个事实断言,而我们并不知道(G8)。
    expect(rings.map(r => r.querySelector('b')?.textContent)).toEqual(['—', '—']);
    // 进度圈只在有值时画;两张都只该有底圈一个 circle。
    expect(rings.every(r => r.querySelectorAll('circle').length === 1)).toBe(true);
    expect(screen.getByText('936 题')).toBeInTheDocument();
    expect(screen.getByText('419 题')).toBeInTheDocument();
    expect(screen.getByText('15 级 → 14 级')).toBeInTheDocument();
  });

  it('读屏拿到的级别卡也带着「进度未知」，不只是一个题量', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: '15 级，936 题，进度未知' })).toBeInTheDocument();
  });

  it('上次那一档和上次那一类各自高亮，互不冒充', async () => {
    localStorage.setItem('kiosk_tsumego_last_level', '14k');
    localStorage.setItem('kiosk_tsumego_last_category', 'semeai');
    renderPage();
    await waitFor(() => expect(screen.getByText('对杀')).toBeInTheDocument());
    const current = Array.from(document.querySelectorAll('.kiosk-card.is-current'));
    expect(current.map(c => c.querySelector('.kiosk-card__t > b')?.textContent))
      .toEqual(['对杀', '14 级']);
  });

  it('分类卡进的是「这一档 + 这一类」', async () => {
    const user = userEvent.setup();
    localStorage.setItem('kiosk_tsumego_last_level', '14k');
    renderPage();
    await waitFor(() => expect(screen.getByText('对杀')).toBeInTheDocument());
    await user.click(screen.getByText('对杀').closest('button')!);
    // 级别取的是作用域那一档(14k),不是恒定的第一档 —— 写死 15k 的实现也能让上一版断言通过。
    expect(screen.getByTestId('landed')).toHaveTextContent('/kiosk/tsumego/14k/semeai');
  });

  it('级别卡进的是这一档的分类页', async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(screen.getByText('14 级')).toBeInTheDocument());
    await user.click(screen.getByText('14 级').closest('button')!);
    expect(screen.getByTestId('landed')).toHaveTextContent('/kiosk/tsumego/14k');
  });

  it('加载中说的是加载中,不是「一道题都没有」', () => {
    renderPage();
    expect(screen.getByTestId('tsumego-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('tsumego-empty')).toBeNull();
    expect(document.querySelector('.kiosk-card')).toBeNull();
  });

  it('读不到时写出原因，并且给得起一次重试', async () => {
    const user = userEvent.setup();
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 500, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('tsumego-error')).toBeInTheDocument());
    expect(within(screen.getByTestId('tsumego-error')).getByText(/HTTP 500/)).toBeInTheDocument();
    // 重试真的再打一次接口,而且第二次成功就该看见卡 —— 否则「重试」只是个装饰。
    await user.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(screen.getByText('死活')).toBeInTheDocument());
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('题库是空的时候说的是「还没同步」,不是「读不到」', async () => {
    (global.fetch as any).mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('tsumego-empty')).toBeInTheDocument());
    expect(screen.queryByTestId('tsumego-error')).toBeNull();
  });

  it('有未完成的练习才出「接着上次」', async () => {
    localStorage.setItem(
      'kiosk_active_practice',
      JSON.stringify({ kind: 'practice', label: '15 级 · 吃子 · 第 1 题', route: '/kiosk/tsumego/problem/p12', ts: Date.now() })
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('接着上次')).toBeInTheDocument();
      expect(screen.getByText('15 级 · 吃子 · 第 1 题')).toBeInTheDocument();
    });
  });

  it('没有未完成的练习时整块不渲染，不留占位', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('死活')).toBeInTheDocument());
    expect(screen.queryByTestId('tsumego-resume-card')).toBeNull();
  });
});
