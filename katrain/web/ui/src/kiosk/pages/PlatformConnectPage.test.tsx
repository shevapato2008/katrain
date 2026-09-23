import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformConnectPage from './PlatformConnectPage';

/**
 * 屏 07 跨平台 · 连接的**行为**那一半。版式归四图,一条几何都不断言;
 * 「软键盘会不会盖住输入框」归真浏览器那条承重闸。
 *
 * 2026-09-23(Task 5):登录改成独立成页(`PlatformLoginPage`),这一屏自己不再有
 * 登录表单 —— 相应地,原来断言字段/验证码/登录提交的用例都搬到
 * `PlatformLoginPage.test.tsx` 里去了,这里只留「登录」按钮跳对了地方。
 *
 * 断言四件事:
 *   ① **点「登录」跳到那一家的登录页**,不再是在本屏展开一段表单。
 *   ② **野狐那行行尾只有一枚标、没有按钮**,而且判别位是 `PLATFORM_META.comingSoon`
 *      那个真标记,不是平台名字符串。
 *   ③ **登出走一次确认**:取消不发请求。
 *   ④ 能力标 / 已连接跳转 / 问不到 `/platforms` 时的降级行为不变。
 */

const { platformStatus, platformLogout } = vi.hoisted(() => ({
  platformStatus: vi.fn(),
  platformLogout: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformStatus, platformLogout } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' }, isAuthenticated: true }) }));
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const row = (platform: string, connected: boolean, extra: Record<string, unknown> = {}) => ({
  platform,
  connected,
  supports_live_play: true,
  supports_automatch: platform === 'ogs',
  supports_rooms: platform !== 'ogs',
  supports_seek_graph: platform === 'ogs',
  supports_engine_play: platform === 'golaxy',
  ...extra,
});

/** 稿子那一帧:OGS 已连、星阵未连、野狐 comingSoon。 */
const DRAFT_STATE = {
  platforms: [
    row('ogs', true, { saved_username: 'stellabox' }),
    row('golaxy', false),
    row('fox', false),
  ],
};

const renderPage = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter><PlatformConnectPage /></MemoryRouter>
  </ThemeProvider>,
);

const rowOf = (name: string) =>
  screen.getAllByTestId('platform-row').find((r) => within(r).queryByText(name))!;

beforeEach(() => {
  vi.clearAllMocks();
  platformStatus.mockResolvedValue(DRAFT_STATE);
  platformLogout.mockResolvedValue({});
});

describe('屏 07 跨平台 · 连接', () => {
  it('三家按目录顺序排:能用的在前,「即将上线」在最后', async () => {
    // 后端注册序是 ogs → fox → golaxy,直接 map 会让野狐夹在中间。
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', true), row('fox', false), row('golaxy', false)],
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    const names = screen.getAllByTestId('platform-row').map((r) => r.querySelector('b')!.textContent);
    expect(names).toEqual(['OGS', '星阵围棋', '野狐围棋']);
  });

  it('点「登录」跳到那一家的登录页,不再展开页内表单', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', false), row('golaxy', false), row('fox', false)],
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    // 登录段这一版已经整个撤掉 —— 撤页内登录表单是这一版的重点,漏了这条断言就等于没测。
    expect(screen.queryByTestId('platform-login-section')).not.toBeInTheDocument();

    await userEvent.click(within(rowOf('星阵围棋')).getByRole('button', { name: '登录' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/golaxy');

    await userEvent.click(within(rowOf('OGS')).getByRole('button', { name: '登录' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/login/ogs');
  });

  it('野狐那行只有一枚标、没有按钮;判别位是 comingSoon 不是平台名', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    const fox = rowOf('野狐围棋');
    const end = fox.querySelector('.kiosk-row__end')!;
    expect(end.querySelectorAll('button')).toHaveLength(0);
    expect(end).toHaveTextContent('暂不能对弈');
    // 「即将上线」是预测不是状态 —— 挡路的那件事没人给过日期。
    expect(document.body.textContent).not.toContain('即将上线');
  });

  it('已连接那行:标上带账号名,登出和进入大厅都在行尾', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    const ogs = rowOf('OGS');
    expect(ogs).toHaveTextContent('已连接 · stellabox');
    expect(within(ogs).getByRole('button', { name: '登出' })).toBeInTheDocument();
    expect(within(ogs).getByRole('button', { name: '进入大厅' })).toBeInTheDocument();
    // 星阵 supports_engine_play ⇒ 它连上之后进的是人机开局,不是大厅。
    expect(within(ogs).queryByRole('button', { name: '人机对弈' })).not.toBeInTheDocument();
  });

  // 从 `__tests__/PlatformConnectPage.test.tsx` 吸收过来的两条(那份已删,见下方注释)。
  it('已连接那行点进去:有引擎的进人机开局,没有的进大厅', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', true), row('golaxy', true), row('fox', false)],
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));

    await userEvent.click(within(rowOf('OGS')).getByRole('button', { name: '进入大厅' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/lobby?platform=ogs');

    await userEvent.click(within(rowOf('星阵围棋')).getByRole('button', { name: '人机对弈' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/golaxy');
  });

  it('返回键回对弈首页', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    await userEvent.click(screen.getByRole('button', { name: /返回对弈/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play');
  });

  it('登出走一次确认:取消不发请求,确认才发', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    await userEvent.click(within(rowOf('OGS')).getByRole('button', { name: '登出' }));

    const dlg = await screen.findByTestId('platform-logout-confirm');
    expect(dlg).toHaveTextContent('断开 OGS？');
    await userEvent.click(within(dlg).getByRole('button', { name: '取消' }));
    expect(platformLogout).not.toHaveBeenCalled();

    await userEvent.click(within(rowOf('OGS')).getByRole('button', { name: '登出' }));
    await userEvent.click(await screen.findByTestId('platform-logout-confirm-action'));
    await waitFor(() => expect(platformLogout).toHaveBeenCalledWith('ogs', 'tok'));
  });

  it('能力标照下发原样渲染 —— 前端不修正', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', true), row('golaxy', false), { ...row('fox', false), supports_rooms: false }],
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    const foxCaps = rowOf('野狐围棋').querySelector('.caps')!;
    const rooms = within(foxCaps as HTMLElement).getByText('房间');
    expect(rooms.className, '下发说没有「房间」,屏上却把它点亮了').not.toContain('on');
  });

  it('问不到 /platforms:能力标全暗、行尾只给登录 —— 不伪造乐观默认', async () => {
    platformStatus.mockRejectedValue(new Error('boom'));
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    const ogsCaps = rowOf('OGS').querySelector('.caps')!;
    expect(ogsCaps.querySelectorAll('.on')).toHaveLength(0);
    expect(within(rowOf('OGS')).getByRole('button', { name: '登录' })).toBeInTheDocument();
  });
});
