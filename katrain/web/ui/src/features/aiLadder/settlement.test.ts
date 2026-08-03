import { describe, expect, it, vi } from 'vitest';
import { deriveSettlementFeedback, pollAiLadderSettlement } from './settlement';

const entry = (rung: number, rank_name = `${rung}级`) => ({ rung, rank_name, certification_status: 'certified' as const, availability: 'available' as const, route: 'server' as const });
const placed = (rung: number, net_score = 0) => ({ view_state: 'ready' as const, placement_state: { phase: 'placed' as const, rung: entry(rung) }, current_opponent: entry(rung), recent_ranked_results: [], net_score: net_score as -2 | -1 | 0 | 1 | 2, pending_settlement: false });
const placement = (completed_games: number) => ({ view_state: 'ready' as const, placement_state: { phase: 'placement' as const, completed_games, total_games: 5 as const }, current_opponent: entry(10), recent_ranked_results: [], net_score: 0 as const, pending_settlement: false });

describe('AI ladder settlement feedback', () => {
  it('distinguishes placement completion, promotion, demotion and score-only change', () => {
    expect(deriveSettlementFeedback(placement(4), placed(18)).kind).toBe('placement_complete');
    expect(deriveSettlementFeedback(placed(18, 2), placed(19, 0)).kind).toBe('promotion');
    expect(deriveSettlementFeedback(placed(18, -2), placed(17, 0)).kind).toBe('demotion');
    expect(deriveSettlementFeedback(placed(18, 0), placed(18, 1)).kind).toBe('score_change');
    expect(deriveSettlementFeedback(placed(18, 1), placed(18, 1)).kind).toBe('no_change');
  });

  it('does not guess a transition without a pre-game snapshot', () => {
    expect(deriveSettlementFeedback(null, placed(18))).toEqual(expect.objectContaining({ kind: 'authoritative_complete' }));
  });

  it('polls pending settlement a finite number of times and returns the final authority', async () => {
    const pending = { ...placed(18), pending_settlement: true };
    const getStatus = vi.fn().mockResolvedValueOnce(pending).mockResolvedValueOnce(placed(19));
    const result = await pollAiLadderSettlement(getStatus, undefined, new AbortController().signal, 4, async () => {});
    expect(result.placement_state).toEqual(expect.objectContaining({ phase: 'placed', rung: expect.objectContaining({ rung: 19 }) }));
    expect(getStatus).toHaveBeenCalledTimes(2);
  });
});
