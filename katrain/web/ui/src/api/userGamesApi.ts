/**
 * API client for personal game library (user_games) and analysis data.
 * 认证：有 JWT 就打 Authorization 头；严格盒端 SSO 里没有 JWT，靠同源 HttpOnly
 * cookie，所以每个方法的 `token` 都允许为 `null`（见下方 authFetch 的说明）。
 */

const API_BASE = '/api/v1/user-games';

export interface UserGameSummary {
  id: string;
  user_id: number;
  title: string | null;
  player_black: string | null;
  player_white: string | null;
  black_rank: string | null;
  white_rank: string | null;
  result: string | null;
  board_size: number;
  rules: string;
  komi: number;
  move_count: number;
  source: string;
  category: string;
  game_type: string | null;
  event: string | null;
  round_name: string | null;
  game_date: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserGameDetail extends UserGameSummary {
  sgf_content: string;
}

/**
 * **这个数是谁数的。**
 *
 * `this_node`   —— 这台机器就是权威(普通服务端 / 本机跑的 web UI),数是全的。
 * `cloud`       —— 盒子在线,列表和 `total` 来自云端,**跨设备完整**。
 * `local_cache` —— 盒子拿不到云端,这是本机那一份,**可能偏小**。
 *
 * 三档和 `growth/summary` 的 `authority` 同名同义 —— 一个概念只许有一套词。
 * ⚠️ 老服务端不带这一格,所以是**选填**:读不到就当「不知道」,而「不知道」
 * 在屏上必须退到最保守的那句话,不许当成 `cloud`。
 */
export type DataAuthority = 'this_node' | 'cloud' | 'local_cache';

export interface UserGameListResponse {
  items: UserGameSummary[];
  total: number;
  page: number;
  page_size: number;
  authority?: DataAuthority;
}

export interface MoveAnalysis {
  id: number;
  game_id: string;
  move_number: number;
  status: string | null;
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
  top_moves: unknown | null;
  ownership: number[][] | null;
  move: string | null;
  actual_player: string | null;
  delta_score: number | null;
  delta_winrate: number | null;
  is_brilliant: boolean;
  is_mistake: boolean;
  is_questionable: boolean;
}

export interface CreateUserGameParams {
  sgf_content: string;
  source: string;
  title?: string;
  player_black?: string;
  player_white?: string;
  black_rank?: string;
  white_rank?: string;
  result?: string;
  board_size?: number;
  rules?: string;
  komi?: number;
  move_count?: number;
  category?: string;
  game_type?: string;
  event?: string;
  round_name?: string;
  game_date?: string;
}

/**
 * **凭据可以是 `null`，那不代表没登录。**
 *
 * 严格盒端 SSO(`VITE_BOX_SSO_STRICT`)里 JS 永远拿不到 token —— 身份在 HttpOnly
 * `sb_go_token` cookie 里，同源请求由浏览器自动带上。所以这里只在**真有** token 时
 * 才打 Authorization 头，没有就把认证交给 cookie。
 *
 * ⚠️ 「该不该发这个请求」是调用方按 `isAuthenticated` 判的，**不是按有没有 token**。
 * 拿 `!token` 当「未登录」用，在盒子上等于把每一个已登录用户都当成未登录
 * (实测：复盘列表因此恒显示「本机 0 局」，而接口本身 200、云端有 21 局)。
 */
async function authFetch<T>(path: string, token: string | null | undefined, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    // `status` / `body` 挂在错误上,给 `utils/requestFailure.ts` 分「连不上 / 找不到 / 积分不足」;
    // message 保持原句 —— galaxy 屏上与既有单测都认这一句。
    throw Object.assign(new Error(`Request failed ${response.status}: ${body}`), { status: response.status, body });
  }
  return response.json();
}

export const UserGamesAPI = {
  list: (
    token: string | null | undefined,
    options?: {
      page?: number;
      page_size?: number;
      category?: string;
      source?: string;
      sort?: string;
      q?: string;
    },
  ): Promise<UserGameListResponse> => {
    const params = new URLSearchParams();
    if (options?.page) params.set('page', String(options.page));
    if (options?.page_size) params.set('page_size', String(options.page_size));
    if (options?.category) params.set('category', options.category);
    if (options?.source) params.set('source', options.source);
    if (options?.sort) params.set('sort', options.sort);
    if (options?.q) params.set('q', options.q);
    const query = params.toString();
    return authFetch(`${API_BASE}/${query ? `?${query}` : ''}`, token);
  },

  get: (token: string | null | undefined, gameId: string): Promise<UserGameDetail> => {
    return authFetch(`${API_BASE}/${gameId}`, token);
  },

  create: (token: string | null | undefined, params: CreateUserGameParams): Promise<UserGameDetail> => {
    return authFetch(`${API_BASE}/`, token, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  update: (
    token: string | null | undefined,
    gameId: string,
    params: Partial<{
      title: string;
      sgf_content: string;
      player_black: string;
      player_white: string;
      result: string;
      move_count: number;
      updated_at: string;
    }>,
  ): Promise<UserGameDetail> => {
    return authFetch(`${API_BASE}/${gameId}`, token, {
      method: 'PUT',
      body: JSON.stringify(params),
    });
  },

  delete: (token: string | null | undefined, gameId: string): Promise<{ status: string }> => {
    return authFetch(`${API_BASE}/${gameId}`, token, {
      method: 'DELETE',
    });
  },

  getAnalysis: (
    token: string | null | undefined,
    gameId: string,
    startMove?: number,
    limit?: number,
  ): Promise<MoveAnalysis[]> => {
    const params = new URLSearchParams();
    if (startMove !== undefined) params.set('start_move', String(startMove));
    if (limit !== undefined) params.set('limit', String(limit));
    const query = params.toString();
    return authFetch(`${API_BASE}/${gameId}/analysis${query ? `?${query}` : ''}`, token);
  },

  getMoveAnalysis: (token: string | null | undefined, gameId: string, moveNumber: number): Promise<MoveAnalysis> => {
    return authFetch(`${API_BASE}/${gameId}/analysis/${moveNumber}`, token);
  },

  saveAnalysisFromSession: (
    token: string | null | undefined,
    gameId: string,
    sessionId: string,
  ): Promise<{ game_id: string; saved_moves: number; total_moves: number }> => {
    return authFetch(`${API_BASE}/${gameId}/analysis/save`, token, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, game_id: gameId }),
    });
  },
};
