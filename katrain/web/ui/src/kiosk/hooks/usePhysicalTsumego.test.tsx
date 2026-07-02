// Hook-level IO smoke tests for usePhysicalTsumego: seq-queue no-loss/no-reprocess,
// physical move → placeStone wiring, hint pause gating, and unmount cleanup.
// The pure reducer's phase logic is covered by physicalTsumegoMachine.test.ts —
// these tests only verify the IO layer wires syncEvents/commands correctly.

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { usePhysicalTsumego, stonesToVisionBoard, type PhysicalTsumegoOptions } from './usePhysicalTsumego';
import { API } from '../../api';
import { LedAPI } from '../../api/ledApi';
import type { VisionSyncEvent } from './useVisionSync';
import type { MoveResult, Stone } from '../../hooks/useTsumegoProblem';

vi.mock('../../api', () => ({
  API: {
    visionMonitor: vi.fn().mockResolvedValue(undefined),
    visionPause: vi.fn().mockResolvedValue(undefined),
    visionMoveDetection: vi.fn().mockResolvedValue(undefined),
    visionExpectedBoard: vi.fn().mockResolvedValue(undefined),
    visionSetupMode: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../../api/ledApi', () => ({
  LedAPI: {
    points: vi.fn().mockResolvedValue({ connected: true }),
    clear: vi.fn().mockResolvedValue({ connected: true }),
  },
}));

// jsdom's HTMLMediaElement.play() logs "Not implemented" noise; the hook's own voice
// wiring is not under test here (useVoice has its own unit coverage), so stub it out.
// IMPORTANT: `speak` must be referentially stable across renders (like the real
// useCallback-memoized useVoice) — created once in the factory closure, not per
// useVoice() call — otherwise usePhysicalTsumego's execute/dispatch memo chain
// never stabilizes and effects that depend on `dispatch` (e.g. the replying-phase
// settle watcher) re-fire on every render, looping forever.
vi.mock('./useVoice', () => {
  const speak = vi.fn();
  return { useVoice: () => ({ speak }) };
});

const BOARD_SIZE = 19;

function makeOpts(overrides: Partial<PhysicalTsumegoOptions> = {}): PhysicalTsumegoOptions {
  return {
    enabled: true,
    problemKey: 'p1',
    boardSize: BOARD_SIZE,
    stones: [],
    isSolved: false,
    showHint: false,
    hintCoords: null,
    isTryMode: false,
    autoAdvance: false,
    syncEvents: [],
    placeStone: vi.fn(),
    undo: vi.fn(),
    playMoveSound: vi.fn(),
    onAdvance: vi.fn(),
    ...overrides,
  };
}

const setupProgressEvent = (
  seq: number,
  missing: Array<[number, number]> = [],
  extra: Array<[number, number, number]> = [],
): VisionSyncEvent => ({ seq, type: 'setup_progress', data: { missing, extra } });

const setupCompleteEvent = (seq: number): VisionSyncEvent => ({ seq, type: 'setup_complete', data: {} });

const moveConfirmedEvent = (seq: number, row: number, col: number, color = 1): VisionSyncEvent => ({
  seq,
  type: 'move_confirmed',
  data: { row, col, color },
});

// Flush the microtasks that follow the mocked (already-resolved) API/LED promises,
// so `.then`/`.catch` continuations settle inside `act` and don't warn.
const flush = () => act(async () => {
  await Promise.resolve();
  await Promise.resolve();
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('usePhysicalTsumego', () => {
  it('consumes every seq-queued event exactly once (no loss, no reprocess)', async () => {
    const stones: Stone[] = [{ player: 'B', coords: [3, 3] }];
    const opts = makeOpts({ stones });
    const { result, rerender } = renderHook((props: PhysicalTsumegoOptions) => usePhysicalTsumego(props), {
      initialProps: opts,
    });
    await flush();

    expect(result.current.phase).toBe('clearing');

    const progress = setupProgressEvent(0, [], [[5, 5, 1]]);
    const complete = setupCompleteEvent(1);
    const events = [progress, complete];

    rerender({ ...opts, syncEvents: events });
    await flush();

    // Evidence event 1 (setup_progress) was consumed: blue "extra" LED command fired.
    expect(LedAPI.points).toHaveBeenCalledWith([{ row: 5, col: 5, color: 'remove' }]);
    // Evidence event 2 (setup_complete) was consumed: phase advanced clearing -> setup,
    // and the physical target now mirrors the screen (non-empty, distinct from the
    // ENABLE-time empty-board setupMode call).
    const expectedTarget = stonesToVisionBoard(stones, BOARD_SIZE);
    expect(API.visionSetupMode).toHaveBeenLastCalledWith(expectedTarget);
    expect(result.current.phase).toBe('setup');

    const pointsCallsBefore = vi.mocked(LedAPI.points).mock.calls.length;
    const setupModeCallsBefore = vi.mocked(API.visionSetupMode).mock.calls.length;

    // Same two events, new array reference (as a real rerender would produce) — both
    // seqs are <= processedSeqRef, so nothing should be reprocessed.
    rerender({ ...opts, syncEvents: [...events] });
    await flush();

    expect(vi.mocked(LedAPI.points).mock.calls.length).toBe(pointsCallsBefore);
    expect(vi.mocked(API.visionSetupMode).mock.calls.length).toBe(setupModeCallsBefore);
    expect(result.current.phase).toBe('setup');
  });

  it('wires a physical move_confirmed event into placeStone with converted coords', async () => {
    const opts = makeOpts();
    const placeStone = vi.mocked(opts.placeStone);
    const moveResult: MoveResult = { type: 'correct', sound: 'stone' };
    placeStone.mockReturnValue(moveResult);

    const { result, rerender } = renderHook((props: PhysicalTsumegoOptions) => usePhysicalTsumego(props), {
      initialProps: opts,
    });
    await flush();

    // clearing -> setup -> ready
    rerender({ ...opts, syncEvents: [setupCompleteEvent(0), setupCompleteEvent(1)] });
    await flush();
    expect(result.current.phase).toBe('ready');

    rerender({ ...opts, syncEvents: [setupCompleteEvent(0), setupCompleteEvent(1), moveConfirmedEvent(2, 10, 4)] });
    await flush();

    // row=10, col=4 -> placeStone(col, boardSize-1-row) = placeStone(4, 8)
    expect(placeStone).toHaveBeenCalledWith(4, 8);
    expect(opts.playMoveSound).toHaveBeenCalledWith('stone');
    expect(result.current.phase).toBe('replying');
  });

  it('pauses recognition and shows the hint LED while showHint is active, gating physical moves in the ready phase', async () => {
    // Isolate the pause gate from the phase gate: reach 'ready' FIRST (unpaused, exactly
    // like the physical-move test), THEN pause. This way the only thing that can stop the
    // move_confirmed from reaching placeStone is the `if (pausedRef.current) continue;`
    // gate — the phase IS 'ready', so the assertion is no longer vacuous.
    const baseOpts = makeOpts();
    const placeStone = vi.mocked(baseOpts.placeStone);
    placeStone.mockReturnValue({ type: 'correct', sound: 'stone' });

    const { result, rerender } = renderHook((props: PhysicalTsumegoOptions) => usePhysicalTsumego(props), {
      initialProps: baseOpts,
    });
    await flush();

    // clearing -> setup -> ready (still unpaused: showHint=false)
    const readyEvents = [setupCompleteEvent(0), setupCompleteEvent(1)];
    rerender({ ...baseOpts, syncEvents: readyEvents });
    await flush();
    expect(result.current.phase).toBe('ready');

    // Now pause via showHint while still in 'ready'.
    const pausedOpts = { ...baseOpts, showHint: true, hintCoords: [7, 11] as [number, number], syncEvents: readyEvents };
    rerender(pausedOpts);
    await flush();

    expect(API.visionPause).toHaveBeenLastCalledWith(true);
    // hintCoords=[x=7,y=11] -> row=boardSize-1-y=18-11=7, col=x=7
    expect(LedAPI.points).toHaveBeenCalledWith([{ row: 7, col: 7, color: 'hint' }]);
    // Phase is genuinely 'ready' — pause is IO-only and does not touch the machine.
    expect(result.current.phase).toBe('ready');

    // Feed a move while paused; the pause gate must swallow it before placeStone.
    rerender({ ...pausedOpts, syncEvents: [...readyEvents, moveConfirmedEvent(2, 3, 3)] });
    await flush();

    expect(placeStone).not.toHaveBeenCalled();
    expect(baseOpts.playMoveSound).not.toHaveBeenCalled();
    expect(result.current.phase).toBe('ready'); // still ready — move never applied
  });

  it('tears down vision/LED state on unmount', async () => {
    const opts = makeOpts();
    const { unmount } = renderHook((props: PhysicalTsumegoOptions) => usePhysicalTsumego(props), {
      initialProps: opts,
    });
    await flush();

    const monitorCallsBefore = vi.mocked(API.visionMonitor).mock.calls.length;
    const pauseCallsBefore = vi.mocked(API.visionPause).mock.calls.length;
    const moveDetCallsBefore = vi.mocked(API.visionMoveDetection).mock.calls.length;
    const ledClearCallsBefore = vi.mocked(LedAPI.clear).mock.calls.length;

    await act(async () => {
      unmount();
      await Promise.resolve();
    });

    expect(vi.mocked(API.visionMonitor).mock.calls.length).toBeGreaterThan(monitorCallsBefore);
    expect(vi.mocked(API.visionPause).mock.calls.length).toBeGreaterThan(pauseCallsBefore);
    expect(vi.mocked(API.visionMoveDetection).mock.calls.length).toBeGreaterThan(moveDetCallsBefore);
    expect(vi.mocked(LedAPI.clear).mock.calls.length).toBeGreaterThan(ledClearCallsBefore);

    expect(API.visionMonitor).toHaveBeenLastCalledWith(false);
    expect(API.visionPause).toHaveBeenLastCalledWith(false);
    expect(API.visionMoveDetection).toHaveBeenLastCalledWith(false);
  });
});
