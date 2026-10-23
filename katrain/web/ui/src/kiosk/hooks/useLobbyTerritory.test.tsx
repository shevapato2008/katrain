import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { API, type LobbyTerritoryResult } from '../../api';
import { useLobbyTerritory } from './useLobbyTerritory';
const scope = { sessionId: 's1', gameId: 'g1', nodeId: 5, moveCount: 5, boardSize: [3, 2] as [number, number], enabled: true };
const answer: LobbyTerritoryResult = { session_id: 's1', game_id: 'g1', current_node_id: 5, move_count: 5,
  board_size: [3, 2], ownership: [1, 0, -1, .5, 0, -.5], black_area: 2, white_area: 2, stale: false };
beforeEach(() => vi.restoreAllMocks());
describe('lobby territory', () => {
  it('is click-only, guards duplicates, orients ownership and toggles the current overlay', async () => {
    let resolve!: (value: LobbyTerritoryResult) => void;
    const request = vi.spyOn(API, 'lobbyTerritory').mockImplementation(() => new Promise(r => { resolve = r; }));
    const { result, rerender } = renderHook(p => useLobbyTerritory(p), { initialProps: scope });
    expect(request).not.toHaveBeenCalled();
    act(() => { void result.current.request(); void result.current.request(); });
    expect(result.current.phase).toBe('loading');
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => resolve(answer));
    expect(result.current.overlay?.ownership[0]).toEqual({ col: 0, row: 1, value: 1 });
    expect(result.current.overlay?.ownership[5]).toEqual({ col: 2, row: 0, value: -.5 });
    act(() => { void result.current.request(); });
    expect(result.current.overlay).toBeNull();
    act(() => { void result.current.request(); });
    expect(result.current.overlay).not.toBeNull();
    rerender({ ...scope, nodeId: 6, moveCount: 6 });
    expect(result.current.phase).toBe('idle');
    expect(result.current.overlay).toBeNull();
    expect(request).toHaveBeenCalledTimes(1);
  });
  it('keeps failures retryable without reporting success', async () => {
    const request = vi.spyOn(API, 'lobbyTerritory').mockRejectedValueOnce(new Error('unavailable')).mockResolvedValueOnce(answer);
    const { result } = renderHook(() => useLobbyTerritory(scope));
    await act(async () => { await result.current.request(); });
    expect(result.current.phase).toBe('error');
    expect(result.current.overlay).toBeNull();
    expect(result.current.disabled).toBe(false);
    await act(async () => { await result.current.request(); });
    expect(request).toHaveBeenCalledTimes(2);
    expect(result.current.phase).toBe('result');
  });
  it.each([{ ...scope, nodeId: 6 }, { ...scope, gameId: 'g2' }, { ...scope, sessionId: 's2' },
    { ...scope, moveCount: 6 }, { ...scope, enabled: false }])('discards late scope/availability answers: %j', async next => {
    let resolve!: (value: LobbyTerritoryResult) => void;
    vi.spyOn(API, 'lobbyTerritory').mockImplementation(() => new Promise(r => { resolve = r; }));
    const { result, rerender } = renderHook(p => useLobbyTerritory(p), { initialProps: scope });
    act(() => { void result.current.request(); });
    rerender(next);
    await act(async () => resolve(answer));
    expect(result.current.overlay).toBeNull();
    expect(result.current.phase).toBe('idle');
  });
  it.each([{ ...answer, stale: true }, { ...answer, session_id: 'wrong' }, { ...answer, game_id: 'wrong' },
    { ...answer, current_node_id: 7 }, { ...answer, move_count: 7 }, { ...answer, board_size: [2, 3] },
    { ...answer, ownership: [1] }, { ...answer, ownership: [NaN, 0, 0, 0, 0, 0] }])('rejects stale/invalid replies: %j', async invalid => {
    vi.spyOn(API, 'lobbyTerritory').mockResolvedValue(invalid as LobbyTerritoryResult);
    const { result } = renderHook(() => useLobbyTerritory(scope));
    await act(async () => { await result.current.request(); });
    expect(result.current.overlay).toBeNull();
    expect(result.current.phase).not.toBe('result');
    expect(result.current.disabled).toBe(false);
  });
  it('discards a pending answer across disable and reenable of the same node', async () => {
    let resolve!: (value: LobbyTerritoryResult) => void;
    vi.spyOn(API, 'lobbyTerritory').mockImplementation(() => new Promise(r => { resolve = r; }));
    const { result, rerender } = renderHook(p => useLobbyTerritory(p), { initialProps: scope });
    act(() => { void result.current.request(); });
    rerender({ ...scope, enabled: false });
    rerender(scope);
    await act(async () => resolve(answer));
    expect(result.current.overlay).toBeNull();
    expect(result.current.phase).toBe('idle');
  });
  it('does not revive a cached answer after disconnect/reconnect', async () => {
    vi.spyOn(API, 'lobbyTerritory').mockResolvedValue(answer);
    const { result, rerender } = renderHook(p => useLobbyTerritory(p), { initialProps: scope });
    await act(async () => { await result.current.request(); });
    rerender({ ...scope, enabled: false });
    rerender(scope);
    expect(result.current.overlay).toBeNull();
    expect(result.current.phase).toBe('idle');
  });
});
