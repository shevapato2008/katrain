export interface PlayerInfo {
  player_type: string;
  player_subtype: string;
  name: string;
  calculated_rank: string | null;  // pre-existing quirk: typed string|null though backend emits int|None; NOT changed here
  rank_display?: string | null;    // NEW: ladder 段位 (optional to avoid breaking existing PlayerInfo literals)
  periods_used: number;
  main_time_used: number;
}

export type GameType = 'free' | 'ranked' | 'rated' | 'ai_ladder_ranked' | 'pvp_local' | 'pvp_online';

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
  sockets_count?: number;
  timer?: {
    paused: boolean;
    main_time_used: number;
    current_node_time_used: number;
    next_player_periods_used: number;
    settings: {
      main_time: number;
      byo_length: number;
      byo_periods: number;
      minimal_use: number;
      sound: boolean;
    };
  };
  language: string;
  count_min_moves?: number;
  engine?: "local" | "cloud";
  trainer_settings?: {
    eval_thresholds: number[];
    show_dots: boolean[];
    save_feedback: boolean[];
    save_marks: boolean[];
    eval_show_ai: boolean;
    lock_ai: boolean;
    top_moves_show: string;
    max_top_moves_on_board: number;
    low_visits: number;
    fast_visits?: number;
    max_visits?: number;
  };
  game_type?: GameType;
  analysis_allowed?: boolean;
  /**
   * 服务端这一局**交付不交付**分析结果。与 `analysis_allowed` 是两件事，别合并：
   *   analysis_allowed  = 这一局允不允许分析（升降级反作弊；服务端连算都不算）
   *   analysis_delivered = 算了，但交不交给你（无人认领的会话 —— 未登录游客建的那种 ——
   *                        拿不到胜率/候选点/领地，AI 走子照常）
   * 为 false 时 UI 要把三个分析键置灰并说明「登录后可用」，而不是留着一个点了没反应的键。
   * 老服务端不带这个字段 ⇒ undefined ⇒ 一切照旧。
   */
  analysis_delivered?: boolean;
  // True once an ai:ladder player refused to move because the engine cannot serve the
  // seated rung at its calibrated strength (interface._surface_ladder_unavailable).
  // It is a terminal condition for the current turn, not a transient one: nothing will
  // arrive later, so the UI must stop saying "AI 思考中…" and say what happened.
  // Cleared by the next successful AI move and by every new game.
  last_ladder_error?: boolean;
  // "B" | "W" = the color the REMOTE ENGINE plays in an engine-play game (Golaxy
  // 人机对弈 genmove tunnel); null/absent for every other game shape (local HvAI,
  // PVP, multiplayer). Authoritative signal for humanColor/aiColor derivation —
  // see kiosk/pages/GamePage.tsx deriveHumanColor/deriveAiTurnState (G2).
  platform_engine_color?: 'B' | 'W' | null;
}

export interface SessionResponse {
  session_id: string;
  state: GameState;
}

// --- Cross-platform play types ---

export interface PlatformInfo {
  platform: string;
  connected: boolean;
  supports_live_play: boolean;
  supports_automatch: boolean;
  supports_rooms: boolean;
  supports_seek_graph: boolean;
  supports_engine_play: boolean;
  saved_username?: string;
}

export interface EngineLevel {
  elo_score: number;
  level_name: string;   // e.g. "1级"
  name: string;         // bot name e.g. "星铠虾"
  goal_difference: number;
  timing: string;
  display_elo: number;
  ref_rank: string;
}

// One rung of the local 棋力阶梯 (strength-ladder) 41-rung opponent — the UI-facing
// subset served by GET /api/ladder-rungs (see katrain/web/server.py). 星阵-free.
// That route and /api/v1/ai-ladder/catalog both return catalog_projection(), so the
// casual picker and the ranked catalog can never disagree about names or count.
export interface LadderRung {
  rung: number;
  rank_name: string;
  // 服务端目录投影的全部字段（`ai_ladder_catalog.catalog_projection`）。原来这里只有前两个，
  // 于是任何按认证/可用性过滤的代码都读不到字段 —— 而本仓 `tsc --noEmit` 检查 0 个文件
  // （根 tsconfig 是 `files: []` + references），漏了也不会红，要用 `tsc -b`。
  certification_status: 'certified' | 'provisional';
  // `unavailable` = 坐不上去。今天它恰好等于「已封档」(`ladder._RETIRED_RUNGS`)，
  // 因为认证集与可坐集重合；但判据是这个字段本身，不是封档清单的前端副本。
  availability: 'available' | 'unavailable';
  route: string;
}

