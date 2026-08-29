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
 * 断言五件事:
 *   ① **登录段的目标是推出来的**:显示顺序里第一个「可登录且未连接」的家。
 *      写死成 golaxy 的实现在这条上会红(变异:让星阵也连上 ⇒ 目标必须换人)。
 *   ② **三家全连上 ⇒ 整段不渲染**;两家未连接**仍然只有一段**。
 *   ③ **字段跟着平台换**:OGS 用户名 + 密码(不给「获取验证码」),星阵手机号 + 验证码。
 *   ④ **野狐那行行尾只有一枚标、没有按钮**,而且判别位是 `PLATFORM_META.comingSoon`
 *      那个真标记,不是平台名字符串。
 *   ⑤ **登出走一次确认**:取消不发请求。
 */

const { platformStatus, platformLogin, platformLogout, platformSmsRequest } = vi.hoisted(() => ({
  platformStatus: vi.fn(),
  platformLogin: vi.fn(),
  platformLogout: vi.fn(),
  platformSmsRequest: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformStatus, platformLogin, platformLogout, platformSmsRequest } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' } }) }));
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
  platformLogin.mockResolvedValue({});
  platformLogout.mockResolvedValue({});
  platformSmsRequest.mockResolvedValue({});
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

  it('登录段的目标是推出来的:OGS 已连、野狐 comingSoon ⇒ 落到星阵', async () => {
    renderPage();
    expect(await screen.findByTestId('platform-login-section')).toHaveTextContent('登录 · 星阵围棋');
  });

  /** 一家可登录的都不剩 ⇒ 整段不渲染。**写死 golaxy 的实现在这条上会红。** */
  it('能登的都连上了:登录段整个不渲染,不留一句「都连上了」', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', true), row('golaxy', true), row('fox', false)],
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('platform-row')).toHaveLength(3));
    expect(screen.queryAllByTestId('platform-login-section')).toHaveLength(0);
  });

  it('两家都没连:仍然只有一段,点谁那一段就换成谁', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', false), row('golaxy', false), row('fox', false)],
    });
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    expect(section).toHaveTextContent('登录 · OGS');
    expect(screen.getAllByTestId('platform-login-section')).toHaveLength(1);

    await userEvent.click(within(rowOf('星阵围棋')).getByRole('button', { name: '登录' }));
    await waitFor(() => expect(screen.getByTestId('platform-login-section'))
      .toHaveTextContent('登录 · 星阵围棋'));
    expect(screen.getAllByTestId('platform-login-section'), '叠出了第二段').toHaveLength(1);
  });

  it('星阵那条路是手机号 + 验证码', async () => {
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    expect(within(section).getByLabelText('手机号')).toBeInTheDocument();
    expect(within(section).getByTestId('platform-sms')).toHaveTextContent('获取验证码');

  });

  it('OGS 那条路是用户名 + 密码,没有「获取验证码」', async () => {
    platformStatus.mockResolvedValue({
      platforms: [row('ogs', false), row('golaxy', true), row('fox', false)],
    });
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    expect(section).toHaveTextContent('登录 · OGS');
    expect(within(section).getByLabelText('用户名')).toBeInTheDocument();
    // 密码那条路没有短信键 —— 摆一颗按下去没有后端的键,比不摆更糟。
    expect(within(section).queryByTestId('platform-sms')).not.toBeInTheDocument();
  });

  it('星阵登录发的是 sms_code,不是 password', async () => {
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    await userEvent.type(within(section).getByTestId('platform-login-user'), '13800000000');
    await userEvent.type(within(section).getByTestId('platform-login-pass'), '123456');
    await userEvent.click(within(section).getByTestId('platform-login-submit'));
    await waitFor(() => expect(platformLogin).toHaveBeenCalledWith(
      'golaxy', { username: '13800000000', sms_code: '123456' }, 'tok',
    ));
  });

  it('没填手机号就点「获取验证码」:说出来,不发请求', async () => {
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    await userEvent.click(within(section).getByTestId('platform-sms'));
    expect(await screen.findByTestId('platform-login-error')).toHaveTextContent('请先输入手机号');
    expect(platformSmsRequest).not.toHaveBeenCalled();
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

  it('填了手机号点「获取验证码」:发出去,并进入 60 秒倒计时', async () => {
    renderPage();
    const section = await screen.findByTestId('platform-login-section');
    await userEvent.type(within(section).getByTestId('platform-login-user'), '13800000000');
    await userEvent.click(within(section).getByTestId('platform-sms'));
    await waitFor(() => expect(platformSmsRequest).toHaveBeenCalledWith('golaxy', '13800000000', 'tok'));
    // 倒计时期间不许再点 —— 连点会把那边的短信配额打光。
    await waitFor(() => expect(within(section).getByTestId('platform-sms')).toBeDisabled());
    expect(within(section).getByTestId('platform-sms')).toHaveTextContent('秒后可重发');
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
