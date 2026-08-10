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

const isGameLifecycle = (
  value: unknown,
  gameId: string,
): value is AiLadderGameLifecycle => {
  if (!isRecord(value) || value.game_id !== gameId) {
    return false;
  }
  if (value.state === 'active' || value.state === 'pending_settlement') return true;
  // 释放没有 receipt,所以它走不到下面那条要求 receipt 的路。`counted` 必须是假:
  // 一个说自己计了分的释放是个矛盾的响应,放它过去等于让界面替后端编一个结果。
  if (value.state === 'released') return value.counted === false;
  // 释放没有 receipt,所以它走不到下面那条要求 receipt 的路。`counted` 必须是假:
  // 一个说自己计了分的释放是个矛盾的响应,放它过去等于让界面替后端编一个结果。
  if (value.state !== 'settled' || !isRecord(value.receipt)) return false;
  const { counted, reason } = value.receipt;
  return typeof counted === 'boolean'
    && (reason === null
      || (typeof reason === 'string' && aiLadderCountingReasons.includes(reason as AiLadderCountingReason)));
};

const createApiError = async (response: Response): Promise<AiLadderApiError> => {
  let detail = `Request failed ${response.status}`;
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === 'string') detail = body.detail;
  } catch {
    // Keep the status-based fallback for non-JSON gateway errors.
  }
  return new AiLadderApiError(response.status, detail);
};

const parseResponse = async <T,>(response: Response): Promise<T> => {
  if (response.ok) return response.json() as Promise<T>;
  throw await createApiError(response);
};

const parseGameLifecycleResponse = async (
  response: Response,
  gameId: string,
  allowActive = false,
): Promise<AiLadderGameLifecycle> => {
  if (response.ok || response.status === 409) {
    try {
      const lifecycle: unknown = await response.clone().json();
      if (isGameLifecycle(lifecycle, gameId) && (allowActive || lifecycle.state !== 'active')) return lifecycle;
    } catch {
      // Invalid lifecycle responses use the same API error mapping as other failures.
    }
  }
  throw await createApiError(response);
};

export const getAiLadderGameStatus = async (
  gameId: string,
  token?: string,
  signal?: AbortSignal,
): Promise<AiLadderGameLifecycle> => parseGameLifecycleResponse(await fetch(
  `/api/v1/ai-ladder/games/${encodeURIComponent(gameId)}/status`,
  { headers: authHeaders(token), credentials: 'same-origin', signal },
), gameId, true);

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
  return parseGameLifecycleResponse(response, gameId);
};
