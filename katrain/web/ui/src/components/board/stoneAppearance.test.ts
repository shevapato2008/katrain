import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  BOARD_STYLE_IDS,
  BOARD_STYLE_OPTIONS,
  CHINESE_FONT_IDS,
  CHINESE_FONT_OPTIONS,
  DEFAULT_STONE_APPEARANCE,
  STONE_STYLE_IDS,
  STONE_STYLE_OPTIONS,
  getActiveBoardStyle,
  getActiveStoneStyle,
  getBoardStylePalette,
  getBoardTextureDataUrl,
  getBoardTextureUrl,
  getStoneAppearance,
  normalizeBoardStyleId,
  normalizeChineseFontId,
  normalizeStoneStyleId,
  setActiveBoardStyle,
  setActiveStoneStyle,
  stoneRotationDegrees,
  stoneSpriteUrl,
  stoneVariant,
  subscribeBoardAppearance,
} from './stoneAppearance';

describe('publishable stone appearance and board style store', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defines strictly the 4 stone styles, 4 board styles, and 4 Chinese fonts', () => {
    expect(STONE_STYLE_IDS).toEqual(['clamshell-slate', 'yunzi', 'jade-agate', 'minimal']);
    expect(STONE_STYLE_IDS).not.toContain('mineral-stone');
    expect(STONE_STYLE_IDS).not.toContain('galaxy-star');
    expect(STONE_STYLE_OPTIONS.map(o => o.id)).toEqual(['clamshell-slate', 'yunzi', 'jade-agate', 'minimal']);

    expect(BOARD_STYLE_IDS).toEqual(['kaya', 'shin-kaya', 'bamboo', 'walnut']);
    expect(BOARD_STYLE_OPTIONS.map(o => o.id)).toEqual(['kaya', 'shin-kaya', 'bamboo', 'walnut']);

    expect(CHINESE_FONT_IDS).toEqual(['wenkai', 'kaiti', 'lishu', 'heiti']);
    expect(CHINESE_FONT_OPTIONS.map(o => o.id)).toEqual(['wenkai', 'kaiti', 'lishu', 'heiti']);
  });

  it('normalizes legacy and unknown IDs safely', () => {
    expect(normalizeStoneStyleId('shell-slate')).toBe('clamshell-slate');
    expect(normalizeStoneStyleId('clamshell-slate')).toBe('clamshell-slate');
    expect(normalizeStoneStyleId('yunzi')).toBe('yunzi');
    expect(normalizeStoneStyleId('jade-agate')).toBe('jade-agate');
    expect(normalizeStoneStyleId('minimal')).toBe('minimal');
    expect(normalizeStoneStyleId('mineral-stone')).toBe('clamshell-slate');
    expect(normalizeStoneStyleId('galaxy-star')).toBe('clamshell-slate');
    expect(normalizeStoneStyleId(null)).toBe('clamshell-slate');
    expect(normalizeStoneStyleId(undefined)).toBe('clamshell-slate');

    expect(normalizeBoardStyleId('kaya')).toBe('kaya');
    expect(normalizeBoardStyleId('shin-kaya')).toBe('shin-kaya');
    expect(normalizeBoardStyleId('bamboo')).toBe('bamboo');
    expect(normalizeBoardStyleId('walnut')).toBe('walnut');
    expect(normalizeBoardStyleId('unknown')).toBe('kaya');
    expect(normalizeBoardStyleId(null)).toBe('kaya');

    expect(normalizeChineseFontId('kaiti')).toBe('kaiti');
    expect(normalizeChineseFontId(null)).toBe('wenkai');
  });

  it('falls back to the default for missing or unknown skin IDs', () => {
    expect(getStoneAppearance()).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('missing')).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('toString')).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('shell-slate')).toBe(DEFAULT_STONE_APPEARANCE);
    expect(getStoneAppearance('clamshell-slate')).toBe(DEFAULT_STONE_APPEARANCE);
  });

  it('persists active stone and board styles to localStorage, notifies subscribers, and resets cleanly on clear()', () => {
    const listener = vi.fn();
    const unsubscribe = subscribeBoardAppearance(listener);

    expect(getActiveStoneStyle()).toBe('clamshell-slate');
    expect(getActiveBoardStyle()).toBe('kaya');

    setActiveStoneStyle('jade-agate');
    expect(getActiveStoneStyle()).toBe('jade-agate');
    expect(localStorage.getItem('katrain_stone_style')).toBe('jade-agate');
    expect(listener).toHaveBeenCalledTimes(1);

    setActiveBoardStyle('walnut');
    expect(getActiveBoardStyle()).toBe('walnut');
    expect(localStorage.getItem('katrain_board_style')).toBe('walnut');
    expect(listener).toHaveBeenCalledTimes(2);

    localStorage.clear();
    expect(getActiveStoneStyle()).toBe('clamshell-slate');
    expect(getActiveBoardStyle()).toBe('kaya');

    unsubscribe();
  });

  it('updates stoneSpriteUrl default output immediately when active stone style changes', () => {
    const clamshellUrl = stoneSpriteUrl('W', 19, 3, 3);
    expect(clamshellUrl).toContain('shell-slate');

    setActiveStoneStyle('yunzi');
    const yunziUrl = stoneSpriteUrl('W', 19, 3, 3);
    expect(yunziUrl).toMatch(/^data:image\//);
    expect(yunziUrl).not.toBe(clamshellUrl);

    setActiveStoneStyle('jade-agate');
    const jadeUrl = stoneSpriteUrl('W', 19, 3, 3);
    expect(jadeUrl).toMatch(/^data:image\//);
    expect(jadeUrl).not.toBe(yunziUrl);

    setActiveStoneStyle('minimal');
    const minimalUrl = stoneSpriteUrl('W', 19, 3, 3);
    expect(minimalUrl).toMatch(/^data:image\//);
    expect(minimalUrl).not.toBe(jadeUrl);
  });

  it('provides procedural sprite sets for yunzi (8), jade-agate (16), and minimal (1)', () => {
    const yunzi = getStoneAppearance('yunzi');
    expect(yunzi.sprites.W).toHaveLength(8);
    expect(yunzi.sprites.B).toMatch(/^data:image\//);

    const jade = getStoneAppearance('jade-agate');
    expect(jade.sprites.W).toHaveLength(16);
    expect(jade.sprites.B).toMatch(/^data:image\//);

    const minimal = getStoneAppearance('minimal');
    expect(minimal.sprites.W).toHaveLength(1);
    expect(minimal.sprites.B).toMatch(/^data:image\//);
  });

  it('returns distinct palettes and valid data URLs for all 4 board styles', () => {
    const palettes = BOARD_STYLE_IDS.map(id => getBoardStylePalette(id));
    expect(new Set(palettes.map(p => p.woodFill)).size).toBe(4);
    expect(getBoardStylePalette('walnut').woodFill).toBe('#876244');
    expect(getBoardStylePalette('walnut').gridColor).toBe('#e6c896');
    expect(getBoardStylePalette('walnut').coordColor).toBe('#eedcb0');

    const textures = BOARD_STYLE_IDS.map(id => getBoardTextureDataUrl(id));
    expect(textures.every(url => url.startsWith('data:image/'))).toBe(true);
    expect(new Set(textures).size).toBe(4);

    expect(getBoardTextureUrl('kaya')).toBe('/assets/textures/kaya-veneer-2k.jpg');
    expect(getBoardTextureUrl('shin-kaya')).toBe('/assets/textures/shinkaya-veneer-2k.jpg');
    expect(getBoardTextureUrl('bamboo')).toBe('/assets/textures/bamboo-veneer-2k.jpg');
    expect(getBoardTextureUrl('walnut')).toBe('/assets/textures/walnut-veneer-2k.jpg');
    expect(getBoardTextureUrl('unknown')).toBe('/assets/textures/kaya-veneer-2k.jpg');
  });

  it('keeps all 32 shell orientations stable across replay order and resize', () => {
    expect(DEFAULT_STONE_APPEARANCE.sprites.W).toHaveLength(32);
    const points = [[3, 3], [4, 7], [12, 2], [18, 18]] as const;
    const urls = points.map(([col, row]) => stoneSpriteUrl('W', 'board', col, row));
    expect([...points].reverse().map(([col, row]) => stoneSpriteUrl('W', 'board', col, row)).reverse()).toEqual(urls);
    for (const viewportSize of [600, 1024]) {
      expect(points.map(([col, row]) => {
        const pixelX = (col + 0.5) * viewportSize / 19;
        const pixelY = (row + 0.5) * viewportSize / 19;
        return stoneSpriteUrl('W', 'board', Math.floor(pixelX * 19 / viewportSize), Math.floor(pixelY * 19 / viewportSize));
      })).toEqual(urls);
    }
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
