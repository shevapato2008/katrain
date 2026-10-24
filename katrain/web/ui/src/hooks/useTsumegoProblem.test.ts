import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTsumegoProblem } from './useTsumegoProblem';
import type { MoveResult } from './useTsumegoProblem';
import * as progressContext from '../context/TsumegoProgressContext';
import { sgfToCoords } from '../utils/sgfParser';

// 9x9 board. Initial stones: black ba, white aa (white's only liberty is ab).
// Off-tree B[ab] fills that liberty -> captures white aa -> judged incorrect.
// On-tree B[cc] is correct and has an AI reply W[dd] (~300ms later); from there
// B[ee] would be the next correct move (unused by these tests, kept for realism).
const SGF = '(;GM[1]SZ[9]AB[ba]AW[aa]PL[B](;B[cc](;W[dd](;B[ee]C[正解]))))';

// Field names/shape match ProblemDetail as read by useTsumegoProblem's fetch-then-
// initializeProblem mapping: boardSize / initialBlack / initialWhite / sgfContent
// (camelCase — NOT the snake_case REST wire shape). initialBlack/initialWhite are
// SGF coordinate strings that seed `stones` directly; they are NOT derived from the
// SGF's own AB/AW tags (those are only used for building the move tree), so they
// must be kept in sync with the SGF's AB[ba]/AW[aa] by hand here.
const problemJson = {
  id: 'p1',
  level: '',
  category: '',
  hint: '',
  boardSize: 9,
  initialBlack: ['ba'],
  initialWhite: ['aa'],
  sgfContent: SGF,
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => problemJson })));
});
afterEach(() => vi.unstubAllGlobals());

async function setup() {
  const hook = renderHook(() => useTsumegoProblem('p1'));
  await waitFor(() => expect(hook.result.current.problem).not.toBeNull());
  return hook;
}

