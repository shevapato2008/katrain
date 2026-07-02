import { describe, expect, it } from 'vitest';
import {
  initialState,
  reduce,
  type Command,
  type MachineEvent,
  type MachineState,
} from './physicalTsumegoMachine';
import type { MoveResult } from '../../hooks/useTsumegoProblem';

// ---- helpers ----

const empty = (n: number): number[][] => Array.from({ length: n }, () => Array(n).fill(0));

/** boardWith(19, {'3,3': 1, '3,4': 2}) — cells keyed by "row,col" -> stone color (1=black, 2=white). */
const boardWith = (n: number, cells: Record<string, number>): number[][] => {
  const b = empty(n);
  for (const key of Object.keys(cells)) {
    const [r, c] = key.split(',').map(Number);
    b[r][c] = cells[key];
  }
  return b;
};

/** Apply a single event to a state, returning both the next state and emitted commands. */
const step = (state: MachineState, evt: MachineEvent): { state: MachineState; commands: Command[] } =>
  reduce(state, evt);

/** Apply a sequence of events from a starting state, returning the final result plus
 *  a per-step trace (useful when a test wants to inspect an intermediate step). */
const run = (start: MachineState, events: MachineEvent[]): { state: MachineState; commands: Command[] }[] => {
  const trace: { state: MachineState; commands: Command[] }[] = [];
  let state = start;
  for (const evt of events) {
    const r = reduce(state, evt);
    trace.push(r);
    state = r.state;
  }
  return trace;
};

const kinds = (commands: Command[]): Command['kind'][] => commands.map((c) => c.kind);

const findCommand = <K extends Command['kind']>(commands: Command[], kind: K): Extract<Command, { kind: K }> | undefined =>
  commands.find((c) => c.kind === kind) as Extract<Command, { kind: K }> | undefined;

const moveResult = (overrides: Partial<MoveResult>): MoveResult => ({
  type: 'correct',
  ...overrides,
});

