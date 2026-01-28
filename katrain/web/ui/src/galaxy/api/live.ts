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
import { i18n } from '../../i18n';

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
   * Automatically includes current UI language for server-side translation
   */
  getMatches: (options?: {
    status?: 'live' | 'finished';
    source?: 'xingzhen' | 'weiqi_org';
    limit?: number;
    lang?: string;
  }): Promise<MatchListResponse> => {
    const params = new URLSearchParams();
    if (options?.status) params.set('status', options.status);
    if (options?.source) params.set('source', options.source);
    if (options?.limit) params.set('limit', options.limit.toString());
    // Add language for server-side translation of player/tournament names
    const lang = options?.lang || i18n.lang;
    if (lang) params.set('lang', lang);
    const query = params.toString();
    return apiGet(`/matches${query ? `?${query}` : ''}`);
  },

  /**
   * Get featured match (most important live or latest finished)
   * Automatically includes current UI language for server-side translation
   */
  getFeaturedMatch: (lang?: string): Promise<{ match: MatchSummary | null }> => {
    const effectiveLang = lang || i18n.lang;
    const params = effectiveLang ? `?lang=${effectiveLang}` : '';
    return apiGet(`/matches/featured${params}`);
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
   * Automatically includes current UI language for server-side translation
   */
  getUpcoming: (limit = 20, lang?: string): Promise<{ matches: UpcomingMatch[] }> => {
    const params = new URLSearchParams();
    params.set('limit', limit.toString());
    // Add language for server-side translation of player/tournament names
    const effectiveLang = lang || i18n.lang;
    if (effectiveLang) params.set('lang', effectiveLang);
    return apiGet(`/upcoming?${params.toString()}`);
  },

  /**
   * Get live service statistics
   */
  getStats: (): Promise<LiveStats> => {
    return apiGet('/stats');
  },

  /**
   * Get live-specific translations for player names, tournament names, etc.
   */
  getTranslations: (lang: string): Promise<{
    lang: string;
    players: Record<string, string>;
    tournaments: Record<string, string>;
    rounds: Record<string, string>;
    rules: Record<string, string>;
  }> => {
    return apiGet(`/translations?lang=${lang}`);
  },

  /**
   * Force refresh match data from sources
   */
  refresh: (): Promise<{ status: string; stats: LiveStats }> => {
    return apiPost('/refresh');
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
