export interface LobbyConfig {
  version: 1;
  enabled: boolean;
  bot_game_limit: number;
  idle_targets: Record<string, number>;
}
export interface LobbyRung {
  rung: number;
  rank_label: string;
  idle_target: number;
  idle_now: number | null;
  playing_now: number | null;
}
export interface LobbyRuntime {
  reported_at: string | null;
  applied_config_revision: number | null;
  stale: boolean;
  active_bot_games: number | null;
  engine_errors: number | null;
  rungs: LobbyRung[];
}
export interface LobbyOverview { config: LobbyConfig; config_revision: number; runtime: LobbyRuntime }
export interface Participant {
  id: number; username: string; kind: 'human' | 'bot'; ladder_rung: number | null;
  rank_label: string | null; presence: 'idle' | 'playing' | 'offline';
}
export interface ParticipantPage { items: Participant[]; total: number; page: number; page_size: number }
export interface ParticipantQuery { page: number; page_size: number; kind: 'all' | 'human' | 'bot'; presence: 'all' | 'online' | 'idle' | 'playing' | 'offline'; q: string }
