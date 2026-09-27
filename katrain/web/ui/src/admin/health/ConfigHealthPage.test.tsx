import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi, type ConfigHealth } from '../api/client';
import ConfigHealthPage from './ConfigHealthPage';

const sample: ConfigHealth = {
  observed_at: '2026-09-27T01:00:00Z', stale_after_s: 1800,
  processes: [
    { process: 'web', state: 'fresh', hostname: 'katrain-web', build: 'a41c9e2', generated_at: '2026-09-27T00:57:00Z', age_s: 180, checks: [{ id: 'billing', level: 'bad', message: '计费闸已开但每周免费报告不为 0' }, { id: 'mode', level: 'ok', message: '服务器模式' }], extra: {} },
    { process: 'cron', state: 'stale', hostname: 'katrain-cron', build: 'a41c9e2', generated_at: '2026-09-27T00:13:00Z', age_s: 2820, checks: [], extra: {} },
    { process: 'admin', state: 'never', hostname: null, build: null, generated_at: null, age_s: null, checks: [], extra: {} },
  ],
  cross_checks: [{ id: 'build_consistency', level: 'unknown', message: '不是每个进程都有新近上报，无法比较版本' }],
};

describe('config health page', () => {
  it('shows fresh verdicts, withholds stale ones, and counts a silent process as a problem', async () => {
    const api = createAdminApi(); api.configHealth = vi.fn(async () => sample);
    render(<ConfigHealthPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('计费闸已开但每周免费报告不为 0')).toBeInTheDocument();
    expect(within(screen.getByLabelText('定时任务 体检')).getByText(/结论不再可信，已隐藏/)).toBeInTheDocument();
    expect(within(screen.getByLabelText('管理后台 体检')).getByText('从未上报')).toBeInTheDocument();
    expect(screen.getByText('2 项有问题')).toBeInTheDocument();
    expect(screen.getByText(/版本一致性：不是每个进程都有新近上报/)).toBeInTheDocument();
  });

  it('reports a failed read with retry instead of an empty all-clear', async () => {
    const api = createAdminApi(); const u = userEvent.setup();
    api.configHealth = vi.fn().mockRejectedValueOnce(new AdminApiError(503, '数据库暂时不可用')).mockResolvedValueOnce(sample);
    render(<ConfigHealthPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('数据库暂时不可用');
    expect(screen.queryByText(/项正常/)).not.toBeInTheDocument();
    await u.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('计费闸已开但每周免费报告不为 0')).toBeInTheDocument();
  });
});
