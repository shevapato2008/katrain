import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { __resetKioskActivityStorageForTests, setKioskIdentity } from '../storage/kioskActivityStorage';

const TEST_UUID = 'tsumego-page-test-user';

// 训练营的「上次」三样按账号存(N10)。盒上 token 恒为 null、身份在 user 上 —— 这里照盒上的样子造。
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, username: '甲', rank: '5段', credits: 0 }, isAuthenticated: true, token: null }),
}));

const mockLevels = [
  { level: '15k', categories: { capturing: 630, 'life-death': 167, tesuji: 139 }, total: 936 },
  { level: '14k', categories: { capturing: 295, semeai: 124 }, total: 419 },
  { level: '1k', categories: { 'life-death': 80, tesuji: 55 }, total: 135 },
  { level: '1d', categories: { 'life-death': 60, tesuji: 45 }, total: 105 },
];

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  __resetKioskActivityStorageForTests();
  setKioskIdentity(TEST_UUID, false);
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

const levelRows = () => Array.from(document.querySelectorAll<HTMLButtonElement>('.tsumego-level-row'));

describe('TsumegoPage · 屏 11 训练营', () => {
  it('问候行照稿子;副标说的是在哪儿做题都成立的那句,不说「题在实体盘上摆好」', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.querySelector('.kiosk-greet b')?.textContent).toBe('今天练点什么');
    });
    // 实体做题开关默认关、无摄像头的盒子根本没有实体盘 —— 稿子那句只在一种情况下成立(N26③)。
    expect(screen.getByText('落子即判，走错当场退回')).toBeInTheDocument();
    expect(screen.queryByText(/实体盘上摆好/)).toBeNull();
  });

  it('首页只让人先选难度，不再把某一档的题型提前放在难度前面', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('按棋力选择')).toBeInTheDocument());
    expect(levelRows().map((row) => row.querySelector('b')?.textContent)).toEqual(['15 级', '14 级', '1 级', '1 段']);
    expect(screen.queryByText('死活')).toBeNull();
    expect(screen.queryByText('按分类')).toBeNull();
  });

  it('每档一行显示题量和真实分类分布，不编这一档的完成百分比', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    expect(screen.getByText('936 题')).toBeInTheDocument();
    expect(screen.getByText('419 题')).toBeInTheDocument();
    expect(levelRows()[0].querySelectorAll('.tsumego-level-row__mix i')).toHaveLength(3);
    expect(document.querySelector('.kiosk-card__tile.is-ring')).toBeNull();
  });

  it('级位和段位之间有一条明确分界', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('1K → 1D')).toBeInTheDocument());
    const seam = document.querySelector('.tsumego-level-seam')!;
    expect(seam.previousElementSibling).toHaveTextContent('1 级');
    expect(seam.nextElementSibling).toHaveTextContent('1 段');
  });

  it('上次练习的难度标成「你的水平」，题型指针不在这一层出现', async () => {
    localStorage.setItem(`kiosk_tsumego_last_level:${TEST_UUID}`, '14k');
    localStorage.setItem(`kiosk_tsumego_last_category:${TEST_UUID}`, 'semeai');
    renderPage();
    await waitFor(() => expect(screen.getByText('你的水平')).toBeInTheDocument());
    const current = document.querySelector('.tsumego-level-row.is-current');
    expect(current).toHaveTextContent('14 级');
    expect(screen.queryByText('对杀')).toBeNull();
  });

  it('点一级先进入该级的题型页', async () => {
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
    expect(levelRows()).toHaveLength(0);
  });

  it('读不到时写出原因，并且给得起一次重试', async () => {
    const user = userEvent.setup();
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 500, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('tsumego-error')).toBeInTheDocument());
    expect(within(screen.getByTestId('tsumego-error')).getByText(/HTTP 500/)).toBeInTheDocument();
    // 重试真的再打一次接口,而且第二次成功就该看见难度行 —— 否则「重试」只是个装饰。
    await user.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('题库真是空的时候说「还没有题」,不说「随云端同步下来」—— 盒上题库是在线直读的,没有同步', async () => {
    (global.fetch as any).mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('tsumego-empty')).toBeInTheDocument());
    expect(screen.getByText('题库里还没有题')).toBeInTheDocument();
    expect(screen.queryByText(/随云端同步/)).toBeNull();
    expect(screen.queryByTestId('tsumego-error')).toBeNull();
  });

  it('连不上云端(503)时说「连不上云端题库」,不说「没有题」,重试键还在', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    renderPage();
    const box = await screen.findByTestId('tsumego-error');
    expect(within(box).getByText('连不上云端题库')).toBeInTheDocument();
    expect(within(box).getByText('题库在云端，盒子上不存题。等网络或云端恢复后再点重试。')).toBeInTheDocument();
    expect(within(box).getByRole('button', { name: '重试' })).toBeInTheDocument();
    expect(screen.queryByTestId('tsumego-empty')).toBeNull();
  });

  it('有未完成的练习才出「接着上次」', async () => {
    localStorage.setItem(
      `kiosk_tsumego_resume:${TEST_UUID}`,
      JSON.stringify({ label: '15 级 · 吃子 · 第 1 题', route: '/kiosk/tsumego/problem/p12' })
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('接着上次')).toBeInTheDocument();
      expect(screen.getByText('15 级 · 吃子 · 第 1 题')).toBeInTheDocument();
    });
  });

  it('没有未完成的练习时整块不渲染，不留占位', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    expect(screen.queryByTestId('tsumego-resume-card')).toBeNull();
  });

  it('别人的「上次」不串过来:另一个账号存下的三样,这个账号一样都看不见', async () => {
    localStorage.setItem('kiosk_tsumego_last_level:another-user', '14k');
    localStorage.setItem(
      'kiosk_tsumego_resume:another-user',
      JSON.stringify({ label: '14 级 · 对杀 · 第 3 题', route: '/kiosk/tsumego/problem/x' })
    );
    // 2026-09-14 之前那几把不分人的旧钥匙:没有主人,不迁移、不再读。
    localStorage.setItem('kiosk_tsumego_last_level', '14k');
    localStorage.setItem('kiosk_active_practice', JSON.stringify({ kind: 'practice', label: '旧的', route: '/x', ts: 1 }));
    renderPage();
    await waitFor(() => expect(screen.getByText('15 级')).toBeInTheDocument());
    expect(screen.queryByTestId('tsumego-resume-card')).toBeNull();
    expect(document.querySelectorAll('.tsumego-level-row.is-current')).toHaveLength(0);
  });
});
