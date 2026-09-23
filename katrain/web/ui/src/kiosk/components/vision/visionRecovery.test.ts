import { describe, expect, it } from 'vitest';

import type { VisionSyncEvent } from '../../hooks/useVisionSync';
import {
  classifyAdjacentRelocation,
  initialRecoveryState,
  reduceRecoveryState,
  type RecoveryState,
  type VisionPos,
} from './visionRecovery';

const event = (type: VisionSyncEvent['type'], data: Record<string, unknown> = {}): VisionSyncEvent => ({
  seq: 1,
  type,
  data,
});

const transition = (state: RecoveryState, type: VisionSyncEvent['type'], data = {}, nowMs = 1_000) =>
  reduceRecoveryState(state, { kind: 'vision_event', event: event(type, data), nowMs });

describe('classifyAdjacentRelocation', () => {
  it('classifies one adjacent same-color extra and missing stone', () => {
    expect(classifyAdjacentRelocation([[18, 4, 2]], [[18, 5, 2]])).toEqual({
      from: [18, 4],
      to: [18, 5],
      color: 2,
    });
  });

  it.each([
    { positions: [[18, 4, 1]], missing: [[18, 5, 2]], label: 'different colors' },
    { positions: [[18, 4, 2]], missing: [[18, 6, 2]], label: 'a non-adjacent pair' },
    { positions: [[18, 4, 2], [17, 4, 2]], missing: [[18, 5, 2]], label: 'multiple extras' },
  ] satisfies Array<{ positions: VisionPos[]; missing: VisionPos[]; label: string }>)(
    'does not guess for $label',
    ({ positions, missing }) => {
      expect(classifyAdjacentRelocation(positions, missing)).toBeNull();
    },
  );
});

