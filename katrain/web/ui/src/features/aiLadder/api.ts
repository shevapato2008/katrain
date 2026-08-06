import type {
  AiLadderCountingReason,
  AiLadderGameLifecycle,
  AiLadderReadyStatus,
  AiLadderSettlementReceipt,
  AiLadderStartPreferences,
  AiLadderStartResponse,
} from './types';

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

const aiLadderCountingReasons: readonly AiLadderCountingReason[] = [
  'invalid_game_type',
  'engine_unavailable',
  'inconclusive',
  'opponent_not_eligible',
  'opponent_rung_mismatch',
];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const isSettledLifecycle = (
  value: unknown,
  gameId: string,
): value is Extract<AiLadderGameLifecycle, { state: 'settled' }> => {
  if (!isRecord(value) || value.state !== 'settled' || value.game_id !== gameId || !isRecord(value.receipt)) {
    return false;
  }
  const { counted, reason } = value.receipt;
  return typeof counted === 'boolean'
    && (reason === null
      || (typeof reason === 'string' && aiLadderCountingReasons.includes(reason as AiLadderCountingReason)));
};

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

export const getAiLadderSettlementReceipt = async (
  gameId: string,
  token?: string,
  signal?: AbortSignal,
): Promise<AiLadderSettlementReceipt> =>
  parseResponse(await fetch(`/api/v1/ai-ladder/settlements/${encodeURIComponent(gameId)}`, {
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

export const endAiLadderGame = async (
  gameId: string,
  token?: string,
): Promise<AiLadderGameLifecycle> => {
  const response = await fetch(`/api/v1/ai-ladder/games/${encodeURIComponent(gameId)}/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    credentials: 'same-origin',
    body: JSON.stringify({ reason: 'user_resigned' }),
  });
  if (response.status === 409) {
    try {
      const lifecycle: unknown = await response.clone().json();
      if (isSettledLifecycle(lifecycle, gameId)) return lifecycle;
    } catch {
      // Let the shared parser preserve the normal error mapping for invalid responses.
    }
  }
  return parseResponse(response);
};