export interface PlatformStatusResponse {
  platforms: PlatformInfo[];
}

// --- Engine analysis (area/options/judge/variation) ---
// Shapes are `dataclasses.asdict` of the GolaxyAdapter.engine_analysis results
// (katrain/web/platforms/golaxy/adapter.py: AreaAnalysis/OptionsAnalysis/
// VariationAnalysis/JudgeAnalysis).

export interface OwnershipPoint {
  col: number;
  row: number;
  value: number;
}
export interface JudgePoint {
  col: number;
  row: number;
  owner: string; // "U" | "B" | "W"
}
export interface AnalysisCandidate {
  col: number;
  row: number;
  prob: number;
  winrate: number;
  delta: number;
}
export interface AnalysisPoint {
  col: number;
  row: number;
}
export type EngineAnalysisData =
  | { ownership: OwnershipPoint[]; winrate: number; delta: number } // area
  | { candidates: AnalysisCandidate[] } // options
  | { sequence: AnalysisPoint[]; winrate: number; delta: number } // variation
  | { ownership: JudgePoint[]; winner: string; delta: number }; // judge
export type EngineAnalysisResponse =
  | { ok: true; kind: "area" | "options" | "judge" | "variation"; data: EngineAnalysisData }
  | { ok: false; reason: "insufficient"; kind: string };
// Remaining metered-道具 counts for the analysis-button badges. Each is a
// number, or null when the platform didn't report it (render as "unknown",
// never as 0). judge (形势) is free and has no count.
export interface EngineItemCounts {
  area: number | null;
  options: number | null;
  variation: number | null;
}

export interface PlatformUser {
  user_id: string;
  username: string;
  rank: string;
  status: string;
}

export interface PlatformClockState {
  black_time: Record<string, any>;
  white_time: Record<string, any>;
  current_player: "B" | "W";
  paused?: boolean;
}

export interface VisionStatusResponse {
  enabled: boolean;
  camera_connected: boolean;
  pose_locked: boolean;
  sync_state: string;
  bound_session_id: string | null;
  recognition_ready?: boolean;
  led_connected?: boolean;
}

// Task 9: physical engine-move (Golaxy 隧道) error recovery. `col`/`row` are GTP/board
// space (row 0 = bottom) — see physical_play_orchestrator.py's enter_engine_error and
// the `physical_engine_error` WS broadcast (server.py _apply_engine_recovery_outcome).
export interface PhysicalEngineErrorState {
  col: number;
  row: number;
  attempts: number;
  detail: string;
  recovery_token: string;
}
export interface EngineMoveRetryResponse {
  ok: boolean;
  detail?: string;
  recovery_token?: string; // present (and NEW) only when ok:false — adopt it for the next retry
}
export interface EngineMoveCancelResponse {
  ok: boolean;
  awaiting_removal?: boolean;
}

export interface HintMove {
  gtp: string;
  coords: [number, number];
  vision_rc: [number, number];
  winrate: number | null;
  score_lead: number | null;
  visits: number | null;
}
export interface HintResponse { moves: HintMove[]; engine: string; timeout_s: number; }

// Thrown by apiPost on a non-2xx HTTP response. Carries the numeric `status` so callers
// can distinguish a genuine server-side rejection (e.g. a 409 on a stale/consumed token)
// from a transient network failure — `fetch` itself throws a plain `TypeError`/`Error` for
// those (offline, DNS, connection reset), never an `ApiError`. Message format is
// unchanged (`Request failed <status>: <body>`) so existing text-based assertions
// (e.g. KifuPage.test.tsx's "Request failed 500") keep working.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* 严格盒端 SSO（kiosk 构建 + VITE_BOX_SSO_STRICT）那一档故意不持有 token，
   鉴权只走 HttpOnly 的 sb_go_token cookie，这里绝不能自己造 Bearer 头。 */
