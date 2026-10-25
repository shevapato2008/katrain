import { describe, expect, it } from 'vitest';

import { translateResult } from '../../utils/resultTranslation';
import { getListRank, listResult } from './listRecordPresentation';

const translations: Record<string, Record<string, string>> = {
  cn: {
    'result:black_win': '黑胜', 'result:white_win': '白胜',
    'result:resign': '中盘', 'result:time': '超时', 'result:forfeit': '弃权',
    'result:draw': '和棋',
    'review:black': '黑', 'review:white': '白', 'review:by_resign': '中盘', 'review:win': '胜',
  },
  tw: {
    'result:black_win': '黑勝', 'result:white_win': '白勝',
    'result:resign': '中盤', 'result:time': '超時', 'result:forfeit': '棄權',
    'review:black': '黑', 'review:white': '白', 'review:by_resign': '中盤', 'review:win': '勝',
  },
  en: { 'strength:professional_dan_format': 'Professional {rank} dan', 'strength:dan': ' dan', 'strength:kyu': ' kyu' },
  fr: { 'result:black_win': 'N+', 'result:white_win': 'B+', 'result:resign': 'Aband.' },
};
const tFor = (lang: string) => (key: string, fallback = '') => translations[lang]?.[key] ?? fallback;
const cn = tFor('cn');

describe('getListRank', () => {
  it('prefers the display rank and falls back only to the same record raw rank', () => {
    expect(getListRank(' 9p ', '6k', cn)).toBe('职业九段');
    expect(getListRank(' ', '9d', cn)).toBe('业余9段');
    expect(getListRank('unknown', '6k', cn)).toBe('6级');
  });

  it('uses explicit identity and locale while preserving ambiguous saved ranks', () => {
    expect(getListRank('9p', null, cn, 'cn')).toBe('职业九段');
    expect(getListRank(null, '6d', cn, 'cn')).toBe('业余6段');
    expect(getListRank(null, '6k', cn, 'cn')).toBe('6级');
    expect(getListRank('职业9段', null, cn, 'tw')).toBe('職業九段');
    expect(getListRank('業餘六段', null, cn, 'tw')).toBe('業餘6段');
    expect(getListRank('九段', '9p', cn, 'cn')).toBe('职业九段');
    expect(getListRank('九段', null, cn, 'cn')).toBe('九段');
    expect(getListRank('九段', '6p', cn, 'cn')).toBe('九段');
    expect(getListRank('9p', null, tFor('en'), 'en')).toBe('Professional 9 dan');
    expect(getListRank(null, '6d', tFor('en'), 'en')).toBe('6 dan');
  });

  it('returns null when historical ranks are missing or explicitly unknown', () => {
    expect(getListRank(undefined, null, cn)).toBeNull();
    expect(getListRank('', ' ', cn)).toBeNull();
    expect(getListRank('?', '等级未知', cn)).toBeNull();
  });

  it('keeps the existing free-text rank convention', () => {
    expect(getListRank('业5', null, cn)).toBe('业5');
    expect(getListRank(null, 'amateur 3 dan', cn)).toBe('amateur 3 dan');
  });
});

describe('listResult', () => {
  it('puts the method before 胜 only for explicit Chinese resignation results', () => {
    expect(listResult('W+R', cn, undefined, 'cn')).toEqual({ label: '白中盘胜', winner: 'W' });
    expect(listResult('B+Resignation', cn, undefined, 'cn')).toEqual({ label: '黑中盘胜', winner: 'B' });
    expect(listResult('白胜中盘', cn, undefined, 'cn')).toEqual({ label: '白中盘胜', winner: 'W' });
    expect(listResult('白中盘胜', cn, undefined, 'cn')).toEqual({ label: '白中盘胜', winner: 'W' });
  });

  it('treats the player who resigns as the loser', () => {
    expect(listResult('白认输', cn, undefined, 'cn')).toEqual({ label: '黑中盘胜', winner: 'B' });
    expect(listResult('黑認輸', cn, undefined, 'cn')).toEqual({ label: '白中盘胜', winner: 'W' });
  });

  it('uses traditional Chinese translation words for tw and accepts traditional input', () => {
    const tw = tFor('tw');
    expect(listResult('W+Resign', tw, undefined, 'tw')).toEqual({ label: '白中盤勝', winner: 'W' });
    expect(listResult('白勝中盤', tw, undefined, 'tw')).toEqual({ label: '白中盤勝', winner: 'W' });
    expect(listResult('白認輸', tw, undefined, 'tw')).toEqual({ label: '黑中盤勝', winner: 'B' });
  });

  it('preserves timeout, forfeit, and scoring units through the existing formatter', () => {
    expect(listResult('B+T', cn, 'chinese', 'cn')).toEqual({ label: '黑胜超时', winner: 'B' });
    expect(listResult('W+F', cn, undefined, 'cn')).toEqual({ label: '白胜弃权', winner: 'W' });
    expect(listResult('B+6.5', cn, 'chinese', 'cn')).toEqual({ label: '黑胜6.5子', winner: 'B' });
    expect(listResult('W+0.5', cn, 'japanese', 'cn')).toEqual({ label: '白胜0.5目', winner: 'W' });
  });

  it('keeps the winner consistent with explicit Chinese wins', () => {
    expect(listResult('黑胜', cn, undefined, 'cn')).toEqual({ label: '黑胜', winner: 'B' });
    expect(listResult('白勝', tFor('tw'), undefined, 'tw')).toEqual({ label: '白勝', winner: 'W' });
  });

  it('does not invent a winner for draws, absent results, or unknown formats', () => {
    for (const raw of ['Draw', '0', 'Void', '?', '', undefined, 'W+banana', '白认输中', '黑胜：']) {
      expect(listResult(raw, cn, undefined, 'cn')).toEqual({
        label: translateResult(raw, cn), winner: null,
      });
    }
  });

  it('preserves existing labels in English and other non-Chinese languages', () => {
    for (const lang of ['en', 'fr']) {
      const t = tFor(lang);
      expect(listResult('W+R', t, undefined, lang)).toEqual({
        label: translateResult('W+R', t), winner: 'W',
      });
      expect(listResult('白认输', t, undefined, lang)).toEqual({ label: '白认输', winner: 'B' });
      expect(listResult('B+2.5', t, 'japanese', lang)).toEqual({
        label: translateResult('B+2.5', t, 'japanese'), winner: 'B',
      });
    }
  });
});
