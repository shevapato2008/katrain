// Geometry lock API (empty-board zero-touch calibration). Used by the setup page
// to lock the board geometry that 摆谱 capture + QA depend on.

const API_BASE = '/api/v1/geometry';

export interface GeometryLockResult {
  ok: boolean;
  reason?: string;
  confidence?: number;
  nmatch?: number;
  empty_self_check?: { black: number; white: number };
  led_cleared?: boolean;
}

export type GeometryPhase =
  | 'disabled' | 'required' | 'waiting_empty' | 'dark_reference'
  | 'flashing_corners' | 'verifying' | 'building_baseline'
  | 'ready' | 'degraded' | 'failed' | 'cancelled';

export interface GeometryPoint {
  row: number;
  col: number;
  x: number;
  y: number;
}

export interface GeometryAnchor extends GeometryPoint {
  color: string;
}

export interface GeometryCorner extends GeometryPoint {
  label: string;
}

export interface GeometryLayout {
  revision: number;
  phase: GeometryPhase;
  stale: boolean;
  frame: { width: number; height: number };
  out_size: number;
  corners: GeometryCorner[];
  points: [number, number][][];
}

export interface GeometryStatus {
  phase: GeometryPhase;
  session_calibrated: boolean;
  last_valid: boolean;
  progress?: { current: number; total: number };
  error?: string | null;
  metrics?: Record<string, number | null>;
  geometry_revision?: number;
  detected_anchors?: GeometryAnchor[];
  capabilities: {
    camera_ready: boolean;
    led_ready: boolean;
    geometry_ready: boolean;
    recognition_ready?: boolean;
    model_ready?: boolean;
  };
}

const json = async <T>(res: Response): Promise<T> => {
  if (!res.ok) throw new Error(`geometry request failed ${res.status}`);
  return res.json();
};

export const GeometryAPI = {
  lock: async (): Promise<GeometryLockResult> => {
    const res = await fetch(`${API_BASE}/lock`, { method: 'POST' });
    if (!res.ok) throw new Error(`geometry/lock failed ${res.status}`);
    return res.json();
  },
  status: async (): Promise<GeometryStatus> => {
    const res = await fetch(`${API_BASE}/status`);
    const data = await json<GeometryStatus & { locked?: boolean }>(res);
    if (data.phase) return data;
    return {
      phase: 'disabled',
      session_calibrated: false,
      last_valid: Boolean(data.locked),
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
    };
  },
  calibrate: async (trigger: 'auto' | 'manual'): Promise<GeometryStatus> => json(await fetch(`${API_BASE}/calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trigger, empty_confirmed: true }),
  })),
  cancel: async (): Promise<GeometryStatus> => json(await fetch(`${API_BASE}/cancel`, { method: 'POST' })),
  layout: async (): Promise<GeometryLayout> => json(await fetch(`${API_BASE}/layout`)),
};
