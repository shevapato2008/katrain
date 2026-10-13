import { act, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import TsumegoBoard from './TsumegoBoard';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('keeps a contrast hollow last-stone ring outside its visible move number', async () => {
  class ImageMock { onload: (() => void) | null = null; set src(_value: string) { this.onload?.(); } }
  vi.stubGlobal('Image', ImageMock);
  const arcs: { radius: number; color: string }[] = [];
  const ctx = new Proxy({ arc: vi.fn((_x: number, _y: number, radius: number) => { arcs.push({ radius, color: String(ctx.strokeStyle) }); }), fillText: vi.fn(), strokeStyle: '', createRadialGradient: () => ({ addColorStop: vi.fn() }) }, { get: (target, key) => key in target ? target[key as keyof typeof target] : vi.fn() }) as unknown as CanvasRenderingContext2D;
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx);
  const stone = { player: 'B' as const, coords: [3, 3] as [number, number] };
  render(<TsumegoBoard boardSize={9} stones={[stone]} lastMove={stone.coords} moveHistory={[stone]} showMoveNumbers showCoordinates={false} onPlaceStone={() => {}} />);
  await act(async () => {});
  await waitFor(() => expect(ctx.fillText).toHaveBeenCalledWith('1', expect.any(Number), expect.any(Number)));
  expect(arcs.some(({ radius }) => radius > 5)).toBe(true);
  expect(ctx.strokeStyle).toBe('rgba(255, 255, 255, 0.9)');
});
