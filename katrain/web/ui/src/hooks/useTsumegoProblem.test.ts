import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTsumegoProblem } from './useTsumegoProblem';
import type { MoveResult } from './useTsumegoProblem';
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
