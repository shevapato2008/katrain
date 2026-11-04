import { describe, expect, it } from 'vitest';

import { formatKifuRank, formatRank, withRank } from './rank';

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

  it('localizes SGF professional dan ranks distinctly from amateur dan', () => {
    expect(formatRank('5p', t)).toBe('职业五段');
    expect(formatRank(' 4P ', t)).toBe('职业四段');
    expect(formatRank('职业七段', t)).toBe('职业七段');
    expect(formatRank('職業7段', (key, fallback) => key === 'strength:professional_dan_format' ? '職業{rank}段' : fallback ?? '')).toBe('職業七段');
    expect(formatRank('7p', (key, fallback) => key === 'strength:professional_dan_format' ? 'Professional {rank} dan' : fallback ?? '')).toBe('Professional 7 dan');
  });

  it('localizes a Chinese numeral dan field while retaining Chinese spelling', () => {
    expect(formatRank('六段', t)).toBe('六段');
    expect(formatRank('六段', (key, fallback) => ({
      'strength:dan': 'dan',
    } as Record<string, string>)[key] ?? fallback ?? '')).toBe('6dan');
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

describe('formatKifuRank', () => {
  it('respects an explicit API empty rank while retaining legacy fallback', () => {
    expect(formatKifuRank('', '前人', t, 'cn')).toBeNull();
    expect(formatKifuRank('', '9p', t, 'en')).toBeNull();
    expect(formatKifuRank(null, '9p', t, 'cn')).toBe('九段');
    expect(formatKifuRank(undefined, '7d', t, 'cn')).toBe('7段');
    expect(formatKifuRank(' ', '9p', t, 'cn')).toBe('九段');
    expect(formatRank('前人', t)).toBe('前人');
  });

  it.each(['cn', 'tw'])('uses the same ninth-dan wording for professional and unspecified ranks in %s', (lang) => {
    for (const rank of ['9p', ' 9P ', '职业九段', '職業九段', '职业9段', '職業9段', '9段', '九段']) {
      expect(formatKifuRank(rank, null, t, lang)).toBe('九段');
    }
    expect(formatKifuRank(null, '9p', t, lang)).toBe('九段');
    expect(formatKifuRank('9d', null, t, lang)).toBe(lang === 'tw' ? '業餘9段' : '业余9段');
    expect(formatRank('9p', t)).toBe('职业九段');
  });

  it('uses the normalized display rank without reclassifying it from raw legacy dan', () => {
    expect(formatKifuRank('7段', '7d', t, 'cn')).toBe('七段');
    expect(formatKifuRank('七段', '7p', t, 'cn')).toBe('七段');
    expect(formatKifuRank('7p', '7d', t, 'cn')).toBe('七段');
    expect(formatKifuRank('7d', '7d', t, 'cn')).toBe('业余7段');
    expect(formatKifuRank('7d', null, t, 'tw')).toBe('業餘7段');
    expect(formatKifuRank('7段', '7d', (key, fallback) => key === 'strength:dan' ? ' dan' : fallback ?? '', 'en')).toBe('7 dan');
  });

  it('keeps unqualified raw dan honest while retaining explicit amateur and kyu', () => {
    expect(formatKifuRank(null, '7d', t, 'cn')).toBe('7段');
    expect(formatKifuRank(null, '业余七段', t, 'cn')).toBe('业余7段');
    expect(formatKifuRank(null, '7p', t, 'tw')).toBe('七段');
    expect(formatKifuRank('6k', '7d', t, 'cn')).toBe('6级');
    expect(formatKifuRank('?', 'unknown', t, 'cn')).toBeNull();
    expect(formatRank('7d', t)).toBe('7段');
    expect(formatRank(7, t)).toBe('7段');
  });
});
