// The cursor belongs to completed SGF operations. Recognition acknowledges a placement
// separately from the final board, so replacements and self-captures stay atomic.
import type { LedColor } from '../../api/ledApi';
export type Board = number[][];
export interface NextStone { row: number; col: number; color: 1 | 2 }
export interface LedPoint { row: number; col: number; color: LedColor }
export interface Point { row: number; col: number }
export type BaipuPhase = 'off' | 'setup' | 'await' | 'advancing' | 'paused';
export type TransactionStage = 'entry' | 'pre' | 'place' | 'post';
export type SetupReason = 'entry' | 'pre_remove' | 'capture' | 'wrong' | 'undo' | 'restore' | 'verify';
export interface PhysicalTransaction {
  before: Board; cleared: Board; placed: Board; final: Board;
  next: NextStone | null; preRemoved: Point[]; postRemoved: Point[]; requiresPlacement: boolean;
}
export type Command =
  | { kind: 'setupMode'; board: Board; setupId: string }
  | { kind: 'expectedBoard'; board: Board }
  | { kind: 'armMoves'; armed: boolean }
  | { kind: 'pause'; paused: boolean }
  | { kind: 'leds'; steady: LedPoint[]; blink: LedPoint[] }
  | { kind: 'relightLater'; ms: number }
  | { kind: 'matched' };
export interface BaipuMachineState {
  phase: BaipuPhase; reason: SetupReason | null; stage: TransactionStage | null;
  target: Board | null; next: NextStone | null; transaction: PhysicalTransaction | null;
  id: string; setupId: string | null; setupSerial: number;
  missing: Array<[number, number]>; extra: Array<[number, number, number]>;
  wrong: [number, number] | null;
}
export type MachineEvent =
  | { type: 'START'; id: string; transaction: PhysicalTransaction; reason: SetupReason; verified?: boolean }
  | { type: 'SETUP_PROGRESS'; setupId: string; missing: Array<[number, number]>; extra: Array<[number, number, number]> }
  | { type: 'SETUP_COMPLETE'; setupId: string }
  | { type: 'MOVE_CONFIRMED'; row: number; col: number; color: number }
  | { type: 'MOVE_PENDING'; row: number; col: number }
  | { type: 'RECHECK' } | { type: 'RELIGHT' }
  | { type: 'PAUSE'; leds: LedPoint[] } | { type: 'RESUME' } | { type: 'STOP' };
