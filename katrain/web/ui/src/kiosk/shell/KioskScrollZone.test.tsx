import { render } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { KioskScrollZone } from './KioskScrollZone';

/**
 * ⚠️ 本文件**不测布局** —— jsdom 没有布局引擎,`scrollHeight` 恒等于 `clientHeight`,
 * 它对「溢没溢出、拇指多高、还是不是 680 宽」一律无权作证。那四条在
 * `tests/kiosk-shell-scroll.spec.ts` 里用真浏览器、真滚轮量。
 *
 * 这里只测两件**不是布局结论**的事:
 *   ① 两种形态各自挂哪些类名(纯字符串)
 *   ② `resetKey` 变了到底有没有把 `scrollTop` 写回 0(纯代码行为 —— 写没写这一下)
 */

const scrollOf = (c: HTMLElement) => c.querySelector('.kiosk-side__scroll') as HTMLElement;

describe('两种形态是同一个组件,只换外壳那一层的类名', () => {
  test('不传 grow = 形态 1:外壳是 .kiosk-side', () => {
    const { container } = render(<KioskScrollZone><p>行</p></KioskScrollZone>);
    const zone = container.querySelector('.kiosk-scrollzone')!;
    expect(zone.className).toBe('kiosk-side kiosk-scrollzone');
    expect(zone.querySelector('.kiosk-scrollbar')).not.toBeNull();
  });

  test('传 grow = 形态 2:外壳是 .kiosk-section--grow,head 留在滚动区外面', () => {
    const { container } = render(
      <KioskScrollZone grow head={<h3 className="kiosk-seclabel">待复盘</h3>}><p>行</p></KioskScrollZone>,
    );
    const zone = container.querySelector('.kiosk-scrollzone')!;
    expect(zone.className).toBe('kiosk-section kiosk-section--grow kiosk-scrollzone');
    // 组标题必须在 .kiosk-side__scroll **之外** —— 在里面它会跟着滚,渐隐也就避不开它。
    expect(scrollOf(container).querySelector('.kiosk-seclabel')).toBeNull();
    expect(zone.querySelector('.kiosk-seclabel')).not.toBeNull();
  });
});

describe('resetKey:换一批内容要回到顶部', () => {
  // 滚动容器是同一个 DOM 节点,React 只换里面的行 —— scrollTop 会原样留着。
  // 国象在真浏览器里量到过 558px(棋谱库翻页),用户看到的第 2 页是从中间开始的。
  test('resetKey 变了 → scrollTop 归零', () => {
    const { container, rerender } = render(
      <KioskScrollZone resetKey="p1"><p>第一页</p></KioskScrollZone>,
    );
    scrollOf(container).scrollTop = 120;
    rerender(<KioskScrollZone resetKey="p2"><p>第二页</p></KioskScrollZone>);
    expect(scrollOf(container).scrollTop).toBe(0);
  });

  test('不传 resetKey 就不管 —— 整栏滚的形态 1 用不上,不许顺手把它也归零', () => {
    const { container, rerender } = render(<KioskScrollZone><p>第一页</p></KioskScrollZone>);
    scrollOf(container).scrollTop = 120;
    rerender(<KioskScrollZone><p>第二页</p></KioskScrollZone>);
    expect(scrollOf(container).scrollTop).toBe(120);
  });
});
