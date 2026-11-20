import { describe, expect, it } from 'vitest';
import type { GameState } from '../../api';
import { projectPaidPlayPosition } from './usePaidPlayPosition';

describe('private play result projection', () => {
  it('maps KataGo top-left ownership to board A19 without mirroring rows or changing black evaluation', () => {
    const raw = { board_size: [19, 19], current_node_id: 1, player_to_move: 'W',
      history: [{ node_id: 0, score: 8, winrate: 0.8 }, { node_id: 1, score: null, winrate: null }],
      stones: [], ui_state: {},
    } as unknown as GameState;
    const ownership = Array(361).fill(0);
    ownership[0] = 1; // KataGo A19 (top left): black.
    ownership[360] = -0.75; // KataGo T1 (bottom right): white.
    const projected = projectPaidPlayPosition(raw, { ownership, moves: [], rootInfo: { visits: 500, winrate: 0.61, scoreLead: 2.5 } });
    expect(projected.analysis.ownership[18][0]).toBe(1); // Board A19.
    expect(projected.analysis.ownership[0][18]).toBe(-0.75); // Board T1.
    expect(projected.analysis.ownership[0][0]).toBe(0); // A1 stays neutral.
    expect(projected.analysis.ownership[18][18]).toBe(0); // T19 stays neutral.
    expect(projected.history).toEqual([{ node_id: 0, score: null, winrate: null }, { node_id: 1, score: 2.5, winrate: 0.61 }]);
    expect(ownership[0]).toBe(1);
    expect(raw.history[0].score).toBe(8);
  });
});
