// API functions for tsumego progress (shared zone — consumed by both kiosk and galaxy)
//
// Mirrors the inline fetch used by the galaxy tsumego pages:
//   GET  /api/v1/tsumego/progress           -> Record<problem_id, TsumegoProgressEntry>
//   POST /api/v1/tsumego/progress/{id}       -> upsert one problem's progress
// 两者都是 account-scoped。凭据由 `authHeaders()` 统一决定:普通部署用 Bearer,
// 出厂盒子(严格 box SSO)用 127.0.0.1 上的共享 cookie —— 那时 token 是 null。

import { apiPost, authHeaders } from '../api';

export interface TsumegoProgressEntry {
  completed: boolean;
  attempts: number;
  firstCompletedAt?: string;
  lastAttemptAt?: string;
  lastDuration?: number;
}

export const TsumegoAPI = {
  /**
   * Fetch the logged-in user's full progress map from the server.
   * Returns {} on a non-OK response so callers can merge safely.
   */
  getProgress: async (token?: string): Promise<Record<string, TsumegoProgressEntry>> => {
    // ⚠️ **token 是可选的,不是「随便传不传」。** 出厂盒子里它恒为 null,身份走
    // 127.0.0.1 上的共享 cookie;后端 `resolve_http_token` 在严格模式下只认 cookie。
    // 写死 `Authorization: Bearer null` 或用 `if (token)` 把请求挡在前端,
    // 都会让盒子上的进度**永远不同步**(而本机开发看不出来)。`authHeaders` 两种都管。
    const response = await fetch('/api/v1/tsumego/progress', {
      headers: authHeaders(token),
    });
    if (!response.ok) {
      throw new Error(`Failed to get tsumego progress: ${response.status}`);
    }
    return response.json();
  },

  /**
   * Persist one problem's progress to the server (terminal write).
   * Offline handling is server-side (local write + sync queue) in board mode.
   */
  saveProgress: (
    id: string,
    data: { completed: boolean; attempts: number; lastDuration?: number },
    token?: string,
  ): Promise<unknown> => apiPost(`/api/v1/tsumego/progress/${id}`, data, token),
};
