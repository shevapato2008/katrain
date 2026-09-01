import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RAIL_CEILING, RAIL_MAX, RAIL_TIERS, railWidth } from '../../../components/railStyles';
import BoardPageShell from './BoardPageShell';

type ResizeCallback = ConstructorParameters<typeof ResizeObserver>[0];

class ResizeObserverMock {
  static callback: ResizeCallback | undefined;
  static observed: Element | undefined;

  constructor(callback: ResizeCallback) {
    ResizeObserverMock.callback = callback;
  }

  observe(target: Element) {
    ResizeObserverMock.observed = target;
  }

  disconnect() {}
  unobserve() {}
}

const renderShell = (onBoardSizeChange?: (edge: number) => void, displayControls = <span>CONTROLS</span>) =>
  render(
    <BoardPageShell
      board={<span>BOARD</span>}
      modulePlate={<span>MODULE</span>}
      railBody={<span>BODY</span>}
      displayControls={displayControls}
      actions={<span>ACTIONS</span>}
      onBoardSizeChange={onBoardSizeChange}
    />,
  );

const cssText = () =>
  Array.from(document.styleSheets)
    .flatMap((sheet) => {
      try {
        return Array.from(sheet.cssRules, (rule) => rule.cssText);
      } catch {
        return [];
      }
    })
    .join('\n');

afterEach(() => {
  vi.unstubAllGlobals();
  ResizeObserverMock.callback = undefined;
  ResizeObserverMock.observed = undefined;
});

describe('BoardPageShell', () => {
  it('keeps the board separate from the fixed module, single scrolling rail middle, and fixed actions', () => {
    renderShell();

    const shell = screen.getByTestId('board-page-shell');
    const stage = screen.getByTestId('board-stage');
    const module = screen.getByTestId('board-rail-module');
    const scroll = screen.getByTestId('board-rail-scroll');
    const actions = screen.getByTestId('board-rail-actions');

    expect(shell).toHaveStyle({ overflow: 'hidden', overflowY: 'auto' });
    expect(stage).toHaveTextContent('BOARD');
    expect(stage).not.toHaveTextContent('MODULE');
    expect(module).toHaveTextContent('MODULE');
    expect(scroll).toHaveTextContent('BODY');
    expect(scroll).toHaveTextContent('CONTROLS');
    expect(actions).toHaveTextContent('ACTIONS');
  });

  it('defines the mobile natural flow and exact horizontal rail widths', () => {
    renderShell();
    const css = cssText();

    expect(css).toContain('@media (min-width:900px)');

    /* 2026-09-01：这里原来断言 emotion 吐出来的 `grid-template-columns: … 320px` 逐档字面量。
       栏宽改成 `clamp(下限, calc(100% - 20px - min(1200px, 100vh - 72px)), 900px)` 之后，
       **jsdom 的 CSS 解析器把整条声明丢掉了** —— 上面那几个 media 块在 jsdom 里是空的。
       于是这条断言从「量宽度」退化成「量 jsdom 支不支持 clamp」，两个方向都不可信：
       规则被整条删掉，和 jsdom 解析不了，在它眼里长得一模一样。

       按仓库口径（jsdom 没有布局引擎，对布局事实无权作证），几何这一半整个搬走了：
       `superpowers/tracks/galaxy-ui-redesign/audit_rail_width.mjs` 在真浏览器里
       8 页 × 13 档断言两条不变式（① 不许比旧档位窄 ② 棋盘边长不许变），
       另有 `audit_rail_gutter.mjs` 断言左右内边距。

       留在这里的是 jsdom **有权作证**的那一半 —— 源码事实，不是布局结论：
       档位表只有一份、就四档，且宽度式子确实由下限和天花板夹出来。
       变异验证：给 RAIL_TIERS 加一条 [2400, 620] → 第一条红；
       把 RAIL_CEILING 里的 `100%` 改成 `100vw` → 第三条红。 */
    expect(RAIL_TIERS).toEqual([[900, 320], [1200, 360], [1536, 420], [1920, 520]]);
    /* 比**去重后的断点集合**：整张样式表里棋盘台和右栏也各有一条 900 的规则，
       逐条比会把它们算进来。去重之后集合仍然对「多加一档」敏感 —— 新档必然带来新断点。 */
    const breakpoints = [...new Set([...css.matchAll(/@media \(min-width:(\d+)px\)/g)]
      .map(([, bp]) => Number(bp)))].sort((a, b) => a - b);
    expect(breakpoints).toEqual(RAIL_TIERS.map(([bp]) => bp));
    for (const [, floor] of RAIL_TIERS) {
      expect(railWidth(floor)).toBe(`clamp(${floor}px, ${RAIL_CEILING}, ${RAIL_MAX}px)`);
    }
    expect(RAIL_CEILING).toContain('100%');
    expect(screen.getByTestId('board-stage')).toHaveStyle({
      display: 'grid',
      placeItems: 'center',
      minWidth: 0,
      minHeight: 0,
      padding: '6px',
    });
  });

  it('reports only changed integer board edges from the stage content box', () => {
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    const onBoardSizeChange = vi.fn();
    renderShell(onBoardSizeChange);

    expect(ResizeObserverMock.observed).toBe(screen.getByTestId('board-stage'));
    const notify = (width: number, height: number) =>
      ResizeObserverMock.callback?.(
        [{ target: ResizeObserverMock.observed, contentRect: { width, height } } as ResizeObserverEntry],
        {} as ResizeObserver,
      );

    notify(612.9, 540.8);
    notify(612.1, 540.2);
    notify(479.9, 500.4);

    expect(onBoardSizeChange).toHaveBeenCalledTimes(2);
    expect(onBoardSizeChange).toHaveBeenNthCalledWith(1, 540);
    expect(onBoardSizeChange).toHaveBeenNthCalledWith(2, 479);
  });

  it('omits optional display controls without changing the rail regions', () => {
    render(
      <BoardPageShell
        board={<span>BOARD</span>}
        modulePlate={<span>MODULE</span>}
        railBody={<span>BODY</span>}
        actions={<span>ACTIONS</span>}
      />,
    );
    expect(screen.getByTestId('board-rail-scroll')).toHaveTextContent('BODY');
    expect(screen.queryByText('CONTROLS')).not.toBeInTheDocument();
    expect(screen.getByTestId('board-rail-actions')).toHaveTextContent('ACTIONS');
  });
});
