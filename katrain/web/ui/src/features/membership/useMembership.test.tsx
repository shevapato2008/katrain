import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useMembership, notifyMembershipChanged } from './useMembership';
import type { MembershipCatalog, MembershipUsage } from './types';

const { auth, getCatalog, getUsage } = vi.hoisted(() => ({
  auth: { identityKey: 'account-a' as string | null, status: 'authenticated', token: null as string | null },
  getCatalog: vi.fn(), getUsage: vi.fn(),
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../api/membershipApi', () => ({ membershipApi: { getCatalog, getUsage } }));

const capabilities = { membership: true, usage: true, quotes: true, positions: true, orders: false, can_claim_free_report: false };
const catalog = { catalog_version: 'v1', environment: 'TEST', capabilities } as MembershipCatalog;
const usage = (revision = 1): MembershipUsage => ({
  catalog_version: 'v1', environment: 'TEST', server_now: '2026-11-02T00:00:00Z', revision, capabilities,
  payments_mode: 'disabled', plan: { current: null, next: null }, term: null, week: null,
  wallet: { credits: 301, display_points: '3.01' }, free: null,
});
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  vi.useFakeTimers();
  Object.assign(auth, { identityKey: 'account-a', status: 'authenticated', token: null });
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  getCatalog.mockReset().mockResolvedValue(catalog);
  getUsage.mockReset().mockResolvedValue(usage());
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('shared membership state', () => {
  it('discovers the deployment environment without hardcoding a product build', async () => {
    const { result } = renderHook(() => useMembership());
    await flush();
    expect(result.current.status).toBe('ready');
    expect(result.current.usage?.environment).toBe('TEST');
    getUsage.mockResolvedValueOnce({ ...usage(2), environment: 'production' });
    getCatalog.mockResolvedValueOnce({ ...catalog, environment: 'production' });
    await act(async () => { await result.current.refresh(); });
    expect(result.current.status).toBe('error');
    expect(result.current.usage).toBeNull();
  });

  it('loads an authenticated cookie identity with null token', async () => {
    const { result } = renderHook(() => useMembership({ environment: 'TEST' }));
    await flush();
    expect(result.current.status).toBe('ready');
    expect(result.current.usage?.wallet?.display_points).toBe('3.01');
    expect(getUsage).toHaveBeenCalledWith(null, expect.any(AbortSignal));
  });

  it('clears snapshots on identity and environment switches, aborting old responses', async () => {
    const { result, rerender } = renderHook(({ environment }) => useMembership({ environment }), { initialProps: { environment: 'TEST' } });
    await flush();
    let resolve!: (data: MembershipUsage) => void;
    getUsage.mockReturnValueOnce(new Promise(r => { resolve = r; }));
    act(() => { void result.current.refresh(); });
    const oldSignal = getUsage.mock.calls.at(-1)![1] as AbortSignal;
    auth.identityKey = 'account-b';
    getUsage.mockReturnValue(new Promise(() => {}));
    rerender({ environment: 'TEST' });
    expect(result.current.usage).toBeNull();
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { resolve(usage(99)); });
    expect(result.current.usage).toBeNull();
    rerender({ environment: 'production' });
    expect(result.current.catalog).toBeNull();
  });

  it('ignores older revisions and clears private data when authentication is unavailable', async () => {
    getUsage.mockResolvedValueOnce(usage(3)).mockResolvedValueOnce(usage(2));
    const { result, rerender } = renderHook(() => useMembership({ environment: 'TEST' }));
    await flush();
    await act(async () => { await result.current.refresh(); });
    expect(result.current.usage?.revision).toBe(3);
    auth.status = 'unavailable';
    rerender();
    expect(result.current.usage).toBeNull();
    expect(result.current.status).toBe('unauthenticated');
  });

  it('polls only while visible, refreshes after activity, and cleans up requests', async () => {
    const { result, unmount } = renderHook(() => useMembership({ environment: 'TEST' }));
    await flush();
    await act(async () => { vi.advanceTimersByTime(15000); });
    expect(getUsage).toHaveBeenCalledTimes(2);
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    await act(async () => { vi.advanceTimersByTime(30000); });
    expect(getUsage).toHaveBeenCalledTimes(2);
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    await flush();
    expect(getUsage).toHaveBeenCalledTimes(3);
    act(() => { notifyMembershipChanged(); });
    await flush();
    expect(getUsage).toHaveBeenCalledTimes(4);
    getUsage.mockReturnValueOnce(new Promise(() => {}));
    act(() => { void result.current.refresh(); });
    const signal = getUsage.mock.calls.at(-1)![1] as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => { vi.advanceTimersByTime(30000); });
    expect(getUsage).toHaveBeenCalledTimes(5);
  });

  it('keeps unknown or disabled balances null instead of inventing zero', async () => {
    getUsage.mockRejectedValueOnce(new Error('offline'));
    const { result } = renderHook(() => useMembership({ environment: 'TEST' }));
    await flush();
    expect(result.current.status).toBe('error');
    expect(result.current.usage).toBeNull();
    getUsage.mockResolvedValueOnce({ ...usage(), capabilities: { ...capabilities, usage: false }, wallet: null });
    await act(async () => { await result.current.refresh(); });
    expect(result.current.status).toBe('unavailable');
    expect(result.current.usage?.wallet).toBeNull();
  });

  it('refreshes when a server deadline reaches zero without locally replenishing quota', async () => {
    const deadline = '2026-11-02T00:00:02Z';
    getUsage.mockResolvedValue({ ...usage(), week: { limit: 10, used: 10, reserved: 0, remaining: 0, percent: 0, reset_at: deadline } });
    const { result } = renderHook(() => useMembership({ environment: 'TEST' }));
    await flush();
    expect(result.current.countdowns.week).toBe(2);
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(result.current.countdowns.week).toBe(0);
    expect(result.current.usage?.week?.remaining).toBe(0);
    expect(getUsage).toHaveBeenCalledTimes(2);
  });
});
