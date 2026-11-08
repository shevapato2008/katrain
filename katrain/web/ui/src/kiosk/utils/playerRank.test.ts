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
    for (const label of ['准6D', '职业', '职业顶尖', '超职业']) expect(accountRank({ placement_state: { phase: 'placed', rung: { rank_name: label } } }).label).toBe(label);
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

describe('owned rank presentation', () => {
  it('localizes known canonical ranks and source labels while preserving custom ranks', async () => {
    const { rankLabel, presentPlayerRank } = await import('./playerRank');
    const words: Record<string, string> = { 'rank:provisional': 'Near {rank}', 'rank:dan': '{n} dan', 'rank:amateur': 'Amateur {rank}', 'rank:professional': 'Professional', 'rank:unknown': 'Rank unknown', 'rank:account_source': 'Account rank' };
    const t = (key: string, fallback?: string) => words[key] ?? fallback ?? key;
    expect(rankLabel('准6D', t)).toBe('Near 6 dan');
    expect(rankLabel('业余 3 段', t)).toBe('Amateur 3 dan');
    expect(rankLabel('职业', t)).toBe('Professional');
    expect(rankLabel('Alice custom 段', t)).toBe('Alice custom 段');
    for (const raw of ['constructor', 'toString', '__proto__']) expect(rankLabel(raw, t)).toBe(raw);
    expect(presentPlayerRank(knownRank('职业九段'), t).label).toBe('职业九段');
    expect(presentPlayerRank(UNKNOWN_RANK, t).label).toBe('Rank unknown');
    expect(presentPlayerRank({ label: '3段', title: '账号等级 · 3段' }, t)).toEqual({ label: '3 dan', title: 'Account rank · 3 dan' });
  });
});

describe('native display fields', () => {
  it('maps owned platform and adaptation reasons while preserving identifiers', async () => {
    const { platformLabel, boardVariantReason } = await import('./nativePresentation');
    const words: Record<string, string> = { '自由战': 'Free game', '进行中': 'Playing', '{n} 手': 'Move {n}', '本次未能确认局部目标': 'Local target could not be verified' };
    const t = (key: string, fallback?: string) => words[key] ?? fallback ?? key;
    expect(platformLabel('自由战', t)).toBe('Free game');
    expect(platformLabel('42手', t)).toBe('Move 42');
    expect(platformLabel('room_$&', t)).toBe('room_$&');
    expect(boardVariantReason('本次未能确认局部目标', t)).toBe('Local target could not be verified');
    expect(boardVariantReason('Source title 原题', t)).toBe('Source title 原题');
  });
});
