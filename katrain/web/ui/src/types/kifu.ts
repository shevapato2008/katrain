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
  display_event?: string | null;
  display_round_name?: string | null;
  sources?: string[];
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
}