describe('physicalTsumegoMachine', () => {
  it('ENABLE → clearing: target=empty board, speaks clear_board, disarms moves, sets up empty board', () => {
    const emptyBoard = empty(19);
    const { state, commands } = step(initialState, { type: 'ENABLE', emptyBoard });

    expect(state.phase).toBe('clearing');
    expect(state.targetBoard).toBe(emptyBoard);
    expect(state.stage).toBeNull();
    expect(state.missing).toEqual([]);
    expect(state.extra).toEqual([]);
    expect(state.pendingReply).toBeNull();
    expect(state.preMoveBoard).toBeNull();

    expect(kinds(commands)).toEqual(['ledClear', 'armMoves', 'speak', 'setupMode']);
    expect(findCommand(commands, 'armMoves')).toEqual({ kind: 'armMoves', armed: false });
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'clear_board' });
    expect(findCommand(commands, 'setupMode')).toEqual({ kind: 'setupMode', board: emptyBoard });
  });

  it('clearing: SETUP_PROGRESS emits blue (remove) LEDs for extra stones only', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const extra: Array<[number, number, number]> = [
      [3, 3, 1],
      [15, 15, 2],
    ];
    const { state, commands } = step(clearingState, {
      type: 'SETUP_PROGRESS',
      missing: [],
      extra,
    });

    expect(state.phase).toBe('clearing');
    expect(state.extra).toEqual(extra);
    expect(state.missing).toEqual([]);
    expect(commands).toHaveLength(1);
    expect(commands[0]).toEqual({
      kind: 'ledPoints',
      points: [
        { row: 3, col: 3, color: 'remove' },
        { row: 15, col: 15, color: 'remove' },
      ],
    });
  });

  it('clearing: SETUP_COMPLETE → setup, target becomes the screen board, starts on black stage when black stones exist', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const initialBoard = boardWith(19, { '3,3': 1, '3,15': 1, '15,3': 2 });
    const { state, commands } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    expect(state.phase).toBe('setup');
    expect(state.stage).toBe('black');
    expect(state.targetBoard).toBe(initialBoard);
    expect(state.missing).toEqual([]);
    expect(state.extra).toEqual([]);
    expect(state.stageMatched).toBe(0);
    expect(state.stageTotal).toBe(2); // two black stones in initialBoard

    expect(kinds(commands)).toEqual(['speak', 'setupMode']);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'place_black' });
    expect(findCommand(commands, 'setupMode')).toEqual({ kind: 'setupMode', board: initialBoard });
  });

  it('clearing: SETUP_COMPLETE with a target that has no black stones jumps straight to white stage', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const whiteOnlyBoard = boardWith(19, { '3,3': 2, '15,15': 2 });
    const { state, commands } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: whiteOnlyBoard });

    expect(state.phase).toBe('setup');
    expect(state.stage).toBe('white');
    expect(state.stageTotal).toBe(2);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'place_white' });
  });

  it('setup staging: missing black stones get black LEDs and the correct stage-scoped totals', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '3,15': 1, '15,3': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    // Neither black stone placed yet, white also missing (but should be ignored while black remains).
    const missing: Array<[number, number]> = [
      [3, 3],
      [3, 15],
      [15, 3],
    ];
    const { state, commands } = step(setupState, { type: 'SETUP_PROGRESS', missing, extra: [] });

    expect(state.phase).toBe('setup');
    expect(state.stage).toBe('black');
    expect(state.stageTotal).toBe(2); // 2 black stones total
    expect(state.stageMatched).toBe(0); // none placed yet
    expect(state.missing).toEqual(missing);

    expect(kinds(commands)).toEqual(['ledPoints']);
    const ledCmd = findCommand(commands, 'ledPoints')!;
    // Only the two black-target missing points get LEDs (white target point is not lit during black stage).
    expect(ledCmd.points).toEqual([
      { row: 3, col: 3, color: 'black' },
      { row: 3, col: 15, color: 'black' },
    ]);
  });

  it('setup staging: black stones all placed → advances to white stage and speaks place_white', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '3,15': 1, '15,3': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    // Only the white stone remains missing now.
    const missing: Array<[number, number]> = [[15, 3]];
    const { state, commands } = step(setupState, { type: 'SETUP_PROGRESS', missing, extra: [] });

    expect(state.phase).toBe('setup');
    expect(state.stage).toBe('white');
    expect(state.stageTotal).toBe(1); // 1 white stone total
    expect(state.stageMatched).toBe(0); // the one white stone is still missing

    expect(kinds(commands)).toEqual(['speak', 'ledPoints']);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'place_white' });
    const ledCmd = findCommand(commands, 'ledPoints')!;
    expect(ledCmd.points).toEqual([{ row: 15, col: 3, color: 'white' }]);
  });

  it('setup staging: no speak/stage transition once already in white stage with white stones missing', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,3': 2, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    // First transition into white stage (black done).
    const { state: whiteStageState } = step(setupState, {
      type: 'SETUP_PROGRESS',
      missing: [[15, 3], [15, 15]],
      extra: [],
    });
    expect(whiteStageState.stage).toBe('white');

    // Second progress event while still in white stage — one white stone placed.
    const { state, commands } = step(whiteStageState, {
      type: 'SETUP_PROGRESS',
      missing: [[15, 15]],
      extra: [],
    });

    expect(state.stage).toBe('white');
    expect(state.stageTotal).toBe(2);
    expect(state.stageMatched).toBe(1);
    // No 'speak' command since stage did not change from black->white this time.
    expect(kinds(commands)).toEqual(['ledPoints']);
  });

  it('setup staging: wrong-color extras get blue LEDs alongside the active stage color', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '3,15': 1 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const missing: Array<[number, number]> = [[3, 15]];
    const extra: Array<[number, number, number]> = [[10, 10, 2]]; // a stray white stone placed by mistake
    const { state, commands } = step(setupState, { type: 'SETUP_PROGRESS', missing, extra });

    expect(state.phase).toBe('setup');
    expect(state.stage).toBe('black');
    expect(state.extra).toEqual(extra);

    const ledCmd = findCommand(commands, 'ledPoints')!;
    expect(ledCmd.points).toEqual([
      { row: 3, col: 15, color: 'black' },
      { row: 10, col: 10, color: 'remove' },
    ]);
  });

  it('setup: SETUP_COMPLETE → ready with setup_done speech, ledClear, expectedBoard, armMoves(true)', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const { state, commands } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    expect(state.phase).toBe('ready');
    expect(state.stage).toBeNull();
    expect(state.missing).toEqual([]);
    expect(state.extra).toEqual([]);
    expect(state.pendingReply).toBeNull();

    expect(kinds(commands)).toEqual(['speak', 'ledClear', 'expectedBoard', 'armMoves']);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'setup_done' });
    expect(findCommand(commands, 'expectedBoard')).toEqual({ kind: 'expectedBoard', board: initialBoard });
    expect(findCommand(commands, 'armMoves')).toEqual({ kind: 'armMoves', armed: true });
  });

  it('MOVE_APPLIED incorrect → removing (disarm, wrong_remove, setupMode(preBoard)); SETUP_COMPLETE → undoFailed + expectedBoard(preBoard) + back to ready', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    expect(readyState.phase).toBe('ready');

    const preBoard = initialBoard;
    const wrongResult: MoveResult = { type: 'incorrect' };
    const { state: removingState, commands: removingCommands } = step(readyState, {
      type: 'MOVE_APPLIED',
      result: wrongResult,
      preBoard,
    });

    expect(removingState.phase).toBe('removing');
    expect(removingState.preMoveBoard).toBe(preBoard);
    expect(removingState.targetBoard).toBe(preBoard);
    expect(kinds(removingCommands)).toEqual(['armMoves', 'speak', 'setupMode']);
    expect(findCommand(removingCommands, 'armMoves')).toEqual({ kind: 'armMoves', armed: false });
    expect(findCommand(removingCommands, 'speak')).toEqual({ kind: 'speak', name: 'wrong_remove' });
    expect(findCommand(removingCommands, 'setupMode')).toEqual({ kind: 'setupMode', board: preBoard });

    // Physical board converged back to preBoard — screen still shows the wrong stone until now.
    const wrongScreenBoard = boardWith(19, { '3,3': 1, '15,15': 2, '5,5': 1 });
    const { state: backToReady, commands: undoCommands } = step(removingState, {
      type: 'SETUP_COMPLETE',
      screenBoard: wrongScreenBoard,
    });

    expect(backToReady.phase).toBe('ready');
    expect(backToReady.preMoveBoard).toBeNull();
    expect(kinds(undoCommands)).toEqual(['undoFailed', 'ledClear', 'expectedBoard', 'armMoves']);
    // Rebased on preMoveBoard, NOT the (stale) screenBoard passed with this event.
    expect(findCommand(undoCommands, 'expectedBoard')).toEqual({ kind: 'expectedBoard', board: preBoard });
    expect(findCommand(undoCommands, 'armMoves')).toEqual({ kind: 'armMoves', armed: true });
  });

  it('MOVE_APPLIED correct+scheduledReply → replying with NO setupMode command; BOARD_SETTLED → setupMode(new board); SETUP_COMPLETE → ready', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const preBoard = initialBoard;
    const scheduledReply: MoveResult['scheduledReply'] = { player: 'W', coords: [4, 4] };
    const correctResult: MoveResult = moveResult({ type: 'correct', scheduledReply });
    const { state: replyingState, commands: replyingCommands } = step(readyState, {
      type: 'MOVE_APPLIED',
      result: correctResult,
      preBoard,
    });

    expect(replyingState.phase).toBe('replying');
    expect(replyingState.pendingReply).toEqual(scheduledReply);
    expect(kinds(replyingCommands)).toEqual(['armMoves']);
    expect(findCommand(replyingCommands, 'armMoves')).toEqual({ kind: 'armMoves', armed: false });
    // Critical: no setupMode command is issued here — the hook must wait for BOARD_SETTLED.
    expect(replyingCommands.find((c) => c.kind === 'setupMode')).toBeUndefined();

    const settledBoard = boardWith(19, { '3,3': 1, '15,15': 2, '5,5': 1, '4,4': 2 });
    const { state: settledState, commands: settledCommands } = step(replyingState, {
      type: 'BOARD_SETTLED',
      board: settledBoard,
    });

    expect(settledState.phase).toBe('replying'); // still replying — waiting for physical convergence
    expect(settledState.targetBoard).toBe(settledBoard);
    expect(settledState.pendingReply).toBeNull();
    expect(kinds(settledCommands)).toEqual(['setupMode']);
    expect(settledCommands[0]).toEqual({ kind: 'setupMode', board: settledBoard });

    const { state: backToReady, commands: readyCommands } = step(settledState, {
      type: 'SETUP_COMPLETE',
      screenBoard: settledBoard,
    });

    expect(backToReady.phase).toBe('ready');
    expect(kinds(readyCommands)).toEqual(['ledClear', 'expectedBoard', 'armMoves']);
    expect(findCommand(readyCommands, 'expectedBoard')).toEqual({ kind: 'expectedBoard', board: settledBoard });
  });

  it('MOVE_APPLIED correct with no scheduledReply → replying with pendingReply=null (no setupMode command either)', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const correctResult: MoveResult = moveResult({ type: 'correct' }); // no scheduledReply field
    const { state, commands } = step(readyState, { type: 'MOVE_APPLIED', result: correctResult, preBoard: initialBoard });

    expect(state.phase).toBe('replying');
    expect(state.pendingReply).toBeNull();
    expect(commands.find((c) => c.kind === 'setupMode')).toBeUndefined();
  });

  it('MOVE_APPLIED correct+captured>0 → includes capture_remove speak', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const correctResult: MoveResult = moveResult({ type: 'correct', captured: 2 });
    const { state, commands } = step(readyState, { type: 'MOVE_APPLIED', result: correctResult, preBoard: initialBoard });

    expect(state.phase).toBe('replying');
    expect(kinds(commands)).toEqual(['armMoves', 'speak']);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'capture_remove' });
  });

  it('MOVE_APPLIED correct+captured=0 → no capture_remove speak', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const correctResult: MoveResult = moveResult({ type: 'correct', captured: 0 });
    const { commands } = step(readyState, { type: 'MOVE_APPLIED', result: correctResult, preBoard: initialBoard });

    expect(kinds(commands)).toEqual(['armMoves']);
  });

  it('MOVE_APPLIED solved → solved + celebrate (armMoves false, ledClear, correct speak)', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const solvedResult: MoveResult = moveResult({ type: 'solved' });
    const { state, commands } = step(readyState, { type: 'MOVE_APPLIED', result: solvedResult, preBoard: initialBoard });

    expect(state.phase).toBe('solved');
    expect(kinds(commands)).toEqual(['armMoves', 'ledClear', 'speak', 'celebrate']);
    expect(findCommand(commands, 'armMoves')).toEqual({ kind: 'armMoves', armed: false });
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'correct' });
  });

  it('MOVE_APPLIED is ignored outside ready phase (unchanged state, no commands)', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const correctResult: MoveResult = moveResult({ type: 'correct' });
    const { state, commands } = step(clearingState, {
      type: 'MOVE_APPLIED',
      result: correctResult,
      preBoard: emptyBoard,
    });

    expect(state).toBe(clearingState); // identity-equal: reducer returns the same object unchanged
    expect(commands).toEqual([]);
  });

  it('MOVE_APPLIED with a null result is also ignored, even inside ready phase', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const { state, commands } = step(readyState, { type: 'MOVE_APPLIED', result: null, preBoard: initialBoard });

    expect(state).toBe(readyState);
    expect(commands).toEqual([]);
  });

  it('SOLVED arriving from replying (AI reply completes the solution) → solved + celebrate', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const correctResult: MoveResult = moveResult({ type: 'correct', scheduledReply: { player: 'W', coords: [4, 4] } });
    const { state: replyingState } = step(readyState, {
      type: 'MOVE_APPLIED',
      result: correctResult,
      preBoard: initialBoard,
    });
    expect(replyingState.phase).toBe('replying');
    expect(replyingState.pendingReply).not.toBeNull();

    const { state, commands } = step(replyingState, { type: 'SOLVED' });

    expect(state.phase).toBe('solved');
    expect(state.pendingReply).toBeNull();
    expect(kinds(commands)).toEqual(['armMoves', 'ledClear', 'speak', 'celebrate']);
    expect(findCommand(commands, 'speak')).toEqual({ kind: 'speak', name: 'correct' });
  });

  it('SOLVED is a no-op when phase is off or already solved', () => {
    const { state: offState, commands: offCommands } = step(initialState, { type: 'SOLVED' });
    expect(offState).toBe(initialState);
    expect(offCommands).toEqual([]);

    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const solvedResult: MoveResult = moveResult({ type: 'solved' });
    const { state: solvedState } = step(readyState, { type: 'MOVE_APPLIED', result: solvedResult, preBoard: initialBoard });
    expect(solvedState.phase).toBe('solved');

    const { state: stillSolved, commands: solvedAgainCommands } = step(solvedState, { type: 'SOLVED' });
    expect(stillSolved).toBe(solvedState);
    expect(solvedAgainCommands).toEqual([]);
  });

  it('CELEBRATION_DONE(autoAdvance=true) → clearing_next + setupMode(empty board); then SETUP_COMPLETE → advance command', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const solvedResult: MoveResult = moveResult({ type: 'solved' });
    const { state: solvedState } = step(readyState, { type: 'MOVE_APPLIED', result: solvedResult, preBoard: initialBoard });

    const nextEmptyBoard = empty(19);
    const { state: clearingNextState, commands: clearingNextCommands } = step(solvedState, {
      type: 'CELEBRATION_DONE',
      autoAdvance: true,
      emptyBoard: nextEmptyBoard,
    });

    expect(clearingNextState.phase).toBe('clearing_next');
    expect(clearingNextState.targetBoard).toBe(nextEmptyBoard);
    expect(kinds(clearingNextCommands)).toEqual(['speak', 'setupMode']);
    expect(findCommand(clearingNextCommands, 'speak')).toEqual({ kind: 'speak', name: 'clear_board' });
    expect(findCommand(clearingNextCommands, 'setupMode')).toEqual({ kind: 'setupMode', board: nextEmptyBoard });

    const { state: advancedState, commands: advanceCommands } = step(clearingNextState, {
      type: 'SETUP_COMPLETE',
      screenBoard: nextEmptyBoard,
    });

    expect(advancedState.phase).toBe('clearing_next'); // reducer does not change phase here — advance is caller-driven navigation
    expect(advancedState.missing).toEqual([]);
    expect(advancedState.extra).toEqual([]);
    expect(kinds(advanceCommands)).toEqual(['advance']);
  });

  it('CELEBRATION_DONE(autoAdvance=false) → stays solved, no commands', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const solvedResult: MoveResult = moveResult({ type: 'solved' });
    const { state: solvedState } = step(readyState, { type: 'MOVE_APPLIED', result: solvedResult, preBoard: initialBoard });

    const { state, commands } = step(solvedState, {
      type: 'CELEBRATION_DONE',
      autoAdvance: false,
      emptyBoard: empty(19),
    });

    expect(state).toBe(solvedState);
    expect(state.phase).toBe('solved');
    expect(commands).toEqual([]);
  });

  it('CELEBRATION_DONE is a no-op when phase is not solved', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const { state, commands } = step(clearingState, {
      type: 'CELEBRATION_DONE',
      autoAdvance: true,
      emptyBoard: empty(19),
    });

    expect(state).toBe(clearingState);
    expect(commands).toEqual([]);
  });

  it('TRY_EXIT → restoring + setupMode(screen board); SETUP_COMPLETE → ready', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const screenBoard = boardWith(19, { '3,3': 1, '15,15': 2, '9,9': 1 }); // user tried a move on screen
    const { state: restoringState, commands: restoringCommands } = step(readyState, {
      type: 'TRY_EXIT',
      board: screenBoard,
    });

    expect(restoringState.phase).toBe('restoring');
    expect(restoringState.targetBoard).toBe(screenBoard);
    expect(restoringState.pendingReply).toBeNull();
    // Disarm move detection FIRST (two-mode invariant enforced by construction), then setupMode.
    expect(kinds(restoringCommands)).toEqual(['armMoves', 'setupMode']);
    expect(findCommand(restoringCommands, 'armMoves')).toEqual({ kind: 'armMoves', armed: false });
    expect(findCommand(restoringCommands, 'setupMode')).toEqual({ kind: 'setupMode', board: screenBoard });

    const { state: backToReady, commands: readyCommands } = step(restoringState, {
      type: 'SETUP_COMPLETE',
      screenBoard,
    });

    expect(backToReady.phase).toBe('ready');
    expect(kinds(readyCommands)).toEqual(['ledClear', 'expectedBoard', 'armMoves']);
    expect(findCommand(readyCommands, 'expectedBoard')).toEqual({ kind: 'expectedBoard', board: screenBoard });
  });

  it('TRY_EXIT is a no-op only when phase is off', () => {
    const { state, commands } = step(initialState, { type: 'TRY_EXIT', board: empty(19) });
    expect(state).toBe(initialState);
    expect(commands).toEqual([]);
  });

  it('TRY_EXIT during clearing/setup still transitions to restoring (not gated to ready)', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const screenBoard = boardWith(19, { '3,3': 1 });
    const { state, commands } = step(clearingState, { type: 'TRY_EXIT', board: screenBoard });

    expect(state.phase).toBe('restoring');
    expect(state.targetBoard).toBe(screenBoard);
    expect(kinds(commands)).toEqual(['armMoves', 'setupMode']);
  });

  it('removing/restoring/replying SETUP_PROGRESS uses convergenceLeds: missing→target color, extra→blue', () => {
    // Build a 'removing' state directly via MOVE_APPLIED(incorrect) so state.targetBoard (=preBoard)
    // is known and colors can be predicted.
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const preBoard = initialBoard; // target while removing == preBoard, contains black@3,3 and white@15,15
    const { state: removingState } = step(readyState, {
      type: 'MOVE_APPLIED',
      result: { type: 'incorrect' },
      preBoard,
    });
    expect(removingState.phase).toBe('removing');

    // Missing: the black stone at 3,3 still needs to be placed back (target color = black).
    // Extra: a stray stone at 9,9 that must come off (blue).
    const missing: Array<[number, number]> = [[3, 3]];
    const extra: Array<[number, number, number]> = [[9, 9, 1]];
    const { state, commands } = step(removingState, { type: 'SETUP_PROGRESS', missing, extra });

    expect(state.phase).toBe('removing');
    expect(kinds(commands)).toEqual(['ledPoints']);
    expect(commands[0]).toEqual({
      kind: 'ledPoints',
      points: [
        { row: 3, col: 3, color: 'black' },
        { row: 9, col: 9, color: 'remove' },
      ],
    });
  });

  it('unknown phase for SETUP_PROGRESS (e.g. ready or solved) returns no commands, only updates missing/extra', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const { state: setupState } = step(clearingState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });
    const { state: readyState } = step(setupState, { type: 'SETUP_COMPLETE', screenBoard: initialBoard });

    const missing: Array<[number, number]> = [[1, 1]];
    const extra: Array<[number, number, number]> = [[2, 2, 1]];
    const { state, commands } = step(readyState, { type: 'SETUP_PROGRESS', missing, extra });

    expect(state.phase).toBe('ready');
    expect(state.missing).toEqual(missing);
    expect(state.extra).toEqual(extra);
    expect(commands).toEqual([]);
  });

  it('SETUP_COMPLETE is a no-op in phases with no defined transition (e.g. off)', () => {
    const { state, commands } = step(initialState, { type: 'SETUP_COMPLETE', screenBoard: empty(19) });
    expect(state).toBe(initialState);
    expect(commands).toEqual([]);
  });

  it('BOARD_SETTLED is ignored outside replying phase', () => {
    const emptyBoard = empty(19);
    const { state: clearingState } = step(initialState, { type: 'ENABLE', emptyBoard });

    const { state, commands } = step(clearingState, { type: 'BOARD_SETTLED', board: empty(19) });

    expect(state).toBe(clearingState);
    expect(commands).toEqual([]);
  });

  it('a full happy-path run through run() helper: ENABLE → clearing → setup(black) → setup(white) → ready → correct move (no reply) → settle → ready', () => {
    const emptyBoard = empty(19);
    const initialBoard = boardWith(19, { '3,3': 1, '15,15': 2 });
    const finalBoard = boardWith(19, { '3,3': 1, '15,15': 2, '9,9': 1 });

    const events: MachineEvent[] = [
      { type: 'ENABLE', emptyBoard },
      { type: 'SETUP_COMPLETE', screenBoard: initialBoard },
      { type: 'SETUP_PROGRESS', missing: [[15, 15]], extra: [] }, // black done, white pending
      { type: 'SETUP_COMPLETE', screenBoard: initialBoard }, // -> ready
      { type: 'MOVE_APPLIED', result: moveResult({ type: 'correct' }), preBoard: initialBoard }, // -> replying
      { type: 'BOARD_SETTLED', board: finalBoard },
      { type: 'SETUP_COMPLETE', screenBoard: finalBoard }, // -> ready
    ];

    const trace = run(initialState, events);
    const phases = trace.map((t) => t.state.phase);
    expect(phases).toEqual(['clearing', 'setup', 'setup', 'ready', 'replying', 'replying', 'ready']);

    const finalState = trace[trace.length - 1].state;
    expect(finalState.targetBoard).toBe(finalBoard);
    expect(finalState.pendingReply).toBeNull();
  });
});
