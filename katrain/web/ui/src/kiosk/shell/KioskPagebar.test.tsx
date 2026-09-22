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

  test('卡顿时排队的几下返回只算一次:这一屏画出来之前按下的不算(RK3562 实测连退出了 katrain)', () => {
    // 触屏抬起那一刻的时间戳,和 `performance.now()` 同一个时钟。jsdom 默认给 Date.now(),永远算「新的」。
    const tapAt = (el: Element, t: number) => {
      const ev = new MouseEvent('click', { bubbles: true });
      Object.defineProperty(ev, 'timeStamp', { value: t });
      el.dispatchEvent(ev);
    };
    const now = vi.spyOn(performance, 'now').mockReturnValue(1000);
    const onBack = vi.fn();
    render(<KioskPagebar title="x" backLabel="返回" onBack={onBack} />);
    const back = screen.getByRole('button', { name: /返回/ });
    tapAt(back, 400); // 这一屏出来之前按的 —— 用户按的是上一屏的返回
    expect(onBack).not.toHaveBeenCalled();
    now.mockReturnValue(2000);
    tapAt(back, 1500); // 看见这一屏之后按的:生效
    tapAt(back, 1600); // 同一次卡顿里排在它后面的:不算
    expect(onBack).toHaveBeenCalledTimes(1);
    tapAt(back, 2500); // 生效之后再按(比如返回只弹了个确认框):照常
    expect(onBack).toHaveBeenCalledTimes(2);
    now.mockRestore();
  });

  test('页级动作可选择显示文字，同时保留更完整的 accessible name', () => {
    render(<KioskPagebar title="x" action={{
      icon: 'arrows-clockwise',
      label: '重置识别 · 以屏幕上的数字棋盘局面为准',
      visibleLabel: '重置识别',
      onClick: () => {},
    }} />);
    const action = screen.getByRole('button', { name: '重置识别 · 以屏幕上的数字棋盘局面为准' });
    expect(action).toHaveTextContent('重置识别');
    expect(action).toHaveClass('kiosk-pagebar__iconbtn--labeled');
  });

  test('未提供 visibleLabel 的旧动作仍是纯图标按钮', () => {
    render(<KioskPagebar title="x" action={{
      icon: 'arrows-clockwise', label: '重新点灯', onClick: () => {},
    }} />);
    const action = screen.getByRole('button', { name: '重新点灯' });
    expect(action).toHaveTextContent('');
    expect(action).not.toHaveClass('kiosk-pagebar__iconbtn--labeled');
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
