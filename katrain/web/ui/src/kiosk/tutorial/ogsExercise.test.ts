import { describe, expect, it } from 'vitest';
import {
  actOgsExercise,
  applyGoMove,
  chooseOgsAnswer,
  createOgsExercise,
  playOgsPoint,
  retryOgsExercise,
  type OgsExerciseStep,
  type OgsTreeNode,
} from './ogsExercise';

const node = (
  point: [number, number] | null,
  children: OgsTreeNode[] = [],
  correct = false,
  wrong = false,
): OgsTreeNode => ({ point, children, correct, wrong });

const step = (exercise: OgsExerciseStep['exercise'], extras: Partial<OgsExerciseStep> = {}): OgsExerciseStep => ({
  size: 5,
  initial_player: 'B',
  stones: { B: [], W: [] },
  exercise,
  ...extras,
});

describe('OGS exercise answers', () => {
  it('accepts every source-approved first move by board click, never a choice answer', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [node([1, 1], [], true), node([3, 3], [], true)]) });
    expect(playOgsPoint(createOgsExercise(source), [1, 1]).status).toBe('correct');
    expect(playOgsPoint(createOgsExercise(source), [3, 3]).status).toBe('correct');
    expect(chooseOgsAnswer(createOgsExercise(source), '1,1').status).toBe('active');
  });

  it('marks an ordinary legal move outside the tree wrong but leaves the untouched root active', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [node([1, 1], [], true)], false, true) });
    const initial = createOgsExercise(source);
    expect(initial.status).toBe('active');
    const wrong = playOgsPoint(initial, [4, 4]);
    expect(wrong.status).toBe('wrong');
    expect(wrong.board[4][4]).toBe('B');
    expect(wrong.treeCursor).toBe(source.exercise.kind === 'puzzle' ? source.exercise.tree : null);
    expect(retryOgsExercise(wrong)).toEqual(initial);
  });

  it('follows automatic opponent replies, checks wrong responses, and stops on a correct response', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [
      node([0, 0], [node([1, 0], [], true)]),
      node([4, 4], [node([3, 4], [], false, true)]),
    ]) });
    const solved = playOgsPoint(createOgsExercise(source), [0, 0]);
    expect(solved.status).toBe('correct');
    expect(solved.board[0][0]).toBe('B');
    expect(solved.board[0][1]).toBe('W');
    expect(solved.treeCursor?.point).toEqual([1, 0]);
    expect(solved.lastTransition).toEqual({
      playerMove: { point: [0, 0], player: 'B', captured: [] },
      automaticResponses: [{ point: [1, 0], player: 'W', captured: [] }],
    });
    const failed = playOgsPoint(createOgsExercise(source), [4, 4]);
    expect(failed.status).toBe('wrong');
    expect(failed.board[4][3]).toBe('W');
    expect(failed.treeCursor?.point).toEqual([3, 4]);
  });

  it('chooses a source opponent reply with a solvable continuation when alternatives exist', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [
      node([0, 0], [node([1, 0], [], false, true), node([0, 1], [node([1, 1], [], true)])]),
    ]) });
    const afterFirst = playOgsPoint(createOgsExercise(source), [0, 0]);
    expect(afterFirst.status).toBe('active');
    expect(afterFirst.treeCursor?.point).toEqual([0, 1]);
    expect(playOgsPoint(afterFirst, [1, 1]).status).toBe('correct');
  });

  it('completes the TEST ladder after six plies and allows retry from a wrong branch', () => {
    // Small source.json fragment from ogs-learning:bl1-calculate-ladder:1.
    const source = step({ kind: 'puzzle', tree: node(null, [
      node([3, 4], [node([4, 5], [node([4, 6], [node([3, 5], [node([2, 5], [node([3, 6], [], true)])])])])]),
      node([4, 5], [node([3, 4], [], false, true)]),
    ]) }, { size: 9, stones: { B: [[4, 3], [5, 4], [5, 5]], W: [[4, 4], [2, 6]] } });
    const wrong = playOgsPoint(createOgsExercise(source), [4, 5]);
    expect(wrong.status).toBe('wrong');
    let state = retryOgsExercise(wrong);
    expect(state.board[5][4]).toBeNull();
    state = playOgsPoint(state, [3, 4]);
    expect(state.status).toBe('active');
    expect(state.board[5][4]).toBe('W');
    state = playOgsPoint(state, [4, 6]);
    expect(state.status).toBe('active');
    expect(state.board[5][3]).toBe('W');
    state = playOgsPoint(state, [2, 5]);
    expect(state.status).toBe('correct');
    expect(state.board[6][3]).toBe('W');
    expect(state.treeCursor?.correct).toBe(true);
  });

  it('counts invalid board points as neither moves nor wrong answers', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [node([0, 0], [], true)]) }, { stones: { B: [[2, 2]], W: [] } });
    const initial = createOgsExercise(source);
    for (const point of [[-1, 0], [5, 0], [2, 2], [1.5, 2]] as [number, number][]) {
      expect(playOgsPoint(initial, point)).toEqual(initial);
    }
  });

  it('accepts choices only for source choice exercises', () => {
    const source = step({ kind: 'choice', choices: [
      { value: '3', label_key: '3' }, { value: '4', label_key: '4' },
    ], correct_choice: '4' });
    const initial = createOgsExercise(source);
    expect(playOgsPoint(initial, [0, 0])).toEqual(initial);
    expect(chooseOgsAnswer(initial, '3').status).toBe('wrong');
    expect(chooseOgsAnswer(initial, 'bogus')).toEqual(initial);
    expect(chooseOgsAnswer(initial, '4').status).toBe('correct');
  });

  it('toggles entire connected groups for remove and matches exactly the target points', () => {
    const source = step({ kind: 'remove', remove_targets: [[0, 0], [0, 1]] }, {
      stones: { B: [[0, 0], [0, 1], [4, 4]], W: [[1, 0]] },
    });
    const initial = createOgsExercise(source);
    expect(playOgsPoint(initial, [3, 3])).toEqual(initial);
    const extra = playOgsPoint(initial, [4, 4]);
    expect(extra.selectedRemoval).toEqual([[4, 4]]);
    const incomplete = playOgsPoint(extra, [0, 1]);
    expect(incomplete.selectedRemoval).toEqual([[4, 4], [0, 0], [0, 1]]);
    expect(incomplete.status).toBe('active');
    const solved = playOgsPoint(incomplete, [4, 4]);
    expect(solved.selectedRemoval).toEqual([[0, 0], [0, 1]]);
    expect(solved.status).toBe('correct');
    expect(retryOgsExercise(solved)).toEqual(initial);
  });

  it('requires the matching explicit pass or finish action', () => {
    for (const kind of ['pass', 'finish'] as const) {
      const initial = createOgsExercise(step({ kind }));
      expect(playOgsPoint(initial, [0, 0])).toEqual(initial);
      expect(actOgsExercise(initial, kind === 'pass' ? 'finish' : 'pass')).toEqual(initial);
      expect(actOgsExercise(initial, kind).status).toBe('correct');
      expect(retryOgsExercise(actOgsExercise(initial, kind))).toEqual(initial);
    }
  });
});

