import { describe, expect, it } from 'vitest';

import { translateResult } from './resultTranslation';

const fallbackT = (key: string, fallback = '') => fallback || key;
const translations: Record<string, Record<string, string>> = {
  cn: { 'result:black_win': '黑胜', 'result:white_win': '白胜', 'result:resign': '中盘' },
  tw: { 'result:black_win': '黑勝', 'result:white_win': '白勝', 'result:resign': '中盤' },
  fr: { 'result:black_win': 'N+', 'result:white_win': 'B+' },
};
const tFor = (lang: string) => (key: string, fallback = '') => translations[lang]?.[key] ?? fallback;

describe('translateResult', () => {
  it('uses readable scoring units when live translations are unavailable', () => {
    expect(translateResult('W+0', fallbackT, 'chinese')).toBe('W+0子');
    expect(translateResult('B+2.5', fallbackT, 'japanese')).toBe('B+2.5目');
  });

  it('localizes a known winner without inventing a method or margin', () => {
    expect(translateResult(' B+ ', tFor('cn'))).toBe('黑胜');
    expect(translateResult('w+', tFor('tw'))).toBe('白勝');
    expect(translateResult('b+', tFor('fr'))).toBe('N+');
    expect(translateResult('W+', fallbackT)).toBe('W+');
    expect(translateResult('B+R', tFor('cn'))).toBe('黑胜中盘');
  });

  it('preserves uncertain or unsupported score details in full', () => {
    for (const raw of ['W+11.5?', 'B+1?', 'W+2.5 penalty', 'W+banana', '白胜2.5子（罚点）', '黑胜1/0子']) {
      expect(translateResult(raw, tFor('cn'), 'chinese')).toBe(raw);
    }
  });

  it('recognizes the observed denominator-first and escaped fractions', () => {
    expect(translateResult('白胜4分之1子', tFor('cn'))).toBe('白胜0.25子');
    expect(translateResult('白胜四分之一子', tFor('cn'))).toBe('白胜0.25子');
    expect(translateResult('白胜1\\/4子', tFor('cn'))).toBe('白胜0.25子');
    expect(translateResult('黑胜3\\/4子', tFor('cn'))).toBe('黑胜0.75子');
    expect(translateResult('黑胜2又3/4子', tFor('cn'))).toBe('黑胜2.75子');
    expect(translateResult('白胜二又四分之一子', tFor('cn'))).toBe('白胜2.25子');
    expect(translateResult('白胜3目半', tFor('cn'))).toBe('白胜3.5目');
  });
});
