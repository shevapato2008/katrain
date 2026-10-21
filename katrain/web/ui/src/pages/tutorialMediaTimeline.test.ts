import { describe, expect, it } from 'vitest';
import { frameAtTime, placementsAtTime, subtitleAtTime, knownRegion, type RecordingData, type ReplayFrame } from './tutorialMediaTimeline';

const frames: ReplayFrame[] = [
  { step: 0, payload: { size: 9, stones: { B: [[8, 8]], W: [] } }, last: null, appeared_stones: [] },
  { step: 1, payload: { size: 9, stones: { B: [[8, 8], [2, 0]], W: [[3, 0]] }, labels: { '2,0': '1', '3,0': '2' } },
    last: null, currentMove: null, appeared_stones: [{ color: 'B', point: [2, 0] }, { color: 'W', point: [3, 0] }] },
  { step: 2, payload: { size: 9, stones: { B: [[8, 8], [2, 0]], W: [[3, 0]] }, labels: { '2,0': '1', '3,0': '2' }, letters: { '2,0': 'A' }, shapes: { '2,0': 'triangle' } },
    last: null, currentMove: null, appeared_stones: [] },
  { step: 3, payload: { size: 9, stones: { B: [[8, 8]], W: [[2, 0]] } }, last: [2, 0], captured: [[3, 0], [2, 0]],
    currentMove: { kind: 'move', color: 'W', point: [2, 0] }, appeared_stones: [{ color: 'W', point: [2, 0] }], nextColor: null },
  { step: 4, payload: { size: 9, stones: { B: [[8, 8]], W: [[2, 0]] } }, last: null,
    currentMove: { kind: 'pass', color: 'B' }, appeared_stones: [] },
];
const data: RecordingData = {
  narration: '白棋被提。之后复用原位。', render_mode: '2d',
  board_payload: { size: 9, stones: { B: [[8, 8], [2, 0]], W: [[3, 0]] }, labels: { '2,0': '1', '3,0': '2' },
    source_region: { col: 1, row: 0, cols: 8, rows: 9, confirmed: true } },
  frames,
  speech_timing: { schema_version: 1, duration_ms: 3000, audio_sha256: 'audio', boundaries: [
    { text: '白棋被提。', start_ms: 100, duration_ms: 800 },
    { text: '之后复用原位。', start_ms: 1200, duration_ms: 1200 },
  ] },
  step_cues: { schema_version: 1, mode: 'presentation', audio_sha256: 'audio', status: 'complete', frames,
    objects: [], events: [], cues: [
      { step: 0, at_ms: 0, source: 'initial' }, { step: 1, at_ms: 1000, source: 'speech_end' },
      { step: 2, at_ms: 1400, source: 'speech_end' }, { step: 3, at_ms: 2000, source: 'speech_end' },
      { step: 4, at_ms: 2500, source: 'speech_end' },
    ] },
};

