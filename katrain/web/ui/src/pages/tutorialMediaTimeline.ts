import type { SGFPayload } from '../components/tutorials/SGFBoard';

export type Point = [number, number];
export interface Region { col: number; row: number; cols: number; rows: number }
export interface PresentationCallout {
  id: string; anchor: Point; side: 'top' | 'right' | 'board'; text: string;
  source_pointer: string; image_sha256: string;
}
export interface RecorderPayload extends SGFPayload {
  unknown_stones?: { point: Point; color: null; evidence?: string }[];
  source_region?: (Region & { confirmed: boolean }) | null;
  presentation_arrows?: { id: string; from: Point; to: Point; source_pointer: string; image_sha256: string }[];
  presentation_callouts?: PresentationCallout[];
  replay?: { initial?: { known_region?: Region | null } | null } | null;
}
export interface ReplayFrame {
  step: number;
  payload: RecorderPayload;
  last: Point | null;
  captured?: Point[];
  currentMove?: { kind: string; color: string; point?: Point | null } | null;
  nextColor?: string | null;
  appeared_stones: { color: 'B' | 'W'; point: Point }[];
  presentation_action?: { kind: 'initial_reveal' | 'forbidden_ko_capture'; object_ids: string[] } | null;
}
export interface SpeechTiming {
  schema_version: 1;
  audio_sha256: string;
  narration_sha256?: string;
  voice?: string;
  duration_ms: number;
  boundaries: { text: string; start_ms: number; duration_ms: number }[];
}
export interface StepCues {
  schema_version: 1;
  audio_sha256: string;
  replay_sha256?: string;
  mode: 'presentation' | 'replay' | 'source_replay' | 'forbidden_ko' | 'static';
  frames: ReplayFrame[];
  objects: { id: string; kind: 'labels' | 'letters' | 'shapes' | 'arrow' | 'callout' | 'replay'; point: Point | null;
    stone_color: 'B' | 'W' | null; value?: string | null; number?: number | null; callout?: PresentationCallout; replay_step?: number; role?: string }[];
  events: { step: number; at_ms: number; object_ids: string[]; span: [number, number]; kind?: 'initial_reveal' | 'forbidden_ko_capture' }[];
  presentation_plan?: { callouts?: PresentationCallout[]; source_replay?: { initial: { known_region?: Region | null } } | null } | null;
  status: 'complete' | 'pending';
  reason?: string;
  cues: { step: number; at_ms: number; source: 'initial' | 'speech_end' }[];
}
export interface RecordingData {
  output_profile?: 'galaxy-4k-v1' | 'kiosk-7-v1';
  /** Stable figure identity; old recording snapshots use the recorder's fixed fallback. */
  visual_seed?: string;
  narration: string;
  board_payload: RecorderPayload;
  frames: ReplayFrame[];
  speech_timing: SpeechTiming;
  step_cues: StepCues;
  render_mode: '2d' | '3d';
}

export function frameAtTime(data: RecordingData, timeMs: number): ReplayFrame {
  const proof = data.step_cues;
  if (proof.status !== 'complete') {
    throw new Error(`Recording presentation is pending: ${proof.reason ?? 'spoken reference cues require calibration'}`);
  }
  if (!['presentation', 'replay', 'source_replay', 'forbidden_ko', 'static'].includes(proof.mode)) {
    throw new Error('Missing validated recording presentation mode');
  }
  if (!proof.frames?.length || (proof.frames !== data.frames && JSON.stringify(proof.frames) !== JSON.stringify(data.frames))) {
    throw new Error('Recording frames do not match the validated presentation frames');
  }
  let step = 0;
  for (const cue of proof.cues) {
    if (cue.at_ms > timeMs) break;
    step = cue.step;
  }
  const frame = proof.frames.find(item => item.step === step);
  if (!frame) throw new Error(`Missing validated presentation frame ${step}`);
  return frame;
}

export interface RecordingPlacement { point: Point; lift: number; scale: number }

/** Pure recording poses: seeking to a timestamp always produces the same placements. */
export function placementsAtTime(data: RecordingData, timeMs: number): RecordingPlacement[] {
  const frame = frameAtTime(data, timeMs);
  const visible = new Set((['B', 'W'] as const).flatMap(color =>
    frame.payload.stones[color].map(point => `${color}:${point.join(',')}`)));
  const appearances = new Map<string, { point: Point; atMs: number }>();
  for (const cue of data.step_cues.cues) {
    if (cue.at_ms > timeMs) break;
    if (cue.source !== 'speech_end' || timeMs - cue.at_ms >= 360) continue;
    const appearedFrame = data.step_cues.frames.find(item => item.step === cue.step);
    if (!appearedFrame) throw new Error(`Missing validated presentation frame ${cue.step}`);
    for (const { color, point } of appearedFrame.appeared_stones) {
      const identity = `${color}:${point.join(',')}`;
      // Later appearances replace the old lifetime; marker-only cues leave its clock alone.
      if (visible.has(identity)) appearances.set(identity, { point, atMs: cue.at_ms });
    }
  }
  return [...appearances.values()].map(({ point, atMs }) => {
    const remaining = (1 - (timeMs - atMs) / 360) ** 2;
    return { point, lift: .25 * remaining, scale: 1 - .04 * remaining };
  });
}

export function knownRegion(data: RecordingData): Region | null {
  if (data.step_cues.mode === 'replay') return data.board_payload.replay?.initial?.known_region ?? null;
  if (data.step_cues.mode === 'source_replay') return data.step_cues.presentation_plan?.source_replay?.initial.known_region ?? null;
  const region = data.board_payload.source_region;
  return region?.confirmed ? { col: region.col, row: region.row, cols: region.cols, rows: region.rows } : null;
}

/** Caption text is sliced verbatim from the saved narration; only times come from words. */
export function subtitleAtTime(narration: string, timing: SpeechTiming, timeMs: number): string {
  const sourceCharacters = [...narration.matchAll(/[\p{L}\p{N}]/gu)];
  const wordCharacters = timing.boundaries.map(boundary => boundary.text.match(/[\p{L}\p{N}]/gu) ?? []);
  if (!sourceCharacters.length || sourceCharacters.map(match => match[0]).join('') !== wordCharacters.flat().join('')) {
    throw new Error('Speech boundary text does not match the exact saved narration');
  }
  let text = '';
  let start = 0;
  let cursor = 0;
  const groups: { text: string; start: number }[] = [];
  for (const [index, boundary] of timing.boundaries.entries()) {
    const count = wordCharacters[index].length;
    if (!count) continue;
    const from = cursor === 0 ? 0 : sourceCharacters[cursor].index!;
    cursor += count;
    const to = cursor < sourceCharacters.length ? sourceCharacters[cursor].index! : narration.length;
    const segment = narration.slice(from, to);
    if (!text) start = boundary.start_ms;
    text += segment;
    if (/[。！？.!?；;][^\p{L}\p{N}]*$/u.test(segment)) {
      groups.push({ text, start });
      text = '';
    }
  }
  if (text) groups.push({ text, start });
  let active = '';
  for (const group of groups) {
    if (group.start > timeMs) break;
    active = group.text;
  }
  return active;
}
