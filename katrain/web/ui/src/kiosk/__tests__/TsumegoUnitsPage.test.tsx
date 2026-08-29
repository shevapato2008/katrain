import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { sequenceKey, UNIT_SIZE } from '../pages/tsumegoUnits';
import type { TsumegoProgressEntry } from '../../context/TsumegoProgressContext';

/**
 * 屏 12 · 单元列表。**文案在 2026-08-22 按稿子整屏换过**(Task 13),所以和上一版对不上是预期的:
 * 上一版断的是 `单元 1 / 1–20 / 20/20 / 转圈 / 返回`,那是 MUI 卡片时代的样子。
 * 稿子上是 `第 1 单元 / 第 1-20 题 / 进度环 0% / 「正在读题库」/ 返回键写「训练营」`。
 *
 * 留下来的是**契约**,不是文案:`?limit=1000` 那一次取、按 20 分组、顺序表写进 sessionStorage、
 * 点哪张进哪一单元、`unitProgress` 按片调用。
 */

const { mockNavigate, mockUnitProgress, progressMap } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockUnitProgress: vi.fn(() => ({ completed: 0, total: 0 })),
  progressMap: {} as Record<string, TsumegoProgressEntry>,
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: progressMap,
    markProgress: vi.fn(),
    isCompleted: (id: string) => !!progressMap[id]?.completed,
    unitProgress: mockUnitProgress,
    categoryProgress: () => ({ completed: 0, total: 0 }),
    refresh: vi.fn(),
  }),
}));

// 45 道题 → ceil(45/20) = 3 个单元(20 / 20 / 5)。
const TOTAL = 45;
const allIds = Array.from({ length: TOTAL }, (_, i) => ({ id: `q${i}` }));

const installFetch = (data: { id: string }[] = allIds) => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(data) }) as any;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUnitProgress.mockReturnValue({ completed: 0, total: 0 });
  for (const k of Object.keys(progressMap)) delete progressMap[k];
  sessionStorage.clear();
  localStorage.clear();
  installFetch();
});

import TsumegoUnitsPage from '../pages/TsumegoUnitsPage';

const renderPage = (level = '15k', category = 'capturing') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/:level/:category" element={<TsumegoUnitsPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

const cardTitles = () =>
  Array.from(document.querySelectorAll('.kiosk-card__t > b')).map((n) => n.textContent);
const rings = () =>
  Array.from(document.querySelectorAll('.kiosk-card__tile.is-ring b')).map((n) => n.textContent);

