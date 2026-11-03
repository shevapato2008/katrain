import { describe, expect, it } from 'vitest';
import { initialState, reduce, setupLeds, type Board, type PhysicalTransaction, type BaipuMachineState } from './physicalBaipuMachine';
const empty = (): Board => Array.from({ length: 3 }, () => Array(3).fill(0));
const stone = (b: Board, r: number, c: number, v: number) => { const n = b.map(row => [...row]); n[r][c] = v; return n; };
const transaction = (extra: Partial<PhysicalTransaction> = {}): PhysicalTransaction => {
  const before = empty(), placed = stone(before, 1, 1, 1);
  return { before, cleared: before, placed, final: placed, next: { row: 1, col: 1, color: 1 }, preRemoved: [], postRemoved: [], requiresPlacement: true, ...extra };
};
const begin = (tx = transaction()) => reduce(initialState, { type: 'START', id: 'session:0', transaction: tx, reason: 'entry' }).state;
const complete = (s: BaipuMachineState) => reduce(s, { type: 'SETUP_COMPLETE', setupId: s.setupId! });
const progress = (s: BaipuMachineState, missing: Array<[number, number]>, extra: Array<[number, number, number]>) => reduce(s, { type: 'SETUP_PROGRESS', setupId: s.setupId!, missing, extra });
const place = (s: BaipuMachineState) => reduce(s, { type: 'MOVE_CONFIRMED', row: 1, col: 1, color: 1 });

describe('authoritative physical replay transactions', () => {
  it('restores entry before arming the exact coordinate and color', () => {
    const s = begin();
    expect(s).toMatchObject({ phase: 'setup', stage: 'entry', target: empty() });
    const r = complete(s);
    expect(r.state).toMatchObject({ phase: 'await', stage: 'place' });
    expect(r.commands.map(c => c.kind)).toEqual(['armMoves', 'expectedBoard', 'armMoves', 'leds']);
    expect(reduce(r.state, { type: 'MOVE_CONFIRMED', row: 1, col: 1, color: 2 }).state.reason).toBe('wrong');
    expect(place(r.state).commands.filter(c => c.kind === 'matched')).toHaveLength(1);
  });
  it('replacement keeps entry, pre-clear, placement and final removal separate', () => {
    const before = stone(empty(), 1, 1, 2), cleared = empty(), placed = stone(cleared, 1, 1, 1);
    const tx = transaction({ before, cleared, placed, final: empty(), preRemoved: [{ row: 1, col: 1 }], postRemoved: [{ row: 1, col: 1 }] });
    const pre = complete(begin(tx));
    expect(pre.state).toMatchObject({ stage: 'pre', reason: 'pre_remove', target: cleared });
    expect(setupLeds(pre.state).blink).toEqual([{ row: 1, col: 1, color: 'remove' }]);
    const awaiting = complete(pre.state).state;
    expect(awaiting.phase).toBe('await');
    const post = place(awaiting);
    expect(post.state).toMatchObject({ stage: 'post', phase: 'setup', target: empty() });
    expect(post.commands.some(c => c.kind === 'matched')).toBe(false);
    expect(complete(post.state).commands.filter(c => c.kind === 'matched')).toHaveLength(1);
  });
  it('acknowledges one-motion replacement with pending or partially removed captures', () => {
    const before = stone(stone(stone(empty(), 1, 1, 2), 0, 0, 2), 0, 1, 2);
    const cleared = stone(before, 1, 1, 0), placed = stone(cleared, 1, 1, 1);
    const tx = transaction({ before, cleared, placed, final: stone(stone(placed, 0, 0, 0), 0, 1, 0), preRemoved: [{ row: 1, col: 1 }], postRemoved: [{ row: 0, col: 0 }, { row: 0, col: 1 }] });
    const pre = complete(begin(tx)).state;
    for (const missing of [[], [[0, 0]] as Array<[number, number]>, [[0, 0], [0, 1]] as Array<[number, number]>]) {
      const r = progress(pre, missing, [[1, 1, 1]]);
      expect(r.state.stage).toBe('post');
      expect(r.commands.some(c => c.kind === 'matched')).toBe(false);
    }
  });
  it('self-capture final equality never proves the transient placement', () => {
    const tx = transaction({ final: empty(), postRemoved: [{ row: 1, col: 1 }] });
    const r = complete(begin(tx));
    expect(r.state.phase).toBe('await');
    expect(r.commands.some(c => c.kind === 'matched')).toBe(false);
    expect(progress(begin(tx), [], []).state.phase).toBe('setup');
    const post = place(r.state).state;
    expect(post.stage).toBe('post');
    expect(complete(post).state.phase).toBe('advancing');
  });
  it('same-color repeat completes after entry verification; clear requires removal', () => {
    const board = stone(empty(), 1, 1, 1);
    const repeat = transaction({ before: board, cleared: board, placed: board, final: board, requiresPlacement: false });
    expect(complete(begin(repeat)).state.phase).toBe('advancing');
    const clear = transaction({ before: board, cleared: board, placed: board, final: empty(), next: null, requiresPlacement: false, postRemoved: [{ row: 1, col: 1 }] });
    const post = complete(begin(clear));
    expect(post.state.stage).toBe('post');
    expect(post.commands.some(c => c.kind === 'matched')).toBe(false);
    expect(complete(post.state).state.phase).toBe('advancing');
  });
  it('post-removal never promotes and completion fires once', () => {
    const post = place(complete(begin(transaction({ final: empty(), postRemoved: [{ row: 1, col: 1 }] }))).state).state;
    expect(progress(post, [], [[1, 1, 1]]).state.phase).toBe('setup');
    expect(setupLeds(progress(post, [], [[1, 1, 1]]).state).blink).toEqual([{ row: 1, col: 1, color: 'remove' }]);
    const done = complete(post);
    expect(complete(done.state).commands).toEqual([]);
    expect(place(done.state).commands).toEqual([]);
  });
  it('rejects stale setup IDs and rechecks unchanged authoritative target with a fresh ID', () => {
    const s = begin();
    expect(reduce(s, { type: 'SETUP_COMPLETE', setupId: 'old' }).state).toBe(s);
    expect(reduce(s, { type: 'SETUP_PROGRESS', setupId: 'old', missing: [], extra: [[1, 1, 1]] }).state).toBe(s);
    const retry = reduce(s, { type: 'RECHECK' });
    expect(retry.state.target).toEqual(s.target);
    expect(retry.state.setupId).not.toBe(s.setupId);
    expect(complete(retry.state).state.phase).toBe('await');
  });
  it('pause disarms and resume restores completed entry instead of unfinished actions', () => {
    const paused = reduce(complete(begin()).state, { type: 'PAUSE', leds: [] });
    expect(paused.state.phase).toBe('paused');
    expect(place(paused.state).commands).toEqual([]);
    const resumed = reduce(paused.state, { type: 'RESUME' });
    expect(resumed.state).toMatchObject({ stage: 'entry', reason: 'restore', target: empty() });
    expect(resumed.commands.map(c => c.kind)).toEqual(['armMoves', 'leds', 'setupMode', 'pause']);
  });
});
