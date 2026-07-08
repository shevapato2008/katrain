// IO layer for physical-board tsumego: consumes vision WS events (seq-ordered, no
// loss), injects physical moves into placeStone, executes machine commands
// (REST/LED/voice/undo/celebrate/advance). All phase logic lives in the pure
// reducer (physicalTsumegoMachine.ts) — keep this file thin.

import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { LedAPI } from '../../api/ledApi';
import type { MoveResult, Stone } from '../../hooks/useTsumegoProblem';
import type { VisionSyncEvent } from './useVisionSync';
import { useVoice } from './useVoice';
import {
  initialState,
  reduce,
  type Command,
  type LedPoint,
  type MachineEvent,
  type MachineState,
  type PhysicalPhase,
  type SetupStage,
} from './physicalTsumegoMachine';

// Re-export phase/stage types so UI consumers (develop's PhysicalStatePanel) import them from the
// hook module without reaching into the reducer. (develop's stub exported these; our real hook is
// the authoritative target its whole physical-tsumego UI was designed against.)
export type { PhysicalPhase, SetupStage } from './physicalTsumegoMachine';

export function stonesToVisionBoard(stones: Stone[], boardSize: number): number[][] {
  const board: number[][] = Array.from({ length: boardSize }, () => Array(boardSize).fill(0));
  for (const s of stones) {
    const [col, y] = s.coords;
    if (col >= 0 && col < boardSize && y >= 0 && y < boardSize) {
      board[boardSize - 1 - y][col] = s.player === 'B' ? 1 : 2;
    }
  }
  return board;
}

const emptyBoard = (size: number): number[][] =>
  Array.from({ length: size }, () => Array(size).fill(0));

const STAR_POINTS: Array<[number, number]> = [
  [3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15],
];

const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

export interface PhysicalTsumegoOptions {
  enabled: boolean;
  visionConnected: boolean; // /ws/vision open — ENABLE must wait for it or SETUP_COMPLETE is lost
  problemKey: string | null; // problem.id — lifecycle restarts on change
  resyncKey: number; // bumped by Reset — re-runs the clearing→setup lifecycle without a problem change
  boardSize: number;
  stones: Stone[];
  isSolved: boolean;
  showHint: boolean;
  hintCoords: [number, number] | null;
  isTryMode: boolean;
  autoAdvance: boolean; // auto-advance setting && next problem exists
  syncEvents: VisionSyncEvent[];
  placeStone: (x: number, y: number) => MoveResult | null;
  undo: () => void;
  playMoveSound: (sound: NonNullable<MoveResult['sound']>) => void;
  onAdvance: () => void; // navigate to next problem (after clearing_next completes)
}

export interface PhysicalTsumegoState {
  phase: PhysicalPhase;
  stage: SetupStage;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  stageMatched: number;
  stageTotal: number;
  ledOk: boolean;
  /** Page reports screen clicks here so the physical board is guided to follow (PRD TR1). */
  onScreenMove: (result: MoveResult | null, preBoard: number[][]) => void;
}