describe('failed-state snapshot restore', () => {
  it('undo after an incorrect capturing move restores stones and moveHistory', async () => {
    const { result } = await setup();

    // Play the correct move, then wait for its AI reply to actually land on the
    // board (the reply is scheduled via setTimeout(~300ms) inside placeStone).
    const correct = sgfToCoords('cc', 9)!;
    act(() => {
      result.current.placeStone(correct[0], correct[1]);
    });
    await waitFor(() => expect(result.current.stones.length).toBe(4)); // ba, aa, cc, dd

    const beforeWrong = result.current.stones;
    const beforeWrongHistory = result.current.moveHistory;
    expect(result.current.nextPlayer).toBe('B');
    expect(beforeWrongHistory.length).toBe(2); // [B cc, W dd] — the AI reply is a real, legal move

    // Off-tree move that captures the white stone at aa (its only remaining liberty).
    const wrong = sgfToCoords('ab', 9)!;
    act(() => {
      result.current.placeStone(wrong[0], wrong[1]);
    });
    expect(result.current.isFailed).toBe(true);

    // Sanity check the capture actually happened before we undo it.
    expect(result.current.stones.some(s => s.player === 'W' && s.coords[0] === 0 && s.coords[1] === 8)).toBe(false);
    expect(result.current.stones.some(s => s.player === 'B' && s.coords[0] === 0 && s.coords[1] === 7)).toBe(true);

    act(() => {
      result.current.undo();
    });

    // Full restore: captured white stone is back, the wrong stone is gone, isFailed
    // is cleared, and the legal AI move (W dd) was NOT dropped from moveHistory.
    expect(result.current.stones).toEqual(beforeWrong);
    expect(result.current.moveHistory).toEqual(beforeWrongHistory);
    expect(result.current.isFailed).toBe(false);
    expect(result.current.nextPlayer).toBe('B');
  });

  it('undo after an incorrect FIRST move (empty history) clears isFailed and restores', async () => {
    const { result } = await setup();

    // Play the wrong off-tree capturing move as the VERY FIRST move: moveHistory stays
    // empty (incorrect moves are never pushed) but isFailed flips true. The kiosk physical
    // 'removing' recovery drives undo() to clear this — it must NOT no-op on empty history
    // (else isFailed sticks forever and every subsequent move is rejected).
    const initialStones = result.current.stones;
    const wrong = sgfToCoords('ab', 9)!;
    act(() => {
      result.current.placeStone(wrong[0], wrong[1]);
    });
    expect(result.current.isFailed).toBe(true);
    expect(result.current.moveHistory.length).toBe(0); // wrong first move is not recorded
    // capture happened: white aa removed.
    expect(result.current.stones.some(s => s.player === 'W' && s.coords[0] === 0 && s.coords[1] === 8)).toBe(false);

    act(() => {
      result.current.undo();
    });

    // Full restore even with empty history: white aa back, wrong stone gone, isFailed cleared.
    expect(result.current.isFailed).toBe(false);
    expect(result.current.stones).toEqual(initialStones);
  });

  it('preserves the failed snapshot across a try-mode excursion (fail → try → exit → undo)', async () => {
    const { result } = await setup();

    // Correct move + wait for its AI reply to land (same setup as the test above).
    const correct = sgfToCoords('cc', 9)!;
    act(() => {
      result.current.placeStone(correct[0], correct[1]);
    });
    await waitFor(() => expect(result.current.stones.length).toBe(4)); // ba, aa, cc, dd

    const beforeWrong = result.current.stones;
    const beforeWrongHistory = result.current.moveHistory;
    expect(result.current.nextPlayer).toBe('B');
    expect(beforeWrongHistory.length).toBe(2);

    // Off-tree capturing move → failed, white aa removed.
    const wrong = sgfToCoords('ab', 9)!;
    act(() => {
      result.current.placeStone(wrong[0], wrong[1]);
    });
    expect(result.current.isFailed).toBe(true);

    // Take a try-mode excursion WHILE failed: enter, place a free stone, then exit.
    act(() => {
      result.current.enterTryMode();
    });
    expect(result.current.isFailed).toBe(false); // try mode clears failed
    act(() => {
      const free = sgfToCoords('gg', 9)!;
      result.current.placeStone(free[0], free[1]);
    });
    act(() => {
      result.current.exitTryMode();
    });
    // exitTryMode restores the failed state it snapshotted.
    expect(result.current.isFailed).toBe(true);

    // undo() must STILL fully restore the pre-failure snapshot — the failed snapshot
    // must have survived the try-mode round trip (regression: enterTryMode used to null it).
    act(() => {
      result.current.undo();
    });
    expect(result.current.stones).toEqual(beforeWrong);
    expect(result.current.moveHistory).toEqual(beforeWrongHistory);
    expect(result.current.isFailed).toBe(false);
    expect(result.current.nextPlayer).toBe('B');
  });
});

describe('scheduledReply metadata', () => {
  it('correct move exposes the pending AI reply without changing judging', async () => {
    const { result } = await setup();
    const correct = sgfToCoords('cc', 9)!;
    let moveResult: MoveResult | null = null;
    act(() => {
      moveResult = result.current.placeStone(correct[0], correct[1]);
    });
    expect(moveResult?.type).toBe('correct');
    expect(moveResult?.scheduledReply).toEqual({ player: 'W', coords: sgfToCoords('dd', 9) });
  });
});

