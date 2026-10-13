export type TrainingRunState = 'starting' | 'running' | 'cancelling' | 'interrupted' | 'failed' | 'completed' | 'cancelled';
export type TrainingState = 'unknown' | 'idle' | 'busy' | TrainingRunState;
export type TrainingParameters = { epochs: number; batch: number; imgsz: number; seed: number };
export type TrainingActualParameters = TrainingParameters & { device: string; amp: boolean; plots: boolean; workers: number };
export type TrainingMetrics = { map50: number | null; precision: number | null; recall: number | null };
export type TrainingStatus = { enabled: boolean; state: TrainingState; reason: string | null; observed_at: string; active_run_id: string | null; gpu_ids: string[] };
export type TrainingDataset = { id: string; manifest_sha256: string; mode: 'stones2' | 'led4'; class_names: string[]; train_count: number; val_count: number };
export type TrainingPresets = { weights: { id: string; sha256: string }[]; augmentations: { id: 'stones-standard' | 'led-safe'; mode: 'stones2' | 'led4' }[]; limits: { epochs: [number, number]; batch: number[]; imgsz: number[]; seed: [number, number] } };
export type TrainingRun = {
  id: string; state: TrainingRunState; created_at: string; started_at: string | null; ended_at: string | null; observed_at: string;
  dataset_id: string; dataset_manifest_sha256: string; weights_id: string; augmentation: string; mode: 'stones2' | 'led4'; class_names: string[];
  parameters: TrainingActualParameters; epoch: number; total_epochs: number; metrics: TrainingMetrics; log_tail: string; error: string | null; model_id: string | null;
};
export type TrainingModel = { id: string; run_id: string; dataset_id: string; dataset_manifest_sha256: string; mode: 'stones2' | 'led4'; class_names: string[]; weights_sha256: string; weights_bytes: number; manifest_sha256: string; parameters: TrainingActualParameters; created_at: string };
export type TrainingStartInput = TrainingParameters & { request_id: string; dataset_id: string; dataset_manifest_sha256: string; weights_id: string; augmentation: 'stones-standard' | 'led-safe'; gpu_id: string; confirmed: true };
