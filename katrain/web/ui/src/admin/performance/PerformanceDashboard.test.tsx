import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi, type PerformanceConfig } from '../api/client';
import PerformanceDashboard from './PerformanceDashboard';

const HOST = { id: '0', title: '主机概览', url: 'http://127.0.0.1:3000/d/host?kiosk' };
const GPU = { id: '1', title: 'KataGo GPU', url: 'http://127.0.0.1:3000/d/gpu?kiosk' };
function mount(result: () => Promise<PerformanceConfig>) {
  const api = createAdminApi(); api.performance = vi.fn(result); const onUnauthorized = vi.fn();
  render(<PerformanceDashboard api={api} environmentLabel="测试环境" onUnauthorized={onUnauthorized} />);
  return { api, onUnauthorized };
}

describe('performance dashboard', () => {
  it('says unconfigured and embeds nothing when no dashboard is configured', async () => {
    mount(async () => ({ state: 'unconfigured', error: null, origin: null, dashboards: [], env: 'test' }));
    expect(await screen.findByRole('heading', { name: '尚未接入' })).toBeInTheDocument();
    expect(screen.getByText(/KATRAIN_ADMIN_GRAFANA_DASHBOARDS/)).toBeInTheDocument();
    expect(document.querySelector('iframe')).toBeNull();
  });

  it('embeds the chosen configured dashboard sandboxed, without claiming it is online', async () => {
    mount(async () => ({ state: 'configured', error: null, origin: 'http://127.0.0.1:3000', dashboards: [HOST, GPU], env: 'test' }));
    const frame = await screen.findByTitle('Grafana 看板：主机概览');
    expect(frame).toHaveAttribute('src', HOST.url);
    expect(frame.getAttribute('sandbox')).not.toContain('allow-top-navigation');
    expect(screen.getByText('已配置 · 未探测在线')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('选择看板'), '1');
    expect(screen.getByTitle('Grafana 看板：KataGo GPU')).toHaveAttribute('src', GPU.url);
  });

  it('shows why an invalid configuration is not embedded', async () => {
    mount(async () => ({ state: 'invalid', error: 'KATRAIN_ADMIN_GRAFANA_DASHBOARDS: all dashboards must share the same origin', origin: null, dashboards: [], env: 'test' }));
    expect(await screen.findByRole('heading', { name: '配置无效' })).toBeInTheDocument();
    expect(screen.getByText(/must share the same origin/)).toBeInTheDocument();
    expect(document.querySelector('iframe')).toBeNull();
  });

  it('reports a failed read with a retry instead of guessing a state', async () => {
    let calls = 0;
    const { api } = mount(async () => { calls += 1; if (calls === 1) throw new AdminApiError(503, '服务暂不可用'); return { state: 'unconfigured', error: null, origin: null, dashboards: [], env: 'test' }; });
    expect(await screen.findByRole('alert')).toHaveTextContent('服务暂不可用');
    expect(screen.getByRole('heading', { name: '配置未读取' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('heading', { name: '尚未接入' })).toBeInTheDocument();
    expect(api.performance).toHaveBeenCalledTimes(2);
  });

  it('hands an expired session back to the login screen', async () => {
    const { onUnauthorized } = mount(async () => { throw new AdminApiError(401, 'expired'); });
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalled());
  });
});
