import { describe, expect, it } from 'vitest';
import { reportPlatformLabel } from './reportOrigin';
const t = (_key: string, fallback?: string) => fallback ?? _key;

describe('trusted report platform labels', () => {
  it('uses only accepted platform IDs on played games', () => {
    expect(reportPlatformLabel({ source: 'play_ai', platform: 'golaxy' }, t)).toBe('Cross-platform · Golaxy');
    expect(reportPlatformLabel({ source: 'play_human', platform: 'ogs' }, t)).toBe('Cross-platform · OGS');
    expect(reportPlatformLabel({ source: 'play_ai', platform: 'fox' }, t)).toBe('Cross-platform · Fox');
    expect(reportPlatformLabel({ source: 'play_ai' }, t)).toBeNull();
    expect(reportPlatformLabel({ source: 'play_ai', platform: 'unknown' }, t)).toBeNull();
  });
  it('never relabels imported, library or research records as participation', () => {
    for (const source of ['import', 'kifu_library', 'research', 'play_local']) {
      expect(reportPlatformLabel({ source, platform: 'golaxy' }, t)).toBeNull();
    }
  });
});