describe('Go board rules used by the exercise tree', () => {
  it('captures adjacent enemy groups without changing the previous board', () => {
    const start = createOgsExercise(step({ kind: 'puzzle', tree: node(null, []) }, {
      stones: { B: [[0, 1], [1, 0], [2, 1]], W: [[1, 1]] },
    })).board;
    const result = applyGoMove(start, [1, 2], 'B');
    expect(result?.[1][1]).toBeNull();
    expect(result?.[2][1]).toBe('B');
    expect(start[1][1]).toBe('W');
  });

  it('reports captured points from a learner move for physical-board synchronization', () => {
    const source = step({ kind: 'puzzle', tree: node(null, [node([1, 2], [], true)]) }, {
      stones: { B: [[0, 1], [1, 0], [2, 1]], W: [[1, 1]] },
    });
    const result = playOgsPoint(createOgsExercise(source), [1, 2]);
    expect(result.lastTransition).toEqual({
      playerMove: { point: [1, 2], player: 'B', captured: [[1, 1]] },
      automaticResponses: [],
    });
    expect(retryOgsExercise(result).lastTransition).toBeNull();
  });

  it('rejects occupied, out-of-bounds, suicide and immediate ko recapture', () => {
    const suicide = createOgsExercise(step({ kind: 'puzzle', tree: node(null, []) }, {
      stones: { B: [], W: [[0, 1], [1, 0], [2, 1], [1, 2]] },
    })).board;
    expect(applyGoMove(suicide, [1, 1], 'B')).toBeNull();
    expect(applyGoMove(suicide, [0, 1], 'B')).toBeNull();
    expect(applyGoMove(suicide, [5, 0], 'B')).toBeNull();
    const beforeKo = createOgsExercise(step({ kind: 'puzzle', tree: node(null, []) }, {
      stones: { B: [[0, 1], [1, 0], [1, 2]], W: [[1, 1], [2, 0], [2, 2], [3, 1]] },
    })).board;
    const afterCapture = applyGoMove(beforeKo, [2, 1], 'B');
    expect(afterCapture?.[1][1]).toBeNull();
    expect(afterCapture && applyGoMove(afterCapture, [1, 1], 'W', beforeKo)).toBeNull();
  });
});
