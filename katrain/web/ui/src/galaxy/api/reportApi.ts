import type { TopMove } from '../../types/live';

export interface ReportTaskSummary {
  id: number;
  user_game_id: string;
  status: string;
  report_type: string;
  total_moves: number;
  analyzed_moves: number;
  requested_visits: number;
}

export interface ReportTaskMove {
  id: number;
  task_id: number;
  move_number: number;
  status: string | null;
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
  top_moves: TopMove[] | null;
  ownership: number[][] | null;
  actual_move: string | null;
  actual_player: string | null;
  delta_score: number | null;
  delta_winrate: number | null;
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

export const ReportsAPI = {
  list: (token: string): Promise<ReportTaskSummary[]> => {
    return authFetch('/api/v1/reports/', token);
  },

  get: (token: string, taskId: number): Promise<ReportTaskSummary> => {
    return authFetch(`/api/v1/reports/${taskId}`, token);
  },

  create: (
    token: string,
    params: { user_game_id: string; report_type?: 'normal' | 'deep'; force?: boolean },
  ): Promise<ReportTaskSummary> => {
    return authFetch('/api/v1/reports/', token, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  getMoves: (token: string, taskId: number): Promise<ReportTaskMove[]> => {
    return authFetch(`/api/v1/reports/${taskId}/moves`, token);
  },
};