describe('restart cancels pending state', () => {
  afterEach(() => vi.useRealTimers());

  it('reset cancels a delayed reply and restores the initial position', async () => {
    const { result } = await setup();
    const initialStones = result.current.stones;
    const root = result.current.currentNode;
    vi.useFakeTimers();
    act(() => { result.current.placeStone(...sgfToCoords('cc', 9)!); });
    act(() => result.current.reset());
    act(() => vi.advanceTimersByTime(300));
    expect(result.current.stones).toEqual(initialStones);
    expect(result.current.moveHistory).toEqual([]);
    expect(result.current.lastMove).toBeNull();
    expect(result.current.currentNode).toEqual(root);
    expect(result.current.nextPlayer).toBe('B');
    expect(result.current.isSolved).toBe(false);
    expect(result.current.isFailed).toBe(false);
  });

  it('problem change cancels a delayed reply while the next problem loads', async () => {
    const { result, rerender } = renderHook(({ id }) => useTsumegoProblem(id), { initialProps: { id: 'p1' } });
    await waitFor(() => expect(result.current.problem).not.toBeNull());
    vi.useFakeTimers();
    act(() => { result.current.placeStone(...sgfToCoords('cc', 9)!); });
    const beforeChange = result.current.stones;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    rerender({ id: 'p2' });
    act(() => vi.advanceTimersByTime(300));
    expect(result.current.stones).toEqual(beforeChange);
    expect(result.current.moveHistory).toHaveLength(1);
  });

  it('unmount cancels the delayed reply timer', async () => {
    const { result, unmount } = await setup();
    vi.useFakeTimers();
    act(() => { result.current.placeStone(...sgfToCoords('cc', 9)!); });
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('reset exits try mode and discards the previous snapshot', async () => {
    const { result } = await setup();
    const initialStones = result.current.stones;
    act(() => { result.current.placeStone(...sgfToCoords('ab', 9)!); });
    act(() => result.current.enterTryMode());
    const exitPreviousTryMode = result.current.exitTryMode;
    act(() => { result.current.placeStone(...sgfToCoords('gg', 9)!); });
    act(() => result.current.reset());
    expect(result.current.isTryMode).toBe(false);
    act(() => exitPreviousTryMode());
    expect(result.current.stones).toEqual(initialStones);
    expect(result.current.isFailed).toBe(false);
    expect(result.current.moveHistory).toEqual([]);
    expect(result.current.lastMove).toBeNull();
  });
});

describe('load errors', () => {
  it('只有 404 说「Problem not found」;其它状态码原样带上 —— 503 不许被说成题不存在', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const unavailable = renderHook(() => useTsumegoProblem('p1'));
    await waitFor(() => expect(unavailable.result.current.error).toBe('HTTP 503'));

    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) })));
    const missing = renderHook(() => useTsumegoProblem('p2'));
    await waitFor(() => expect(missing.result.current.error).toBe('Problem not found'));
  });
});


