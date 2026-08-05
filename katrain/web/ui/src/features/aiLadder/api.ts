import type { AiLadderReadyStatus, AiLadderStartPreferences, AiLadderStartResponse } from './types';

export class AiLadderApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'AiLadderApiError';
    this.status = status;
  }
}

const authHeaders = (token?: string): Record<string, string> =>
  token ? { Authorization: `Bearer ${token}` } : {};

const parseResponse = async <T,>(response: Response): Promise<T> => {
  if (response.ok) return response.json() as Promise<T>;
  let detail = `Request failed ${response.status}`;
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === 'string') detail = body.detail;
  } catch {
    // Keep the status-based fallback for non-JSON gateway errors.
  }
  throw new AiLadderApiError(response.status, detail);
};

export const getAiLadderStatus = async (token?: string, signal?: AbortSignal): Promise<AiLadderReadyStatus> =>
  parseResponse(await fetch('/api/v1/ai-ladder/status', {
    headers: authHeaders(token),
    credentials: 'same-origin',
    signal,
  }));

export const startAiLadderGame = async (
  preferences: AiLadderStartPreferences,
  token?: string,
): Promise<AiLadderStartResponse> =>
  parseResponse(await fetch('/api/v1/ai-ladder/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    credentials: 'same-origin',
    body: JSON.stringify(preferences),
  }));
