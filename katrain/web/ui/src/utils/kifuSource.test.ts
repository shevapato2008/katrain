import { describe, expect, it } from 'vitest';
import { kifuSourceLabel } from './kifuSource';

const fallback = (_key: string, value?: string) => value ?? '';

describe('棋谱来源标签', () => {
  it('无编译词条时中文仍认得星阵，19x19 不被误标', () => {
    expect(kifuSourceLabel('golaxy', fallback, 'cn')).toBe('星阵');
    expect(kifuSourceLabel('19x19', fallback, 'cn')).toBe('19x19');
    expect(kifuSourceLabel('cwi', fallback, 'cn')).toBe('CWI');
    expect(kifuSourceLabel('unknown', fallback, 'cn')).toBe('来源待核实');
  });
});