export const initialState: BaipuMachineState = {
  phase: 'off', reason: null, stage: null, target: null, next: null, transaction: null,
  id: '', setupId: null, setupSerial: 0, missing: [], extra: [], wrong: null,
};
const OFF: Command = { kind: 'leds', steady: [], blink: [] };
const none = (state: BaipuMachineState) => ({ state, commands: [] as Command[] });
const stoneLed = (v: number): LedColor => v === 2 ? 'white' : 'black';
const isNext = (n: NextStone | null, r: number, c: number, v: number) => !!n && n.row === r && n.col === c && n.color === v;
const canWitness = (s: BaipuMachineState) => s.stage !== 'post' && !!s.transaction?.requiresPlacement;
export function setupLeds(s: BaipuMachineState): { steady: LedPoint[]; blink: LedPoint[] } {
  return {
    steady: s.missing.map(([row, col]) => ({ row, col, color: stoneLed(s.target?.[row]?.[col] ?? 1) })),
    blink: s.extra.filter(([r, c, v]) => !(canWitness(s) && isNext(s.next, r, c, v)))
      .map(([row, col]) => ({ row, col, color: 'remove' })),
  };
}
function setup(s: BaipuMachineState, stage: TransactionStage, board: Board, reason: SetupReason, removals: Point[] = []) {
  const setupSerial = s.setupSerial + 1;
  const setupId = `${s.id}:${stage}:${setupSerial}`;
  const state: BaipuMachineState = { ...s, phase: 'setup', stage, target: board, reason, setupSerial, setupId,
    missing: [], extra: removals.map(p => [p.row, p.col, (stage === 'pre' ? s.transaction?.before : s.transaction?.placed)?.[p.row]?.[p.col] ?? 1]), wrong: reason === 'wrong' ? s.wrong : null };
  return { state, commands: [
    { kind: 'armMoves', armed: false }, OFF, { kind: 'setupMode', board, setupId },
    ...(removals.length ? [{ kind: 'leds', ...setupLeds(state) } as Command] : []),
  ] as Command[] };
}
function finish(s: BaipuMachineState) {
  return { state: { ...s, phase: 'advancing' as const, setupId: null },
    commands: [{ kind: 'armMoves', armed: false }, OFF, { kind: 'matched' }] as Command[] };
}
function placed(s: BaipuMachineState) {
  const tx = s.transaction!;
  return tx.postRemoved.length ? setup(s, 'post', tx.final, 'capture', tx.postRemoved) : finish(s);
}
function awaitPlacement(s: BaipuMachineState) {
  const tx = s.transaction!;
  if (!tx.requiresPlacement || !tx.next) return placed(s);
  return { state: { ...s, phase: 'await' as const, stage: 'place' as const, reason: null, target: tx.cleared,
    setupId: null, missing: [], extra: [], wrong: null }, commands: [
    { kind: 'armMoves', armed: false }, { kind: 'expectedBoard', board: tx.cleared }, { kind: 'armMoves', armed: true },
    { kind: 'leds', steady: [{ ...tx.next, color: stoneLed(tx.next.color) }], blink: [] },
  ] as Command[] };
}
function afterEntry(s: BaipuMachineState) {
  const tx = s.transaction!;
  return tx.preRemoved.length ? setup(s, 'pre', tx.cleared, 'pre_remove', tx.preRemoved) : awaitPlacement(s);
}
// Reconstruct only the observed diff from setup's authoritative target. Go rules
// are never recomputed here. Already lifted post-removal stones are allowed.
function hasPlacementWitness(s: BaipuMachineState) {
  if (!canWitness(s) || !s.target || !s.transaction?.next) return false;
  const tx = s.transaction, n = tx.next!;
  const observed = s.target.map(row => [...row]);
  for (const [r, c] of s.missing) { if (observed[r]) observed[r][c] = 0; }
  for (const [r, c, v] of s.extra) { if (observed[r]) observed[r][c] = v; }
  if (observed[n.row]?.[n.col] !== n.color) return false;
  return tx.placed.every((row, r) => row.every((v, c) => observed[r]?.[c] === v
    || (observed[r]?.[c] === 0 && tx.postRemoved.some(p => p.row === r && p.col === c))));
}
export function reduce(s: BaipuMachineState, e: MachineEvent): { state: BaipuMachineState; commands: Command[] } {
  switch (e.type) {
    case 'START': {
      const state = { ...initialState, id: e.id, transaction: e.transaction, next: e.transaction.next };
      return e.verified ? afterEntry(state) : setup(state, 'entry', e.transaction.before, e.reason);
    }
    case 'SETUP_PROGRESS': {
      if (s.phase !== 'setup' || e.setupId !== s.setupId) return none(s);
      const state = { ...s, missing: e.missing, extra: e.extra };
      if (hasPlacementWitness(state)) return placed(state);
      return { state, commands: [{ kind: 'leds', ...setupLeds(state) }] };
    }
    case 'SETUP_COMPLETE':
      if (s.phase !== 'setup' || e.setupId !== s.setupId || !s.transaction) return none(s);
      if (s.stage === 'post') return finish(s);
      if (s.stage === 'entry') return afterEntry(s);
      return awaitPlacement(s);
    case 'MOVE_CONFIRMED':
      if (s.phase !== 'await' || !s.transaction) return none(s);
      if (isNext(s.next, e.row, e.col, e.color)) return placed(s);
      return setup({ ...s, wrong: [e.row, e.col] }, 'place', s.transaction.cleared, 'wrong');
    case 'MOVE_PENDING':
      return s.phase === 'await' && s.next?.row === e.row && s.next.col === e.col
        ? { state: s, commands: [OFF, { kind: 'relightLater', ms: 3000 }] } : none(s);
    case 'RELIGHT':
      if (s.phase === 'setup') return { state: s, commands: [{ kind: 'leds', ...setupLeds(s) }] };
      if (s.phase === 'await') return { state: s, commands: [{ kind: 'leds', steady: s.next ? [{ ...s.next, color: stoneLed(s.next.color) }] : [], blink: [] }] };
      return none(s);
    case 'RECHECK':
      if (s.phase === 'setup' && s.target && s.stage && s.reason) return setup(s, s.stage, s.target, s.reason);
      if (s.phase === 'await' && s.transaction) return setup(s, 'place', s.transaction.cleared, 'verify');
      return none(s);
    case 'PAUSE':
      return { state: { ...s, phase: 'paused', setupId: null }, commands: [
        { kind: 'armMoves', armed: false }, { kind: 'pause', paused: true }, { kind: 'leds', steady: [], blink: e.leds },
      ] };
    case 'RESUME': {
      if (s.phase !== 'paused' || !s.transaction) return none(s);
      const r = setup(s, 'entry', s.transaction.before, 'restore');
      r.commands.push({ kind: 'pause', paused: false }); return r;
    }
    case 'STOP': return none(initialState);
  }
}