export function usePhysicalTsumego(opts: PhysicalTsumegoOptions): PhysicalTsumegoState {
  const { enabled, visionConnected, problemKey, resyncKey, boardSize, stones, isSolved, showHint, hintCoords, isTryMode, syncEvents } = opts;
  const { speak } = useVoice();

  const machineRef = useRef<MachineState>(initialState);
  const [ui, setUi] = useState<MachineState>(initialState);
  const [ledOk, setLedOk] = useState(true);

  // Refs so executors/consumers always see current values without re-subscribing.
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const stonesRef = useRef(stones);
  stonesRef.current = stones;
  const pausedRef = useRef(false);
  pausedRef.current = showHint || isTryMode;

  const runIdRef = useRef(0); // bumps on lifecycle changes → aborts in-flight celebrate
  const lastLedKeyRef = useRef('');
  const processedSeqRef = useRef(-1);
  const prevTryRef = useRef(false); // last-seen isTryMode; drives try-exit edge detection

  // Flash plumbing: 'flash'-coloured points (a wrong/extra stone) BLINK, because their LED sits
  // occluded directly under the offending stone — a static colour is invisible. Everything else is
  // steady. renderLeds composes steady ∪ (flash while the blink phase is "on"); the interval below
  // toggles flashOnRef ~2Hz. Frame-rate SETUP_PROGRESS re-emits must NOT reset the blink phase, so we
  // only re-arm (flashOnRef=true) when the flash SET actually changes (flashKeyRef).
  const steadyPtsRef = useRef<LedPoint[]>([]);
  const flashPtsRef = useRef<LedPoint[]>([]);
  const flashOnRef = useRef(true);
  const flashKeyRef = useRef('');

  const renderLeds = useCallback(() => {
    const pts = flashOnRef.current ? [...steadyPtsRef.current, ...flashPtsRef.current] : steadyPtsRef.current;
    const key = JSON.stringify(pts);
    if (key === lastLedKeyRef.current) return;
    lastLedKeyRef.current = key;
    LedAPI.points(pts)
      .then((r) => setLedOk(r.connected))
      .catch(() => setLedOk(false));
  }, []);

  const ledPoints = useCallback((pts: LedPoint[]) => {
    steadyPtsRef.current = pts.filter((p) => p.color !== 'flash');
    const flash = pts.filter((p) => p.color === 'flash');
    const flashKey = JSON.stringify(flash);
    if (flashKey !== flashKeyRef.current) {
      flashKeyRef.current = flashKey;
      flashPtsRef.current = flash;
      flashOnRef.current = true; // fresh set of extras → show immediately, then let the interval blink
    }
    renderLeds();
  }, [renderLeds]);

  const ledClear = useCallback(() => {
    steadyPtsRef.current = [];
    flashPtsRef.current = [];
    flashKeyRef.current = '';
    lastLedKeyRef.current = '';
    LedAPI.clear().catch(() => setLedOk(false));
  }, []);

  // Blink the 'flash' (wrong-stone) LEDs ~2Hz while enabled; no LED traffic when none are active.
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => {
      if (flashPtsRef.current.length === 0) return;
      flashOnRef.current = !flashOnRef.current;
      renderLeds();
    }, 450);
    return () => window.clearInterval(id);
  }, [enabled, renderLeds]);

  // Forward declaration pattern: dispatch and celebrate reference each other.
  const dispatchRef = useRef<(evt: MachineEvent) => void>(() => {});

  const celebrate = useCallback(async (runId: number) => {
    const board = stonesToVisionBoard(stonesRef.current, optsRef.current.boardSize);
    const empties = STAR_POINTS.filter(([r, c]) => board[r]?.[c] === 0);
    const pts: LedPoint[] = empties.map(([row, col]) => ({ row, col, color: 'hint' }));
    for (let i = 0; i < 2; i++) {
      if (runId !== runIdRef.current) return; // aborted (problem change / disable)
      ledPoints(pts);
      await delay(350);
      if (runId !== runIdRef.current) return;
      ledClear();
      await delay(250);
    }
    if (runId !== runIdRef.current) return;
    dispatchRef.current({
      type: 'CELEBRATION_DONE',
      autoAdvance: optsRef.current.autoAdvance,
      emptyBoard: emptyBoard(optsRef.current.boardSize),
    });
  }, [ledPoints, ledClear]);

  const execute = useCallback((cmd: Command) => {
    switch (cmd.kind) {
      case 'setupMode':
        API.visionSetupMode(cmd.board).catch(() => {});
        break;
      case 'expectedBoard':
        API.visionExpectedBoard(cmd.board).catch(() => {});
        break;
      case 'armMoves':
        API.visionMoveDetection(cmd.armed).catch(() => {});
        break;
      case 'ledPoints':
        ledPoints(cmd.points);
        break;
      case 'ledClear':
        ledClear();
        break;
      case 'speak':
        speak(cmd.name);
        break;
      case 'undoFailed':
        optsRef.current.undo();
        break;
      case 'celebrate':
        void celebrate(runIdRef.current);
        break;
      case 'advance':
        optsRef.current.onAdvance();
        break;
    }
  }, [ledPoints, ledClear, speak, celebrate]);

  const dispatch = useCallback((evt: MachineEvent) => {
    const { state, commands } = reduce(machineRef.current, evt);
    machineRef.current = state;
    setUi(state);
    commands.forEach(execute);
  }, [execute]);
  dispatchRef.current = dispatch;

  // ---- enable / per-problem lifecycle ---------------------------------------
  // Wait for the vision WS: arming setup-mode before /ws/vision is registered loses the
  // (near-instant, on an empty board) SETUP_COMPLETE, wedging the flow at "clear board".
  useEffect(() => {
    if (!enabled || !visionConnected) return;
    runIdRef.current += 1;
    API.visionMonitor(true).catch(() => {});
    dispatch({ type: 'ENABLE', emptyBoard: emptyBoard(boardSize) });
    return () => {
      runIdRef.current += 1; // abort celebrate
      machineRef.current = initialState;
      prevTryRef.current = false; // clear stale try-mode edge so re-enable can't fire a stray TRY_EXIT
      setUi(initialState);
      API.visionMoveDetection(false).catch(() => {});
      API.visionPause(false).catch(() => {});
      API.visionMonitor(false).catch(() => {});
      LedAPI.clear().catch(() => {});
    };
    // dispatch/boardSize stable across a problem's life; problemKey drives per-problem
    // restarts, resyncKey drives Reset-triggered restarts, visionConnected gates the
    // first arm until the WS can receive events.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, visionConnected, problemKey, resyncKey]);

  // ---- WS event consumption (seq queue — every event exactly once, in order) --
  useEffect(() => {
    if (!enabled) return;
    for (const evt of syncEvents) {
      if (evt.seq <= processedSeqRef.current) continue;
      processedSeqRef.current = evt.seq;
      if (pausedRef.current) continue; // hint/try active: recognition is paused backend-side too
      if (evt.type === 'setup_progress') {
        const d = evt.data as { missing?: Array<[number, number]>; extra?: Array<[number, number, number]> };
        dispatch({ type: 'SETUP_PROGRESS', missing: d.missing ?? [], extra: d.extra ?? [] });
      } else if (evt.type === 'setup_complete') {
        dispatch({ type: 'SETUP_COMPLETE', screenBoard: stonesToVisionBoard(stonesRef.current, boardSize) });
      } else if (evt.type === 'move_confirmed' && machineRef.current.phase === 'ready') {
        const d = evt.data as { row: number; col: number; color: number };
        const preBoard = stonesToVisionBoard(stonesRef.current, boardSize);
        const result = optsRef.current.placeStone(d.col, boardSize - 1 - d.row);
        if (result?.sound) optsRef.current.playMoveSound(result.sound); // 三通道：物理落子也播既有音效
        dispatch({ type: 'MOVE_APPLIED', result, preBoard });
      }
    }
  }, [enabled, syncEvents, boardSize, dispatch]);

  // ---- screen settle watcher (replying phase) --------------------------------
  useEffect(() => {
    if (!enabled) return;
    const m = machineRef.current;
    if (m.phase !== 'replying') return;
    const reply = m.pendingReply;
    if (
      reply &&
      !stones.some((s) => s.player === reply.player && s.coords[0] === reply.coords[0] && s.coords[1] === reply.coords[1])
    ) {
      return; // AI reply not on screen yet (~300ms) — do NOT converge early (评审 Blocker)
    }
    dispatch({ type: 'BOARD_SETTLED', board: stonesToVisionBoard(stones, boardSize) });
  }, [enabled, stones, boardSize, dispatch]);

  // ---- solved watcher (AI reply may complete the solution) --------------------
  useEffect(() => {
    if (!enabled || !isSolved) return;
    dispatch({ type: 'SOLVED' }); // reducer ignores if already solved/off
  }, [enabled, isSolved, dispatch]);

  // ---- pause aggregate + hint white LED (order matters: before try-exit effect) --
  useEffect(() => {
    if (!enabled) return;
    const paused = showHint || isTryMode;
    API.visionPause(paused).catch(() => {});
    ledClear(); // wipe convergence frame on pause; wipe hint LED on unpause
    if (paused && showHint && hintCoords) {
      ledPoints([{ row: boardSize - 1 - hintCoords[1], col: hintCoords[0], color: 'hint' }]);
    }
    // On unpause the next SETUP_PROGRESS frame re-lights convergence LEDs; 'ready' has no LEDs.
  }, [enabled, showHint, isTryMode, hintCoords, boardSize, ledPoints, ledClear]);

  // ---- try-mode exit → restore/verify physical board --------------------------
  useEffect(() => {
    if (!enabled) {
      prevTryRef.current = isTryMode;
      return;
    }
    if (prevTryRef.current && !isTryMode) {
      // exitTryMode restored the screen snapshot in the same render — stonesRef is current.
      dispatch({ type: 'TRY_EXIT', board: stonesToVisionBoard(stonesRef.current, boardSize) });
    }
    prevTryRef.current = isTryMode;
  }, [enabled, isTryMode, boardSize, dispatch]);

  // ---- screen click passthrough (PRD TR1 dual input) --------------------------
  const onScreenMove = useCallback((result: MoveResult | null, preBoard: number[][]) => {
    dispatch({ type: 'MOVE_APPLIED', result, preBoard }); // reducer no-ops outside 'ready'
  }, [dispatch]);

  return {
    phase: ui.phase,
    stage: ui.stage,
    missing: ui.missing,
    extra: ui.extra,
    stageMatched: ui.stageMatched,
    stageTotal: ui.stageTotal,
    ledOk,
    onScreenMove,
  };
}
