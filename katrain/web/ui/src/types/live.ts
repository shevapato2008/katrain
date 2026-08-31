// Types for live broadcasting module

export type MatchSource = 'xingzhen' | 'yike' | 'pandanet';
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

export type UpcomingSource = 'foxwq' | 'yike' | 'yugen' | 'nihonkiin';

export interface UpcomingMatch {
  id: string;
  tournament: string;
  round_name: string | null;
  scheduled_time: string;
  player_black: string | null;
  player_white: string | null;
  source: UpcomingSource;
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
  winrate: number | null;
  score_lead: number | null;
  prior: number;
  pv: string[];
  psv: number;  // playSelectionValue - KataGo's composite ranking metric
  // 人类倾向：某一档人类棋手会下这一点的概率（KataGo human SL 模型的 humanPrior）。
  // 与上面的 prior **是两张网**：prior 是 KataGo 自己的 policy 先验。
  // 成对出现，缺一个就都当没有 —— 一个概率不说清是哪一档人给的就没有意义。
  // 旧报告、直播链路、引擎没开人类模型时都是 null，界面必须显示成「—」而不是 0。
  human_prior?: number | null;
  human_profile?: string | null;
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
  // 旧的三个布尔量。直播链路仍由后端下发，报告链路改用下面的 grade。
  // 它们建在 delta_score 这一根**单边**轴上，实测 is_brilliant 基本只在搜索噪声上触发，
  // 新代码请用 grade / points_lost，不要再消费这三个。
  is_brilliant: boolean;
  is_mistake: boolean;
  is_questionable: boolean;
  delta_score: number;
  delta_winrate: number;
  // 七档评价（服务端下发）。见 src/features/analysis/moveGrade.ts。
  grade?: string | null;
  points_lost?: number | null;
  is_top_move?: boolean | null;
  top_prior?: number | null;
  brilliance?: number | null;
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
