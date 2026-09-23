import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformLoginPage from './PlatformLoginPage';
import { KioskRoutes } from '../KioskApp';

/**
 * 登录独立成页(屏 07b/08)的**行为**那一半。版式归四图(Task 5 这一轮不建,详见
 * `task-5-report.md`),软键盘避让归 `kiosk-geometry-platform.spec.ts` 那条真浏览器闸。
 *
 * 断言:
 *   ① 星阵两个标签(验证码/密码),默认密码;OGS 没有标签栏(单一登录方式)。
 *   ② 字段跟着平台/标签换,提交发对了字段名(`password` vs `sms_code`)。
 *   ③ 登录失败时把平台给的话原样显示,不换成自己编的(`platformErrorMessage`)。
 *   ④ 左栏那几条 fact 按平台换(`PlatformLoginAside`,由 `LOGIN_FACTS` 推导)。
 *   ⑤ **登录成功后的目标路由在当前这一版里真的存在**(`KioskRoutes`,真 Router,
 *      不是 mock 掉 navigate 断言字符串)。
 */

const { platformLogin, platformSmsRequest, platformEngineLevels, platformStatus } = vi.hoisted(() => ({
  platformLogin: vi.fn(),
  platformSmsRequest: vi.fn(),
  platformEngineLevels: vi.fn(),
  // `PlayPage` 是「登录成功后目标路由真的存在」那条用真 `KioskRoutes` 时的兜底目的地 ——
  // 只有在那条测试里目标路由**没**匹配上才会渲染到它,而它挂载时会调这个;
  // 不 mock 的话失败信息会是一条无关的 TypeError,盖住真正的断言失败。
  platformStatus: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformLogin, platformSmsRequest, platformEngineLevels, platformStatus } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' }, isAuthenticated: true, isLoading: false }),
}));
// 只有「真 Router 证明目标路由存在」那一条会真的挂载 `PlatformEngineSetupPage`,
// 它用 `useVision()` —— 其余用例都不碰这个 context,mock 放这里对它们零影响。
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ visionStatus: { enabled: false }, isVisionEnabled: false, refreshStatus: vi.fn() }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  platformLogin.mockResolvedValue({});
  platformSmsRequest.mockResolvedValue({});
  platformEngineLevels.mockResolvedValue({ levels: [] });
  platformStatus.mockResolvedValue({ platforms: [] });
});

/** 真 `<Route>`,不 mock `useNavigate` —— 用一个探针路由把导航结果读出来,
 * 比断言「我调了这个字符串」更硬:探针路由真的要匹配得上才会渲染。 */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="__loc">{location.pathname}{location.search}</div>;
}

const renderLogin = (platform: string) => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[`/kiosk/play/cross-platform/login/${platform}`]}>
      <Routes>
        <Route path="/kiosk/play/cross-platform/login/:platform" element={<PlatformLoginPage />} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
);

