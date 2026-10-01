import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import CronPage from './CronPage';
import type { CronJob, CronView } from './types';

const job = (extra: Partial<CronJob> = {}): CronJob => ({
  name: 'fetch_list', kind: 'interval', interval_seconds: 1800, enabled: true, health: { state: 'ok', reason: '正常' },
  process_started_at: null, heartbeat_at: new Date().toISOString(), last_started_at: null, last_finished_at: null, last_success_at: null,
  last_status: 'success', last_duration_ms: 10, last_error: null, consecutive_failures: 0, loop_iteration_at: null, loop_stats: null, ...extra,
});
const view = (j: CronJob): CronView => ({ state: 'healthy', observed_at: new Date().toISOString(), jobs: [j], runs: {}, queues: null, selectedJob: j.name });
const controls = () => ({ pause: vi.fn(async () => undefined), resume: vi.fn(async () => undefined), runNow: vi.fn(async () => undefined) });

describe('cron job controls', () => {
  it('pauses only with a real reason', async () => {
    const c = controls(); const u = userEvent.setup();
    render(<CronPage view={view(job())} onRefresh={vi.fn()} controls={c} />);
    await u.click(screen.getByRole('button', { name: '暂停…' }));
    await u.type(screen.getByLabelText(/暂停原因/), '维护');
    expect(screen.getByRole('button', { name: '确认暂停' })).toBeDisabled();
    await u.type(screen.getByLabelText(/暂停原因/), '上游接口');
    await u.click(screen.getByRole('button', { name: '确认暂停' }));
    await waitFor(() => expect(c.pause).toHaveBeenCalledWith('fetch_list', '维护上游接口'));
  });

  it('shows a queued run, a cron refusal, and the resume path for a paused job', async () => {
    const c = controls(); const u = userEvent.setup();
    const pending = { id: 1, state: 'pending' as const, requested_at: 'x', requested_by: 'admin:fan', handled_at: null, note: null };
    const { rerender } = render(<CronPage view={view(job({ pending_run: pending }))} onRefresh={vi.fn()} controls={c} />);
    expect(screen.getByRole('button', { name: '已排队' })).toBeDisabled();
    rerender(<CronPage view={view(job({ last_command: { ...pending, state: 'rejected', note: '任务已暂停，先恢复再运行' } }))} onRefresh={vi.fn()} controls={c} />);
    expect(screen.getByText(/上次立即运行被 cron 拒绝：任务已暂停/)).toBeInTheDocument();
    rerender(<CronPage view={view(job({ paused: true, pause_reason: '上游接口维护中', paused_by: 'admin:fan', health: { state: 'paused', reason: '已在后台暂停：上游接口维护中' } }))} onRefresh={vi.fn()} controls={c} />);
    await u.click(screen.getByRole('button', { name: '恢复' }));
    await waitFor(() => expect(c.resume).toHaveBeenCalledWith('fetch_list'));
  });

  it('offers nothing for loop jobs', () => {
    render(<CronPage view={view(job({ kind: 'loop', interval_seconds: null, name: 'analyze' }))} onRefresh={vi.fn()} controls={controls()} />);
    expect(screen.getByText('常驻循环任务不支持暂停或立即运行。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '立即运行' })).not.toBeInTheDocument();
  });
});
