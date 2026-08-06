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
    expect(css).toMatch(/min-width:1200px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 340px/);
    expect(css).toMatch(/min-width:1536px[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) 380px/);
    expect(screen.getByTestId('board-stage')).toHaveStyle({
      display: 'grid',
      placeItems: 'center',
      minWidth: 0,
      minHeight: 0,
      padding: '10px',
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
