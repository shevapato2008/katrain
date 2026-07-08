// LED control API (UI-tolerant path). Coordinates are canonical (row=0 top,
// col=0 left) — sent straight through; the backend LUT maps to chain indices.
// Failures are surfaced via the return value but never thrown at the caller's
// expense of blocking the UI (callers treat the LED as advisory).

const API_BASE = '/api/v1/led';

// 'flash' = bright white, meant to BLINK (client-driven) — used for a wrong/extra stone whose LED
// sits occluded directly under it; the blink + max brightness leak around the stone's base.
export type LedColor = 'black' | 'white' | 'remove' | 'hint' | 'flash';

export interface LedResult {
  ok: boolean;
  connected: boolean;
  shown_at: number | null;
  errors: string[];
}

async function post(path: string, body?: unknown): Promise<LedResult> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`led${path} failed ${res.status}`);
  }
  return res.json();
}

export const LedAPI = {
  point: (p: { row: number; col: number; color: LedColor }): Promise<LedResult> => post('/point', p),
  points: (points: { row: number; col: number; color: LedColor }[]): Promise<LedResult> => post('/points', { points }),
  clear: (): Promise<LedResult> => post('/clear'),
  status: async (): Promise<{ connected: boolean }> => {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error(`led/status failed ${res.status}`);
    return res.json();
  },
};
