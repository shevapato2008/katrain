import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../../api';
import { LedAPI } from '../../api/ledApi';
import type { BaipuStep } from '../../api/baipuApi';
import type { VisionSyncEvent } from './useVisionSync';
import { initialState, reduce, type BaipuMachineState, type BaipuPhase, type Board, type Command,
  type LedPoint, type MachineEvent, type NextStone, type SetupReason, type TransactionStage, type PhysicalTransaction } from './physicalBaipuMachine';
export type { BaipuPhase, NextStone, SetupReason, LedPoint } from './physicalBaipuMachine';
const BLINK_MS = 450;
const STUCK_MS = 10_000;
export interface PhysicalBaipuOptions {
  enabled: boolean; visionConnected: boolean; syncEvents: VisionSyncEvent[];
  /** Account/source generation; changing it invalidates pending device IO. */
  identity?: string;
  /** Explicit reconciliation boundary for undo or a resolved history choice at the same cursor. */
  revision?: number;
  k: number; board: Board; step?: BaipuStep; next: NextStone | null;
  paused: boolean; hintLeds: LedPoint[]; onMatched: () => void;
}
export interface PhysicalBaipuState {
  phase: BaipuPhase; reason: SetupReason | null; stage: TransactionStage | null; target: Board | null;
  missing: Array<[number, number]>; extra: Array<[number, number, number]>; wrong: [number, number] | null;
  stuck: boolean; ledOk: boolean; relight: () => void; recheck: () => void;
}
function transactionFor(o: PhysicalBaipuOptions): PhysicalTransaction {
  const step = o.step;
  const preRemoved = step?.pre_removed ?? [];
  const postRemoved = step?.removed ?? [];
  const cleared = o.board.map(row => [...row]);
  for (const p of preRemoved) cleared[p.row][p.col] = 0;
  const placed = cleared.map(row => [...row]);
  // Recorded assignment also applies to same-color repetitions.
  if (step?.row != null && step.col != null && step.color) placed[step.row][step.col] = step.color === 'B' ? 1 : 2;
  else if (!step && o.next) placed[o.next.row][o.next.col] = o.next.color;
  const final = placed.map(row => [...row]);
  for (const p of postRemoved) final[p.row][p.col] = 0;
  return { before: o.board, cleared, placed, final, next: o.next, preRemoved, postRemoved,
    requiresPlacement: step ? step.requires_placement ?? (step.kind !== 'pass' && step.kind !== 'clear') : !!o.next };
}
export function usePhysicalBaipu(opts: PhysicalBaipuOptions): PhysicalBaipuState {
  const { enabled, visionConnected, syncEvents, paused, hintLeds, k, board, step, identity, revision } = opts;
  const optsRef = useRef(opts); optsRef.current = opts;
  const machineRef = useRef<BaipuMachineState>(initialState);
  const [ui, setUi] = useState(initialState);
  const [ledOk, setLedOk] = useState(true), [stuck, setStuck] = useState(false);
  const sessionRef = useRef(crypto.randomUUID()), serialRef = useRef(0);
  const activeRef = useRef(false), genRef = useRef(0), processedRef = useRef(-1);
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const previousRef = useRef<{ key: string; k: number } | null>(null);
  const prevPaused = useRef(paused);
  const relightTimer = useRef<number | undefined>(undefined);
  const steadyRef = useRef<LedPoint[]>([]), blinkRef = useRef<LedPoint[]>([]);
  const blinkOn = useRef(true), lastLedKey = useRef('');
  const dispatchRef = useRef<(e: MachineEvent) => void>(() => {});

  const renderLeds = useCallback(() => {
    const pts = blinkOn.current ? [...steadyRef.current, ...blinkRef.current] : steadyRef.current;
    const key = JSON.stringify(pts);
    if (key === lastLedKey.current) return Promise.resolve();
    lastLedKey.current = key;
    return (pts.length ? LedAPI.points(pts) : LedAPI.clear()).then(r => setLedOk(r.connected)).catch(() => setLedOk(false));
  }, []);
  const setLeds = useCallback((steady: LedPoint[], blink: LedPoint[]) => {
    steadyRef.current = steady;
    if (JSON.stringify(blinkRef.current) !== JSON.stringify(blink)) blinkOn.current = true;
    blinkRef.current = blink; return renderLeds();
  }, [renderLeds]);
  const run = useCallback(async (cmd: Command) => {
    switch (cmd.kind) {
      case 'setupMode': await API.visionSetupMode(cmd.board, cmd.setupId); break;
      case 'expectedBoard': await API.visionExpectedBoard(cmd.board); break;
      case 'armMoves': await API.visionMoveDetection(cmd.armed); break;
      case 'pause': await API.visionPause(cmd.paused); break;
      case 'leds': await setLeds(cmd.steady, cmd.blink); break;
      case 'relightLater': {
        window.clearTimeout(relightTimer.current);
        const gen = genRef.current;
        relightTimer.current = window.setTimeout(() => { if (gen === genRef.current) dispatchRef.current({ type: 'RELIGHT' }); }, cmd.ms);
        break;
      }
      case 'matched': optsRef.current.onMatched(); break;
    }
  }, [setLeds]);
  const enqueue = useCallback((commands: Command[]) => {
    const gen = genRef.current;
    queueRef.current = queueRef.current.then(async () => {
      for (const cmd of commands) {
        if (!activeRef.current || gen !== genRef.current) return;
        try { await run(cmd); } catch { return; } // Do not arm or light guidance after a failed target update.
      }
    });
  }, [run]);
  const dispatch = useCallback((e: MachineEvent) => {
    const previous = machineRef.current;
    const result = reduce(previous, e);
    machineRef.current = result.state; setUi(result.state);
    if (result.state.setupId !== previous.setupId || e.type === 'PAUSE') window.clearTimeout(relightTimer.current);
    enqueue(result.commands);
  }, [enqueue]);
  dispatchRef.current = dispatch;
  const key = useMemo(() => JSON.stringify([k, board, step, opts.next, revision]), [k, board, step, opts.next, revision]);
  const start = useCallback((reason: SetupReason, verified = false) => {
    const o = optsRef.current;
    dispatch({ type: 'START', id: `${sessionRef.current}:${genRef.current}:${++serialRef.current}:${o.k}`,
      transaction: transactionFor(o), reason, verified });
  }, [dispatch]);

  useEffect(() => {
    if (!enabled || !visionConnected) return;
    genRef.current += 1; activeRef.current = true;
    const o = optsRef.current;
    processedRef.current = o.syncEvents.at(-1)?.seq ?? processedRef.current;
    previousRef.current = { key, k: o.k }; prevPaused.current = o.paused;
    const gen = genRef.current;
    queueRef.current = queueRef.current.then(async () => { if (gen === genRef.current) await API.visionMonitor(true).catch(() => {}); });
    start('entry');
    if (o.paused) dispatch({ type: 'PAUSE', leds: o.hintLeds });
    return () => {
      activeRef.current = false; genRef.current += 1;
      window.clearTimeout(relightTimer.current);
      machineRef.current = initialState; setUi(initialState); setStuck(false);
      steadyRef.current = []; blinkRef.current = []; lastLedKey.current = '';
      queueRef.current = queueRef.current.then(async () => {
        await API.visionMoveDetection(false).catch(() => {});
        await API.visionPause(false).catch(() => {});
        await API.visionMonitor(false).catch(() => {});
        await LedAPI.clear().catch(() => {});
      });
    };
    // Other values start a transaction below, without replacing the monitor lifecycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, visionConnected, identity]);

  // Reconcile cursor / pause boundaries before consuming this render's camera events.
  useEffect(() => {
    if (!activeRef.current) return;
    if (previousRef.current?.key !== key) {
      const prev = previousRef.current;
      const verified = !!prev && k === prev.k + 1 && machineRef.current.phase === 'advancing';
      previousRef.current = { key, k }; genRef.current += 1;
      start(prev && k < prev.k ? 'undo' : 'entry', verified);
      if (paused) dispatch({ type: 'PAUSE', leds: optsRef.current.hintLeds });
    }
    if (paused !== prevPaused.current) {
      genRef.current += 1;
      if (paused) dispatch({ type: 'PAUSE', leds: optsRef.current.hintLeds });
      else dispatch({ type: 'RESUME' });
      prevPaused.current = paused;
    }
  }, [key, k, paused, start, dispatch]);
  useEffect(() => {
    if (!enabled) return;
    for (const event of syncEvents) {
      if (event.seq <= processedRef.current) continue;
      processedRef.current = event.seq;
      if (!activeRef.current || optsRef.current.paused) continue;
      const d = event.data as { setup_id?: string; missing?: Array<[number, number]>; extra?: Array<[number, number, number]>; row?: number; col?: number; color?: number };
      switch (event.type) {
        case 'setup_progress': if (d.setup_id) dispatch({ type: 'SETUP_PROGRESS', setupId: d.setup_id, missing: d.missing ?? [], extra: d.extra ?? [] }); break;
        case 'setup_complete': if (d.setup_id) dispatch({ type: 'SETUP_COMPLETE', setupId: d.setup_id }); break;
        case 'move_confirmed': if (d.row != null && d.col != null && d.color != null) dispatch({ type: 'MOVE_CONFIRMED', row: d.row, col: d.col, color: d.color }); break;
        case 'move_pending': if (d.row != null && d.col != null) dispatch({ type: 'MOVE_PENDING', row: d.row, col: d.col }); break;
      }
    }
  }, [enabled, syncEvents, dispatch]);
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => { if (blinkRef.current.length) { blinkOn.current = !blinkOn.current; void renderLeds(); } }, BLINK_MS);
    return () => window.clearInterval(id);
  }, [enabled, renderLeds]);
  const hintKey = JSON.stringify(hintLeds);
  useEffect(() => {
    if (activeRef.current && optsRef.current.paused) enqueue([{ kind: 'leds', steady: [], blink: optsRef.current.hintLeds }]);
  }, [hintKey, enqueue]);
  useEffect(() => {
    setStuck(false);
    if (ui.phase !== 'setup' && ui.phase !== 'await') return;
    const id = window.setTimeout(() => setStuck(true), STUCK_MS);
    return () => window.clearTimeout(id);
  }, [ui.phase, ui.setupId]);
  const relight = useCallback(() => { lastLedKey.current = ''; dispatch({ type: 'RELIGHT' }); }, [dispatch]);
  const recheck = useCallback(() => { if (activeRef.current) { genRef.current += 1; dispatch({ type: 'RECHECK' }); } }, [dispatch]);
  return { phase: ui.phase, reason: ui.reason, stage: ui.stage, target: ui.target, missing: ui.missing, extra: ui.extra,
    wrong: ui.wrong, stuck, ledOk, relight, recheck };
}
