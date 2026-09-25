import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminApp from '../AdminApp';

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

describe('admin cron navigation', () => {
  const fetchMock = vi.fn<typeof fetch>();
  let cronUnauthorized = false;

  beforeEach(() => {
    localStorage.clear();
    cronUnauthorized = false;
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (path) => {
      const url = String(path);
      if (url === '/api/admin/auth/login') return json({ access_token: 'admin-token', token_type: 'bearer' });
      if (url === '/api/admin/auth/me') return json({ username: 'admin:fan', env: 'local' });
      if (url === '/api/v1/tutorials/categories') return json([]);
      if (url === '/api/admin/cron/jobs') return cronUnauthorized ? json({ detail: '会话失效' }, 401) : json({ observed_at: '2026-09-25T03:00:00Z', jobs: [] });
      if (url === '/api/admin/cron/queues') return json({ observed_at: '2026-09-25T03:00:00Z', live_analysis: { by_status: {}, oldest_pending_at: null }, report_tasks: { by_status: {}, oldest_pending_at: null } });
      throw new Error(`Unexpected ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  it('opens live cron status and returns to tutorial management', async () => {
    const user = userEvent.setup();
    render(<AdminApp />);
    await user.type(screen.getByLabelText('后台用户名'), 'admin:fan');
    await user.type(screen.getByLabelText('密码'), 'password');
    await user.click(screen.getByRole('button', { name: '登录' }));
    await user.click(await screen.findByRole('button', { name: '定时任务' }));
    expect(await screen.findByText('cron 进程还没上报任务')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '教程管理' }));
    expect(screen.getByText('当前环境没有教程教材。')).toBeInTheDocument();
  });

  it('clears the token and returns to sign-in when cron status returns 401', async () => {
    cronUnauthorized = true;
    const user = userEvent.setup();
    render(<AdminApp />);
    await user.type(screen.getByLabelText('后台用户名'), 'admin:fan');
    await user.type(screen.getByLabelText('密码'), 'password');
    await user.click(screen.getByRole('button', { name: '登录' }));
    await user.click(await screen.findByRole('button', { name: '定时任务' }));
    expect(await screen.findByText('后台会话已失效，请重新登录。')).toBeInTheDocument();
    expect(localStorage.getItem('katrain_admin_session')).toBeNull();
  });
});
