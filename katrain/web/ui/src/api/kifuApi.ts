// API functions for kifu album (tournament game records) module

import type { KifuAlbumListResponse, KifuAlbumDetail, KifuAnalysisDetail } from '../types/kifu';
import { ApiError } from '../api';

const API_BASE = '/api/v1/kifu';
const previews = new Map<string, { detail: KifuAlbumDetail; expires: number }>();
let latestListRequest = 0;
declare global {
  interface Window { __kifuListRequest?: { path: string; response: Promise<Response> }; }
}

async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  signal?.throwIfAborted();
  const url = `${API_BASE}${path}`;
  const initial = typeof window !== 'undefined' ? window.__kifuListRequest : undefined;
  if (initial?.path === url) delete window.__kifuListRequest;
  const response = initial?.path === url ? (await initial.response).clone() : await fetch(url, { signal });
  signal?.throwIfAborted();
  if (!response.ok) {
    const body = await response.text();
    signal?.throwIfAborted();
    let detail: unknown;
    try { detail = JSON.parse(body).detail; } catch { /* Keep non-JSON errors as they are. */ }
    throw new ApiError(response.status, `Request failed ${response.status}: ${body}`, detail);
  }
  const data = await response.json();
  signal?.throwIfAborted();
  return data;
}

export const KifuAPI = {
  getAlbums: async (options?: { q?: string; page?: number; page_size?: number; lang?: string; signal?: AbortSignal }): Promise<KifuAlbumListResponse> => {
    const request = ++latestListRequest;
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.page) params.set('page', String(options.page));
    if (options?.page_size) params.set('page_size', String(options.page_size));
    if (options?.lang) params.set('lang', options.lang);
    const query = params.toString();
    const data = await apiGet<KifuAlbumListResponse>(`/albums${query ? `?${query}` : ''}`, options?.signal);
    if (request === latestListRequest) {
      previews.clear();
      if (data.preview) {
        previews.set(`${data.preview.id}:${options?.lang ?? ''}`, { detail: data.preview, expires: Date.now() + 10000 });
      }
    }
    return data;
  },

  getAlbum: async (id: number, lang?: string, signal?: AbortSignal): Promise<KifuAlbumDetail> => {
    signal?.throwIfAborted();
    const cached = previews.get(`${id}:${lang ?? ''}`);
    if (cached && cached.expires > Date.now()) return cached.detail;
    return apiGet(`/albums/${id}${lang ? `?lang=${encodeURIComponent(lang)}` : ''}`, signal);
  },

  getAnalysis: (id: number): Promise<KifuAnalysisDetail> => apiGet(`/albums/${id}/analysis`),
};
