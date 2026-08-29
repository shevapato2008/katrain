import { render } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { Icon, ICON_NAMES } from './icons';

describe('Icon', () => {
  // 用 <img src> 就跟不了容器的 color,而 .kiosk-dock__item[aria-current]{color:var(--ink)}
  // 全靠 currentColor 翻色 —— 选中那一格的图标会一直是灰的。
  test('内联 <svg>,不是 <img>', () => {
    const { container } = render(<Icon name="game-controller" />);
    expect(container.querySelector('svg')).not.toBeNull();
    expect(container.querySelector('img')).toBeNull();
  });

  test('svg 用 currentColor,没有写死的颜色', () => {
    const { container } = render(<Icon name="game-controller" />);
    const html = container.innerHTML;
    expect(html).toContain('currentColor');
    expect(html).not.toMatch(/fill="#[0-9a-fA-F]/);
  });

  test('filled 取 -fill 那一份,不是给同一份加个 CSS', () => {
    const off = render(<Icon name="gear" />).container.innerHTML;
    const on = render(<Icon name="gear" filled />).container.innerHTML;
    expect(on).not.toBe(off);
  });

  test('包裹层是 .kiosk-icon(icon.css 把它设成 display:contents)—— 默认的 inline span 会打断 Dock 项的纵向 flex', () => {
    const { container } = render(<Icon name="gear" />);
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain('kiosk-icon');
  });
});

describe('ICON_NAMES 与 icons/ 目录**一一对应**', () => {
  // 这个联合类型是手写的(TS 没法从 import.meta.glob 推出字面量联合)。
  // 手写就会漂:目录里多抄进来一个、或者上游删掉一个,类型都不会响。
  // 下面两条把「手写的名单」和「真实的目录」对死,两个方向都堵上。
  test('名单里的每一个名字,基础版和 -fill 版都在目录里', () => {
    const missing = ICON_NAMES.flatMap((n) => {
      const bad: string[] = [];
      if (!Icon.has(n)) bad.push(`${n}.svg`);
      if (!Icon.has(`${n}-fill`)) bad.push(`${n}-fill.svg`);
      return bad;
    });
    expect(missing).toEqual([]);
  });

  test('目录里没有名单之外的图标 —— 抄进来却没登记,等于屏上永远用不到它', () => {
    const declared = new Set<string>(ICON_NAMES);
    const stray = Icon.all()
      .filter((f) => !f.endsWith('-fill'))
      .filter((f) => !declared.has(f));
    expect(stray).toEqual([]);
  });

  test('目录 82 个文件 = 41 对', () => {
    expect(Icon.all()).toHaveLength(ICON_NAMES.length * 2);
  });
});

describe('缺图标要响,不许静默画空盒子', () => {
  test('名字不在目录里就抛', () => {
    // @ts-expect-error 故意传一个不在联合类型里的名字 —— 运行期也必须挡住
    expect(() => render(<Icon name="not-a-real-icon" />)).toThrow(/not-a-real-icon/);
  });
});
