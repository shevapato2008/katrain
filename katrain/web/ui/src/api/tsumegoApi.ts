// API functions for tsumego progress (shared zone — consumed by both kiosk and galaxy)
//
// Mirrors the inline fetch used by the galaxy tsumego pages:
//   GET  /api/v1/tsumego/progress           -> Record<problem_id, TsumegoProgressEntry>
//   POST /api/v1/tsumego/progress/{id}       -> upsert one problem's progress
// 两者都是 account-scoped。凭据由 `authHeaders()` 统一决定:普通部署用 Bearer,
// 出厂盒子(严格 box SSO)用 127.0.0.1 上的共享 cookie —— 那时 token 是 null。

import { apiPost, authHeaders } from '../api';
import type { DataAuthority } from './userGamesApi';

export interface TsumegoProgressEntry {
  completed: boolean;
  attempts: number;
  firstCompletedAt?: string;
  lastAttemptAt?: string;
  lastDuration?: number;
}

/**
 * 盒上 `GET /progress` 这一份是谁给的(T1 错题页;Codex 对抗审查第 2 轮 #2)。
 * 三档词同 `DataAuthority`(`userGamesApi.ts`)。响应体是「题号 → 进度」的 map、放不下 `authority` 字段 ⇒ 后端走响应头。
 * ⚠️ 后端 `katrain/web/api/v1/endpoints/tsumego.py` 的 `PROGRESS_AUTHORITY_HEADER` 写的是同一个字面量,改一边必须改另一边。
 */
export const PROGRESS_AUTHORITY_HEADER = 'X-Data-Authority';

/**
 * **只有这一档算降级。** 和 `DataAuthority` 那段「读不到就当不知道、退到最保守」不同,这里缺头**不**当降级:
 * 缺头的只会是服务端模式 / galaxy 打的云端 —— 它们自己就是权威;当成降级会让 galaxy 每一次读都算没读到。
 * 盒子的前端和后端同一次发布,盒上恒带这个头。
 */
const LOCAL_CACHE: DataAuthority = 'local_cache';

/** `getProgress` 的回答。 */
export interface TsumegoProgressAnswer {
  progress: Record<string, TsumegoProgressEntry>;
  /**
   * `true` = 盒子没拿到云端那份,`progress` 是本机缓存 —— 真的下界,但**不是**这个人的全部进度
   * (在线写成功不落本机缓存,常常是 `{}`)。调用方不许把它当「读到了」。
   */
  degraded: boolean;
}

export const TsumegoAPI = {
  /**
   * Fetch the logged-in user's progress map, and whether the box served its local cache
   * instead of the cloud's copy (`degraded`, see `PROGRESS_AUTHORITY_HEADER`). Throws on a non-OK response.
   */
  getProgress: async (token?: string): Promise<TsumegoProgressAnswer> => {
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
    // `headers?.`:单测里手搓的 fetch 替身常常没有 headers(`navigation.integration.test.tsx`),那也是「没带这个头」。
    const degraded = response.headers?.get(PROGRESS_AUTHORITY_HEADER) === LOCAL_CACHE;
    return { progress: await response.json(), degraded };
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
