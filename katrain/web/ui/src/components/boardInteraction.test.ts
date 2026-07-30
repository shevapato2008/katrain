import { describe, expect, test } from 'vitest';
import type { GameState } from '../api';
import { resolveBoardIntersectionAction } from './boardInteraction';

const gameState = (
  stones: GameState['stones'] = [],
  history: GameState['history'] = [],
): GameState => ({ stones, history } as GameState);

describe('resolveBoardIntersectionAction', () => {
  test('returns a move for an empty point', () => {
    expect(resolveBoardIntersectionAction(gameState(), 3, 4, false)).toEqual({ kind: 'move', x: 3, y: 4 });
  });

  test('ignores an occupied point when navigation is disabled', () => {
    const state = gameState([['B', [3, 4], null, 0]], [{ node_id: 17, score: null, winrate: null }]);

    expect(resolveBoardIntersectionAction(state, 3, 4, false)).toEqual({ kind: 'ignore' });
  });

  test('navigates from an occupied point with a valid move number', () => {
    const state = gameState([['W', [5, 6], null, 1]], [
      { node_id: 17, score: null, winrate: null },
      { node_id: 23, score: null, winrate: null },
    ]);

    expect(resolveBoardIntersectionAction(state, 5, 6, true)).toEqual({ kind: 'navigate', nodeId: 23 });
  });

  test('ignores an occupied setup stone without a move number', () => {
    const state = gameState([['B', [7, 8], null, null]]);

    expect(resolveBoardIntersectionAction(state, 7, 8, true)).toEqual({ kind: 'ignore' });
  });
});
