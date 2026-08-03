import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from '../../context/AuthContext';
import Dashboard from './Dashboard';

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn' }),
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
};

const AuthProbe = () => {
  const { isAuthenticated, isLoading } = useAuth();
  return <div data-testid="auth-state">{isLoading ? 'loading' : isAuthenticated ? 'authenticated' : 'anonymous'}</div>;
};

const renderDashboard = (entry = '/galaxy', withAuth = false) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      {withAuth && <AuthProbe />}
      <LocationProbe />
      <Routes>
        <Route path="/galaxy" element={<Dashboard />} />
        <Route path="/galaxy/play/ai" element={<div>ranked AI destination</div>} />
      </Routes>
    </MemoryRouter>,
    withAuth ? { wrapper: AuthProvider } : undefined,
  );

describe('Dashboard AI ladder demo', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    const values = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      clear: vi.fn(() => values.clear()),
      getItem: vi.fn((key: string) => values.get(key) ?? null),
      removeItem: vi.fn((key: string) => values.delete(key)),
      setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it.each([
    {
      label: 'authenticated',
      response: {
        ok: true,
        json: async () => ({ id: 7, username: 'demo-user', rank: '3d', credits: 10 }),
      },
    },
    {
      label: 'anonymous',
      response: { ok: false, json: async () => ({}) },
    },
  ])('preserves the current dashboard with no demo query for $label AuthContext', async ({ label, response }) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    renderDashboard('/galaxy', true);

    await waitFor(() => expect(screen.getByTestId('auth-state')).toHaveTextContent(label));
    expect(screen.getByRole('heading', { name: '欢迎使用弈航' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 5 }).map((heading) => heading.textContent)).toEqual([
      'Play',
      'Research',
      'Review',
      'Live',
      'Tsumego',
    ]);
    expect(screen.queryByRole('heading', { name: 'AI升降级对弈' })).not.toBeInTheDocument();
  });

  it('shows the placement fixture with a certified server opponent', () => {
    renderDashboard('/galaxy?ai-ladder-demo=placement');

    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText(/当前对手：/)).toHaveTextContent('当前对手：4级');
    expect(screen.getByText('已认证')).toBeInTheDocument();
    expect(screen.getByText('服务器对弈')).toBeInTheDocument();
  });

  it('shows the placed fixture with its current rank, recent five, and +2 net score', () => {
    renderDashboard('/galaxy?ai-ladder-demo=placed');

    expect(screen.getByText('当前段位：5段')).toBeInTheDocument();
    expect(screen.getByText('累计净胜分：+2')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: '最近5盘升降级AI对局结果' })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(5);
  });

  it('shows the pending-settlement fixture as non-actionable', () => {
    renderDashboard('/galaxy?ai-ladder-demo=pending');

    expect(screen.getByRole('status')).toHaveTextContent('本盘成绩结算中');
    expect(screen.getByRole('button', { name: '成绩结算中' })).toBeDisabled();
  });

  it('shows the unavailable fixture as provisional and non-actionable', () => {
    renderDashboard('/galaxy?ai-ladder-demo=unavailable');

    expect(screen.getByText('暂定')).toBeInTheDocument();
    expect(screen.getByText('该档位暂不可挑战')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '暂不可挑战' })).toBeDisabled();
  });

  it('shows the loading fixture semantic', () => {
    renderDashboard('/galaxy?ai-ladder-demo=loading');

    expect(screen.getByRole('status')).toHaveTextContent('正在加载升降级对弈状态…');
  });

  it('shows the error fixture and retries into the working placement demo', () => {
    renderDashboard('/galaxy?ai-ladder-demo=error');

    expect(screen.getByRole('alert')).toHaveTextContent('升降级对弈状态加载失败');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(screen.getByTestId('location')).toHaveTextContent('/galaxy?ai-ladder-demo=placement');
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
  });

  it.each(['toString', 'constructor'])(
    'ignores the inherited object key %s without rendering a card or crashing',
    (state) => {
      expect(() => renderDashboard(`/galaxy?ai-ladder-demo=${state}`)).not.toThrow();
      expect(screen.queryByRole('heading', { name: 'AI升降级对弈' })).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: '欢迎使用弈航' })).toBeInTheDocument();
    },
  );

  it.each(['placement', 'placed'])(
    'routes the %s primary CTA to ranked AI play',
    (state) => {
      renderDashboard(`/galaxy?ai-ladder-demo=${state}`);

      fireEvent.click(screen.getByRole('button', { name: state === 'placement' ? '继续定级' : '开始升降级对弈' }));

      expect(screen.getByTestId('location')).toHaveTextContent('/galaxy/play/ai?mode=ai_ladder_ranked');
      expect(screen.getByText('ranked AI destination')).toBeInTheDocument();
    },
  );

  it.each(['placement', 'placed', 'pending', 'unavailable', 'loading', 'error'])(
    'keeps forbidden provider and engine internals out of the %s fixture',
    (state) => {
      const { container } = renderDashboard(`/galaxy?ai-ladder-demo=${state}`);

      expect(container).not.toHaveTextContent(/星阵|recipe|配方|model|模型文件|temperature|温度|visits|访问次数/i);
    },
  );
});
