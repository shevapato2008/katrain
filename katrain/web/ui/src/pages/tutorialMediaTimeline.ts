import type { SGFPayload } from '../components/tutorials/SGFBoard';

export type Point = [number, number];
export interface Region { col: number; row: number; cols: number; rows: number }
export interface RecorderPayload extends SGFPayload {
  unknown_stones?: { point: Point; color: null; evidence?: string }[];
  source_region?: (Region & { confirmed: boolean }) | null;
  replay?: { initial?: { known_region?: Region | null } | null } | null;
}
export interface ReplayFrame {
  step: number;
  payload: RecorderPayload;
  last: Point | null;
  captured?: Point[];
  currentMove?: { kind: string; color: string; point?: Point | null } | null;
  nextColor?: string;
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
  status: 'complete' | 'pending';
  reason?: string;
  cues: { step: number; at_ms: number }[];
}
export interface RecordingData {
  board_payload: RecorderPayload;
  frames: ReplayFrame[];
  speech_timing: SpeechTiming;
  step_cues: StepCues;
  render_mode: '2d' | '3d';
}

export function frameAtTime(data: RecordingData, timeMs: number): ReplayFrame {
  if (data.step_cues.status !== 'complete') {
    return { step: -1, payload: data.board_payload, last: null };
  }
  let step = 0;
  for (const cue of data.step_cues.cues) {
    if (cue.at_ms > timeMs) break;
    step = cue.step;
  }
  const frame = data.frames.find(item => item.step === step);
  if (!frame) throw new Error(`Missing validated replay frame ${step}`);
  return frame;
}

export function knownRegion(data: RecordingData): Region | null {
  if (data.step_cues.status === 'complete') return data.board_payload.replay?.initial?.known_region ?? null;
  const region = data.board_payload.source_region;
  return region?.confirmed ? { col: region.col, row: region.row, cols: region.cols, rows: region.rows } : null;
}

/** Sentence-sized captions retain the actual start time of their first boundary. */
export function subtitleAtTime(timing: SpeechTiming, timeMs: number): string {
  let text = '';
  let start = 0;
  const groups: { text: string; start: number }[] = [];
  for (const boundary of timing.boundaries) {
    if (!text) start = boundary.start_ms;
    text += boundary.text;
    if (/[。！？.!?；;]$/.test(boundary.text.trim()) || text.length >= 30) {
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