describe('reduceRecoveryState', () => {
  it('suppresses only the exact pending extra for four seconds', () => {
    const pending = transition(initialRecoveryState, 'move_pending', { row: 4, col: 5, color: 2 }, 1_000);
    const suppressed = transition(
      pending,
      'illegal_change',
      { positions: [[4, 5, 2]], missing: [] },
      4_999,
    );

    expect(suppressed).toEqual(pending);
  });

  it.each([
    {
      positions: [[4, 5, 2], [9, 9, 1]],
      missing: [],
      label: 'another extra stone',
    },
    {
      positions: [[4, 5, 2]],
      missing: [[8, 8, 1]],
      label: 'a missing stone',
    },
    {
      positions: [[4, 5, 1]],
      missing: [],
      label: 'a different color',
    },
  ] satisfies Array<{ positions: VisionPos[]; missing: VisionPos[]; label: string }>)(
    'does not suppress when the mismatch includes $label',
    ({ positions, missing }) => {
      const pending = transition(initialRecoveryState, 'move_pending', { row: 4, col: 5, color: 2 }, 1_000);
      const next = transition(pending, 'illegal_change', { positions, missing }, 2_000);

      expect(next.blocking).toEqual({ kind: 'mismatch', positions, missing });
    },
  );

  it('releases suppression at the deadline', () => {
    const pending = transition(initialRecoveryState, 'move_pending', { row: 4, col: 5, color: 2 }, 1_000);
    const expired = reduceRecoveryState(pending, { kind: 'pending_deadline', nowMs: 5_000 });
    const next = transition(expired, 'illegal_change', { positions: [[4, 5, 2]], missing: [] }, 5_000);

    expect(expired.pending).toBeNull();
    expect(next.blocking).toEqual({ kind: 'mismatch', positions: [[4, 5, 2]], missing: [] });
  });

  it.each(['node_advanced', 'ambiguous_stone', 'capture_pending', 'board_lost', 'synced'] as const)(
    '%s clears a pending candidate',
    (kind) => {
      const pending = transition(initialRecoveryState, 'move_pending', { row: 4, col: 5, color: 2 });
      const next = kind === 'node_advanced'
        ? reduceRecoveryState(pending, { kind })
        : transition(
            pending,
            kind,
            kind === 'ambiguous_stone'
              ? { row: 4, col: 5, color: 2, unbacked: true }
              : kind === 'capture_pending'
                ? { positions: [[7, 8, 1]] }
                : {},
          );

      expect(next.pending).toBeNull();
    },
  );

  it('capture converts wire tuples and replaces ambiguous or mismatch recovery', () => {
    const ambiguous = transition(initialRecoveryState, 'ambiguous_stone', {
      row: 4,
      col: 5,
      color: 2,
      unbacked: false,
    });
    const capture = transition(ambiguous, 'capture_pending', { positions: [[7, 8, 1], [9, 10, 2]] });

    expect(capture.blocking).toEqual({
      kind: 'capture',
      positions: [
        { row: 7, col: 8, color: 1 },
        { row: 9, col: 10, color: 2 },
      ],
    });

    const mismatch = transition(initialRecoveryState, 'illegal_change', {
      positions: [[2, 2, 1]],
      missing: [],
    });
    expect(transition(mismatch, 'capture_pending', { positions: [[7, 8, 1]] }).blocking?.kind).toBe('capture');
  });

  it('ambiguous replaces mismatch but cannot displace capture', () => {
    const mismatch = transition(initialRecoveryState, 'illegal_change', {
      positions: [[2, 2, 1]],
      missing: [],
    });
    const ambiguous = transition(mismatch, 'ambiguous_stone', {
      row: 4,
      col: 5,
      color: 2,
      unbacked: true,
    });
    expect(ambiguous.blocking).toEqual({
      kind: 'stone',
      row: 4,
      col: 5,
      color: 2,
      unbacked: true,
    });

    const capture = transition(initialRecoveryState, 'capture_pending', { positions: [[7, 8, 1]] });
    expect(transition(capture, 'ambiguous_stone', { row: 4, col: 5 }).blocking).toEqual(capture.blocking);
  });

  it('captures_cleared relinquishes only capture ownership', () => {
    const capture = transition(initialRecoveryState, 'capture_pending', { positions: [[7, 8, 1]] });
    expect(transition(capture, 'captures_cleared').blocking).toBeNull();

    const stone = transition(initialRecoveryState, 'ambiguous_stone', { row: 4, col: 5, unbacked: false });
    expect(transition(stone, 'captures_cleared')).toEqual(stone);
  });

  it('classifies adjacent relocation as targeted stone recovery', () => {
    const next = transition(initialRecoveryState, 'illegal_change', {
      positions: [[18, 4, 2]],
      missing: [[18, 5, 2]],
    });

    expect(next.blocking).toEqual({
      kind: 'stone',
      row: 18,
      col: 5,
      color: 2,
      unbacked: true,
      from: [18, 4],
    });
  });

  it.each([
    { positions: [[18, 4, 2]], missing: [[18, 6, 2]] },
    { positions: [[18, 4, 2], [17, 4, 2]], missing: [[18, 5, 2]] },
  ] satisfies Array<{ positions: VisionPos[]; missing: VisionPos[] }>)(
    'keeps non-adjacent and multi-stone changes as a mismatch',
    ({ positions, missing }) => {
      expect(transition(initialRecoveryState, 'illegal_change', { positions, missing }).blocking).toEqual({
        kind: 'mismatch',
        positions,
        missing,
      });
    },
  );

  it('synced clears all recovery while passive events leave it intact', () => {
    const mismatch = transition(initialRecoveryState, 'illegal_change', {
      positions: [[2, 2, 1]],
      missing: [],
    });
    expect(transition(mismatch, 'degraded')).toEqual(mismatch);
    expect(transition(mismatch, 'board_reacquired')).toEqual(mismatch);
    expect(transition(mismatch, 'synced')).toEqual(initialRecoveryState);
  });
});
