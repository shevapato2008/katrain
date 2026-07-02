// Pure phase machine for physical-board tsumego (kiosk). No IO — reduce() maps
// (state, event) to (state, declarative commands); usePhysicalTsumego executes them.
//
// Vision alternates between two modes: "converge to target board" (setup semantics —
// clearing, initial layout, mirroring screen state, wrong-move removal, try-exit
// restore) and "watch for one new stone" (move detection, explicitly armed ONLY in
// phase 'ready').
//
// Coordinates: vision row 0 = top (all boards here are vision-coord matrices).

import type { LedColor } from '../../api/ledApi';
import type { MoveResult } from '../../hooks/useTsumegoProblem';
import type { VoiceName } from './useVoice';

export type PhysicalPhase =
  | 'off'
  | 'clearing'       // converge to empty board (problem entry)
  | 'setup'          // converge to initial position (black stage, then white)
  | 'ready'          // user's turn — move detection armed
  | 'replying'       // waiting for screen to settle, then converge physical board to it
  | 'removing'       // wrong move — converge back to pre-move board, then undo screen
  | 'restoring'      // try-mode exit — converge physical board back to screen board
  | 'solved'         // celebration
  | 'clearing_next'; // auto-advance: converge to empty, then navigate

export type SetupStage = 'black' | 'white' | null;
export interface LedPoint { row: number; col: number; color: LedColor }

export type Command =
  | { kind: 'setupMode'; board: number[][] }
  | { kind: 'expectedBoard'; board: number[][] }
  | { kind: 'armMoves'; armed: boolean }
  | { kind: 'ledPoints'; points: LedPoint[] }
  | { kind: 'ledClear' }
  | { kind: 'speak'; name: VoiceName }
  | { kind: 'undoFailed' }   // executor: opts.undo() — restores pre-failure snapshot (Task 8)
  | { kind: 'celebrate' }    // executor: abortable white double-flash, then CELEBRATION_DONE
  | { kind: 'advance' };     // executor: opts.onAdvance() — navigate to next problem

export interface MachineState {
  phase: PhysicalPhase;
  stage: SetupStage;
  targetBoard: number[][] | null; // current vision setup target
  missing: Array<[number, number]>; // raw backend scope (full target)
  extra: Array<[number, number, number]>;
  stageMatched: number; // stage-scoped numbers for BoardSetupGuide (evaluation差异见评审 C10)
  stageTotal: number;
  pendingReply: { player: 'B' | 'W'; coords: [number, number] } | null;
  preMoveBoard: number[][] | null; // board before an incorrect move
}

export type MachineEvent =
  | { type: 'ENABLE'; emptyBoard: number[][] }
  | { type: 'SETUP_PROGRESS'; missing: Array<[number, number]>; extra: Array<[number, number, number]> }
  | { type: 'SETUP_COMPLETE'; screenBoard: number[][] }
  | { type: 'MOVE_APPLIED'; result: MoveResult | null; preBoard: number[][] }
  | { type: 'BOARD_SETTLED'; board: number[][] }
  | { type: 'SOLVED' }
  | { type: 'CELEBRATION_DONE'; autoAdvance: boolean; emptyBoard: number[][] }
  | { type: 'TRY_EXIT'; board: number[][] };

export const initialState: MachineState = {
  phase: 'off',
  stage: null,
  targetBoard: null,
  missing: [],
  extra: [],
  stageMatched: 0,
  stageTotal: 0,
  pendingReply: null,
  preMoveBoard: null,
};

const countColor = (board: number[][], color: number) =>
  board.reduce((n, row) => n + row.reduce((m, v) => m + (v === color ? 1 : 0), 0), 0);

const stoneColorAt = (board: number[][] | null, r: number, c: number): LedColor =>
  board?.[r]?.[c] === 2 ? 'white' : 'black';

const blues = (extra: Array<[number, number, number]>): LedPoint[] =>
  extra.map(([row, col]) => ({ row, col, color: 'remove' as LedColor }));

// While converging: still-to-place points in their target stone color, extras in blue.
const convergenceLeds = (state: MachineState, missing: Array<[number, number]>, extra: Array<[number, number, number]>): LedPoint[] => [
  ...missing.map(([row, col]) => ({ row, col, color: stoneColorAt(state.targetBoard, row, col) })),
  ...blues(extra),
];

const toReady = (state: MachineState, board: number[][]): { state: MachineState; commands: Command[] } => ({
  state: { ...state, phase: 'ready', stage: null, missing: [], extra: [], pendingReply: null },
  commands: [
    { kind: 'ledClear' },
    { kind: 'expectedBoard', board },
    { kind: 'armMoves', armed: true },
  ],
});

