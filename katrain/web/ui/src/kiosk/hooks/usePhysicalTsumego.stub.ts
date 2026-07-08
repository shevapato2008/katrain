// STUB (Phase D). Side-effect-free ADAPTER conforming to the REAL physical-track hook's
//   exported signature (katrain-kiosk-physical-tsumego/.../hooks/usePhysicalTsumego.ts).
//   The REAL signature is AUTHORITATIVE — the types in this file mirror it verbatim; they
//   are NOT an independent contract (see .superpowers/sdd/phase-D-real-contract.md).
//   Real-hook shape this stub conforms to:
//     - signature: usePhysicalTsumego(opts: PhysicalTsumegoOptions) -- opts-driven + WS-fed
//     - phase enum has 9 values, including 'restoring' (try-mode exit)
//     - setup progress: stage/missing/extra/stageMatched/stageTotal
//     - removals via a machine command stream; plus ledOk + onScreenMove passthrough
//   Landing the real hook = re-point the indirection re-export (./usePhysicalTsumego.ts)
//   at an adapter over it, keeping PhysicalStatePanel/TsumegoProblemPage untouched.
//
//   This stub is intentionally side-effect-free: it imports NOTHING from the `api` layer,
//   `ledApi`, `useVoice`, or any WebSocket, and has no IO `useEffect`. `opts.enabled` is the
//   only option it reacts to; every other option is accepted purely for type fidelity (so the
//   real hook is a drop-in replacement) and otherwise ignored.

import { useCallback, useState } from 'react';
import type { MoveResult, Stone } from '../../hooks/useTsumegoProblem';
import type { VisionSyncEvent } from './useVisionSync';

export type PhysicalPhase =
  | 'off'
  | 'clearing'
  | 'setup'
  | 'ready'
  | 'replying'
  | 'removing'
  | 'restoring'
  | 'solved'
  | 'clearing_next';

export type SetupStage = 'black' | 'white' | null;

export interface PhysicalTsumegoOptions {
  enabled: boolean;
  visionConnected: boolean;
  problemKey: string | null;
  resyncKey: number;
  boardSize: number;
  stones: Stone[];
  isSolved: boolean;
  showHint: boolean;
  hintCoords: [number, number] | null;
  isTryMode: boolean;
  autoAdvance: boolean;
  syncEvents: VisionSyncEvent[];
  placeStone: (x: number, y: number) => MoveResult | null;
  undo: () => void;
  playMoveSound: (sound: NonNullable<MoveResult['sound']>) => void;
  onAdvance: () => void;
}

export interface PhysicalTsumegoState {
  phase: PhysicalPhase;
  stage: SetupStage;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>; // [row, col, color] -- stones on board not in target
  stageMatched: number;
  stageTotal: number;
  ledOk: boolean;
  /** Page reports screen clicks here so the physical board is guided to follow (PRD TR1). */
  onScreenMove: (result: MoveResult | null, preBoard: number[][]) => void;
}

/** Deterministic, side-effect-free per-phase derivation -- no IO. */
function deriveStubState(phase: PhysicalPhase): Omit<PhysicalTsumegoState, 'ledOk' | 'onScreenMove'> {
  switch (phase) {
    case 'setup': // A 摆放黑棋
      return { phase, stage: 'black', stageMatched: 2, stageTotal: 5, missing: [[3, 3], [15, 15]], extra: [] };
    case 'ready': // B 做题中
      return { phase, stage: null, stageMatched: 0, stageTotal: 0, missing: [], extra: [] };
    case 'replying': // C 应手
      return { phase, stage: null, stageMatched: 0, stageTotal: 0, missing: [], extra: [] };
    case 'removing': // D 答错拿除 -- one wrong stone to remove
      return { phase, stage: null, stageMatched: 0, stageTotal: 0, missing: [], extra: [[9, 9, 1]] };
    case 'solved': // E 答对
      return { phase, stage: null, stageMatched: 0, stageTotal: 0, missing: [], extra: [] };
    case 'off':
    case 'clearing':
    case 'clearing_next':
    case 'restoring':
    default:
      return { phase, stage: null, stageMatched: 0, stageTotal: 0, missing: [], extra: [] };
  }
}

export function usePhysicalTsumego(
  opts: PhysicalTsumegoOptions,
): PhysicalTsumegoState & { __devSetPhase?: (p: PhysicalPhase) => void } {
  // side-effect-free: NO import/call of api / ledApi / useVoice / WS; NO IO useEffect.
  const [devPhase, setDevPhase] = useState<PhysicalPhase | null>(null);
  // opts.enabled is the ONLY opt the stub reacts to; everything else is accepted for
  // TYPE fidelity (so the real hook is a drop-in) but ignored by the stub.
  const phase: PhysicalPhase = opts.enabled ? (devPhase ?? 'setup') : 'off';
  const __devSetPhase = useCallback((p: PhysicalPhase) => setDevPhase(p), []);
  const onScreenMove = useCallback(() => {}, []); // real dispatches MOVE_APPLIED; stub no-ops
  return { ...deriveStubState(phase), ledOk: true, onScreenMove, __devSetPhase };
}
