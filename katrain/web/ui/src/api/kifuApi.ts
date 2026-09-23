// API functions for kifu album (tournament game records) module

import type { KifuAlbumListResponse, KifuAlbumDetail } from '../types/kifu';
import { ApiError } from '../api';

const API_BASE = '/api/v1/kifu';

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    // 带上 `status`:board 模式下棋谱库连不上云端是 **503**,屏上要说「要联网」而不是「没搜到」。
    // 消息格式不变(`Request failed <status>: <body>`),按文本断言的既有测试照旧。
    throw new ApiError(response.status, `Request failed ${response.status}: ${body}`);
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
