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

export const GeometryAPI = {
  lock: async (): Promise<GeometryLockResult> => {
    const res = await fetch(`${API_BASE}/lock`, { method: 'POST' });
    if (!res.ok) throw new Error(`geometry/lock failed ${res.status}`);
    return res.json();
  },
  status: async (): Promise<{ locked: boolean; confidence?: number; out_size?: number }> => {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error(`geometry/status failed ${res.status}`);
    return res.json();
  },
};
