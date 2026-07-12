// Shared (both builds) minimal load-only client for the personal game library
// (user_games). Auth-required, so every call takes a token. Kiosk must NOT import
// galaxy/api/userGamesApi.ts (SBC boundary); this lives in shared src/api/ like kifuApi.ts.

export interface UserGameSummary {
  id: string;
  source: string;
  player_black: string | null;
  player_white: string | null;
  result: string | null;
  move_count: number;
  board_size: number;
  game_type: string | null;
  game_date: string | null;
  created_at: string;
}

export interface UserGameListResponse {
  items: UserGameSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserGameDetail extends UserGameSummary {
  sgf_content: string;
  komi: number;
  rules: string;
}

async function authGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`user-games ${res.status}`);
  return res.json() as Promise<T>;
}

export const UserGamesAPI = {
  list: (token: string, params: { page?: number; page_size?: number; source?: string; q?: string } = {}): Promise<UserGameListResponse> => {
    const qs = new URLSearchParams();
    qs.set('page', String(params.page ?? 1));
    qs.set('page_size', String(params.page_size ?? 20));
    if (params.source) qs.set('source', params.source);
    if (params.q) qs.set('q', params.q);
    return authGet<UserGameListResponse>(`/api/v1/user-games/?${qs.toString()}`, token);
  },
  get: (token: string, gameId: string): Promise<UserGameDetail> =>
    authGet<UserGameDetail>(`/api/v1/user-games/${gameId}`, token),
};
