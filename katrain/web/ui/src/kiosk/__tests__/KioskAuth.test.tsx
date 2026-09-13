import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LoginPage from '../pages/LoginPage';

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// 严格盒端与否是这一屏的**输入**,所以在测试里把它造出来 —— 否则这两条分支各自
// 只在一种构建的 `npm test` 里跑得到,而仓里没有任何 CI 跑严格那一档
// (`npm test` 不带 VITE_BOX_SSO_STRICT ⇒ 盒端分支恒被跳过)。
const boxMode = vi.hoisted(() => ({ strict: false }));
vi.mock('../shell/boxUrls', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../shell/boxUrls')>();
  return {
    ...actual,
    get isStrictBoxKiosk() { return boxMode.strict; },
  };
});

const authState = vi.hoisted(() => ({
  current: { isAuthenticated: false, isLoading: false } as { isAuthenticated: boolean; isLoading: boolean },
}));
const mockLogin = vi.fn();
const mockLogout = vi.fn();

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: authState.current.isAuthenticated,
    isLoading: authState.current.isLoading,
    user: null,
    login: mockLogin,
    logout: mockLogout,
    token: null,
  }),
}));

const renderLoginPage = (route = '/kiosk/login') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/kiosk/login" element={<LoginPage />} />
          <Route path="/kiosk/play" element={<div>PLAY_PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  vi.clearAllMocks();
  mockLogin.mockResolvedValue(undefined);
  boxMode.strict = false;
  authState.current = { isAuthenticated: false, isLoading: false };
});

describe('LoginPage (shared auth)', () => {
  it('renders username and password inputs', () => {
    renderLoginPage();
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/密码/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登录/i })).toBeInTheDocument();
  });

  it('login button is disabled when username is empty', () => {
    renderLoginPage();
    expect(screen.getByRole('button', { name: /登录/i })).toBeDisabled();
  });

  it('calls login with username and password on submit', async () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'testpass' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', 'testpass');
    });
  });

  it('navigates to /kiosk/play on successful login', async () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'pass123' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
    });
  });

  it('displays error message on login failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/用户名/i), { target: { value: 'baduser' } });
    fireEvent.change(screen.getByLabelText(/密码/i), { target: { value: 'badpass' } });
    fireEvent.click(screen.getByRole('button', { name: /登录/i }));

    await waitFor(() => {
      expect(screen.getByText('登录失败')).toBeInTheDocument();
    });
  });
});

/**
 * 出厂盒子(`KATRAIN_MODE=board` + `KATRAIN_BOX_SSO`,前端 `VITE_BOX_SSO_STRICT`)那一档。
 *
 * 2026-09-13 之前这一屏在盒上是**死页**:表单照画,但 `AuthContext.login()` 第一行就抛、
 * 后端 `POST /api/v1/auth/login` 也恒 403,而这一屏挂在 `KioskLayout` 外面 ——
 * 没顶栏、没 Dock、没主页键,人进来了就出不去。
 */
describe('LoginPage 严格盒端', () => {
  beforeEach(() => {
    boxMode.strict = true;
  });

  it('不画注定提交不了的登录表单', () => {
    renderLoginPage();
    expect(screen.queryByLabelText(/用户名/i)).toBeNull();
    expect(screen.queryByLabelText(/密码/i)).toBeNull();
    expect(screen.queryByRole('button', { name: /^登录$/ })).toBeNull();
  });

  it('给一条真出路:整页跳回 launcher,且**不带 logout=1**', () => {
    renderLoginPage();
    const cta = screen.getByTestId('login-go-launcher');
    // 是 <a> 不是 button —— 目标在另一个源上,这是整页离开,不是本 SPA 的路由。
    expect(cta.tagName).toBe('A');
    expect(cta).toHaveAttribute('href', 'http://127.0.0.1:8080/launcher?authmode=login');
    // `logout=1` 在盒上没有 sb_session 时会撞 launcher 的 fail-closed 错误屏
    // (`performLogoutThenGate` → 401 → `showRetirementError()`,故意不露表单),
    // 而围棋走到这一屏时恰恰不知道 wizard 会话还在不在。
    expect(cta.getAttribute('href')).not.toContain('logout=1');
  });

  it('照实说账号归主页管,不假装这里能登', () => {
    renderLoginPage();
    expect(screen.getByText('请在智星盒主页登录')).toBeInTheDocument();
  });
});

describe('LoginPage 已登录时不该停在登录页', () => {
  it('探针跑完且已登录 → 直接回对弈页(两种构建都要)', async () => {
    authState.current = { isAuthenticated: true, isLoading: false };
    renderLoginPage();
    expect(screen.getByText('PLAY_PAGE')).toBeInTheDocument();
  });

  it('探针还没跑完时不跳 —— 否则会在冷启动那一帧把人甩走', () => {
    authState.current = { isAuthenticated: false, isLoading: true };
    renderLoginPage();
    expect(screen.getByTestId('kiosk-login-page')).toBeInTheDocument();
    expect(screen.queryByText('PLAY_PAGE')).toBeNull();
  });
});
