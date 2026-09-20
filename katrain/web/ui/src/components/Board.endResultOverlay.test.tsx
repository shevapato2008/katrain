import React from 'react';
import { act, render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import Board from './Board';
import type { GameState } from '../api';

// 只钉住改动 1 的判据:`suppressEndResultOverlay` 打开时棋盘不再画半透明遮罩 +
// 大字,默认(不传)仍画 —— galaxy 与其它终局态逐字不变。
// mock 一个记录 fillRect 调用的 2D context,断言遮罩那次 `fillRect(0,0,w,h)` 调用
// (改自 setup.ts 里 `rgba(0, 0, 0, 0.6)` 的 overlay fillStyle)在两态下的有无。
function mockContext() {
  const fillRectCalls: string[] = [];
  const ctx = {
    save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), stroke: vi.fn(),
    fill: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), drawImage: vi.fn(), clearRect: vi.fn(),
    fillText: vi.fn(), createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    measureText: vi.fn(() => ({ width: 0 })),
    set fillStyle(v: string) { fillRectCalls.push(`style:${v}`); },
    get fillStyle() { return ''; },
    set strokeStyle(_v: string) {}, get strokeStyle() { return ''; },
    set font(_v: string) {}, get font() { return ''; },
    set textAlign(_v: string) {}, get textAlign() { return ''; },
    set textBaseline(_v: string) {}, get textBaseline() { return ''; },
    set lineWidth(_v: number) {}, get lineWidth() { return 0; },
    set lineCap(_v: string) {}, get lineCap() { return ''; },
    set globalAlpha(_v: number) {}, get globalAlpha() { return 1; },
    set shadowColor(_v: string) {}, get shadowColor() { return ''; },
    set shadowBlur(_v: number) {}, get shadowBlur() { return 0; },
    fillRect: vi.fn((...args: number[]) => fillRectCalls.push(`rect:${args.join(',')}`)),
  };
  return { ctx, fillRectCalls };
}

const baseState = {
  stones: [], history: [], analysis: null, player_to_move: 'B',
  board_size: [19, 19], current_node_id: 42, end_result: 'W+T', awaiting_count: false,
} as unknown as GameState;

describe('Board end-result overlay', () => {
  afterEach(() => vi.unstubAllGlobals());

  test('draws the full-canvas overlay by default (galaxy/未指定态不变)', () => {
    const { ctx, fillRectCalls } = mockContext();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<Board gameState={baseState} onMove={() => {}} analysisToggles={{}} />);
    expect(fillRectCalls.some((c) => c.startsWith('rect:0,0,'))).toBe(true);
  });

  test('suppressEndResultOverlay 打开时不画遮罩(kiosk 超时状态条已说过一遍)', () => {
    const { ctx, fillRectCalls } = mockContext();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<Board gameState={baseState} onMove={() => {}} analysisToggles={{}} suppressEndResultOverlay />);
    expect(fillRectCalls.some((c) => c.startsWith('rect:0,0,'))).toBe(false);
  });

  test('acknowledges the latest node when images finish loading after a state update', async () => {
    const { ctx } = mockContext();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    const onPaintedNode = vi.fn();
    const pendingImages: LoadedImage[] = [];
    class LoadedImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor() { pendingImages.push(this); }
      set src(_value: string) {}
    }
    vi.stubGlobal('Image', LoadedImage);

    const view = render(
      <Board
        gameState={{ ...baseState, current_node_id: 41 }}
        onMove={() => {}}
        analysisToggles={{}}
        onPaintedNode={onPaintedNode}
      />,
    );
    view.rerender(
      <Board
        gameState={{ ...baseState, current_node_id: 42 }}
        onMove={() => {}}
        analysisToggles={{}}
        onPaintedNode={onPaintedNode}
      />,
    );

    expect(onPaintedNode).not.toHaveBeenCalled();
    await act(async () => pendingImages.forEach(image => image.onload?.()));
    await waitFor(() => expect(onPaintedNode).toHaveBeenCalledWith(42));
    expect(onPaintedNode).not.toHaveBeenCalledWith(41);
    expect(ctx.drawImage.mock.invocationCallOrder[0]).toBeLessThan(onPaintedNode.mock.invocationCallOrder[0]);
  });
});
