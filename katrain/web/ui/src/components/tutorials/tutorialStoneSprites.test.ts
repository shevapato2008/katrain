import { expect, it } from 'vitest';
import { stoneVariant, TUTORIAL_WHITE_VARIANT_COUNT } from './tutorialStoneSprites';

it('keeps each figure point stable regardless of replay order and spreads white angles', () => {
  const points = [[3, 3], [4, 7], [12, 2], [18, 18]] as const;
  const first = points.map(([col, row]) => stoneVariant('figure:1030', col, row));
  const reversed = [...points].reverse().map(([col, row]) => stoneVariant('figure:1030', col, row)).reverse();
  expect(reversed).toEqual(first);
  expect(first).not.toEqual(points.map(([col, row]) => stoneVariant('figure:1031', col, row)));
  const board = Array.from({ length: 19 * 19 }, (_, i) => stoneVariant('figure:1030', i % 19, Math.floor(i / 19)));
  expect(board.every(value => Number.isInteger(value) && value >= 0 && value < TUTORIAL_WHITE_VARIANT_COUNT)).toBe(true);
  expect(new Set(board).size).toBe(TUTORIAL_WHITE_VARIANT_COUNT);
});
