import type { TopMove } from '../types/live';

export type ReportType = 'normal' | 'deep';
export type KnownReportStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ReportStatus = KnownReportStatus | (string & Record<never, never>);

export const isActiveReportStatus = (status: string): status is 'pending' | 'running' =>
  status === 'pending' || status === 'running';

export const isTerminalReportStatus = (status: string): status is 'completed' | 'failed' =>
  status === 'completed' || status === 'failed';

export interface ReportQueueSummary {
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

export interface ReportTaskSummary {
  id: number;
  user_game_id: string;
  status: ReportStatus;
  report_type: ReportType;
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
  // 着手评价（服务端算好；阈值真源是 katrain/core/move_grade.yaml）。
  // grade 为 null / "unrated" = 这手没有被评级，前端要显示成「未评级」而不是「没问题」。
  grade: string | null;
  points_lost: number | null;
  points_lost_source: string | null;
  is_top_move: boolean | null;
  top_prior: number | null;
  brilliance: number | null;
  root_visits: number | null;
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

  summary: (token: string): Promise<ReportQueueSummary> => {
    return authFetch('/api/v1/reports/summary', token);
  },

  get: (token: string, taskId: number): Promise<ReportTaskSummary> => {
    return authFetch(`/api/v1/reports/${taskId}`, token);
  },

  create: (
    token: string,
    params: { user_game_id: string; report_type?: ReportType; force?: boolean },
  ): Promise<ReportTaskSummary> => {
    return authFetch('/api/v1/reports/', token, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  retry: (token: string, taskId: number): Promise<ReportTaskSummary> => {
    return authFetch(`/api/v1/reports/${taskId}/retry`, token, { method: 'POST' });
  },

  getMoves: (token: string, taskId: number): Promise<ReportTaskMove[]> => {
    return authFetch(`/api/v1/reports/${taskId}/moves`, token);
  },
};
