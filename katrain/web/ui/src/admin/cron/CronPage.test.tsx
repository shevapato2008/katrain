import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import CronPage from './CronPage';
import { testView, testStates } from './cronTestData';

describe('cron presentation', () => {
  it.each(testStates)('renders the %s state independently', (state) => {
    render(<CronPage view={testView(state)} onRefresh={vi.fn()} />);
    expect(screen.getByTestId('cron-view')).toHaveAttribute('data-state', state);
    if (state === 'empty') expect(screen.getByText('cron 进程还没上报任务')).toBeInTheDocument();
    if (state === 'loading') expect(screen.getByText('正在读取任务状态…')).toBeInTheDocument();
    if (state === 'no-table') expect(screen.getByText('状态表尚未建立')).toBeInTheDocument();
  });

  it('keeps zero jobs unknown instead of reporting healthy', () => {
    render(<CronPage view={testView('empty')} onRefresh={vi.fn()} />);
    expect(screen.queryByText('运行正常')).not.toBeInTheDocument();
    expect(screen.queryByText('0 正常')).not.toBeInTheDocument();
    expect(screen.getByText(/cron 进程还没上报过，可能新版 cron 还没部署/)).toBeInTheDocument();
    expect(screen.queryByText(/无法连接数据库/)).not.toBeInTheDocument();
  });

  it('shows concise icon-labeled status counts that follow a new snapshot', () => {
    const healthy = testView('healthy');
    const { rerender } = render(<CronPage view={healthy} onRefresh={vi.fn()} />);
    const overview = screen.getByRole('group', { name: '任务概况' });
    expect(within(overview).getByText('9 正常')).toBeInTheDocument();
    expect(within(overview).getByText('9 正常').closest('.cron-summary-chip')?.querySelector('svg')).toBeInTheDocument();

    const failed = testView('failed');
    rerender(<CronPage view={failed} onRefresh={vi.fn()} />);
    expect(within(overview).getByText('1 失败')).toBeInTheDocument();
    expect(within(overview).getByText('1 报错')).toBeInTheDocument();
    expect(within(overview).getByText('7 正常')).toBeInTheDocument();
    expect(within(overview).queryByText('9 正常')).not.toBeInTheDocument();
  });

  it('names every task with its owning module in the task column', () => {
    render(<CronPage view={testView('healthy')} onRefresh={vi.fn()} />);
    const rows = within(screen.getByRole('region', { name: '定时任务列表' })).getAllByRole('button');
    expect(rows.map((row) => row.querySelector('.cron-job-name')?.textContent)).toEqual([
      '直播 - 落子轮询', '直播 - 分析', '复盘 - 分析',
      '直播 - 赛事预告', '直播 - 赛事列表', '直播 - Pandanet 对局',
      '直播 - 棋手译名', '教程 - 备份', '系统 - 数据清理',
    ]);
  });

  it('explains a selected task before its technical run history', async () => {
    const user = userEvent.setup();
    render(<CronPage view={testView('failed')} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /数据清理/ }));
    const drawer = screen.getByRole('complementary', { name: '任务运行历史' });
    expect(within(drawer).getByText(/定期清理过期对局/)).toBeInTheDocument();
    expect(within(drawer).getByText('最近一次运行失败')).toBeInTheDocument();
    expect(within(drawer).getByText('每 1 天执行')).toBeInTheDocument();
    expect(within(drawer).getByText('清理任务连接数据库失败')).toBeInTheDocument();
    expect(within(drawer).getByText('运行历史')).toBeInTheDocument();
    expect(within(drawer).getByText(/最多显示 200 条/)).toBeInTheDocument();
  });

  it('shows unhealthy jobs first while preserving source order within each group', () => {
    const view = testView('healthy');
    const base = view.jobs[0];
    const names = ['normal_a', 'failed_b', 'disabled_c', 'errors_d', 'offline_e', 'normal_f', 'stuck_g', 'overdue_h'];
    const states = ['ok', 'failed', 'disabled', 'errors', 'offline', 'ok', 'stuck', 'overdue'] as const;
    view.jobs = names.map((name, index) => ({ ...base, name, health: { ...base.health, state: states[index] } }));
    render(<CronPage view={view} onRefresh={vi.fn()} />);
    const rows = within(screen.getByRole('region', { name: '定时任务列表' })).getAllByRole('button');
    expect(rows.map((row) => row.querySelector('.cron-job-code')?.textContent)).toEqual([
      'failed_b', 'errors_d', 'offline_e', 'stuck_g', 'overdue_h', 'normal_a', 'disabled_c', 'normal_f',
    ]);
    expect(view.jobs.map((job) => job.name)).toEqual(names);
  });

  it('opens a selected job history with 200 scrollable runs', async () => {
    const user = userEvent.setup();
    render(<CronPage view={testView('healthy')} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    const drawer = screen.getByRole('complementary', { name: '任务运行历史' });
    expect(within(drawer).getAllByTestId('cron-run')).toHaveLength(200);
    expect(within(drawer).getByTestId('cron-history-scroll')).toBeInTheDocument();
    await user.click(within(drawer).getByRole('button', { name: '关闭运行历史' }));
    expect(screen.queryByRole('complementary', { name: '任务运行历史' })).not.toBeInTheDocument();
  });

  it('provides refresh and retry feedback without claiming a successful fetch', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(<CronPage view={testView('api-error')} onRefresh={onRefresh} />);
    expect(screen.getByRole('alert')).toHaveTextContent('接口请求失败');
    expect(screen.getByText('状态待确认')).toBeInTheDocument();
    expect(screen.queryByText('运行正常')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(screen.getByRole('status')).toHaveTextContent('重新检查');
  });

  it('does not promise history pagination before it exists', async () => {
    const user = userEvent.setup();
    render(<CronPage view={testView('healthy')} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    expect(screen.getByText('仅显示最近记录 · 状态和错误均来自 cron 记录器')).toBeInTheDocument();
  });

  it('uses the healthy 200-run upcoming history reference state', () => {
    const view = testView('history');
    expect(view.jobs.every((job) => job.health.state === 'ok')).toBe(true);
    expect(view.selectedJob).toBe('fetch_upcoming');
    expect(view.runs.fetch_upcoming).toHaveLength(200);
  });

  it('derives process and queue details from the snapshot and names mixed states honestly', () => {
    const view = testView('healthy');
    view.observed_at = '2026-09-24T17:00:00+08:00';
    view.jobs[0].heartbeat_at = '2026-09-24T16:59:30+08:00';
    view.jobs[0].process_started_at = '2026-09-24T12:00:00+08:00';
    view.jobs[1].health.state = 'overdue';
    view.queues!.live_analysis.oldest_pending_at = '2026-09-24T16:54:00+08:00';
    render(<CronPage view={view} onRefresh={vi.fn()} />);
    expect(screen.getByText(/心跳 30 秒前 · 12:00 启动/)).toBeInTheDocument();
    expect(screen.getByText(/最早等待 6 分钟/)).toBeInTheDocument();
    expect(screen.getByText('8 正常')).toBeInTheDocument();
    expect(screen.getByText('1 逾期')).toBeInTheDocument();
    expect(screen.queryByText(/九项任务/)).not.toBeInTheDocument();
  });

  it('keeps the selected history open when a new snapshot arrives', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<CronPage view={testView('healthy')} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /赛事预告/ }));
    rerender(<CronPage view={testView('healthy')} onRefresh={vi.fn()} />);
    expect(screen.getByRole('complementary', { name: '任务运行历史' })).toBeInTheDocument();
  });
});