describe('tutorial recorder time axis', () => {
  it('reveals complete presentation snapshots only at the spoken reference end, without requiring rules history', () => {
    expect(data.board_payload.replay).toBeUndefined();
    expect(frameAtTime(data, 999)).toBe(frames[0]);
    expect(frameAtTime(data, 1000)).toBe(frames[1]);
    expect(frameAtTime(data, 1399).payload.letters).toBeUndefined();
    expect(frameAtTime(data, 1400)).toBe(frames[2]);
    expect(frameAtTime(data, 2100).payload.stones).toEqual({ B: [[8, 8]], W: [[2, 0]] });
    expect(frameAtTime(data, 0)).toBe(frames[0]);
    expect(frameAtTime(data, 2500).currentMove?.kind).toBe('pass');
  });
  it('settles every appeared stone gently for 360ms and never repeats a landing for independent annotations', () => {
    expect(placementsAtTime(data, 999)).toEqual([]);
    expect(placementsAtTime(data, 1000)).toEqual([
      { point: [2, 0], lift: .25, scale: .96 }, { point: [3, 0], lift: .25, scale: .96 },
    ]);
    const middle = placementsAtTime(data, 1180);
    expect(middle[0].lift).toBeCloseTo(.0625);
    expect(middle[1].scale).toBeCloseTo(.99);
    expect(placementsAtTime(data, 1360)).toEqual([]);
    expect(placementsAtTime(data, 1400)).toEqual([]);
    expect(placementsAtTime(data, 2000)).toEqual([{ point: [2, 0], lift: .25, scale: .96 }]);
    expect(placementsAtTime(data, 1180)).toEqual(middle);
    expect(placementsAtTime(data, 0)).toEqual([]);
    expect(placementsAtTime(data, 2500)).toEqual([]);
  });
  it('keeps a stone settling across an annotation-only cue without restarting its pose', () => {
    const closelySpaced = { ...data, step_cues: { ...data.step_cues, cues: data.step_cues.cues.map(cue =>
      cue.step === 2 ? { ...cue, at_ms: 1100 } : cue) } };
    expect(placementsAtTime(closelySpaced, 1099)[0].lift).toBeCloseTo(.25 * (261 / 360) ** 2);
    expect(placementsAtTime(closelySpaced, 1100)).toHaveLength(2);
    expect(placementsAtTime(closelySpaced, 1100)[0].lift).toBeCloseTo(.25 * (260 / 360) ** 2);
    expect(placementsAtTime(closelySpaced, 1180)[0].lift).toBeCloseTo(.0625);
    expect(placementsAtTime(closelySpaced, 1360)).toEqual([]);
  });
  it('keeps an appearance when an annotation event shares its exact cue time', () => {
    const simultaneous = { ...data, step_cues: { ...data.step_cues, cues: data.step_cues.cues.map(cue =>
      cue.step === 2 ? { ...cue, at_ms: 1000 } : cue) } };
    expect(frameAtTime(simultaneous, 1000)).toBe(frames[2]);
    expect(placementsAtTime(simultaneous, 1000)).toEqual([
      { point: [2, 0], lift: .25, scale: .96 }, { point: [3, 0], lift: .25, scale: .96 },
    ]);
  });
  it('settles overlapping stone cues independently using each appearance time', () => {
    const overlappingFrames: ReplayFrame[] = [frames[0], frames[1], { ...frames[2],
      payload: { ...frames[2].payload, stones: { ...frames[2].payload.stones, W: [[3, 0], [4, 0]] } },
      appeared_stones: [{ color: 'W', point: [4, 0] }],
    }];
    const overlapping: RecordingData = { ...data, frames: overlappingFrames, step_cues: { ...data.step_cues,
      frames: overlappingFrames, cues: [data.step_cues.cues[0], data.step_cues.cues[1], { step: 2, at_ms: 1100, source: 'speech_end' }],
    } };
    const poses = placementsAtTime(overlapping, 1100);
    expect(poses.map(pose => pose.point)).toEqual([[2, 0], [3, 0], [4, 0]]);
    expect(poses[0].lift).toBeCloseTo(.25 * (260 / 360) ** 2);
    expect(poses[2]).toEqual({ point: [4, 0], lift: .25, scale: .96 });
    expect(placementsAtTime(overlapping, 1360).map(pose => pose.point)).toEqual([[4, 0]]);
    expect(placementsAtTime(overlapping, 1460)).toEqual([]);
    expect(placementsAtTime(overlapping, 1100)).toEqual(poses);
  });
  it('stops captured poses and starts fresh for opposite-color and same-color point reuse', () => {
    const lifecycleFrames: ReplayFrame[] = [
      { step: 0, payload: { size: 9, stones: { B: [], W: [] } }, last: null, appeared_stones: [] },
      { step: 1, payload: { size: 9, stones: { B: [[2, 0]], W: [] } }, last: [2, 0], appeared_stones: [{ color: 'B', point: [2, 0] }] },
      { step: 2, payload: { size: 9, stones: { B: [], W: [[2, 0]] } }, last: [2, 0], captured: [[2, 0]], appeared_stones: [{ color: 'W', point: [2, 0] }] },
      { step: 3, payload: { size: 9, stones: { B: [], W: [] } }, last: null, captured: [[2, 0]], appeared_stones: [] },
      { step: 4, payload: { size: 9, stones: { B: [[2, 0]], W: [] } }, last: [2, 0], appeared_stones: [{ color: 'B', point: [2, 0] }] },
    ];
    const lifecycle: RecordingData = { ...data, frames: lifecycleFrames, step_cues: { ...data.step_cues,
      frames: lifecycleFrames, cues: [0, 1000, 1100, 1200, 1250].map((at_ms, step) => ({ step, at_ms, source: step ? 'speech_end' : 'initial' })),
    } };
    expect(placementsAtTime(lifecycle, 1100)).toEqual([{ point: [2, 0], lift: .25, scale: .96 }]);
    expect(placementsAtTime(lifecycle, 1200)).toEqual([]);
    expect(placementsAtTime(lifecycle, 1250)).toEqual([{ point: [2, 0], lift: .25, scale: .96 }]);
    expect(placementsAtTime(lifecycle, 1360)[0].lift).toBeCloseTo(.25 * (250 / 360) ** 2);
    expect(placementsAtTime(lifecycle, 1610)).toEqual([]);
  });
  it('blocks pending proof instead of exposing the fully annotated saved diagram', () => {
    const pending: RecordingData = { ...data, step_cues: { ...data.step_cues, status: 'pending', reason: 'Missing spoken A', frames: [], cues: [] }, frames: [] };
    expect(() => frameAtTime(pending, 0)).toThrow(/Missing spoken A/);
    expect(() => frameAtTime(pending, 2500)).toThrow(/pending/i);
    expect(() => placementsAtTime(pending, 1000)).toThrow(/pending/i);
  });
  it('requires the same validated frames in the recording snapshot and presentation proof', () => {
    expect(() => frameAtTime({ ...data, frames: [frames[0]] }, 1000)).toThrow(/frames.*match/i);
    const sameFrames = structuredClone(frames);
    expect(frameAtTime({ ...data, frames: sameFrames }, 1000)).toBe(frames[1]);
    expect(() => frameAtTime({ ...data, step_cues: { ...data.step_cues, mode: undefined } } as unknown as RecordingData, 0)).toThrow(/mode/i);
  });
  it('keeps static complete snapshots while requiring an explicit validated mode', () => {
    const staticData: RecordingData = { ...data, frames: [frames[0]], step_cues: { ...data.step_cues, mode: 'static', frames: [frames[0]], cues: [{ step: 0, at_ms: 0, source: 'initial' }] } };
    expect(frameAtTime(staticData, 2500)).toBe(frames[0]);
  });
  it('uses actual boundary starts for subtitles, including on backward seeks', () => {
    expect(subtitleAtTime(data.narration, data.speech_timing, 0)).toBe('');
    expect(subtitleAtTime(data.narration, data.speech_timing, 1500)).toBe('之后复用原位。');
    expect(subtitleAtTime(data.narration, data.speech_timing, 300)).toBe('白棋被提。');
  });
  it('keeps exact saved punctuation and spaces such as 黑2、4 while retaining word timestamps', () => {
    const narration = '“白1”， 黑2、4 后，白3。下一句 保留 空格，白5！';
    const first = ['白', '1', '黑', '2', '4', '后', '白', '3'];
    const second = ['下一句', '保留', '空格', '白', '5'];
    const timing = { ...data.speech_timing, boundaries: [
      ...first.map((text, index) => ({ text, start_ms: 100 + index * 100, duration_ms: 80 })),
      ...second.map((text, index) => ({ text, start_ms: 1700 + index * 100, duration_ms: 80 })),
    ] };
    const originalBoundaries = structuredClone(timing.boundaries);
    expect(subtitleAtTime(narration, timing, 99)).toBe('');
    expect(subtitleAtTime(narration, timing, 100)).toBe('“白1”， 黑2、4 后，白3。');
    expect(subtitleAtTime(narration, timing, 1699)).toBe('“白1”， 黑2、4 后，白3。');
    expect(subtitleAtTime(narration, timing, 1700)).toBe('下一句 保留 空格，白5！');
    expect(timing.boundaries).toEqual(originalBoundaries);
  });
  it.each([
    '它的威力在于，接下来黑棋在a位和b位必能占到其中一处，白棋无法同时守住这两个要点。',
    '因此，黑1这一点夺去了白棋的眼位，使白棋失去眼形，形成难以下好的局面。',
    '看这幅图，要把白二冲和白四双倒扑联系起来理解，不能因为黑三挡住了眼前的冲击，就判断黑棋已经安全。',
    '空点上的一、二、三，表示另外三种挂角选择：一位是一间高挂，二位是二间高挂，这两种走法往往依个人的布局策略选择；',
    '这个形状也可以从另一种次序来理解：假如白棋面对一间夹先脱先，后来黑棋在图中七位靠，白棋在六位长，就会形成与图中黑五、白四相同的图形，原书对此注明可参看第五十四图。',
  ])('keeps a complete source sentence or semicolon clause regardless of length: %s', sentence => {
    const narration = sentence + '下一句。';
    const boundaries = [...narration].filter(character => /[\p{L}\p{N}]/u.test(character))
      .map((text, index) => ({ text, start_ms: 100 + index * 100, duration_ms: 80 }));
    const timing = { ...data.speech_timing, boundaries };
    const originalBoundaries = structuredClone(boundaries);
    const sentenceCharacters = [...sentence].filter(character => /[\p{L}\p{N}]/u.test(character)).length;
    const followingStart = boundaries[sentenceCharacters].start_ms;
    expect(subtitleAtTime(narration, timing, 99)).toBe('');
    for (const boundary of boundaries.slice(0, sentenceCharacters)) {
      expect(subtitleAtTime(narration, timing, boundary.start_ms)).toBe(sentence);
    }
    expect(subtitleAtTime(narration, timing, followingStart - 1)).toBe(sentence);
    expect(subtitleAtTime(narration, timing, followingStart)).toBe('下一句。');
    expect(subtitleAtTime(narration, timing, 100)).toBe(sentence);
    expect(timing.boundaries).toEqual(originalBoundaries);
  });
  it('uses known region evidence from the explicit recording mode', () => {
    const replayRegion = { col: 0, row: 0, cols: 5, rows: 6 };
    const sourceRegion = { col: 4, row: 2, cols: 4, rows: 5 };
    const payload = { ...data.board_payload, replay: { initial: { known_region: replayRegion } } };
    expect(knownRegion({ ...data, board_payload: payload })).toEqual({ col: 1, row: 0, cols: 8, rows: 9 });
    expect(knownRegion({ ...data, board_payload: payload, step_cues: { ...data.step_cues, mode: 'replay' } })).toEqual(replayRegion);
    expect(knownRegion({ ...data, board_payload: payload, step_cues: { ...data.step_cues, mode: 'source_replay', presentation_plan: { source_replay: { initial: { known_region: sourceRegion } } } } })).toEqual(sourceRegion);
    expect(knownRegion({ ...data, board_payload: { ...payload, source_region: { ...data.board_payload.source_region!, confirmed: false } } })).toBeNull();
  });
  it('keeps forbidden-ko initial reveals silent and settles only the hypothetical capture', () => {
    const koFrames: ReplayFrame[] = [
      { step: 0, payload: { size: 9, stones: { B: [], W: [] } }, last: null, currentMove: null, appeared_stones: [] },
      { step: 1, payload: { size: 9, stones: { B: [], W: [[4, 4]] }, labels: { '4,4': '1' } }, last: null, currentMove: null,
        appeared_stones: [], presentation_action: { kind: 'initial_reveal', object_ids: ['reference:2:labels:4,4'] } },
      { step: 2, payload: { size: 9, stones: { B: [[3, 4]], W: [] }, labels: { '3,4': '1' } }, last: [3, 4],
        currentMove: { kind: 'forbidden_ko_capture', color: 'B', point: [3, 4] }, captured: [[4, 4]],
        appeared_stones: [{ color: 'B', point: [3, 4] }], presentation_action: { kind: 'forbidden_ko_capture', object_ids: ['labels:3,4'] } },
    ];
    const koData: RecordingData = { ...data, frames: koFrames, step_cues: { ...data.step_cues, mode: 'forbidden_ko', frames: koFrames,
      cues: [{ step: 0, at_ms: 0, source: 'initial' }, { step: 1, at_ms: 1000, source: 'speech_end' }, { step: 2, at_ms: 2000, source: 'speech_end' }] } };
    expect(frameAtTime(koData, 1000)).toBe(koFrames[1]);
    expect(placementsAtTime(koData, 1000)).toEqual([]);
    expect(frameAtTime(koData, 1999).payload.stones.W).toEqual([[4, 4]]);
    expect(frameAtTime(koData, 2000).captured).toEqual([[4, 4]]);
    expect(placementsAtTime(koData, 2000)).toEqual([{ point: [3, 4], lift: .25, scale: .96 }]);
    expect(frameAtTime(koData, 1000)).toBe(koFrames[1]);
    expect(placementsAtTime(koData, 1000)).toEqual([]);
  });
});
