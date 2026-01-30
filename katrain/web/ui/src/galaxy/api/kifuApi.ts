// API functions for kifu album (tournament game records) module

import type { KifuAlbumListResponse, KifuAlbumDetail } from '../types/kifu';

const API_BASE = '/api/v1/kifu';

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const KifuAPI = {
  getAlbums: (options?: { q?: string; page?: number; page_size?: number }): Promise<KifuAlbumListResponse> => {
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.page) params.set('page', String(options.page));
    if (options?.page_size) params.set('page_size', String(options.page_size));
    const query = params.toString();
    return apiGet(`/albums${query ? `?${query}` : ''}`);
  },

  getAlbum: (id: number): Promise<KifuAlbumDetail> => {
    return apiGet(`/albums/${id}`);
  },
};
