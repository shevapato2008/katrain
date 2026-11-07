import { describe, expect, it } from 'vitest';
import { getGalaxyNavigation, isGalaxyNavigationActive } from './galaxyNavigation';

describe('Galaxy root navigation', () => {
  it('uses the root homepage and root paths for every destination', () => {
    const items = getGalaxyNavigation((_key, fallback) => fallback);
    expect(items.map(({ key, path }) => [key, path])).toEqual([
      ['home', '/'],
      ['play', '/play'],
      ['research', '/research'],
      ['tsumego', '/tsumego'],
      ['review', '/report'],
      ['live', '/live'],
      ['kifu', '/kifu'],
      ['membership', '/membership'],
      ['tutorials', '/tutorials'],
    ]);
  });

  it.each([
    ['/', true],
    ['/play', false],
    ['/play/game/session-1', false],
    ['/galaxy', false],
  ])('marks home active at %s: %s', (pathname, active) => {
    expect(isGalaxyNavigationActive(pathname, '/')).toBe(active);
  });

  it('keeps a section active for its root and descendant routes', () => {
    expect(isGalaxyNavigationActive('/play', '/play')).toBe(true);
    expect(isGalaxyNavigationActive('/play/game/session-1', '/play')).toBe(true);
    expect(isGalaxyNavigationActive('/research', '/play')).toBe(false);
  });
});
