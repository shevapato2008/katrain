import { expect, it } from 'vitest';
import { buildTutorialReplay, type DiagramV2 } from './tutorialReplay';

it('removes captured labels, letters and shapes through pass and coordinate reuse, matching server replay frames', () => {
  const diagram: DiagramV2 = {
    schema_version: 2, size: 19, stones: { B: [], W: [[0, 1], [1, 0], [2, 1], [1, 2], [1, 1]] },
    labels: { '1,2': '41', '1,1': '43' }, unknown_stones: [],
    source_region: { col: 0, row: 0, cols: 4, rows: 4, confirmed: true },
    replay: {
      status: 'complete',
      evidence: { kind: 'source', source_pointer: 'fixture:/capture-mark-removal', description: 'Synthetic capture, pass and coordinate reuse; not book evidence.' },
      initial: {
        stones: { B: [[1, 1]], W: [[0, 1], [1, 0], [2, 1]] }, unknown_stones: [],
        labels: { '1,1': 'old' }, letters: { '1,1': 'A', '3,3': 'B' }, shapes: { '1,1': 'triangle', '3,2': 'square' },
        known_region: { col: 0, row: 0, cols: 4, rows: 4 }, to_play: 'W',
      },
      moves: [
        { kind: 'move', color: 'W', point: [1, 2], printed_number: '41' },
        { kind: 'pass', color: 'B', point: null, printed_number: null },
        { kind: 'move', color: 'W', point: [1, 1], printed_number: '43' },
      ],
    },
  };
  const before = structuredClone(diagram);
  const replay = buildTutorialReplay(diagram);
  expect(replay.status).toBe('complete');
  expect(replay.frames[1].captured).toEqual([[1, 1]]);
  for (const frame of replay.frames.slice(1)) {
    expect(frame.payload.letters).toEqual({ '3,3': 'B' });
    expect(frame.payload.shapes).toEqual({ '3,2': 'square' });
    expect(frame.payload.labels!['1,1']).not.toBe('old');
  }
  expect(replay.frames[3].payload.labels!['1,1']).toBe('43');
  expect(replay.frames[0].payload.labels!['1,1']).toBe('old');
  expect(replay.frames[0].payload.letters!['1,1']).toBe('A');
  expect(replay.frames[0].payload.shapes!['1,1']).toBe('triangle');
  expect(diagram).toEqual(before);
});
