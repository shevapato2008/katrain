/** Account-owned immutable SGF snapshots and optimistic cursor writes. */
export type HistoryAuthority = 'cloud' | 'local_cache' | 'this_node';
export type HistorySyncState = 'synced' | 'pending' | 'conflict' | 'refused';
export interface BaipuHistorySummary {
  id: string; source_id: string; name: string; sgf_sha256: string; replay_version: number;
  k: number; total: number; completed: boolean; local_revision: number; cloud_revision: number;
  updated_at: string; completed_at: string | null; authority: HistoryAuthority; sync_state: HistorySyncState;
}
export interface BaipuHistoryDetail extends BaipuHistorySummary {
  sgf_content: string;
  conflict_remote?: { k: number; total: number; updated_at: string; cloud_revision: number } | null;
}
export interface HistoryCredentials { identityKey: string; token: string | null; signal?: AbortSignal }
export class BaipuHistoryError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly current: BaipuHistoryDetail | null;
  constructor(status: number, detail: unknown) {
    const value = typeof detail === 'object' && detail !== null ? detail as Record<string, unknown> : null;
    super(typeof detail === 'string' ? detail : typeof value?.message === 'string' ? value.message : `History request failed (${status})`);
    this.status = status;
    this.code = typeof value?.code === 'string' ? value.code : null;
    this.current = (value?.current ?? null) as BaipuHistoryDetail | null;
  }
}
const BASE = '/api/v1/baipu/history';
async function request<T>(path: string, credentials: HistoryCredentials, method = 'GET', body?: unknown): Promise<T> {
  if (!credentials.identityKey) throw new Error('Resolved account identity required');
  const controller = new AbortController();
  const abort = () => controller.abort();
  credentials.signal?.addEventListener('abort', abort, { once: true });
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new Error('History request timed out')); }, 10000);
  });
  const headers: Record<string, string> = { 'X-Katrain-Expected-Identity': credentials.identityKey };
  if (credentials.token) headers.Authorization = `Bearer ${credentials.token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  try {
    if (credentials.signal?.aborted) controller.abort();
    const work = async () => {
      const response = await fetch(`${BASE}${path}`, {
        method, headers, credentials: 'same-origin', signal: controller.signal,
        ...(body === undefined ? {} : { body: JSON.stringify(body), keepalive: method === 'PUT' }),
      });
      const result = await response.json();
      if (!response.ok) throw new BaipuHistoryError(response.status, result?.detail);
      if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
      return result as T;
    };
    return await Promise.race([work(), deadline]);
  } finally {
    clearTimeout(timer);
    credentials.signal?.removeEventListener('abort', abort);
  }
}
const recordPath = (id: string) => {
  if (!/^[a-f0-9]{64}$/.test(id)) throw new Error('Invalid history identifier');
  return `/${id}`;
};
export const BaipuHistoryAPI = {
  list: (credentials: HistoryCredentials) => request<{ items: BaipuHistorySummary[]; authority: HistoryAuthority }>('?limit=30', credentials),
  get: (id: string, credentials: HistoryCredentials) => request<BaipuHistoryDetail>(recordPath(id), credentials),
  open: (data: { sgf_content: string; source_id: string; name: string }, credentials: HistoryCredentials) => request<BaipuHistoryDetail>('/open', credentials, 'POST', data),
  save: (id: string, data: { k: number; expected_local_revision: number; mutation_id: string }, credentials: HistoryCredentials) => request<BaipuHistoryDetail>(recordPath(id), credentials, 'PUT', data),
  resolve: (id: string, data: { strategy: 'use_cloud' | 'keep_local'; expected_local_revision: number }, credentials: HistoryCredentials) => request<BaipuHistoryDetail>(`${recordPath(id)}/resolve`, credentials, 'POST', data),
};