describe('TsumegoUnitsPage · 屏 12 单元列表', () => {
  it('页控条:标题是「这一档 · 这一类」,返回键回训练营', async () => {
    renderPage('15k', 'capturing');
    await waitFor(() => expect(screen.getByText('15 级 · 吃子')).toBeInTheDocument());
    fireEvent.click(screen.getByText('训练营'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k');
  });

  it('整类题号只取一次(limit=1000),并按顺序写进 sessionStorage —— 做题屏的上/下一题靠它', async () => {
    renderPage('15k', 'capturing');
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories/capturing?limit=1000',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    });
    await waitFor(() => {
      const raw = sessionStorage.getItem(sequenceKey('15k', 'capturing'));
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      expect(parsed).toHaveLength(TOTAL);
      expect(parsed[0]).toBe('q0');
      expect(parsed[TOTAL - 1]).toBe('q44');
    });
  });

  it('按 20 分组:45 道 → 三个单元,最后一个是 5 道', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
    expect(cardTitles().slice(0, 3)).toEqual(['第 1 单元', '第 2 单元', '第 3 单元']);
    expect(screen.getByText('第 41-45 题')).toBeInTheDocument();
    expect(cardTitles()).not.toContain('第 4 单元');
    const calls = mockUnitProgress.mock.calls as unknown as string[][];
    expect(calls.some((c) => (c[0] as unknown as string[]).length === UNIT_SIZE)).toBe(true);
    expect(calls.some((c) => (c[0] as unknown as string[]).length === TOTAL % UNIT_SIZE)).toBe(true);
  });

  it('环里写的是真 0%,不是「—」—— 这一层算得出进度,和训练营那一屏不是一回事', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
    // 前三张是单元环卡;「整级一起做」那两张不是环卡,不该混进来。
    expect(rings()).toEqual(['0%', '0%', '0%']);
    expect(rings()).not.toContain('—');
  });

  it('做完的单元环走到 100%,而且底圈之外真的画了那一圈', async () => {
    mockUnitProgress.mockImplementation((ids: string[]) => ({ completed: ids.length, total: ids.length }));
    renderPage();
    await waitFor(() => expect(rings()[0]).toBe('100%'));
    const tile = document.querySelector('.kiosk-card__tile.is-ring')!;
    // 底圈 + 进度圈 = 2;只有一个 circle 就是「写着 100% 但没画」。
    expect(tile.querySelectorAll('circle')).toHaveLength(2);
  });

  it('点一张单元卡进那一单元', async () => {
    renderPage('15k', 'capturing');
    await waitFor(() => expect(screen.getByText('第 41-45 题')).toBeInTheDocument());
    fireEvent.click(screen.getByText('第 41-45 题').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing/3');
  });

  it('「当前单元」是第一个没做完的,不是恒定的第 1 单元', async () => {
    // 第 1 单元全做完,第 2 单元做了 3 道。
    mockUnitProgress.mockImplementation((ids: string[]) => ({
      completed: ids.filter((id) => progressMap[id]?.completed).length,
      total: ids.length,
    }));
    for (let i = 0; i < 23; i += 1) progressMap[`q${i}`] = { completed: true, attempts: 1 };
    renderPage();
    await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
    const start = screen.getByTestId('units-start');
    expect(within(start).getByText('开始 · 第 2 单元')).toBeInTheDocument();
    // 第 2 单元的下一道没做的是全类第 24 题(q23)。
    expect(within(start).getByText('15 级 · 吃子 · 第 24 题')).toBeInTheDocument();
    // 高亮也跟着走。
    const current = document.querySelector('.kiosk-card.is-current .kiosk-card__t > b');
    expect(current?.textContent).toBe('第 2 单元');
  });

  it('数据条三格全是真数,分母写在值里不写在标签里', async () => {
    mockUnitProgress.mockImplementation((ids: string[]) => ({
      completed: ids.filter((id) => progressMap[id]?.completed).length,
      total: ids.length,
    }));
    for (let i = 0; i < 3; i += 1) progressMap[`q${i}`] = { completed: true, attempts: 1 };
    localStorage.setItem('kiosk_tsumego_autoadvance', 'false');
    renderPage();
    await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
    const stats = Array.from(document.querySelectorAll('.kiosk-stat')).map((s) => [
      s.querySelector('.kiosk-stat__v')?.textContent,
      s.querySelector('.kiosk-stat__k')?.textContent,
    ]);
    expect(stats).toEqual([
      ['20', '每单元题数 · 当前'],
      ['3 / 20', '本单元已做对'],
      ['关', '做对后自动下一题 · 当前'],
    ]);
  });

  it('「只做错过的」按不动,但道数是真的 —— 算得出来、没地方去,两件事都说出来', async () => {
    progressMap['q0'] = { completed: false, attempts: 2 };
    progressMap['q5'] = { completed: false, attempts: 1 };
    progressMap['q7'] = { completed: true, attempts: 3 };   // 做对了,不算错题
    progressMap['q9'] = { completed: false, attempts: 0 };  // 没试过,也不算
    renderPage();
    await waitFor(() => expect(screen.getByText('只做错过的')).toBeInTheDocument());
    const card = screen.getByText('只做错过的').closest('button') as HTMLButtonElement;
    expect(within(card).getByText('现在有 2 道')).toBeInTheDocument();
    expect(within(card).getByText('还没接')).toBeInTheDocument();
    expect(card.disabled).toBe(true);
  });

  it('「整级一起做」进的是这一档的全部题', async () => {
    renderPage('3d', 'capturing');
    await waitFor(() => expect(screen.getByText('3 段全部')).toBeInTheDocument());
    fireEvent.click(screen.getByText('3 段全部').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/3d/all');
  });

  it('进了这一类就记下来 —— 训练营那一排的高亮靠它', async () => {
    renderPage('15k', 'semeai');
    await waitFor(() => expect(localStorage.getItem('kiosk_tsumego_last_category')).toBe('semeai'));
  });

  it('加载中说的是加载中,不是「这一类没有题」', () => {
    renderPage();
    expect(screen.getByTestId('units-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('units-empty')).toBeNull();
    expect(document.querySelector('.kiosk-card')).toBeNull();
  });

  it('读不到时写出原因,并且给得起一次重试', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('units-error')).toBeInTheDocument());
    expect(within(screen.getByTestId('units-error')).getByText(/HTTP 404/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(screen.getByText('第 1-20 题')).toBeInTheDocument());
  });

  it('这一类真的一道题都没有时,说的是「还没有题」不是「读不到」', async () => {
    installFetch([]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId('units-empty')).toBeInTheDocument());
    expect(screen.queryByTestId('units-error')).toBeNull();
  });
});
