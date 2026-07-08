import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { usePhysicalTsumego } from '../hooks/usePhysicalTsumego';
import type { PhysicalTsumegoOptions } from '../hooks/usePhysicalTsumego';

function makeOpts(overrides: Partial<PhysicalTsumegoOptions> = {}): PhysicalTsumegoOptions {
  return {
    enabled: true,
    visionConnected: true,
    problemKey: 'p1',
    resyncKey: 0,
    boardSize: 19,
    stones: [],
    isSolved: false,
    showHint: false,
    hintCoords: null,
    isTryMode: false,
    autoAdvance: false,
    syncEvents: [],
    placeStone: () => null,
    undo: () => {},
    playMoveSound: () => {},
    onAdvance: () => {},
    ...overrides,
  };
}

describe('usePhysicalTsumego (stub)', () => {
  it('is side-effect-free: cycles through all dev phases without ever touching fetch', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    const { result } = renderHook(() => usePhysicalTsumego(makeOpts()));

    expect(result.current.phase).toBe('setup');

    act(() => {
      result.current.__devSetPhase?.('setup');
    });
    expect(result.current.phase).toBe('setup');
    expect(result.current.stage).toBe('black');
    expect(result.current.stageMatched).toBe(2);
    expect(result.current.stageTotal).toBe(5);
    expect(result.current.missing).toEqual([[3, 3], [15, 15]]);
    expect(result.current.extra).toEqual([]);

    act(() => {
      result.current.__devSetPhase?.('ready');
    });
    expect(result.current.phase).toBe('ready');
    expect(result.current.stage).toBeNull();
    expect(result.current.missing).toEqual([]);
    expect(result.current.extra).toEqual([]);

    act(() => {
      result.current.__devSetPhase?.('replying');
    });
    expect(result.current.phase).toBe('replying');
    expect(result.current.stage).toBeNull();

    act(() => {
      result.current.__devSetPhase?.('removing');
    });
    expect(result.current.phase).toBe('removing');
    expect(result.current.extra.length).toBeGreaterThan(0);
    expect(result.current.extra).toEqual([[9, 9, 1]]);

    act(() => {
      result.current.__devSetPhase?.('solved');
    });
    expect(result.current.phase).toBe('solved');
    expect(result.current.missing).toEqual([]);
    expect(result.current.extra).toEqual([]);

    // ledOk is always true in the stub (no LED IO to fail).
    expect(result.current.ledOk).toBe(true);
    // onScreenMove is a stub no-op -- calling it must not throw or perform IO.
    expect(() => result.current.onScreenMove(null, [])).not.toThrow();

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('derives phase "off" when disabled, and "setup" once enabled', () => {
    const { result, rerender } = renderHook(
      (opts: PhysicalTsumegoOptions) => usePhysicalTsumego(opts),
      { initialProps: makeOpts({ enabled: false }) },
    );

    expect(result.current.phase).toBe('off');

    rerender(makeOpts({ enabled: true }));
    expect(result.current.phase).toBe('setup');
  });
});
