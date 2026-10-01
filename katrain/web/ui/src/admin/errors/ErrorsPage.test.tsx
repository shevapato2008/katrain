import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createAdminApi, type ErrorList } from '../api/client';
import AdminSidebar from '../AdminSidebar';
import ErrorsPage from './ErrorsPage';

const fresh = { state: 'fresh' as const, age_s: 30, last_flush_at: new Date().toISOString(), last_flush_ok: true, dropped: 0, overflow: 0, queued: 0 };
const group = { id: 7, process: 'web', logger: 'katrain.web', exc_type: 'ReadTimeout', template: 'Engine request failed for session %s', location: 'engine_client.py:analyze', job: null, first_seen: new Date().toISOString(), last_seen: new Date().toISOString(), state_changed_at: new Date().toISOString(), count: 3, sample: 'Engine request failed for session <redacted>', build: 'a41c9e2', resolved_at: null, resolved_by: null };
const list = (items: ErrorList['items'], cron = fresh): ErrorList => ({ items, total: items.length, page: 1, page_size: 30, collectors: { web: fresh, cron, admin: fresh } });

describe('errors page', () => {
  it('does not claim "no errors" while a collector is silent', async () => {
    const api = createAdminApi(); api.errors = vi.fn(async () => list([], { state: 'stale', age_s: 3120 } as never));
    render(<ErrorsPage api={api} onUnauthorized={vi.fn()} onChanged={vi.fn()} />);
    expect(await screen.findByText('有采集器未在上报，不能据此判断没有报错')).toBeInTheDocument();
    expect(screen.getByText('采集器 · 上报已过期 · 52 分钟前')).toBeInTheDocument();
    expect(screen.queryByText('没有未解决的报错')).not.toBeInTheDocument();
  });

  it('resolves the selected group and refreshes the badge', async () => {
    const api = createAdminApi(); const onChanged = vi.fn(); const u = userEvent.setup();
    api.errors = vi.fn().mockResolvedValueOnce(list([group])).mockResolvedValueOnce(list([]));
    api.resolveError = vi.fn(async () => ({ ...group, resolved_at: 'now', resolved_by: 'admin:fan' }));
    render(<ErrorsPage api={api} onUnauthorized={vi.fn()} onChanged={onChanged} />);
    expect(await screen.findByText('新')).toBeInTheDocument();
    await u.click(screen.getByRole('button', { name: '标记已解决' }));
    await waitFor(() => expect(api.resolveError).toHaveBeenCalledWith(7));
    expect(onChanged).toHaveBeenCalled();
    expect(await screen.findAllByText('没有未解决的报错')).not.toHaveLength(0);
  });

  it('shows attention badges in the sidebar only when there is something to look at', () => {
    render(<AdminSidebar attention={{ errors: 2, config: 0 }} page="tutorial" labOpen={false} environmentLabel="测试环境" onPage={vi.fn()} onToggleLab={vi.fn()} />);
    expect(screen.getByLabelText('2 项需要关注')).toBeInTheDocument();
    expect(screen.getAllByText(/项需要关注|^\d+$/).length).toBe(1);
  });
});