export function reduce(state: MachineState, evt: MachineEvent): { state: MachineState; commands: Command[] } {
  switch (evt.type) {
    case 'ENABLE':
      return {
        state: { ...initialState, phase: 'clearing', targetBoard: evt.emptyBoard },
        commands: [
          { kind: 'ledClear' },
          { kind: 'armMoves', armed: false },
          { kind: 'speak', name: 'clear_board' },
          { kind: 'setupMode', board: evt.emptyBoard },
        ],
      };

    case 'SETUP_PROGRESS': {
      const { missing, extra } = evt;
      const base = { ...state, missing, extra };
      switch (state.phase) {
        case 'clearing':
        case 'clearing_next':
          return { state: base, commands: [{ kind: 'ledPoints', points: blues(extra) }] };
        case 'removing':
        case 'restoring':
        case 'replying':
          // Guide both directions: put back what's missing (target color), take off extras (blue).
          return { state: base, commands: [{ kind: 'ledPoints', points: convergenceLeds(state, missing, extra) }] };
        case 'setup': {
          const target = state.targetBoard!;
          const missingBlack = missing.filter(([r, c]) => target[r][c] === 1);
          const missingWhite = missing.filter(([r, c]) => target[r][c] === 2);
          const nextStage: SetupStage = missingBlack.length > 0 ? 'black' : 'white';
          const active = nextStage === 'black' ? missingBlack : missingWhite;
          const stageTotal = countColor(target, nextStage === 'black' ? 1 : 2);
          const commands: Command[] = [];
          if (state.stage === 'black' && nextStage === 'white') commands.push({ kind: 'speak', name: 'place_white' });
          commands.push({
            kind: 'ledPoints',
            points: [
              ...active.map(([row, col]) => ({ row, col, color: nextStage as LedColor })),
              ...blues(extra),
            ],
          });
          return {
            state: { ...base, stage: nextStage, stageTotal, stageMatched: stageTotal - active.length },
            commands,
          };
        }
        default:
          return { state: base, commands: [] };
      }
    }

    case 'SETUP_COMPLETE': {
      switch (state.phase) {
        case 'clearing': {
          const target = evt.screenBoard;
          const stage: SetupStage = countColor(target, 1) > 0 ? 'black' : 'white';
          return {
            state: {
              ...state, phase: 'setup', stage, targetBoard: target,
              missing: [], extra: [], stageMatched: 0,
              stageTotal: countColor(target, stage === 'black' ? 1 : 2),
            },
            commands: [
              { kind: 'speak', name: stage === 'black' ? 'place_black' : 'place_white' },
              { kind: 'setupMode', board: target },
            ],
          };
        }
        case 'setup': {
          const r = toReady(state, evt.screenBoard);
          return { ...r, commands: [{ kind: 'speak', name: 'setup_done' }, ...r.commands] };
        }
        case 'replying':
        case 'restoring':
          return toReady(state, evt.screenBoard);
        case 'removing': {
          // Physical board is back at pre-move state; NOW restore the screen (undo snapshot)
          // and rebase on preMoveBoard (screenBoard still contains the wrong stone here).
          const board = state.preMoveBoard ?? evt.screenBoard;
          const r = toReady({ ...state, preMoveBoard: null }, board);
          return { ...r, commands: [{ kind: 'undoFailed' }, ...r.commands] };
        }
        case 'clearing_next':
          return { state: { ...state, missing: [], extra: [] }, commands: [{ kind: 'advance' }] };
        default:
          return { state, commands: [] };
      }
    }

    case 'MOVE_APPLIED': {
      if (state.phase !== 'ready' || !evt.result) return { state, commands: [] };
      const { result, preBoard } = evt;
      if (result.type === 'incorrect') {
        return {
          state: { ...state, phase: 'removing', preMoveBoard: preBoard, targetBoard: preBoard },
          commands: [
            { kind: 'armMoves', armed: false },
            { kind: 'speak', name: 'wrong_remove' },
            { kind: 'setupMode', board: preBoard },
          ],
        };
      }
      if (result.type === 'solved') {
        return {
          state: { ...state, phase: 'solved' },
          commands: [
            { kind: 'armMoves', armed: false },
            { kind: 'ledClear' },
            { kind: 'speak', name: 'correct' },
            { kind: 'celebrate' },
          ],
        };
      }
      // 'correct' (and defensive 'continue'): wait for the screen to settle, then converge.
      const commands: Command[] = [{ kind: 'armMoves', armed: false }];
      if ((result.captured ?? 0) > 0) commands.push({ kind: 'speak', name: 'capture_remove' });
      return {
        state: { ...state, phase: 'replying', pendingReply: result.scheduledReply ?? null },
        commands,
      };
    }

    case 'BOARD_SETTLED':
      if (state.phase !== 'replying') return { state, commands: [] };
      return {
        state: { ...state, targetBoard: evt.board, pendingReply: null },
        commands: [{ kind: 'setupMode', board: evt.board }],
      };

    case 'SOLVED':
      if (state.phase === 'off' || state.phase === 'solved') return { state, commands: [] };
      // May arrive from 'replying' when the AI reply completes the solution — celebrate
      // now; the physical board catches up during the next clearing (v1 simplification).
      return {
        state: { ...state, phase: 'solved', pendingReply: null },
        commands: [
          { kind: 'armMoves', armed: false },
          { kind: 'ledClear' },
          { kind: 'speak', name: 'correct' },
          { kind: 'celebrate' },
        ],
      };

    case 'CELEBRATION_DONE':
      if (state.phase !== 'solved' || !evt.autoAdvance) return { state, commands: [] };
      return {
        state: { ...state, phase: 'clearing_next', targetBoard: evt.emptyBoard },
        commands: [{ kind: 'speak', name: 'clear_board' }, { kind: 'setupMode', board: evt.emptyBoard }],
      };

    case 'TRY_EXIT':
      if (state.phase === 'off') return { state, commands: [] };
      return {
        state: { ...state, phase: 'restoring', targetBoard: evt.board, pendingReply: null },
        commands: [{ kind: 'setupMode', board: evt.board }],
      };

    default:
      return { state, commands: [] };
  }
}
