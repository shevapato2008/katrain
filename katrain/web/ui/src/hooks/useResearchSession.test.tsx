import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useResearchSession } from './useResearchSession';
import type { GameState } from '../api';

const mocks = vi.hoisted(() => ({ base: {} as Record<string, unknown>, getCatalog: vi.fn(), createQuote: vi.fn(), createPosition: vi.fn(), toggleUI: vi.fn() }));
vi.mock('./useSessionBase', () => ({ useSessionBase: () => mocks.base }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ identityKey: 'person-a', status: 'authenticated', token: null }) }));
vi.mock('../api/membershipApi', () => ({ membershipApi: { getCatalog: mocks.getCatalog, createQuote: mocks.createQuote, createPosition: mocks.createPosition } }));
vi.mock('../api', async (original) => ({ ...await original<typeof import('../api')>(), API: { toggleUI: mocks.toggleUI } }));
const state = { game_id: 'local-game', board_size: [19, 19], komi: 7.5, ruleset: 'chinese', current_node_id: 1,
  current_node_index: 1, history: [{ node_id: 0, score: 9, winrate: 0.99 }, { node_id: 1, player: 'B', move: 'D4', score: 8, winrate: 0.98 }],
  stones: [['B', [3, 3], null, 1]], analysis: { moves: [{ move: 'Q16' }], ownership: [[9]], winrate: 0.99 },
  ui_state: { show_hints: true, show_ownership: true, show_coordinates: true } } as unknown as GameState;
beforeEach(() => {
  vi.resetAllMocks();
  mocks.base = { sessionId: 'local-session', gameState: state, setGameState: vi.fn(), error: null };
  mocks.getCatalog.mockResolvedValue({ membership_mode: 'enabled', capabilities: { quotes: true, positions: true } });
  mocks.createQuote.mockResolvedValue({ token: 'signed' });
  mocks.createPosition.mockResolvedValue({ operation_id: 'op-1', state: 'succeeded', result: { ownership: Array(361).fill(0.2), moves: [{ move: 'D4', visits: 500, winrate: 0.6, score_lead: 2 }], rootInfo: { visits: 500, winrate: 0.6, scoreLead: 2 } } });
});
it('uses an owner-scoped HTTP result without inheriting private WebSocket analysis', async () => {
  const { result, rerender } = renderHook(() => useResearchSession());
  expect(result.current.gameState?.analysis?.moves ?? []).toHaveLength(0);
  expect(result.current.gameState?.history.every(node => node.score == null && node.winrate == null)).toBe(true);
  await act(async () => { await result.current.toggleHints(); });
  expect(mocks.toggleUI).not.toHaveBeenCalled();
  expect(mocks.createPosition).not.toHaveBeenCalled();
  await act(async () => { await result.current.confirmAnalysis(); });
  expect(mocks.createQuote).toHaveBeenCalledWith(expect.objectContaining({ session_id: 'local-session' }), null);
  expect(result.current.gameState?.analysis?.moves[0].move).toBe('D4');
  expect(result.current.gameState?.analysis?.ownership).toHaveLength(19);
  expect(result.current.gameState?.stones).toEqual(state.stones);
  mocks.base = { ...mocks.base, gameState: { ...state, current_node_id: 2 } };
  rerender();
  expect(result.current.gameState?.analysis?.moves ?? []).toHaveLength(0);
});
