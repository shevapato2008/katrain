import { describe, expect, it } from 'vitest';

import { formatRank, withRank } from './rank';

const t = (key: string, fallback?: string) => ({
  'strength:kyu': '级',
  'strength:dan': '段',
}[key] ?? fallback ?? '');

describe('formatRank', () => {
  it('localizes stored SGF ranks and the numeric KaTrain scale', () => {
    expect(formatRank('6k', t)).toBe('6级');
    expect(formatRank('3D', t)).toBe('3段');
    expect(formatRank(-5, t)).toBe('6级');
    expect(formatRank(3, t)).toBe('3段');
  });

  it('passes legacy free-text ranks through unchanged', () => {
    expect(formatRank('业5', t)).toBe('业5');
    expect(formatRank('amateur 3 dan', t)).toBe('amateur 3 dan');
  });

  it('omits missing and non-finite ranks without leaving a separator', () => {
    expect(formatRank(null, t)).toBe('');
    expect(formatRank(Number.NaN, t)).toBe('');
    expect(withRank('AI', undefined, t)).toBe('AI');
    expect(withRank('AI', '6k', t)).toBe('AI · 6级');
  });
});
