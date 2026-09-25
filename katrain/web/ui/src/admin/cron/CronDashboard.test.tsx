import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createAdminApi } from '../api/client';
import { testView } from './cronTestData';
import CronDashboard from './CronDashboard';

const sample = testView('healthy');
const jobs = { observed_at: sample.observed_at!, jobs: sample.jobs };
const queues = { observed_at: sample.observed_at!, ...sample.queues! };
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

describe('cron live dashboard', () => {
  const fetchMock = vi.fn<typeof fetch>();
  const unauthorized = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    unauthorized.mockReset();
    fetchMock.mockImplementation(async (path) => {
      if (path === '/api/admin/cron/jobs') return response(jobs);
      if (path === '/api/admin/cron/queues') return response(queues);
      if (String(path).includes('/runs?')) return response({ runs: sample.runs.fetch_upcoming.slice(0, 2), next_before_id: null });
      throw new Error(`Unexpected ${path}`);
    });
  });

  afterEach(() => vi.useRealTimers());

  function mount() {
    return render(<CronDashboard api={createAdminApi(fetchMock, () => 'admin-token')} onUnauthorized={unauthorized} />);
  }

  it('loads real jobs and queues, then fetches history when a job is selected', async () => {
    const user = userEvent.setup();
    mount();
    expect(screen.getByText('正在读取任务状态…')).toBeInTheDocument();
    await screen.findByText('直播分析队列');
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    const drawer = await screen.findByRole('complementary', { name: '任务运行历史' });
    expect(await within(drawer).findAllByTestId('cron-run')).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([path]) => String(path).endsWith('/fetch_upcoming/runs?limit=200'))).toBe(true);
  });

  it('keeps prior jobs and an open history drawer when refresh fails', async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText('直播分析队列');
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    await screen.findAllByTestId('cron-run');
    fetchMock.mockImplementation(async (path) => String(path) === '/api/admin/cron/jobs' ? response({ detail: '请求失败' }, 502) : response(queues));
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('502');
    expect(screen.getByText(/数据停在/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /赛事预告/ })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: '任务运行历史' })).toBeInTheDocument();
  });

  it('treats a database outage 503 as a stale-data API error, not a missing table', async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText('直播分析队列');
    fetchMock.mockImplementation(async (path) => String(path) === '/api/admin/cron/jobs'
      ? response({ detail: 'cron 状态暂不可用：数据库查询失败' }, 503) : response(queues));
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('503：cron 状态暂不可用：数据库查询失败');
    expect(screen.getByText(/数据停在/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /赛事预告/ })).toBeInTheDocument();
    expect(screen.queryByText('状态表尚未建立')).not.toBeInTheDocument();
  });

  it('ignores an older poll that resolves after a newer offline snapshot', async () => {
    const user = userEvent.setup();
    let resolveOld!: (value: Response) => void;
    const oldResponse = new Promise<Response>((resolve) => { resolveOld = resolve; });
    let jobReads = 0;
    const newer = {
      observed_at: '2026-09-25T03:01:00Z',
      jobs: jobs.jobs.map((job) => ({ ...job, health: { state: 'offline', reason: '心跳超时' } })),
    };
    fetchMock.mockImplementation(async (path) => {
      if (path === '/api/admin/cron/jobs') return ++jobReads === 1 ? oldResponse : response(newer);
      if (path === '/api/admin/cron/queues') return response(queues);
      throw new Error(`Unexpected ${path}`);
    });
    mount();
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(await screen.findByText('cron 进程失联')).toBeInTheDocument();
    expect(screen.getByText(/采样于 11:01:00/)).toBeInTheDocument();
    await act(async () => { resolveOld(response(jobs)); });
    expect(screen.getByTestId('cron-view')).toHaveAttribute('data-state', 'offline');
    expect(screen.getByText(/采样于 11:01:00/)).toBeInTheDocument();
  });

  it('shows an initial API failure and a distinct missing-table state', async () => {
    fetchMock.mockImplementation(async (path) => String(path) === '/api/admin/cron/jobs' ? response({ detail: '代理故障' }, 502) : response(queues));
    const first = mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('502');
    expect(screen.queryByText(/数据停在/)).not.toBeInTheDocument();
    expect(screen.queryByText('cron 进程还没上报任务')).not.toBeInTheDocument();
    first.unmount();
    fetchMock.mockImplementation(async (path) => String(path) === '/api/admin/cron/jobs' ? response({ detail: 'cron 状态表不存在：katrain-web 新版本还没启动过' }, 503) : response(queues));
    mount();
    expect(await screen.findByText('状态表尚未建立')).toBeInTheDocument();
    expect(screen.getByText(/cron 状态表不存在/)).toBeInTheDocument();
  });

  it('reports 401 from history to the session owner', async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText('直播分析队列');
    fetchMock.mockImplementation(async (path) => String(path).includes('/runs?') ? response({ detail: '会话无效' }, 401) : String(path).endsWith('/queues') ? response(queues) : response(jobs));
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    await vi.waitFor(() => expect(unauthorized).toHaveBeenCalledOnce());
  });

  it('polls every 15 seconds and cancels polling on unmount', async () => {
    vi.useFakeTimers();
    const page = mount();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const first = fetchMock.mock.calls.filter(([path]) => path === '/api/admin/cron/jobs').length;
    await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
    expect(fetchMock.mock.calls.filter(([path]) => path === '/api/admin/cron/jobs')).toHaveLength(first + 1);
    page.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(15000); });
    expect(fetchMock.mock.calls.filter(([path]) => path === '/api/admin/cron/jobs')).toHaveLength(first + 1);
  });
});
