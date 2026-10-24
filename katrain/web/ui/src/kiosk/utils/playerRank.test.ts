import { describe, expect, it } from 'vitest';
import { accountRank, knownRank, seatRank, UNKNOWN_RANK } from './playerRank';
import type { GameState } from '../../api';

describe('kiosk player rank sources', () => {
  it('preserves labels and treats empty labels as unknown', () => {
    for (const raw of [null, undefined, '', '   ']) expect(knownRank(raw)).toEqual(UNKNOWN_RANK);
    for (const raw of ['20k', '9p', '职业九段']) expect(knownRank(raw).label).toBe(raw);
  });
  it('only marks explicit account placement as unrated', () => {
    expect(accountRank({ placement_state: { phase: 'placement' } }).label).toBe('尚未定级');
    expect(accountRank({ placement_state: { phase: 'placed', rung: { rank_name: '3段' } } }).label).toBe('3段');
    expect(accountRank({ placement_state: { phase: 'placed', rung: { rank_name: null } } })).toEqual(UNKNOWN_RANK);
  });
  it('never transfers AI strength to humans or account rank to platform seats', () => {
    const state = { game_type: 'free', players_info: { B: { player_type: 'human', calculated_rank: '8', rank_display: '9段' }, W: { player_type: 'ai', calculated_rank: '20k' } } } as unknown as GameState;
    expect(seatRank(state, 'B')).toEqual(UNKNOWN_RANK);
    expect(seatRank(state, 'W', false, 'cn').label).toBe('20级');
    expect(seatRank(state, 'W').title).toContain('AI');
    expect(seatRank({ ...state, platform_player_ranks: {} }, 'W').label).toBe('20级');
    expect(seatRank({ ...state, game_type: 'pvp_online', platform_player_ranks: { B: '2d' } }, 'B').label).toBe('2d');
    expect(seatRank({ ...state, platform_player_ranks: { W: null }, platform_engine_color: 'W' }, 'W', true)).toEqual(UNKNOWN_RANK);
  });
});