const isStrictBoxKiosk = __KIOSK_2D_ONLY__ && import.meta.env.VITE_BOX_SSO_STRICT === 'true';

/**
 * 统一取鉴权头。调用方没显式传 token 时，从 localStorage 兜底。
 *
 * 为什么必须兜底而不是逐个调用点补 token：后端 72 个端点挂着
 * `Depends(get_current_user)`，前端有一批 `apiPost(path, body)` 从来不传 token。
 * 这批调用在本机看着是好的 —— 因为 auth.py 的 _issue_loopback_sso_cookie 只在
 * hostname == 127.0.0.1 时发 `sb_token` cookie，而 box_sso.resolve_http_token 是
 * `cookie or header`，cookie 先赢。一换成 go.sailorvoyage.top / modelstella.com
 * 就没有那块 cookie，header 又是空的，于是 401。
 * 「研究 → 开始研究 卡在『正在连接研究会话…』不动」就是这么来的：
 * /api/analysis/scan 和 /api/analysis/progress 每秒 401，而轮询把异常吞了。
 * getState 上面那条注释记的是同一个坑的上一次发作 —— 那次只补了一个端点。
 *
 * 顺序上兜底是安全的：非严格档 cookie 优先于 header，所以盒端/本机行为不变；
 * 只有本来就没有 cookie 的远端会用上这个头。
 */
export function authHeaders(token?: string): Record<string, string> {
  if (isStrictBoxKiosk) return {};
  let resolved = token;
  if (!resolved) {
    try {
      resolved = localStorage.getItem('token') ?? undefined;
    } catch {
      resolved = undefined;   // 隐私模式下 localStorage 会抛
    }
  }
  return resolved ? { Authorization: `Bearer ${resolved}` } : {};
}

export async function apiPost(path: string, payload: any, token?: string) {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...authHeaders(token) };
  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, `Request failed ${response.status}: ${body}`);
  }
  return response.json();
}

