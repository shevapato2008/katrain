import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AdminApp from './AdminApp';

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });
describe('admin vision entry', () => {
  it('uses the real protected controller without adding the performance fixture navigation', async () => {
    localStorage.setItem('katrain_admin_session', 'admin-token');
    const fetcher = vi.fn<typeof fetch>(async (input) => {
      const path = String(input);
      return new Response(JSON.stringify(path.endsWith('/auth/me') ? { username: 'fan', env: 'test' } : path.endsWith('/vision/status') ? {
        enabled: false, camera: { state: 'unknown' }, led: { state: 'disabled' }, geometry: { state: 'required' }, sgf: { game_id: null }, dataset: { state: 'none', count: 0 },
      } : []), { status: 200 });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<AdminApp />);
    await userEvent.click(await screen.findByRole('button', { name: '视觉实验室' }));
    await screen.findByText(/此服务未启用本机视觉控制/);
    expect(screen.queryByRole('button', { name: '性能监控' })).not.toBeInTheDocument();
    await waitFor(() => expect(fetcher.mock.calls.some(([path, init]) => String(path) === '/api/admin/vision/status' && new Headers(init?.headers).get('Authorization') === 'Bearer admin-token')).toBe(true));
    expect(fetcher.mock.calls.some(([path]) => String(path).endsWith('/vision/connect'))).toBe(false);
  });
});
