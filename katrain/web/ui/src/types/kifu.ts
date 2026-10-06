// Types for kifu album (tournament game records) module

export interface KifuAlbumSummary {
  id: number;
  player_black: string;
  player_white: string;
  black_rank: string | null;
  white_rank: string | null;
  event: string | null;
  result: string | null;
  rules: string | null;
  date_played: string | null;
  komi: number | null;
  handicap: number;
  board_size: number;
  round_name: string | null;
  move_count: number;
  display_player_black?: string | null;
  display_player_white?: string | null;
  display_black_rank?: string | null;
  display_white_rank?: string | null;
  display_event?: string | null;
  display_round_name?: string | null;
  sources?: string[];
  has_analysis?: boolean;
}

export interface KifuAlbumDetail extends KifuAlbumSummary {
  place: string | null;
  source: string | null;
  sgf_content: string;
}

export interface KifuAlbumListResponse {
  items: KifuAlbumSummary[];
  total: number;
  page: number;
  page_size: number;
  preview?: KifuAlbumDetail | null;
}

/** Analysis belongs to the canonical professional game, independently of user reports. */
export interface KifuAnalysisMove {
  move_number: number;
  actual_move: string | null;
  actual_player: string | null;
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
  root_visits: number | null;
  top_moves: import('./live').TopMove[] | null;
  ownership: number[][] | null;
  delta_score: number | null;
  delta_winrate: number | null;
  grade: string | null;
  points_lost: number | null;
  points_lost_source: string | null;
  is_top_move: boolean | null;
  top_prior: number | null;
  brilliance: number | null;
}

export interface VerifiedAnalysisParameters {
  version: 1 | 2;
  verified: true;
  rules: string;
  komi: number;
  sgf_sha256: string;
  parameter_sha256: string;
  provenance: Record<string, unknown>;
}

export interface KifuAnalysisDetail {
  album_id: number;
  canonical_album_id: number;
  sgf_sha256: string;
  model_sha256: string;
  requested_visits: number;
  status: 'unavailable' | 'pending' | 'running' | 'completed' | 'failed' | 'rules_unresolved';
  analysis_parameters: VerifiedAnalysisParameters | null;
  parameters_verified: boolean;
  parameter_error: { code: string; message: string } | null;
  total_moves: number;
  analyzed_moves: number;
  error_message: string | null;
  moves: KifuAnalysisMove[];
}
