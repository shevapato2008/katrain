import { describe, expect, it } from 'vitest';
import { frameAtTime, subtitleAtTime, knownRegion, type RecordingData } from './tutorialMediaTimeline';

const data: RecordingData = {
  render_mode: '2d',
  board_payload: { size: 9, stones: { B: [[1, 0]], W: [[2, 0]] }, source_region: { col: 1, row: 0, cols: 8, rows: 9, confirmed: true } },
  frames: [
    { step: 0, payload: { size: 9, stones: { B: [], W: [[1, 0]] } }, last: null },
    { step: 1, payload: { size: 9, stones: { B: [[2, 0]], W: [] } }, last: [2, 0] },
    { step: 2, payload: { size: 9, stones: { B: [[2, 0]], W: [[1, 0]] } }, last: [1, 0] },
  ],
  speech_timing: { schema_version: 1, duration_ms: 3000, audio_sha256: 'audio', narration_sha256: 'text', voice: 'voice', boundaries: [
    { text: '白棋被提。', start_ms: 100, duration_ms: 800 },
    { text: '之后复用原位。', start_ms: 1200, duration_ms: 1200 },
  ] },
  step_cues: { schema_version: 1, audio_sha256: 'audio', replay_sha256: 'replay', status: 'complete', cues: [{ step: 1, at_ms: 1000 }, { step: 2, at_ms: 2000 }] },
};

describe('tutorial recorder time axis', () => {
  it('selects whole capture/reuse snapshots and rewinds without accumulating stones', () => {
    expect(frameAtTime(data, 2100)).toBe(data.frames[2]);
    expect(frameAtTime(data, 1100).payload.stones.W).toEqual([]);
    expect(frameAtTime(data, 0)).toBe(data.frames[0]);
    expect(frameAtTime(data, 2100).payload.stones.W).toEqual([[1, 0]]);
  });
  it('uses the saved static board for every time while cues are pending', () => {
    const pending = { ...data, step_cues: { ...data.step_cues, status: 'pending' as const, cues: [] } };
    expect(frameAtTime(pending, 0).payload).toBe(data.board_payload);
    expect(frameAtTime(pending, 2500).payload).toBe(data.board_payload);
  });
  it('uses actual boundary starts for subtitles, including on backward seeks', () => {
    expect(subtitleAtTime(data.speech_timing, 0)).toBe('');
    expect(subtitleAtTime(data.speech_timing, 1500)).toBe('之后复用原位。');
    expect(subtitleAtTime(data.speech_timing, 300)).toBe('白棋被提。');
  });
  it('only treats confirmed source extent as known in static mode', () => {
    expect(knownRegion({ ...data, step_cues: { ...data.step_cues, status: 'pending' } })).toEqual({ col: 1, row: 0, cols: 8, rows: 9 });
    expect(knownRegion({ ...data, board_payload: { ...data.board_payload, source_region: null } })).toBeNull();
  });
});
