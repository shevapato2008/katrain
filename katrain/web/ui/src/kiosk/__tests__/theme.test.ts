import { describe, it, expect } from 'vitest';
import { kioskTheme } from '../theme';

describe('kioskTheme', () => {
  it('is dark mode with ink-black background', () => {
    expect(kioskTheme.palette.mode).toBe('dark');
    expect(kioskTheme.palette.background.default).toBe('#1a1714');
  });

  it('uses Noto Sans SC as primary body font', () => {
    expect(kioskTheme.typography.fontFamily).toContain('Noto Sans SC');
  });

  it('uses Noto Serif SC only for h1', () => {
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('Noto Serif SC');
    // h3+ should use Sans, not Serif
    expect((kioskTheme.typography.h3 as any).fontFamily).toContain('Noto Sans SC');
  });

  it('has jade-glow #5cb57a as primary color', () => {
    expect(kioskTheme.palette.primary.main).toBe('#5cb57a');
  });

  it('has ember #c45d3e as error color', () => {
    expect(kioskTheme.palette.error.main).toBe('#c45d3e');
  });

  it('has secondary text with sufficient contrast (WCAG AA)', () => {
    // #9a9590 on #1a1714 gives ~4.7:1 ratio (AA requires 4.5:1)
    expect(kioskTheme.palette.text.secondary).toBe('#9a9590');
  });

  it('does NOT globally force button minHeight', () => {
    const overrides = kioskTheme.components?.MuiButton?.styleOverrides as any;
    expect(overrides.root.minHeight).toBeUndefined();
  });

  it('enforces 48px min icon button size for touch targets', () => {
    const overrides = kioskTheme.components?.MuiIconButton?.styleOverrides as any;
    expect(overrides.root.minWidth).toBe(48);
    expect(overrides.root.minHeight).toBe(48);
  });
});
