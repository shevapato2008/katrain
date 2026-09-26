export type VisionMode = 'stones2' | 'led4';
export type ObservedState = { source: string | null; updated_at: string | null; error?: string | null };
export type VisionGeometry = ObservedState & {
  state: 'required' | 'ready' | 'stale'; revision: string | null; confidence: number | null;
};
export type VisionStatus = {
  enabled: boolean; local_only: true; observed_at: string; mode: VisionMode | null;
  camera: ObservedState & { state: 'unknown' | 'disconnected' | 'connecting' | 'connected' | 'occupied' | 'error'; device_id: number | null };
  led: ObservedState & { state: 'unknown' | 'disabled' | 'disconnected' | 'connected' | 'occupied' | 'error' };
  geometry: VisionGeometry;
  sgf: ObservedState & { state: 'none' | 'loaded'; game_id: string | null; total_steps: number; next_step: number | null };
  dataset: ObservedState & { state: 'none' | 'draft' | 'frozen'; id: string | null; count: number };
};
export type VisionStep = {
  kind: 'setup' | 'move' | 'pass' | 'clear'; move_index: number; property: string;
  row: number | null; col: number | null; color: 'B' | 'W' | null;
  removed: { row: number; col: number }[]; board_hash: string;
};
export type VisionImport = {
  game_id: string; sgf_sha256: string; total_steps: number; next_step: number | null;
  mode: VisionMode; steps: VisionStep[];
};
export type VisionFrame = {
  frame_id: string; file: string; sha256: string; mode: VisionMode;
  applied_move_index: number; next_guided_move_index: number | null;
  geometry_revision: string; geometry_source: string; captured_at: string; camera_seq: number;
  led_point: { row: number; col: number; color: 'black' | 'white' } | null;
  idempotent?: boolean;
  capture_condition?: Record<string, unknown> & { camera_device_id?: number };
};
export type VisionSession = {
  state: 'draft' | 'captured'; game_id: string; mode: VisionMode; steps: VisionStep[];
  frames: VisionFrame[]; next_step: number | null; original_sgf?: string; sgf_sha256?: string;
  geometry_revision: string;
  camera_device_id?: number;
};
export type VisionSessionSummary = {
  game_id: string; state: 'draft' | 'captured' | 'error'; mode?: VisionMode;
  count?: number; total_steps?: number; next_step?: number | null; geometry_revision?: string; error?: string;
};
export type VisionSessionList = { sessions: VisionSessionSummary[]; limit: number; truncated: boolean };
export type VisionDevices = { candidates: { device_id: number; label: string; probed: false }[] };
export type VisionPreview = {
  frame_id: string; captured_at: string; captured_at_source: string; camera_seq: number;
  camera_monotonic_ts: number; geometry_revision: string | null;
  raw_jpeg_base64: string; warped_jpeg_base64: string | null; geometry_overlay_jpeg_base64: string | null;
};
export type VisionCaptureInput = {
  game_id: string; move_index: number; operator_confirmed: boolean; overwrite_existing: boolean;
  capture_condition?: Record<string, unknown>;
};
export type VisionSampleReview = {
  frame_id: string; source_sha256: string; geometry_revision: string; geometry_source: string;
  mode: VisionMode; class_names: string[]; boxes: { class_id: number; cx: number; cy: number; w: number; h: number }[];
  led_evidence: unknown; overlay_jpeg_base64: string; captured_at: string; camera_seq: number; applied_move_index: number;
};
export type VisionReviewFailure = { frame: VisionFrame; message: string };
export type VisionFreezeParameters = { val_fraction?: number; stone_frac?: number; led_frac?: number; margin_cells?: number };
export type VisionFrozen = {
  id: string; manifest_sha256: string; idempotent: boolean; mode: VisionMode; class_names: string[];
  samples: { frame_id: string; split: 'train' | 'val'; [key: string]: unknown }[];
  parameters: VisionFreezeParameters; [key: string]: unknown;
};
