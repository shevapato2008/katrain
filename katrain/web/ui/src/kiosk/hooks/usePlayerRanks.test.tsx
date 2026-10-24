import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePlayerRanks } from './usePlayerRanks';
import { UNKNOWN_RANK, type PlayerRank } from '../utils/playerRank';
import type { GameState } from '../../api';

const identity = { user: { id: 1, uuid: 'account-1' }, token: 'token-1', isAuthenticated: true, isGuest: false };
const game = { game_id: 'game-1', game_type: 'free', rank_owner: { user_id: 1, color: 'B' }, players_info: { B: { player_type: 'human' }, W: { player_type: 'ai' } } } as unknown as GameState;
const placed = (label: string) => ({ placement_state: { phase: 'placed', rung: { rank_name: label } } });
const response = (body: unknown) => ({ ok: true, json: async () => body }) as Response;
const label = (rank: PlayerRank | undefined) => (rank ?? UNKNOWN_RANK).label;
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };

describe('scoped kiosk player rank requests', () => {
  beforeEach(() => { vi.useFakeTimers(); Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' }); });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
  it('loads both invited seats by exact local session and does not infer from rung', async () => {
    const fetcher = vi.fn().mockResolvedValue(response([
      { session_id: 'other', player_b_rank_label: '9段', player_w_rank_label: '9段' },
      { session_id: 'local', player_b_rank_label: '2段', player_w_rank_label: '20k' },
    ])); vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ sessionId }) => usePlayerRanks({ sessionId, gameState: { ...game, game_type: 'pvp_lobby' }, ...identity }), { initialProps: { sessionId: 'local' } });
    await flush(); expect(label(result.current.B)).toBe('2段'); expect(label(result.current.W)).toBe('20k');
    fetcher.mockResolvedValue(response([{ session_id: 'next', player_b_rung: 4, player_b_rank_label: null, player_w_rank_label: '   ' }]));
    rerender({ sessionId: 'next' }); expect(label(result.current.B)).toBe('等级未知'); await flush();
    expect(label(result.current.B)).toBe('等级未知'); expect(label(result.current.W)).toBe('等级未知');
  });
  it('uses the explicit lobby route for legacy free frames and rejects ambiguous rooms', async () => {
    const fetcher = vi.fn().mockResolvedValue(response([{ session_id: 'local', player_b_rank_label: '4段' }])); vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(() => usePlayerRanks({ sessionId: 'local', gameState: game, lobbyRoom: true, ...identity }));
    await flush(); expect(label(result.current.B)).toBe('4段'); expect(label(result.current.W)).toBe('等级未知');
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/games/active/multiplayer');
    fetcher.mockResolvedValue(response([{ session_id: 'local', player_b_rank_label: '9段' }, { session_id: 'local', player_b_rank_label: '9段' }]));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); }); expect(label(result.current.B)).toBe('等级未知');
  });
  it('ignores an old room response and never overlaps a slow foreground poll', async () => {
    let resolveOld!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; })).mockResolvedValue(response([{ session_id: 'new', player_b_rank_label: '2段', player_w_rank_label: '1段' }]));
    vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ id }) => usePlayerRanks({ sessionId: id, gameState: game, lobbyRoom: true, ...identity }), { initialProps: { id: 'old' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(7000); }); expect(fetcher).toHaveBeenCalledTimes(1);
    rerender({ id: 'new' }); expect(label(result.current.B)).toBe('等级未知'); await flush(); expect(label(result.current.B)).toBe('2段');
    resolveOld(response([{ session_id: 'old', player_b_rank_label: '9段' }])); await flush(); expect(label(result.current.B)).toBe('2段');
    await act(async () => { await vi.advanceTimersByTimeAsync(29999); }); expect(fetcher).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); }); expect(fetcher).toHaveBeenCalledTimes(3);
  });
  it('only queries the verified real owner and scopes out late account and game responses', async () => {
    let resolveOld!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; })).mockResolvedValue(response(placed('3段')));
    vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ auth, state }) => usePlayerRanks({ sessionId: 'local', gameState: state, ...auth }), { initialProps: { auth: identity, state: game } });
    rerender({ auth: { ...identity, user: { id: 2, uuid: 'account-2' }, token: 'token-2' }, state: game });
    expect(label(result.current.B)).toBe('等级未知'); expect(fetcher).toHaveBeenCalledTimes(1);
    resolveOld(response(placed('9段'))); await flush(); expect(label(result.current.B)).toBe('等级未知');
    rerender({ auth: identity, state: { ...game, game_id: 'game-2', rank_owner: { user_id: 1, color: 'W' } } }); await flush();
    expect(label(result.current.W)).toBe('3段'); expect(label(result.current.B)).toBe('等级未知');
    rerender({ auth: { ...identity, isGuest: true }, state: game }); expect(label(result.current.B)).toBe('等级未知'); expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('does not reuse an old grade when returning to a previous account scope', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(placed('4段'))).mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ guest }) => usePlayerRanks({ sessionId: 'local', gameState: game, ...identity, isGuest: guest }), { initialProps: { guest: false } });
    await flush(); expect(label(result.current.B)).toBe('4段');
    rerender({ guest: true }); expect(label(result.current.B)).toBe('等级未知');
    rerender({ guest: false }); expect(label(result.current.B)).toBe('等级未知');
  });
  it('does not fetch per move or while hidden, refreshes visible return, clears failure and times out', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ placement_state: { phase: 'placement' } })); vi.stubGlobal('fetch', fetcher);
    const { result, rerender } = renderHook(({ state, settlement }) => usePlayerRanks({ sessionId: 'local', gameState: state, settlement, ...identity }), { initialProps: { state: game, settlement: '' } });
    await flush(); expect(label(result.current.B)).toBe('尚未定级');
    rerender({ state: { ...game, current_node_id: 1 }, settlement: '' }); await flush(); expect(fetcher).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' }); act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); }); expect(fetcher).toHaveBeenCalledTimes(1);
    fetcher.mockRejectedValueOnce(new Error('offline'));
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' }); act(() => document.dispatchEvent(new Event('visibilitychange'))); await flush();
    expect(label(result.current.B)).toBe('等级未知'); expect(fetcher).toHaveBeenCalledTimes(2);
    fetcher.mockImplementationOnce(() => new Promise(() => {}));
    rerender({ state: game, settlement: 'settled' }); await flush(); expect(fetcher).toHaveBeenCalledTimes(3);
    await act(async () => { await vi.advanceTimersByTimeAsync(8000); }); expect(label(result.current.B)).toBe('等级未知');
    expect(fetcher.mock.calls[2][1].signal.aborted).toBe(true);
  });
});
