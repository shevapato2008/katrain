import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';
import { KioskPagebar } from './KioskPagebar';

/**
 * §11 页控条:顶栏在所有层级恒为品牌态,返回 / 视图切换 / 上下文标题全部下放到这里。
 * **悔棋、认输、求和、提示一律不许上页控条** —— 它们属于右栏下面的动作区。
 *
 * 几何(x16–1008 / y70–114 / 高 44 / 返回键 36)是**布局结论**,在
 * `tests/kiosk-shell-geometry.spec.ts` 里用真浏览器量。这里只测结构与行为。
 */
describe('KioskPagebar', () => {
  test('没有返回回调时不渲染返回键,但标题照旧在', () => {
    const { container } = render(<KioskPagebar title="设置" />);
    expect(container.querySelector('.kiosk-pagebar__back')).toBeNull();
    expect(screen.getByText('设置')).toBeInTheDocument();
  });

  test('标题是**标题** —— 读屏的人靠层级跳转,不能因为稿子里是 span 就跟着丢语义', () => {
    render(<KioskPagebar title="设置" />);
    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument();
  });

  test('没有 sub 就整块不渲染 —— 不占位、不写占位字', () => {
    const { container } = render(<KioskPagebar title="设置" />);
    expect(container.querySelector('.kiosk-pagebar__sub')).toBeNull();
  });

  test('没有 segment 时右端就空着,不留一个空壳', () => {
    const { container } = render(<KioskPagebar title="x" onBack={() => {}} backLabel="返回" />);
    expect(container.querySelector('.kiosk-seg')).toBeNull();
  });

  test('分段最多 3 段 —— 再多就该换别的控件', () => {
    expect(() => render(<KioskPagebar title="x" segment={{
      value: 'a', options: [['a', 'A'], ['b', 'B'], ['c', 'C'], ['d', 'D']], onChange: () => {},
    }} />)).toThrow(/最多 3 段/);
  });

  test('忙碌时返回键保留位置与去向,但如实标成忙碌且不可点', () => {
    render(<KioskPagebar title="x" backLabel="返回" onBack={() => {}} backBusy />);
    const back = screen.getByRole('button', { name: /返回/ });
    expect(back).toBeDisabled();
    expect(back).toHaveAttribute('aria-busy', 'true');
  });

  test('分段是单选组:左右方向键在段间走,不用 Tab 逐个过', () => {
    const onChange = vi.fn();
    render(<KioskPagebar title="x" segment={{ value: 'b', options: [['a', 'A'], ['b', 'B']], onChange }} />);
    const current = screen.getByRole('radio', { name: 'B' });
    expect(current).toHaveAttribute('aria-checked', 'true');
    // 只有选中那一段进 Tab 序列 —— 单选组的标准手势
    expect(screen.getByRole('radio', { name: 'A' })).toHaveAttribute('tabindex', '-1');
    current.focus();
    current.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    expect(onChange).toHaveBeenCalledWith('a');
  });
});