describe('登录独立成页', () => {
  it('星阵默认密码标签,两个标签都在(R-19:这一轮只出验证码/密码,不出扫码)', async () => {
    renderLogin('golaxy');
    const tabs = await screen.findByTestId('login-mode-tabs');
    expect(within(tabs).getByRole('button', { name: '验证码' })).toBeInTheDocument();
    const pwTab = within(tabs).getByRole('button', { name: '密码' });
    expect(pwTab).toHaveAttribute('aria-pressed', 'true');
    // 默认就是密码字段(type=password),不是验证码字段。
    expect(screen.getByTestId('login-field-password')).toHaveAttribute('type', 'password');
  });

  it('OGS 只有一种登录方式,标签栏整条不渲染', async () => {
    renderLogin('ogs');
    await screen.findByTestId('login-field-user');
    expect(screen.queryByTestId('login-mode-tabs')).not.toBeInTheDocument();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    expect(screen.getByTestId('login-field-password')).toHaveAttribute('type', 'password');
  });

  it('切到验证码标签:手机号 + 验证码字段,出现「获取验证码」', async () => {
    renderLogin('golaxy');
    const tabs = await screen.findByTestId('login-mode-tabs');
    await userEvent.click(within(tabs).getByRole('button', { name: '验证码' }));
    expect(screen.getByTestId('login-field-password')).toHaveAttribute('type', 'text');
    expect(screen.getByTestId('login-sms-request')).toHaveTextContent('获取验证码');
  });

  it('星阵密码模式提交发 password,不是 sms_code', async () => {
    renderLogin('golaxy');
    await screen.findByTestId('login-field-user');
    await userEvent.type(screen.getByTestId('login-field-user'), '13800000000');
    await userEvent.type(screen.getByTestId('login-field-password'), 'secret123');
    await userEvent.click(screen.getByTestId('login-submit'));
    await waitFor(() => expect(platformLogin).toHaveBeenCalledWith(
      'golaxy', { username: '13800000000', password: 'secret123' }, 'tok',
    ));
  });

  it('星阵验证码模式提交发 sms_code,不是 password', async () => {
    renderLogin('golaxy');
    const tabs = await screen.findByTestId('login-mode-tabs');
    await userEvent.click(within(tabs).getByRole('button', { name: '验证码' }));
    await userEvent.type(screen.getByTestId('login-field-user'), '13800000000');
    await userEvent.type(screen.getByTestId('login-field-password'), '123456');
    await userEvent.click(screen.getByTestId('login-submit'));
    await waitFor(() => expect(platformLogin).toHaveBeenCalledWith(
      'golaxy', { username: '13800000000', sms_code: '123456' }, 'tok',
    ));
  });

  it('没填手机号就点「获取验证码」:说出来,不发请求', async () => {
    renderLogin('golaxy');
    const tabs = await screen.findByTestId('login-mode-tabs');
    await userEvent.click(within(tabs).getByRole('button', { name: '验证码' }));
    await userEvent.click(screen.getByTestId('login-sms-request'));
    expect(await screen.findByTestId('login-error')).toHaveTextContent('请先输入手机号');
    expect(platformSmsRequest).not.toHaveBeenCalled();
  });

  it('登录失败:把平台给的话原样显示,不换成自己编的', async () => {
    platformLogin.mockRejectedValue({ status: 409, detail: '这台盒子上现在连着别人的星阵账号' });
    renderLogin('golaxy');
    await screen.findByTestId('login-field-user');
    await userEvent.type(screen.getByTestId('login-field-user'), '13800000000');
    await userEvent.type(screen.getByTestId('login-field-password'), 'secret123');
    await userEvent.click(screen.getByTestId('login-submit'));
    expect(await screen.findByTestId('login-error')).toHaveTextContent('这台盒子上现在连着别人的星阵账号');
  });

  it('左栏 fact 按平台换:星阵讲「三种都能用」,OGS 讲「盒上只做这一种」', async () => {
    renderLogin('golaxy');
    expect(await screen.findByText('三种都能用')).toBeInTheDocument();
    expect(screen.queryByText('盒上只做这一种')).not.toBeInTheDocument();

    renderLogin('ogs');
    expect(await screen.findAllByText('盒上只做这一种')).not.toHaveLength(0);
  });

  it('页控条副标跟着标签换', async () => {
    renderLogin('golaxy');
    await screen.findByTestId('login-field-user');
    expect(screen.getByText(/用星阵围棋的账号密码登录|账号密码登录/)).toBeInTheDocument();
    const tabs = screen.getByTestId('login-mode-tabs');
    await userEvent.click(within(tabs).getByRole('button', { name: '验证码' }));
    expect(screen.getByText('未连接 · 用手机验证码登录')).toBeInTheDocument();
  });

  it('返回键回连接页', async () => {
    renderLogin('golaxy');
    await screen.findByTestId('login-field-user');
    await userEvent.click(screen.getByRole('button', { name: /返回对弈|Back/ }));
    expect(screen.getByTestId('__loc')).toHaveTextContent('/kiosk/play/cross-platform');
  });

  it('登录成功后的目标路由在当前这一版里真的存在(真 Router + 真 KioskRoutes,不复制路由表)', async () => {
    // ⚠️ **不在测试里复制一份路由表** —— 用的是 `KioskApp.tsx` 导出的真 `KioskRoutes`,
    // 断言的是「跳过去那条路由真的渲染得出来」,不是「我调了这个字符串」。
    // 切片 A 之前 `/kiosk/play/cross-platform/golaxy` 还不存在,所以目标必须是
    // `/kiosk/play/cross-platform/engine/golaxy`(今天就有),这条测试顺带锁死这一点:
    // 写成前者的话,这里会卡在兜底路由(`*` → `/kiosk/play`),下面的 findByTestId 会超时。
    render(
      <ThemeProvider theme={kioskTheme}>
        {/* `KioskRoutes` 的路由段都是相对路径("play/…"),要靠一层 `path="/kiosk/*"` 的
            祖先 `<Route>` 才能吃掉 "/kiosk" 前缀 —— `AppRouter.tsx:37` 挂 `KioskApp` 就是
            这样挂的,这里原样照抄那层壳,不是又造了一份 `KioskRoutes` 内部的路由表。 */}
        <MemoryRouter initialEntries={['/kiosk/play/cross-platform/login/golaxy']}>
          <Routes>
            <Route path="/kiosk/*" element={<KioskRoutes />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
    await screen.findByTestId('login-field-user');
    await userEvent.type(screen.getByTestId('login-field-user'), '13800000000');
    await userEvent.type(screen.getByTestId('login-field-password'), 'secret123');
    await userEvent.click(screen.getByTestId('login-submit'));
    expect(await screen.findByTestId('platform-engine-setup-page')).toBeInTheDocument();
  });
});
