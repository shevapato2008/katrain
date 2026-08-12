import { describe, it, expect } from 'vitest';
import { kioskTheme } from '../theme';

describe('kioskTheme', () => {
  it('is dark mode with slate background', () => {
    expect(kioskTheme.palette.mode).toBe('dark');
    expect(kioskTheme.palette.background.default).toBe('#0f1416');
  });

  // 这两条原来钉的是 'Hanken Grotesk' / 'Newsreader'。**规则过期了,陷阱没有**:
  // 规范 §9(`kiosk-shell-spec.md:634/648`)把中文定成霞鹜文楷、把 Noto Sans SC 列为退役,
  // 而 Hanken Grotesk 从来不在字库表里 —— 所以改的是期望值,不是删掉这两条。
  // 它们守的那个陷阱一直在:**有人把 `typography` 里的字族拆掉或写回某个具体西文族**,
  // 而那种改动在屏上只表现为「中文忽然变成系统字」,不报错。
  //
  // ⚠️ 但这里必须说清这两条**答不了什么**:它们读的是主题对象里的字符串,
  // 证明不了「屏上那些字真的是用这个字体画的」。kiosk 有 22 处 `sx={{ fontFamily }}`
  // 绕开主题直接写栈,这两条对它们一无所知 —— 那一层归 `tests/kiosk-font-routing.spec.ts`
  // 用 CDP 问浏览器。**声明层和渲染层是两道闸,谁也替不了谁。**
  it('body 字族走 SmartBox Sans,中文回退到楷体', () => {
    expect(kioskTheme.typography.fontFamily).toContain('SmartBox Sans');
    expect(kioskTheme.typography.fontFamily).toContain('SmartBox Kai');
  });

  it('h1 走 Serif、h3 走 Sans,两者的中文都落在同一个楷体上', () => {
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('SmartBox Serif');
    expect((kioskTheme.typography.h3 as any).fontFamily).toContain('SmartBox Sans');
    expect((kioskTheme.typography.h1 as any).fontFamily).toContain('SmartBox Kai');
    expect((kioskTheme.typography.h3 as any).fontFamily).toContain('SmartBox Kai');
  });

  // 退役字库一个都不许留在主题里。上面两条是「该有的在不在」,这一条是「不该有的走没走」——
  // 加法式的改动不会让前者变红:栈里同时留着新旧两族,两条照样绿。
  it('主题里不残留任何退役字库', () => {
    const stacks = [
      kioskTheme.typography.fontFamily,
      ...(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'body1', 'body2', 'button', 'caption'] as const)
        .map((key) => (kioskTheme.typography[key] as any)?.fontFamily),
    ].filter(Boolean).join(' | ');
    for (const retired of ['Noto Sans SC', 'Noto Serif SC', 'Hanken Grotesk']) {
      expect(stacks, `${retired} 还在主题里`).not.toContain(retired);
    }
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