export const API = {
  createSession: (token?: string): Promise<SessionResponse> => apiPost("/api/session", {}, token),
  // GET /api/state requires an authenticated user (server.py: Depends(get_current_user)).
  // It used to send no Authorization header, which only worked because the server also
  // accepts the `sb_token` cookie -- and that cookie is issued ONLY on the 127.0.0.1
  // loopback host (auth.py _issue_loopback_sso_cookie, whose whole point is to leave the
  // Galaxy JSON-token flow alone). So it passed on a kiosk and 401'd on Galaxy, where the
  // game page then showed "Failed to connect to game" with no way to recover.
  getState: async (sessionId: string, token?: string): Promise<SessionResponse> => {
    const params = new URLSearchParams({ session_id: sessionId });
    const headers: Record<string, string> = authHeaders(token);
    const response = await fetch(`/api/state?${params.toString()}`, { headers });
    if (!response.ok) throw new Error("Failed to get state");
    return { session_id: sessionId, state: (await response.json()).state };
  },
  playMove: (sessionId: string, coords: { x: number; y: number } | null, token?: string): Promise<SessionResponse> =>
    apiPost("/api/move", {
      session_id: sessionId,
      coords: coords ? [coords.x, coords.y] : null,
      pass_move: coords === null,
    }, token),
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
  navigate: (sessionId: string, nodeId?: number, token?: string): Promise<SessionResponse> =>
    apiPost("/api/nav", { session_id: sessionId, node_id: nodeId }, token),
  loadSGF: (sessionId: string, sgf: string, skipAnalysis: boolean = false): Promise<SessionResponse> =>
    apiPost("/api/sgf/load", { session_id: sessionId, sgf, skip_analysis: skipAnalysis }),
  saveSGF: async (sessionId: string): Promise<{ sgf: string }> => {
    const params = new URLSearchParams({ session_id: sessionId });
    const response = await fetch(`/api/sgf/save?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to save SGF");
    return response.json();
  },
  /* `GET /api/config` 现在要求「这局是你的」（server.py 的 guard_session_reader），
     所以这个裸 fetch 必须带上凭据 —— 与 `getState` 上面那条注释记的是同一个坑：
     不带头时它只在 127.0.0.1 上靠 loopback 的 `sb_token` cookie 侥幸通过，
     在 galaxy 上会 401，而唯一的调用方（ZenMode 的 AI 设置对话框）catch 里只有
     console.error，屏上什么都不会说。 */
  getConfig: async (sessionId: string, setting: string, token?: string): Promise<any> => {
    const params = new URLSearchParams({ session_id: sessionId, setting });
    const response = await fetch(`/api/config?${params.toString()}`, { headers: authHeaders(token) });
    if (!response.ok) throw new Error("Failed to get config");
    return (await response.json()).value;
  },
  updateConfig: (sessionId: string, setting: string, value: any): Promise<SessionResponse> =>
    apiPost("/api/config", { session_id: sessionId, setting, value }),
  updateConfigBulk: (sessionId: string, updates: Record<string, any>): Promise<SessionResponse> =>
    apiPost("/api/config/bulk", { session_id: sessionId, updates }),
  updatePlayer: (sessionId: string, bw: string, playerType?: string, playerSubtype?: string, name?: string): Promise<SessionResponse> =>
    apiPost("/api/player", { session_id: sessionId, bw, player_type: playerType, player_subtype: playerSubtype, name }),
  swapPlayers: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/player/swap", { session_id: sessionId }),
  resign: (sessionId: string, token?: string): Promise<SessionResponse> =>
    apiPost("/api/resign", { session_id: sessionId }, token),
  timeout: (sessionId: string, token?: string): Promise<SessionResponse> =>
    apiPost("/api/timeout", { session_id: sessionId }, token),
  requestCount: (sessionId: string, token?: string): Promise<any> =>
    apiPost("/api/count/request", { session_id: sessionId }, token),
  respondCount: (sessionId: string, accept: boolean, token?: string): Promise<any> =>
    apiPost("/api/count/respond", { session_id: sessionId, accept }, token),
  pauseTimer: (sessionId: string): Promise<SessionResponse> =>
    apiPost("/api/timer/pause", { session_id: sessionId }),
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
  analyze: (sessionId: string, payload: any): Promise<any> =>
    apiPost("/api/v1/analysis/analyze", { session_id: sessionId, payload }),
  analyzeGame: (sessionId: string, visits?: number, mistakes_only: boolean = false): Promise<SessionResponse> =>
    apiPost("/api/analysis/game", { session_id: sessionId, visits, mistakes_only }),
  analysisScan: (sessionId: string, visits?: number): Promise<SessionResponse> =>
    apiPost("/api/analysis/scan", { session_id: sessionId, visits }),
  quickAnalyze: (params: {
    moves: string[][]; initial_stones?: string[][]; board_size?: number; komi?: number; rules?: string; max_visits?: number;
  }, token?: string): Promise<any> =>
    apiPost("/api/v1/analysis/quick-analyze", params, token),
  // On-demand analysis of the current position (kiosk 领地/图表 in board mode, where per-move
  // auto-eval is suppressed). Result streams back over the game WebSocket, not this response.
  analyzeCurrent: (sessionId: string): Promise<any> =>
    apiPost("/api/analysis/current", { session_id: sessionId }),
  analysisProgress: async (sessionId: string, token?: string): Promise<{ session_id: string; analyzed: number; total: number }> => {
    const response = await fetch(`/api/analysis/progress?session_id=${sessionId}`, { headers: authHeaders(token) });
    if (!response.ok) throw new ApiError(response.status, `Failed to fetch analysis progress (${response.status})`);
    return response.json();
  },
  getGameReport: (sessionId: string, depth_filter?: number[]): Promise<any> => 
    apiPost("/api/analysis/report", { session_id: sessionId, depth_filter }),
  getAIConstants: async (): Promise<{ strategies: string[], options: Record<string, any>, key_properties: string[], default_strategy: string }> => {
    const response = await fetch('/api/ai-constants');
    if (!response.ok) throw new Error("Failed to fetch AI constants");
    return response.json();
  },
  estimateRank: (strategy: string, settings: any): Promise<{ rank: string }> =>
    apiPost("/api/ai/estimate-rank", { strategy, settings }),
  getLadderRungs: async (): Promise<{ rungs: LadderRung[] }> => {
    const response = await fetch('/api/ladder-rungs');
    if (!response.ok) throw new Error("Failed to fetch ladder rungs");
    return response.json();
  },
  getTranslations: async (lang: string) => {
    const params = new URLSearchParams({ lang });
    const response = await fetch(`/api/translations?${params.toString()}`);
    if (!response.ok) throw new Error("Failed to fetch translations");
    return response.json();
  },
  login: async (username: string, password: string): Promise<{ access_token: string, token_type: string }> => {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Login failed ${response.status}: ${body}`);
    }
    return response.json();
  },
  register: async (username: string, password: string): Promise<any> => {
    const response = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Registration failed ${response.status}: ${body}`);
    }
    return response.json();
  },
  getMe: async (token: string): Promise<any> => {
    const response = await fetch("/api/v1/auth/me", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get user info");
    return response.json();
  },
  followUser: async (token: string, username: string): Promise<any> => {
    const response = await fetch(`/api/v1/users/follow/${username}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to follow user");
    return response.json();
  },
  unfollowUser: async (token: string, username: string): Promise<any> => {
    const response = await fetch(`/api/v1/users/follow/${username}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to unfollow user");
    return response.json();
  },
  getFollowing: async (token: string): Promise<any[]> => {
    const response = await fetch("/api/v1/users/following", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get following list");
    return response.json();
  },
  getFollowers: async (token: string): Promise<any[]> => {
    const response = await fetch("/api/v1/users/followers", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get followers list");
    return response.json();
  },
  leaveMultiplayerGame: (sessionId: string, token: string): Promise<any> =>
    apiPost("/api/multiplayer/leave", { session_id: sessionId }, token),

  // Vision API
  visionStatus: (): Promise<VisionStatusResponse> =>
    fetch("/api/v1/vision/status").then(r => r.json()),
  visionConfirmPoseLock: (): Promise<void> =>
    apiPost("/api/v1/vision/pose-lock/confirm", {}),
  visionBind: (sessionId: string): Promise<void> =>
    apiPost("/api/v1/vision/bind", { session_id: sessionId }),
  visionUnbind: (): Promise<void> =>
    apiPost("/api/v1/vision/unbind", {}),
  // adopt='digital' (default): trust-digital recovery — re-baseline to the game, clear the
  // stuck removal/pause. adopt='physical': accept the camera board as-is (ambiguous 忽略) so
  // the ignored stone isn't re-detected.
  visionResetSync: (adopt: 'digital' | 'physical' = 'digital'): Promise<void> =>
    apiPost("/api/v1/vision/sync/reset", { adopt }),
  visionSetupMode: (targetBoard: number[][]): Promise<void> =>
    apiPost("/api/v1/vision/setup-mode", { target_board: targetBoard }),
  visionMonitor: (active: boolean): Promise<void> =>
    apiPost("/api/v1/vision/monitor", { active }),
  visionPause: (paused: boolean): Promise<void> =>
    apiPost("/api/v1/vision/pause", { paused }),
  visionMoveDetection: (armed: boolean): Promise<void> =>
    apiPost("/api/v1/vision/move-detection", { armed }),
  visionExpectedBoard: (board: number[][]): Promise<void> =>
    apiPost("/api/v1/vision/expected-board", { board }),
  // Task 9: engine-move recovery dialog actions. 200 {ok:false, recovery_token} is a
  // normal "failed again" outcome (NOT an HTTP error); a 409 (stale/consumed token) DOES
  // reject via apiPost's !response.ok throw — callers treat that as "recovery expired".
  visionEngineMoveRetry: (sessionId: string, recoveryToken: string, token?: string): Promise<EngineMoveRetryResponse> =>
    apiPost("/api/v1/vision/engine-move/retry", { session_id: sessionId, recovery_token: recoveryToken }, token),
  visionEngineMoveCancel: (sessionId: string, recoveryToken: string, token?: string): Promise<EngineMoveCancelResponse> =>
    apiPost("/api/v1/vision/engine-move/cancel", { session_id: sessionId, recovery_token: recoveryToken }, token),

  // AI Hint API (free games only)
  hint: (sessionId: string, topN?: number): Promise<HintResponse> =>
    apiPost("/api/v1/hint", { session_id: sessionId, top_n: topN ?? null }) as Promise<HintResponse>,
  hintDismiss: (): Promise<{ ok: boolean }> =>
    apiPost("/api/v1/hint/dismiss", {}) as Promise<{ ok: boolean }>,

  logout: async (token?: string): Promise<any> => {
    const request: RequestInit = { method: "POST" };
    if (token) request.headers = { "Authorization": `Bearer ${token}` };
    const response = await fetch("/api/v1/auth/logout", {
      ...request,
    });
    if (!response.ok) {
      // Don't throw on logout failure - still proceed with local cleanup
      console.warn("Server logout failed, proceeding with local cleanup");
    }
    return response.ok ? response.json() : { status: "local_only" };
  },

  // --- Cross-platform online play ---
  platformLogin: (
    platform: string,
    credentials: { username: string; password?: string; sms_code?: string },
    token: string,
  ) => apiPost(`/api/v1/platforms/${platform}/login`, credentials, token),
  platformSmsRequest: (platform: string, phone: string, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/sms/request`, { phone }, token),
  platformEngineLevels: async (platform: string, token: string): Promise<{ levels: EngineLevel[] }> => {
    const response = await fetch(`/api/v1/platforms/${platform}/engine/levels`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get engine levels");
    return response.json();
  },
  platformEngineStart: (
    platform: string,
    body: { level: number; human_color: "B" | "W" | "nigiri"; handicap: number },
    token: string,
  ): Promise<{ session_id: string; human_color?: "B" | "W" }> =>
    apiPost(`/api/v1/platforms/${platform}/engine/start`, body, token),
  platformEngineAnalysis: (
    platform: string,
    sessionId: string,
    kind: "area" | "options" | "judge" | "variation",
    token: string,
  ): Promise<EngineAnalysisResponse> =>
    apiPost(`/api/v1/platforms/${platform}/engine/analysis`, { session_id: sessionId, kind }, token),
  platformEngineItems: async (platform: string, token: string): Promise<EngineItemCounts> => {
    const response = await fetch(`/api/v1/platforms/${platform}/engine/items`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get engine item counts");
    return response.json();
  },
  platformLogout: async (platform: string, token: string) => {
    const response = await fetch(`/api/v1/platforms/${platform}/logout`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error(`Logout failed: ${response.status}`);
    return response.json();
  },
  platformStatus: async (token: string): Promise<PlatformStatusResponse> => {
    const response = await fetch("/api/v1/platforms/status", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get platform status");
    return response.json();
  },
  platformUsers: async (platform: string, token: string, query?: string): Promise<{ users: PlatformUser[] }> => {
    const params = query ? `?q=${encodeURIComponent(query)}` : '';
    const response = await fetch(`/api/v1/platforms/${platform}/users${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get users");
    return response.json();
  },
  platformRooms: async (platform: string, token: string) => {
    const response = await fetch(`/api/v1/platforms/${platform}/rooms`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get rooms");
    return response.json();
  },
  platformChallenges: async (platform: string, token: string) => {
    const response = await fetch(`/api/v1/platforms/${platform}/challenges`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to get challenges");
    return response.json();
  },
  platformSendChallenge: (platform: string, data: object, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/challenge`, data, token),
  platformAcceptChallenge: (platform: string, challengeId: string, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/challenge/accept`, { challenge_id: challengeId }, token),
  platformDeclineChallenge: (platform: string, challengeId: string, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/challenge/decline`, { challenge_id: challengeId }, token),
  platformStartAutomatch: (platform: string, prefs: object, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/automatch/start`, prefs, token),
  platformCancelAutomatch: (platform: string, token: string) =>
    apiPost(`/api/v1/platforms/${platform}/automatch/cancel`, {}, token),
};
