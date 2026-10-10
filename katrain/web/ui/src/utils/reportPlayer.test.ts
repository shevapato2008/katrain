import { describe, expect, it } from 'vitest';
import { reportPlayerToMove } from './reportPlayer';

describe('reportPlayerToMove', () => {
  it('uses recorded SGF colors for handicap and white-to-play games', () => {
    expect(reportPlayerToMove(['B', 'B', 'W', 'B'], 2, 2)).toBe('W');
    expect(reportPlayerToMove(['W', 'B'], 0)).toBe('W');
  });

  it('uses the last move at the end of a game', () => {
    expect(reportPlayerToMove(['B', 'W'], 2)).toBe('B');
    expect(reportPlayerToMove(['B', 'B'], 2, 2)).toBe('W');
  });
});
