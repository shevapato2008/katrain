import { describe, expect, it } from 'vitest';
import {
  DEFAULT_STONE_APPEARANCE,
  getStoneAppearance,
  stoneRotationDegrees,
  stoneSpriteUrl,
  stoneVariant,
} from './stoneAppearance';

describe('publishable stone appearance', () => {
  it('falls back to the default for missing or unknown skin IDs', () => {
    expect(getStoneAppearance()).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('missing')).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('toString')).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('shell-slate')).toBe(DEFAULT_STONE_APPEARANCE);
  });

  it('keeps shell variants stable across replay order and uses every available variant', () => {
    const points = [[3, 3], [4, 7], [12, 2], [18, 18]] as const;
    const urls = points.map(([col, row]) => stoneSpriteUrl('W', 'board', col, row));
    expect([...points].reverse().map(([col, row]) => stoneSpriteUrl('W', 'board', col, row)).reverse()).toEqual(urls);
    const board = Array.from({ length: 361 }, (_, i) => stoneSpriteUrl('W', 'board', i % 19, Math.floor(i / 19)));
    expect(new Set(board)).toEqual(new Set(DEFAULT_STONE_APPEARANCE.sprites.W));
    expect(stoneSpriteUrl('B', 'board', 2, 3, 'missing')).toBe(DEFAULT_STONE_APPEARANCE.sprites.B);
    expect(stoneVariant('board', 4, 7)).toBe(stoneVariant('board', 4, 7));
    expect(stoneVariant('board', 4, 7, 1)).toBe(0);
  });

  it('ships photo-free model-rendered PNG URLs and a renderer-independent material recipe', () => {
    const { sprites, material3d } = DEFAULT_STONE_APPEARANCE;
    for (const url of [sprites.B, ...sprites.W]) {
      expect(/\/shell-slate\/[^/]+\.png$/.test(url)).toBe(true);
      expect(url).not.toContain('tutorial-stones');
    }
    expect(material3d?.W.shell?.opacity).toBeGreaterThan(0);
    expect(material3d?.B.metalness).toBe(0);
  });

  it('keeps varied placement angles stable at each intersection', () => {
    const angles = Array.from({ length: 361 }, (_, i) => stoneRotationDegrees(19, i % 19, Math.floor(i / 19)));
    expect(new Set(angles).size).toBeGreaterThan(100);
    expect(angles.every(angle => angle >= 0 && angle < 360)).toBe(true);
    expect(stoneRotationDegrees(19, 4, 7)).toBe(stoneRotationDegrees(19, 4, 7));
  });
});
