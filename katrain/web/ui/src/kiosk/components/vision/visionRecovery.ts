import type { VisionSyncEvent } from '../../hooks/useVisionSync';

export type VisionPos = [number, number, number];
export type PendingStone = { row: number; col: number; color: number };

export type BlockingRecovery =
  | { kind: 'capture'; positions: Array<{ row: number; col: number; color: number }> }
  | {
      kind: 'stone';
      row: number;
      col: number;
      color?: number;
      unbacked: boolean;
      from?: [number, number];
    }
  | { kind: 'mismatch'; positions: VisionPos[]; missing: VisionPos[] };

export interface RecoveryState {
  pending: { row: number; col: number; color: number; expiresAt: number } | null;
  blocking: BlockingRecovery | null;
}

export type RecoveryAction =
  | { kind: 'vision_event'; event: VisionSyncEvent; nowMs: number; platformPendingStone?: PendingStone | null }
  | { kind: 'node_advanced' }
  | { kind: 'pending_deadline'; nowMs: number };

export const initialRecoveryState: RecoveryState = {
  pending: null,
  blocking: null,
};

const PENDING_WINDOW_MS = 4_000;

export function classifyAdjacentRelocation(
  positions: VisionPos[],
  missing: VisionPos[],
): { from: [number, number]; to: [number, number]; color: number } | null {
  if (positions.length !== 1 || missing.length !== 1) return null;

  const [fromRow, fromCol, fromColor] = positions[0];
  const [toRow, toCol, toColor] = missing[0];
  const distance = Math.max(Math.abs(fromRow - toRow), Math.abs(fromCol - toCol));
  if (fromColor !== toColor || distance !== 1) return null;

  return {
    from: [fromRow, fromCol],
    to: [toRow, toCol],
    color: fromColor,
  };
}

function isExactPendingMismatch(
  pending: PendingStone,
  positions: VisionPos[],
  missing: VisionPos[],
): boolean {
  return positions.length === 1
    && missing.length === 0
    && positions[0][0] === pending.row
    && positions[0][1] === pending.col
    && positions[0][2] === pending.color;
}

export function reduceRecoveryState(state: RecoveryState, action: RecoveryAction): RecoveryState {
  if (action.kind === 'node_advanced') {
    return state.pending === null ? state : { ...state, pending: null };
  }

  if (action.kind === 'pending_deadline') {
    if (state.pending === null || action.nowMs < state.pending.expiresAt) return state;
    return { ...state, pending: null };
  }

  const { event, nowMs } = action;

  if (event.type === 'move_pending') {
    const { row, col, color } = event.data as { row: number; col: number; color: number };
    return {
      ...state,
      pending: { row, col, color, expiresAt: nowMs + PENDING_WINDOW_MS },
    };
  }

  if (event.type === 'synced') return initialRecoveryState;

  if (event.type === 'board_lost') {
    return state.pending === null ? state : { ...state, pending: null };
  }

  if (event.type === 'capture_pending') {
    const positions = (event.data.positions as VisionPos[] | undefined) ?? [];
    return {
      pending: null,
      blocking: {
        kind: 'capture',
        positions: positions.map(([row, col, color]) => ({ row, col, color })),
      },
    };
  }

  if (event.type === 'captures_cleared') {
    if (state.blocking?.kind !== 'capture') return state;
    return { ...state, blocking: null };
  }

  if (event.type === 'ambiguous_stone') {
    const { row, col, color, unbacked } = event.data as {
      row: number;
      col: number;
      color?: number;
      unbacked?: boolean;
    };
    if (action.platformPendingStone?.row === row && action.platformPendingStone.col === col
      && action.platformPendingStone.color === color) return state;
    if (state.blocking?.kind === 'capture') {
      return state.pending === null ? state : { ...state, pending: null };
    }
    return {
      pending: null,
      blocking: {
        kind: 'stone',
        row,
        col,
        ...(typeof color === 'number' ? { color } : {}),
        unbacked: Boolean(unbacked),
      },
    };
  }

  if (event.type === 'illegal_change') {
    const positions = (event.data.positions as VisionPos[] | undefined) ?? [];
    const missing = (event.data.missing as VisionPos[] | undefined) ?? [];

    if (action.platformPendingStone && isExactPendingMismatch(action.platformPendingStone, positions, missing)) {
      return state;
    }

    if (
      state.pending
      && nowMs < state.pending.expiresAt
      && isExactPendingMismatch(state.pending, positions, missing)
    ) {
      return state;
    }

    if (state.blocking?.kind === 'capture' || state.blocking?.kind === 'stone') return state;

    const relocation = classifyAdjacentRelocation(positions, missing);
    if (relocation) {
      return {
        ...state,
        blocking: {
          kind: 'stone',
          row: relocation.to[0],
          col: relocation.to[1],
          color: relocation.color,
          unbacked: true,
          from: relocation.from,
        },
      };
    }

    return { ...state, blocking: { kind: 'mismatch', positions, missing } };
  }

  return state;
}
