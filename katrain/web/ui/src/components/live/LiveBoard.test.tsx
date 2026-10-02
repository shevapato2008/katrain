import { act, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BOARD_ASSETS } from '../board/boardUtils';
import LiveBoard, { type AiMoveMarker } from './LiveBoard';

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

const requestedAssets: string[] = [];

class ImageMock {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  set src(value: string) {
    requestedAssets.push(value);
    this.onload?.();
  }
}

const fillText = vi.fn();
const context = new Proxy(
  { fillText, createRadialGradient: () => ({ addColorStop: vi.fn() }) },
  {
    get(target, property) {
      if (property in target) return target[property as keyof typeof target];
      return vi.fn();
    },
  },
) as unknown as CanvasRenderingContext2D;

function notifySize(width = 380, height = 380) {
  const target = ResizeObserverMock.observed as HTMLElement;
  vi.spyOn(target, 'getBoundingClientRect').mockReturnValue({
    width,
    height,
    top: 0,
    right: width,
    bottom: height,
    left: 0,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
  act(() => {
    ResizeObserverMock.callback?.(
      [{ target, contentRect: target.getBoundingClientRect() } as ResizeObserverEntry],
      {} as ResizeObserver,
    );
  });
}

beforeEach(() => {
  requestedAssets.length = 0;
  fillText.mockClear();
  ResizeObserverMock.callback = undefined;
  ResizeObserverMock.observed = undefined;
  vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  vi.stubGlobal('Image', ImageMock);
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
});

describe('LiveBoard AI marker limit', () => {
  const markers: AiMoveMarker[] = ['Q16', 'D4', 'C3', 'R14', 'F6', 'K10'].map((move, index) => ({
    move, rank: index + 1, visits: 100 + index, winrate: 0.51 + index / 100, score_lead: 2,
  }));

  it.each([
    ['default', undefined, 3],
    ['report', 5, 5],
  ])('uses the %s marker limit', async (_name, aiMarkerLimit, count) => {
    render(
      <LiveBoard moves={[]} currentMove={0} showCoordinates={false} aiMarkers={markers} aiMarkerLimit={aiMarkerLimit} />,
    );

    await waitFor(() => expect(fillText).toHaveBeenCalled());
    const displayed = fillText.mock.calls.map(([text]) => text);
    markers.forEach((marker, index) => {
      const winrate = (marker.winrate * 100).toFixed(1);
      if (index < count) expect(displayed).toContain(winrate);
      else expect(displayed).not.toContain(winrate);
    });
    expect(markers).toHaveLength(6);
  });

  it('redraws when the marker limit changes', async () => {
    const props = { moves: [], currentMove: 0, showCoordinates: false, aiMarkers: markers };
    const { rerender } = render(<LiveBoard {...props} />);
    await waitFor(() => expect(fillText).toHaveBeenCalled());
    fillText.mockClear();

    rerender(<LiveBoard {...props} aiMarkerLimit={5} />);

    expect(fillText.mock.calls.map(([text]) => text)).toContain('55.0');
    expect(fillText.mock.calls.map(([text]) => text)).not.toContain('56.0');
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('LiveBoard responsive sizing', () => {
  it('retains the existing 400px canvas minimum by default', () => {
    const { container } = render(<LiveBoard moves={[]} currentMove={0} />);

    notifySize();

    expect(container.querySelector('canvas')).toHaveAttribute('width', '400');
  });

  it('can opt in to the full 372px space of a 380px container', () => {
    const { container } = render(
      <LiveBoard moves={[]} currentMove={0} minimumCanvasSize={0} minContainerHeight={0} />,
    );

    notifySize();

    expect(container.querySelector('canvas')).toHaveAttribute('width', '372');
    expect(container.querySelector('canvas')).not.toHaveAttribute('width', '400');
  });

  it.each([
    ['default floor', {}],
    ['opt-in responsive floor', { minimumCanvasSize: 0, minContainerHeight: 0 }],
  ])('keeps requesting the board and both stone assets in %s mode', async (_name, props) => {
    render(<LiveBoard moves={[]} currentMove={0} {...props} />);

    await waitFor(() => {
      expect(requestedAssets).toEqual(
        expect.arrayContaining([BOARD_ASSETS.board, BOARD_ASSETS.blackStone, BOARD_ASSETS.whiteStone]),
      );
    });
  });

  it.each([
    ['default floor', {}],
    ['opt-in responsive floor', { minimumCanvasSize: 0, minContainerHeight: 0 }],
  ])('lets showCoordinates control labels on all four sides in %s mode', async (_name, props) => {
    const { rerender } = render(<LiveBoard moves={[]} currentMove={0} boardSize={9} {...props} />);
    notifySize();

    await waitFor(() => expect(fillText).toHaveBeenCalledTimes(9 * 4));

    fillText.mockClear();
    rerender(<LiveBoard moves={[]} currentMove={0} boardSize={9} showCoordinates={false} {...props} />);

    await waitFor(() => expect(fillText).not.toHaveBeenCalled());
  });
});
