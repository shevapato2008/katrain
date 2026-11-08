import { describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { kioskMessages, kioskText } from './messages';
import { OGS_COURSE_LANGUAGE } from '../tutorial/useOgsLocale';
describe('five-locale Go appearance and course presentation', () => {
  it('uses the actual OGS catalog language IDs', () => {
    expect(OGS_COURSE_LANGUAGE).toEqual({ cn: 'zh-cn', tw: 'zh-tw', en: 'en', jp: 'ja', ko: 'ko' });
  });
  it('supplies every visible control and preserves placeholders in each language', () => {
    const placeholders = (value: string) => [...new Set([...value.matchAll(/\{\w+\}/g)].map(x => x[0]))].sort();
    for (const variants of Object.values(kioskMessages)) {
      for (const locale of ['cn', 'tw', 'en', 'jp', 'ko'] as const) {
        expect(variants[locale].trim()).not.toBe('');
        expect(placeholders(variants[locale])).toEqual(placeholders(variants.en));
      }
    }
    expect(kioskText('jp', 'stepProgress', { step: 3, count: 7 })).toBe('ステップ 3 / 7');
  });
  it('ships its own licensed script-only font and keeps Latin/brand/coordinate ownership', () => {
    const dir = 'src/kiosk-shell/';
    const font = readFileSync(dir + 'fonts/noto-sans-cjk-jp-kr-scripts.woff2');
    expect(createHash('sha256').update(font).digest('hex')).toBe('f4294c2d2587c85dab34943bd9011052a364dcb8e6bca98d24c43a3ce06469e5');
    const css = readFileSync(dir + 'fonts.css', 'utf8');
    const face = css.match(/@font-face\{font-family:"SmartBox CJK Scripts"[^}]+\}/)?.[0];
    expect(face).toContain('U+AC00-D7AF');
    expect(face).not.toContain('U+4E00');
    expect(face).not.toContain('U+0000');
    expect(css).toContain('font-family:"SmartBox Brand LongCang"');
  });
});
