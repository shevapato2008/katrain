// Types for live broadcasting module

export type MatchSource = 'xingzhen' | 'weiqi_org';
export type MatchStatus = 'live' | 'finished';

export interface MatchSummary {
  id: string;
  source: MatchSource;
  tournament: string;
  round_name: string | null;
  date: string;
  player_black: string;
  player_white: string;
  black_rank: string | null;
  white_rank: string | null;
  status: MatchStatus;
  result: string | null;
  move_count: number;
  current_winrate: number;
  current_score: number;
  last_updated: string;
  // Game rules
  board_size: number;
  komi: number;
  rules: string;  // "chinese" | "japanese" | "korean" etc.
}

export interface MatchDetail extends MatchSummary {
  sgf: string | null;
  moves: string[];
}

export interface MatchListResponse {
  matches: MatchSummary[];
  total: number;
  live_count: number;
}

export interface UpcomingMatch {
  id: string;
  tournament: string;
  round_name: string | null;
  scheduled_time: string;
  player_black: string | null;
  player_white: string | null;
  source_url: string | null;
}

export interface LiveStats {
  live_count: number;
  finished_count: number;
  upcoming_count: number;
  featured_id: string | null;
  last_list_update: string | null;
  last_cleanup: string | null;
}

export interface TopMove {
  move: string;
  visits: number;
  winrate: number;
  score_lead: number;
  prior: number;
  pv: string[];
  psv: number;  // playSelectionValue - KataGo's composite ranking metric
}

export interface MoveAnalysis {
  match_id: string;
  move_number: number;
  move: string | null;
  player: string | null;
  winrate: number;
  score_lead: number;
  top_moves: TopMove[];
  ownership: number[][] | null; // 2D grid of ownership values (-1 to 1, positive=Black)
  is_brilliant: boolean;
  is_mistake: boolean;
  is_questionable: boolean;
  delta_score: number;
  delta_winrate: number;
}

// Comment types
export interface Comment {
  id: number;
  match_id: string;
  user_id: number;
  username: string;
  content: string;
  created_at: string;
}

export interface CommentListResponse {
  comments: Comment[];
  total: number;
}

export interface CommentPollResponse {
  comments: Comment[];
  count: number;
}
