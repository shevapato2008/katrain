export interface PlayerInfo {
  player_type: string;
  player_subtype: string;
  name: string;
  calculated_rank: string | null;
}

export interface GameState {
  game_id: string;
  board_size: [number, number];
  komi: number;
  handicap: number;
  ruleset: string;
  current_node_id: number;
  current_node_index: number;
  history: { node_id: number; score: number | null; winrate: number | null }[];
  player_to_move: string;
  stones: [string, [number, number] | null, number | null, number | null][];
  last_move: [number, number] | null;
  prisoner_count: { B: number; W: number };
  analysis: any;
  commentary: string;
  is_root: boolean;
  is_pass: boolean;
  end_result: string | null;
  children: [string, [number, number] | null][];
  ghost_stones: [string, [number, number] | null][];
  players_info: { B: PlayerInfo; W: PlayerInfo };
  note: string;
  ui_state: {
    show_children: boolean;
    show_dots: boolean;
    show_hints: boolean;
    show_policy: boolean;
    show_ownership: boolean;
    show_move_numbers: boolean;
    show_coordinates: boolean;
    zen_mode: boolean;
  };
  language: string;
}

export interface SessionResponse {
  session_id: string;
  state: GameState;
}

async function apiPost(path: string, payload: any) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const API = {
  createSession: (): Promise<SessionResponse> => apiPost("/api/session", {}),
  getState: async (sessionId: string): Promise<SessionResponse> => {
    const params = new URLSearchParams({ session_id: sessionId });
    const response = await fetch(`/api/state?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to get state");
    return { session_id: sessionId, state: (await response.json()).state };
  },
  playMove: (sessionId: string, coords: { x: number; y: number } | null): Promise<SessionResponse> =>
    apiPost("/api/move", {
      session_id: sessionId,
      coords: coords ? [coords.x, coords.y] : null,
      pass_move: coords === null,
    }),
  undo: (sessionId: string, nTimes: number | string = 1): Promise<SessionResponse> =>
    apiPost("/api/undo", { session_id: sessionId, n_times: nTimes }),
  redo: (sessionId: string, nTimes: number = 1): Promise<SessionResponse> =>
    apiPost("/api/redo", { session_id: sessionId, n_times: nTimes }),
  newGame: (sessionId: string, settings?: any): Promise<SessionResponse> =>
    apiPost("/api/new-game", { session_id: sessionId, ...settings }),
  gameSetup: (sessionId: string, mode: string, settings: any): Promise<SessionResponse> =>
    apiPost("/api/game/setup", { session_id: sessionId, mode, settings }),
  aiMove: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/ai-move", { session_id: sessionId }),
  navigate: (sessionId: string, nodeId?: number): Promise<SessionResponse> =>
    apiPost("/api/nav", { session_id: sessionId, node_id: nodeId }),
  loadSGF: (sessionId: string, sgf: string): Promise<SessionResponse> =>
    apiPost("/api/sgf/load", { session_id: sessionId, sgf }),
  saveSGF: async (sessionId: string): Promise<{ sgf: string }> => {
    const params = new URLSearchParams({ session_id: sessionId });
    const response = await fetch(`/api/sgf/save?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to save SGF");
    return response.json();
  },
  getConfig: async (sessionId: string, setting: string): Promise<any> => {
    const params = new URLSearchParams({ session_id: sessionId, setting });
    const response = await fetch(`/api/config?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to get config");
    return (await response.json()).value;
  },
  updateConfig: (sessionId: string, setting: string, value: any): Promise<SessionResponse> =>
    apiPost("/api/config", { session_id: sessionId, setting, value }),
  updatePlayer: (sessionId: string, bw: string, playerType?: string, playerSubtype?: string): Promise<SessionResponse> =>
    apiPost("/api/player", { session_id: sessionId, bw, player_type: playerType, player_subtype: playerSubtype }),
  swapPlayers: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/player/swap", { session_id: sessionId }),
  resign: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/resign", { session_id: sessionId }),
  rotate: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/rotate", { session_id: sessionId }),
  showPV: (sessionId: string, pv: string): Promise<SessionResponse> =>
    apiPost("/api/analysis/show-pv", { session_id: sessionId, pv }),
  clearPV: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/analysis/clear-pv", { session_id: sessionId }),
  findMistake: (sessionId: string, fn: "redo" | "undo"): Promise<SessionResponse> =>
    apiPost("/api/nav/mistake", { session_id: sessionId, fn }),
  setMode: (sessionId: string, mode: string): Promise<SessionResponse> =>
    apiPost("/api/mode", { session_id: sessionId, mode }),
  deleteNode: (sessionId: string, nodeId?: number): Promise<SessionResponse> =>
    apiPost("/api/node/delete", { session_id: sessionId, node_id: nodeId }),
  pruneBranch: (sessionId: string, nodeId?: number): Promise<SessionResponse> =>
    apiPost("/api/node/prune", { session_id: sessionId, node_id: nodeId }),
  makeMainBranch: (sessionId: string, nodeId?: number): Promise<SessionResponse> =>
    apiPost("/api/node/make-main", { session_id: sessionId, node_id: nodeId }),
  toggleCollapse: (sessionId: string, nodeId?: number): Promise<SessionResponse> =>
    apiPost("/api/node/toggle-collapse", { session_id: sessionId, node_id: nodeId }),
  toggleUI: (sessionId: string, setting: string): Promise<SessionResponse> =>
    apiPost("/api/ui/toggle", { session_id: sessionId, setting }),
  analyzeGame: (sessionId: string, visits?: number, mistakes_only: boolean = false): Promise<SessionResponse> => 
    apiPost("/api/analysis/game", { session_id: sessionId, visits, mistakes_only }),
  getGameReport: (sessionId: string, depth_filter?: number[]): Promise<any> => 
    apiPost("/api/analysis/report", { session_id: sessionId, depth_filter }),
  getAIConstants: async (): Promise<{ strategies: string[], options: Record<string, any>, key_properties: string[], default_strategy: string }> => {
    const response = await fetch('/api/ai-constants');
    if (!response.ok) throw new Error("Failed to fetch AI constants");
    return response.json();
  },
  estimateRank: (strategy: string, settings: any): Promise<{ rank: string }> =>
    apiPost("/api/ai/estimate-rank", { strategy, settings }),
  getTranslations: async (lang: string) => {
    const params = new URLSearchParams({ lang });
    const response = await fetch(`/api/translations?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to fetch translations");
    return response.json();
  }
};
