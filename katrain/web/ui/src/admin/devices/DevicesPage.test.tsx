import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createAdminApi, type BoxDeviceRow, type DeviceFleet } from '../api/client';
import DevicesPage from './DevicesPage';

const row = (device_id: string, state: BoxDeviceRow['state'], extra: Partial<BoxDeviceRow> = {}): BoxDeviceRow => ({ device_id, state, status: state === 'pending' || state === 'rejected' ? state : 'approved', registered_at: '2026-09-27T00:12:00Z', decided_at: null, decided_by: null, last_seen: null, silent_s: null, last_ip: '10.8.0.31', board: 'rk3562', smartbox_version: null, katrain_build: null, mode: null, uptime_s: null, ...extra });
const fleet = (devices: BoxDeviceRow[]): DeviceFleet => ({ observed_at: 'x', online_within_s: 900, devices, counts: devices.reduce((acc, d) => ({ ...acc, [d.state]: (acc[d.state] ?? 0) + 1 }), {} as Record<string, number>), versions: { smartbox: {}, katrain: {} } });
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});

describe('devices page', () => {
  it('separates never-reported, offline and pending devices', async () => {
    const api = createAdminApi();
    api.devices = vi.fn(async () => fleet([row('sbx-a', 'online', { silent_s: 120, uptime_s: 7200 }), row('sbx-b', 'offline', { silent_s: 3 * 86400 }), row('sbx-c', 'never'), row('sbx-p', 'pending')]));
    render(<DevicesPage api={api} production={false} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('1 台在线')).toBeInTheDocument();
    expect(screen.getByText('3 天前')).toBeInTheDocument();
    expect(screen.getAllByText('从未上报').length).toBeGreaterThan(0);
    expect(within(screen.getByRole('region', { name: '待批准' })).getByText('sbx-p')).toBeInTheDocument();
  });

  it('approves a pending device after confirmation and reloads', async () => {
    const api = createAdminApi(); const u = userEvent.setup();
    api.devices = vi.fn().mockResolvedValueOnce(fleet([row('sbx-p', 'pending')])).mockResolvedValueOnce(fleet([row('sbx-p', 'never')]));
    api.decideDevice = vi.fn(async () => ({ device_id: 'sbx-p', status: 'approved' }));
    render(<DevicesPage api={api} production onUnauthorized={vi.fn()} />);
    await u.click(await screen.findByRole('button', { name: '批准' }));
    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByText('生产环境')).toBeInTheDocument();
    await u.click(dialog.getByRole('button', { name: '确认批准' }));
    await waitFor(() => expect(api.decideDevice).toHaveBeenCalledWith('sbx-p', 'approve'));
    expect(await screen.findByText('1 台从未上报')).toBeInTheDocument();
  });
});
