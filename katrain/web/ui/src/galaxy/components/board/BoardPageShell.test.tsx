import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
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
    expect(css).toMatch(/min-width:900px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 320px/);
    expect(css).toMatch(/min-width:1200px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 360px/);
    expect(css).toMatch(/min-width:1536px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 420px/);
    expect(css).toMatch(/min-width:1920px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 520px/);

    /* 钉「一共就这四档」。逐条 toMatch 对**多出来的档**是免疫的：谁再补一条
       `min-width:2560px` 它们全绿。所以这里把右栏那几条规则整个抽出来比集合。
       变异验证：加一条 2400 档 → 断点集合多出 2400，红；把 520 改成 620 → 宽度集合变，红。 */
    const railTiers = [...css.matchAll(/min-width:\s*(\d+)px\s*\)?\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*(\d+)px/g)]
      .map(([, bp, w]) => [Number(bp), Number(w)] as const);
    expect(railTiers).toEqual([[900, 320], [1200, 360], [1536, 420], [1920, 520]]);
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
