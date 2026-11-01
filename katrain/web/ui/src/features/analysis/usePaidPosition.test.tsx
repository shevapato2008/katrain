import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { usePaidPosition } from './usePaidPosition';

const api = vi.hoisted(() => ({ getCatalog: vi.fn(), createQuote: vi.fn(), createPosition: vi.fn(), getPosition: vi.fn() }));
vi.mock('../../api/membershipApi', () => ({ membershipApi: api }));
const quote = { token: 'signed', source: 'membership', wallet_max_display_points: '0.01', fingerprint: 'full-history-a' };
const receipt = { operation_id: 'op-1', state: 'succeeded', result: { ownership: Array(361).fill(0.2), moves: [{ move: 'D4', visits: 500, winrate: 0.6, score_lead: 2 }], rootInfo: { visits: 500, winrate: 0.6, scoreLead: 2 } } };
const options = { identityKey: 'person-a', status: 'authenticated', token: null, snapshotKey: 'cursor-a', input: { sgf: '(;SZ[19];B[dd])' } };
beforeEach(() => {
  vi.resetAllMocks();
  api.getCatalog.mockResolvedValue({ membership_mode: 'enabled', capabilities: { quotes: true, positions: true } });
  api.createQuote.mockResolvedValue(quote);
  api.createPosition.mockResolvedValue(receipt);
});

describe('usePaidPosition', () => {
  it('does nothing automatically and shares one confirmed result between hints and territory', async () => {
    const { result } = renderHook(() => usePaidPosition(options));
    expect(api.createPosition).not.toHaveBeenCalled();
    await act(async () => { await result.current.toggle('ownership'); });
    expect(api.createQuote).toHaveBeenCalledWith({ kind: 'position', profile: 'normal', ...options.input }, null);
    expect(api.createPosition).not.toHaveBeenCalled();
    await act(async () => { await result.current.confirm(); });
    expect(result.current.result).toEqual(receipt.result);
    expect(result.current.showOwnership).toBe(true);
    await act(async () => { await result.current.toggle('hints'); await result.current.toggle('ownership'); await result.current.toggle('ownership'); });
    expect(result.current.showHints).toBe(true);
    expect(result.current.showOwnership).toBe(true);
    expect(api.createPosition).toHaveBeenCalledTimes(1);
    expect(api.createPosition).toHaveBeenCalledWith(expect.objectContaining({ quote_token: 'signed', idempotency_key: expect.any(String) }), null);
  });
  it('cancels without POST and rejects private WS data as a source', async () => {
    const { result } = renderHook(() => usePaidPosition(options));
    await act(async () => { await result.current.toggle('hints'); });
    act(() => result.current.cancel());
    expect(result.current.pendingQuote).toBeNull();
    expect(result.current.result).toBeNull();
    expect(api.createPosition).not.toHaveBeenCalled();
  });
  it('clears the result on cursor and profile change without automatically buying the next position', async () => {
    const { result, rerender } = renderHook(({ cursor, profile }) => usePaidPosition({ ...options, snapshotKey: cursor, profile }), { initialProps: { cursor: 'a', profile: 'normal' as 'normal' | 'advanced' } });
    await act(async () => { await result.current.toggle('hints'); });
    await act(async () => { await result.current.confirm(); });
    rerender({ cursor: 'b', profile: 'normal' });
    expect(result.current.result).toBeNull();
    expect(result.current.showHints).toBe(false);
    expect(api.createPosition).toHaveBeenCalledTimes(1);
    rerender({ cursor: 'b', profile: 'advanced' });
    expect(result.current.result).toBeNull();
  });
  it('discards an old identity response and never starts from an old confirmation callback', async () => {
    let resolve!: (value: typeof receipt) => void;
    api.createPosition.mockReturnValue(new Promise((done) => { resolve = done; }));
    const { result, rerender } = renderHook(({ identity }) => usePaidPosition({ ...options, identityKey: identity }), { initialProps: { identity: 'a' } });
    await act(async () => { await result.current.toggle('hints'); });
    const oldConfirm = result.current.confirm;
    let pending!: Promise<void>;
    act(() => { pending = result.current.confirm(); });
    rerender({ identity: 'b' });
    resolve(receipt);
    await act(async () => { await pending; await oldConfirm(); });
    expect(result.current.result).toBeNull();
    expect(api.createPosition).toHaveBeenCalledTimes(1);
  });
  it('uses an identical key for one transport replay and surfaces refunded failure', async () => {
    api.createPosition.mockRejectedValueOnce(new TypeError('connection lost')).mockResolvedValueOnce({ operation_id: 'op-1', state: 'refunded' });
    const { result } = renderHook(() => usePaidPosition(options));
    await act(async () => { await result.current.toggle('hints'); });
    await act(async () => { await result.current.confirm(); });
    expect(api.createPosition.mock.calls[0]).toEqual(api.createPosition.mock.calls[1]);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toMatch(/退还|退回/);
  });
});
