import { describe, it, expect } from 'vitest';
import { kioskTheme } from '../theme';

describe('kioskTheme', () => {
  it('is dark mode with slate background', () => {
    expect(kioskTheme.palette.mode).toBe('dark');
    expect(kioskTheme.palette.background.default).toBe('#0f1416');
  });

  it('uses Hanken Grotesk as primary body font', () => {
    expect(kioskTheme.typography.fontFamily).toContain('Hanken Grotesk');
  });

  it('uses Newsreader for h1 and Hanken Grotesk for h3', () => {
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('Newsreader');
    expect((kioskTheme.typography.h3 as any).fontFamily).toContain('Hanken Grotesk');
  });

  it('has jade #58b57a as primary color', () => {
    expect(kioskTheme.palette.primary.main).toBe('#58b57a');
  });

  it('has coral #e2685c as error color', () => {
    expect(kioskTheme.palette.error.main).toBe('#e2685c');
  });

  it('has amber #e0a24a as the single warning/accent token', () => {
    expect(kioskTheme.palette.warning.main).toBe('#e0a24a');
  });

  it('has ice #eef3f1 as primary text color', () => {
    expect(kioskTheme.palette.text.primary).toBe('#eef3f1');
  });

  it('has secondary text with sufficient contrast (WCAG AA)', () => {
    // #93a49d on #0f1416 gives sufficient contrast for AA
    expect(kioskTheme.palette.text.secondary).toBe('#93a49d');
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
