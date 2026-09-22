import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AccountSection from './AccountSection';

const { authState, statusHook, retry, boxMode, leaveToLauncher } = vi.hoisted(() => ({
  authState: { current: { token: undefined, user: { username: 'fan' }, isGuest: false, logout: vi.fn() } as any },
  statusHook: vi.fn(),
  retry: vi.fn(),
  // 严格盒端与否是**输入**：仓里没有任何 CI 跑那一档，不造就永远不会被执行。
  boxMode: { strict: false },
  leaveToLauncher: vi.fn(),
}));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => authState.current }));
vi.mock('../../../features/aiLadder/useAiLadderStatus', () => ({ useAiLadderStatus: statusHook }));
vi.mock('../../shell/boxUrls', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../shell/boxUrls')>();
  return {
    ...actual,
    get isStrictBoxKiosk() { return boxMode.strict; },
    leaveToLauncher,
  };
});

beforeEach(() => {
  boxMode.strict = false;
  leaveToLauncher.mockClear();
  authState.current = { token: undefined, user: { username: 'fan' }, isGuest: false, logout: vi.fn() };
});

describe('AccountSection ladder summary', () => {
  it('shows placement progress using cookie-compatible status', () => {
    statusHook.mockReturnValue({ status: { view_state: 'ready', placement_state: { phase: 'placement', completed_games: 3, total_games: 5 }, current_opponent: { rung: 12, rank_name: '9级', certification_status: 'certified', availability: 'available', route: 'server' }, recent_ranked_results: ['win', 'loss'], net_score: 1, pending_settlement: false }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('累计净胜分：+1')).toBeInTheDocument();
    expect(screen.getByText('服务器对弈')).toBeInTheDocument();
    expect(screen.getByText('已认证')).toBeInTheDocument();
    // 2026-08-23 重排成外壳的行之后,那一行的高度由 `.kiosk-row` 给(52) ——
    // **不在 jsdom 里断言它**:类给的高度 jsdom 看不见,判据在真浏览器那份几何闸里。
    expect(screen.getByTestId('ai-ladder-account-summary')).toHaveClass('kiosk-row');
    expect(screen.queryByText('最近5盘仅供展示，升降段只看累计净胜分')).not.toBeInTheDocument();
    // 详情**就地展开**在同一列行里,不是弹层:这一屏本来就是滚动列表,也省掉遮罩和焦点陷阱。
    const toggle = screen.getByRole('button', { name: '查看AI段位详情' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByTestId('ladder-detail')).toBeInTheDocument();
    expect(screen.getByText('最近5盘仅供展示，升降段只看累计净胜分')).toBeInTheDocument();
    const close = screen.getByRole('button', { name: '收起' });
    expect(close).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(close);
    expect(screen.queryByTestId('ladder-detail')).toBeNull();
  });

  // 以前这一行自己写了一套词(「认证中」「本地对弈」「AI段位：」),而共享卡说「暂定」「本机对弈」
  // 「当前段位：」—— 同一个状态,两块屏两种说法。现在只有 AI_LADDER_COPY 那一套。
  it('已定档:摘要行用的是共享那套词', () => {
    const rung = { rung: 16, rank_name: '5级', certification_status: 'provisional', availability: 'available', route: 'local' };
    statusHook.mockReturnValue({ status: { view_state: 'ready', placement_state: { phase: 'placed', rung }, current_opponent: rung, recent_ranked_results: [], net_score: -1, pending_settlement: false }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    const row = screen.getByTestId('ai-ladder-account-summary');
    expect(row).toHaveTextContent('当前段位：5级');
    expect(row).toHaveTextContent('累计净胜分：-1');
    expect(row).toHaveTextContent('暂定');
    expect(row).toHaveTextContent('本机对弈');
    expect(row.textContent).not.toMatch(/认证中|本地对弈|AI段位：/);
  });

  // 读不到段位的时候照实说,但用的是外壳的行,不是从别的应用剪进来的一张卡。
  it('段位读不到时,顶在列表里的是一行 .kiosk-row + 能按的重试,不是 MUI 卡', () => {
    retry.mockClear();
    statusHook.mockReturnValue({ status: { view_state: 'error', message: '' }, retry });
    const { container } = render(<MemoryRouter><AccountSection /></MemoryRouter>);
    const row = screen.getByTestId('ai-ladder-account-fallback');
    expect(row).toHaveClass('kiosk-row');
    expect(row).toHaveTextContent('升降级对弈状态加载失败');
    expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('加载中也是一行 .kiosk-row,并且照实说在加载', () => {
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    const row = screen.getByTestId('ai-ladder-account-fallback');
    expect(row).toHaveClass('kiosk-row');
    expect(row).toHaveTextContent('正在加载升降级对弈状态…');
  });

  it('does not request or leave a loading ladder card for a guest', () => {
    authState.current = { token: undefined, user: null, isGuest: false, logout: vi.fn() };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);
    expect(statusHook).toHaveBeenCalledWith(undefined, false);
    expect(screen.queryByText('正在加载AI段位…')).not.toBeInTheDocument();
  });
});

/**
 * 出厂盒子那一档:围棋**退不了登录**。
 * `POST /api/v1/auth/logout` 在 strict 下恒 403，而且它要清的 key 是 `sb_token`，
 * 盒端的 cookie 叫 `sb_go_token` —— 旧写法只清 React state，刷新一下就又登回来了，
 * 中间还把人踢到 `KioskLayout` 外面那一屏。
 */
describe('AccountSection 严格盒端', () => {
  it('不再假装自己能退出登录，改成回主页切账号', () => {
    boxMode.strict = true;
    const logout = vi.fn();
    authState.current = { token: undefined, user: { username: 'fan' }, isGuest: false, logout };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);

    expect(screen.queryByText('退出登录')).toBeNull();
    fireEvent.click(screen.getByTestId('settings-logout'));
    // 不能再打那个恒 403 的端点，也不能导向登录页。
    expect(logout).not.toHaveBeenCalled();
    expect(leaveToLauncher).toHaveBeenCalledWith();
  });

  it('非盒端照旧：真退出 + 回登录页', async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    authState.current = { token: 't', user: { username: 'fan' }, isGuest: false, logout };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);

    expect(screen.getByText('退出登录')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('settings-logout'));
    await waitFor(() => expect(logout).toHaveBeenCalled());
    expect(leaveToLauncher).not.toHaveBeenCalled();
  });

  it('未登录时那颗「登录」在盒上也不能进死页', () => {
    boxMode.strict = true;
    authState.current = { token: undefined, user: null, isGuest: false, logout: vi.fn() };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(leaveToLauncher).toHaveBeenCalledWith('http://127.0.0.1:8080/launcher?authmode=login');
  });

  it('访客显示注册登录入口并回 launcher 退出访客态', () => {
    boxMode.strict = true;
    authState.current = { token: undefined, user: { username: 'guest' }, isGuest: true, logout: vi.fn() };
    statusHook.mockReturnValue({ status: { view_state: 'loading' }, retry });
    render(<MemoryRouter><AccountSection /></MemoryRouter>);

    expect(statusHook).toHaveBeenCalledWith(undefined, false);
    expect(screen.queryByTestId('settings-logout')).toBeNull();
    fireEvent.click(screen.getByTestId('account-register-login'));
    expect(leaveToLauncher).toHaveBeenCalledWith('http://127.0.0.1:8080/launcher?logout=1&authmode=register');
  });
});
