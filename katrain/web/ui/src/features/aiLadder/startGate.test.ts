import { describe, expect, it } from 'vitest';
import { aiLadderStartBlock, canStartAiLadderGame, isProvisionalSeating } from './startGate';
import type { AiLadderCatalogEntry, AiLadderReadyStatus } from './types';

const rung = (overrides: Partial<AiLadderCatalogEntry> = {}): AiLadderCatalogEntry => ({
  rung: 16,
  rank_name: '5级',
  certification_status: 'certified',
  availability: 'available',
  route: 'server',
  ...overrides,
});

const ready = (overrides: Partial<AiLadderReadyStatus> = {}): AiLadderReadyStatus => ({
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 0, total_games: 5 },
  current_opponent: rung(),
  recent_ranked_results: [],
  net_score: 0,
  pending_settlement: false,
  ...overrides,
});

describe('aiLadderStartBlock', () => {
  it('lets a certified, available rung start', () => {
    expect(aiLadderStartBlock(ready())).toBeNull();
    expect(canStartAiLadderGame(ready())).toBe(true);
  });

  it('blocks while the status is loading or failed', () => {
    expect(aiLadderStartBlock({ view_state: 'loading' })).toBe('not_ready');
    expect(aiLadderStartBlock({ view_state: 'error', message: 'x' })).toBe('not_ready');
  });

  it('blocks while the previous game is still settling', () => {
    expect(aiLadderStartBlock(ready({ pending_settlement: true }))).toBe('pending_settlement');
  });

  it('blocks an uncertified rung on a node that will not seat one', () => {
    expect(aiLadderStartBlock(ready({ current_opponent: rung({ certification_status: 'provisional' }) })))
      .toBe('rung_not_certified');
    expect(aiLadderStartBlock(ready({ current_opponent: rung({ availability: 'unavailable' }) })))
      .toBe('rung_not_certified');
  });

  it('lets the same rung start where the server says it will seat one', () => {
    const status = ready({
      current_opponent: rung({ certification_status: 'provisional', availability: 'unavailable' }),
      provisional_play_allowed: true,
    });
    expect(aiLadderStartBlock(status)).toBeNull();
    // ...and the UI must say the rung is unmeasured, because it still is.
    expect(isProvisionalSeating(status)).toBe(true);
  });

  it('does not call a certified rung provisional just because the switch is on', () => {
    expect(isProvisionalSeating(ready({ provisional_play_allowed: true }))).toBe(false);
  });

  it('treats a server that never sends the field as one that will not seat an uncertified rung', () => {
    const status = ready({ current_opponent: rung({ certification_status: 'provisional' }) });
    expect(status.provisional_play_allowed).toBeUndefined();
    expect(aiLadderStartBlock(status)).toBe('rung_not_certified');
    expect(isProvisionalSeating(status)).toBe(false);
  });

  it('blocks when the server offered no opponent at all', () => {
    expect(aiLadderStartBlock(ready({ current_opponent: null }))).toBe('no_opponent');
  });
});
