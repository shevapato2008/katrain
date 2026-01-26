// API functions for live broadcasting module

import type {
  MatchSummary,
  MatchDetail,
  MatchListResponse,
  UpcomingMatch,
  LiveStats,
  MoveAnalysis,
  Comment,
  CommentListResponse,
  CommentPollResponse,
} from '../types/live';

const API_BASE = '/api/v1/live';

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

async function apiPost<T>(path: string, payload?: any): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

async function apiPostAuth<T>(path: string, token: string, payload?: any): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

async function apiDeleteAuth<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const LiveAPI = {
  /**
   * Get list of matches (live + finished)
   */
  getMatches: (options?: {
    status?: 'live' | 'finished';
    source?: 'xingzhen' | 'weiqi_org';
    limit?: number;
  }): Promise<MatchListResponse> => {
    const params = new URLSearchParams();
    if (options?.status) params.set('status', options.status);
    if (options?.source) params.set('source', options.source);
    if (options?.limit) params.set('limit', options.limit.toString());
    const query = params.toString();
    return apiGet(`/matches${query ? `?${query}` : ''}`);
  },

  /**
   * Get featured match (most important live or latest finished)
   */
  getFeaturedMatch: (): Promise<{ match: MatchSummary | null }> => {
    return apiGet('/matches/featured');
  },

  /**
   * Get match details
   */
  getMatch: (matchId: string, fetchDetail = false): Promise<MatchDetail> => {
    const params = fetchDetail ? '?fetch_detail=true' : '';
    return apiGet(`/matches/${matchId}${params}`);
  },

  /**
   * Get match analysis data
   */
  getMatchAnalysis: (matchId: string, moveNumber?: number): Promise<{
    match_id: string;
    analyzed_moves: number[];
    analysis: Record<number, MoveAnalysis>;
  }> => {
    const params = moveNumber !== undefined ? `?move_number=${moveNumber}` : '';
    return apiGet(`/matches/${matchId}/analysis${params}`);
  },

  /**
   * Preload analysis for a match (call when entering match page)
   */
  preloadAnalysis: (matchId: string): Promise<{
    match_id: string;
    analyzed_moves: number[];
    total_moves: number;
    analysis: Record<number, MoveAnalysis>;
  }> => {
    return apiGet(`/matches/${matchId}/analysis/preload`);
  },

  /**
   * Get upcoming matches
   */
  getUpcoming: (limit = 20): Promise<{ matches: UpcomingMatch[] }> => {
    return apiGet(`/upcoming?limit=${limit}`);
  },

  /**
   * Get live service statistics
   */
  getStats: (): Promise<LiveStats> => {
    return apiGet('/stats');
  },

  /**
   * Force refresh match data from sources
   */
  refresh: (): Promise<{ status: string; stats: LiveStats }> => {
    return apiPost('/refresh');
  },

  /**
   * Request KataGo analysis for a match
   */
  requestAnalysis: (matchId: string, startMove = 0, endMove?: number): Promise<{
    status: string;
    match_id: string;
    start_move: number;
    end_move: number;
    queue_size: number;
  }> => {
    const params = new URLSearchParams();
    params.set('start_move', startMove.toString());
    if (endMove !== undefined) params.set('end_move', endMove.toString());
    return apiPost(`/matches/${matchId}/analyze?${params.toString()}`);
  },

  // ==================== Comment API ====================

  /**
   * Get comments for a match
   */
  getComments: (matchId: string, options?: {
    limit?: number;
    offset?: number;
  }): Promise<CommentListResponse> => {
    const params = new URLSearchParams();
    if (options?.limit) params.set('limit', options.limit.toString());
    if (options?.offset) params.set('offset', options.offset.toString());
    const query = params.toString();
    return apiGet(`/matches/${matchId}/comments${query ? `?${query}` : ''}`);
  },

  /**
   * Poll for new comments since a given ID
   */
  pollComments: (matchId: string, sinceId: number): Promise<CommentPollResponse> => {
    return apiGet(`/matches/${matchId}/comments/poll?since_id=${sinceId}`);
  },

  /**
   * Create a new comment (requires authentication)
   */
  createComment: (matchId: string, content: string, token: string): Promise<Comment> => {
    return apiPostAuth(`/matches/${matchId}/comments`, token, { content });
  },

  /**
   * Delete a comment (requires authentication, only owner can delete)
   */
  deleteComment: (commentId: number, token: string): Promise<{ status: string; message: string }> => {
    return apiDeleteAuth(`/comments/${commentId}`, token);
  },
};
