// API functions for tsumego progress (shared zone — consumed by both kiosk and galaxy)
//
// Mirrors the inline fetch used by the galaxy tsumego pages:
//   GET  /api/v1/tsumego/progress           -> Record<problem_id, TsumegoProgressEntry>
//   POST /api/v1/tsumego/progress/{id}       -> upsert one problem's progress
// Both require an Authorization: Bearer <token> header (progress is account-scoped).

import { apiPost } from '../api';

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
  getProgress: async (token: string): Promise<Record<string, TsumegoProgressEntry>> => {
    const response = await fetch('/api/v1/tsumego/progress', {
      headers: { Authorization: `Bearer ${token}` },
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
    token: string,
  ): Promise<unknown> => apiPost(`/api/v1/tsumego/progress/${id}`, data, token),
};