describe('cumulative progress per problem', () => {
  afterEach(() => vi.restoreAllMocks());

  it('navigates A → B → A with independent persisted cumulative counts', async () => {
    const progress = { A: { completed: false, attempts: 4 }, B: { completed: false, attempts: 1 } };
    const markProgress = vi.fn((id: string, input: progressContext.MarkProgressInput) => {
      progress[id as keyof typeof progress] = { completed: input.completed, attempts: input.attempts };
    });
    vi.spyOn(progressContext, 'useTsumegoProgress').mockReturnValue({
      progress, markProgress, progressLoading: false, serverLoadFailed: false,
      isCompleted: () => false, unitProgress: () => ({ completed: 0, total: 0 }),
      categoryProgress: () => ({ completed: 0, total: 0 }), refresh: vi.fn(),
    });
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => ({ ...problemJson, id: url.split('/').pop() }) })));
    const { result, rerender } = renderHook(({ id }) => useTsumegoProblem(id), { initialProps: { id: 'A' } });
    await waitFor(() => expect(result.current.problem?.id).toBe('A'));
    expect(result.current.attempts).toBe(4);
    act(() => { result.current.placeStone(...sgfToCoords('ab', 9)!); });
    expect(result.current.attempts).toBe(5);
    rerender({ id: 'B' });
    await waitFor(() => expect(result.current.problem?.id).toBe('B'));
    expect(markProgress).toHaveBeenCalledWith('A', expect.objectContaining({ attempts: 5 }));
    expect(result.current.attempts).toBe(1);
    rerender({ id: 'A' });
    await waitFor(() => expect(result.current.problem?.id).toBe('A'));
    act(() => { result.current.placeStone(...sgfToCoords('ab', 9)!); });
    act(() => result.current.flushProgress());
    expect(result.current.attempts).toBe(6);
    expect(markProgress).toHaveBeenLastCalledWith('A', expect.objectContaining({ attempts: 6 }));
  });

  it('adds failures made before account history arrives to its authoritative baseline', async () => {
    vi.spyOn(progressContext, 'readLocalProgress').mockReturnValue({});
    const context = {
      progress: {} as progressContext.TsumegoProgressMap, markProgress: vi.fn(),
      progressLoading: true, serverLoadFailed: false, isCompleted: () => false,
      unitProgress: () => ({ completed: 0, total: 0 }), categoryProgress: () => ({ completed: 0, total: 0 }), refresh: vi.fn(),
    };
    vi.spyOn(progressContext, 'useTsumegoProgress').mockImplementation(() => context);
    const { result, rerender } = renderHook(() => useTsumegoProblem('p1'));
    await waitFor(() => expect(result.current.problem?.id).toBe('p1'));
    act(() => result.current.placeStone(...sgfToCoords('ab', 9)!));
    expect(result.current.attempts).toBe(1);
    context.progress = { p1: { completed: false, attempts: 9 } };
    context.progressLoading = false;
    rerender();
    expect(result.current.attempts).toBe(10);
    act(() => result.current.flushProgress());
    expect(context.markProgress).toHaveBeenLastCalledWith('p1', expect.objectContaining({ attempts: 10 }));
    // The provider echoes our cumulative write; it must not count that write again.
    context.progress = { p1: { completed: false, attempts: 10 } };
    rerender();
    expect(result.current.attempts).toBe(10);
    act(() => result.current.undo());
    act(() => result.current.placeStone(...sgfToCoords('ab', 9)!));
    expect(result.current.attempts).toBe(11);
  });

  it('republishes a solved total when history arrives after the initial solve write', async () => {
    vi.spyOn(progressContext, 'readLocalProgress').mockReturnValue({});
    // Use a one-move solution so this regression has no delayed AI response.
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
      ...problemJson, sgfContent: '(;GM[1]SZ[9]AB[ba]AW[aa]PL[B];B[cc]C[正解])',
    }) })));
    const context = {
      progress: {} as progressContext.TsumegoProgressMap, markProgress: vi.fn(),
      progressLoading: true, serverLoadFailed: false, isCompleted: () => false,
      unitProgress: () => ({ completed: 0, total: 0 }), categoryProgress: () => ({ completed: 0, total: 0 }), refresh: vi.fn(),
    };
    vi.spyOn(progressContext, 'useTsumegoProgress').mockImplementation(() => context);
    const { result, rerender, unmount } = renderHook(() => useTsumegoProblem('p1'));
    await waitFor(() => expect(result.current.problem?.id).toBe('p1'));
    act(() => result.current.placeStone(...sgfToCoords('ab', 9)!));
    act(() => result.current.undo());
    act(() => result.current.placeStone(...sgfToCoords('cc', 9)!));
    expect(result.current.isSolved).toBe(true);
    expect(context.markProgress).toHaveBeenLastCalledWith('p1', expect.objectContaining({ completed: true, attempts: 1 }));
    context.progress = { p1: { completed: true, attempts: 9 } };
    context.progressLoading = false;
    rerender();
    expect(result.current.attempts).toBe(10);
    expect(context.markProgress).toHaveBeenLastCalledWith('p1', expect.objectContaining({ completed: true, attempts: 10 }));
    expect(context.markProgress).toHaveBeenCalledTimes(2);
    context.progress = { p1: { completed: true, attempts: 10 } };
    rerender();
    expect(result.current.attempts).toBe(10);
    unmount();
    expect(context.markProgress).toHaveBeenCalledTimes(2);
  });

  it('uses late account history for the next failure and ignores try exploration', async () => {
    vi.spyOn(progressContext, 'readLocalProgress').mockReturnValue({});
    const context = {
      progress: {} as progressContext.TsumegoProgressMap, markProgress: vi.fn(),
      progressLoading: true, serverLoadFailed: false, isCompleted: () => false,
      unitProgress: () => ({ completed: 0, total: 0 }), categoryProgress: () => ({ completed: 0, total: 0 }), refresh: vi.fn(),
    };
    vi.spyOn(progressContext, 'useTsumegoProgress').mockImplementation(() => context);
    const { result, rerender } = renderHook(() => useTsumegoProblem('p1'));
    await waitFor(() => expect(result.current.problem?.id).toBe('p1'));
    context.progress = { p1: { completed: false, attempts: 9 } };
    rerender();
    expect(result.current.attempts).toBe(9);
    act(() => result.current.enterTryMode());
    act(() => result.current.placeStone(...sgfToCoords('ab', 9)!));
    act(() => result.current.flushProgress());
    expect(context.markProgress).not.toHaveBeenCalled();
    expect(result.current.attempts).toBe(9);
    act(() => result.current.exitTryMode());
    act(() => result.current.placeStone(...sgfToCoords('ab', 9)!));
    act(() => result.current.flushProgress());
    expect(context.markProgress).toHaveBeenCalledWith('p1', expect.objectContaining({ attempts: 10 }));
  });
});
