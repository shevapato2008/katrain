import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { membershipApi } from './membershipApi';

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); localStorage.clear(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('membership API', () => {
  it('accepts null tokens and uses same-origin cookies for strict box identity', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ revision: 1 }), { status: 200 }));
    const controller = new AbortController();
    await membershipApi.getUsage(null, controller.signal);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/billing/usage', expect.objectContaining({
      credentials: 'same-origin', signal: controller.signal, headers: {}, cache: 'no-store',
    }));
  });

  it('uses shared bearer headers and sends exact quote payload', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const payload = { kind: 'position' as const, profile: 'normal' as const, sgf: '(;SZ[19])' };
    await membershipApi.createQuote(payload, 'account-token');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/billing/quotes', expect.objectContaining({
      method: 'POST', body: JSON.stringify(payload),
      headers: { Authorization: 'Bearer account-token', 'Content-Type': 'application/json' },
    }));
  });

  it('covers catalog, orders and positions with safely encoded IDs', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(new Response('{}', { status: 200 })));
    await membershipApi.getCatalog(null);
    await membershipApi.getOrders(null);
    await membershipApi.getOrder('order/1', null);
    await membershipApi.createOrder({ sku: 'membership_plus', idempotency_key: 'key' }, null);
    await membershipApi.createPosition({ sgf: '(;SZ[19])', profile: 'normal', quote_token: 'signed', idempotency_key: 'position-key' }, null);
    await membershipApi.getPosition('op/1', null);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/billing/catalog', '/api/v1/billing/orders', '/api/v1/billing/orders/order%2F1',
      '/api/v1/billing/orders', '/api/v1/analysis/positions', '/api/v1/analysis/positions/op%2F1',
    ]);
  });

  it('preserves shared ApiError status and structured reason', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: { code: 'quote_expired', message: 'Refresh quote' } }), { status: 409 }));
    await expect(membershipApi.getUsage(null)).rejects.toMatchObject({
      status: 409, detail: { code: 'quote_expired', message: 'Refresh quote' },
    });
    await expect(membershipApi.getUsage(null)).rejects.toBeInstanceOf(ApiError);
  });
});
