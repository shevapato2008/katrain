import { describe, expect, it } from 'vitest';

import { translateResult } from './resultTranslation';

const fallbackT = (key: string, fallback = '') => fallback || key;

describe('translateResult', () => {
  it('uses readable scoring units when live translations are unavailable', () => {
    expect(translateResult('W+0', fallbackT, 'chinese')).toBe('W+0子');
    expect(translateResult('B+2.5', fallbackT, 'japanese')).toBe('B+2.5目');
  });
});
