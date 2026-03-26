/**
 * API client for personal game library (user_games) and analysis data.
 * Requires JWT auth token for all requests.
 */

const API_BASE = '/api/v1/user-games';

export interface UserGameSummary {
  id: string;
  user_id: number;
  title: string | null;
  player_black: string | null;
  player_white: string | null;
  result: string | null;
  board_size: number;
  rules: string;
  komi: number;
  move_count: number;
  source: string;
  category: string;
  game_type: string | null;
  event: string | null;
  game_date: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserGameDetail extends UserGameSummary {
  sgf_content: string;
}

export interface UserGameListResponse {
  items: UserGameSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface MoveAnalysis {
  id: number;
  game_id: string;
  move_number: number;
  status: string | null;
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
  top_moves: any | null;
  ownership: any | null;
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
  result?: string;
  board_size?: number;
  rules?: string;
  komi?: number;
  move_count?: number;
  category?: string;
  game_type?: string;
  event?: string;
  game_date?: string;
}

async function authFetch<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options?.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const UserGamesAPI = {
  list: (
    token: string,
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

  get: (token: string, gameId: string): Promise<UserGameDetail> => {
    return authFetch(`${API_BASE}/${gameId}`, token);
  },

  create: (token: string, params: CreateUserGameParams): Promise<UserGameDetail> => {
    return authFetch(`${API_BASE}/`, token, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  update: (
    token: string,
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

  delete: (token: string, gameId: string): Promise<{ status: string }> => {
    return authFetch(`${API_BASE}/${gameId}`, token, {
      method: 'DELETE',
    });
  },

  getAnalysis: (
    token: string,
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

  getMoveAnalysis: (token: string, gameId: string, moveNumber: number): Promise<MoveAnalysis> => {
    return authFetch(`${API_BASE}/${gameId}/analysis/${moveNumber}`, token);
  },

  saveAnalysisFromSession: (
    token: string,
    gameId: string,
    sessionId: string,
  ): Promise<{ game_id: string; saved_moves: number; total_moves: number }> => {
    return authFetch(`${API_BASE}/${gameId}/analysis/save`, token, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, game_id: gameId }),
    });
  },
};
