import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar } from '@mui/material';
// TipsAndUpdates is intentionally NOT imported: the standalone header hint button is gone
// (AI 支招 is folded into the right-panel button in GameControlPanel). EmojiEvents is used
// by the endgame result card below.
import { ExitToApp, Videocam, Lightbulb, GpsFixed, Refresh, EmojiEvents } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board, { type EngineOverlay } from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';
import KioskResultBadge from '../components/game/KioskResultBadge';
import RecalibrationModal from '../components/game/RecalibrationModal';
import VisionSyncOverlay from '../components/vision/VisionSyncOverlay';
import { useVision } from '../context/VisionContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { useTranslation } from '../../hooks/useTranslation';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';
import EngineMoveErrorDialog from '../components/physical/EngineMoveErrorDialog';
import HintPanel from '../components/physical/HintPanel';
import { API, type HintResponse, type OwnershipPoint, type AnalysisCandidate, type AnalysisPoint, type EngineItemCounts, type GameState } from '../../api';
import { writeActiveSession, clearActiveSession } from '../utils/activeSession';
import { usePlatformEvents } from '../hooks/usePlatformEvents';
import { formatGtpCoord } from '../../utils/gtpCoord';
import { isRankedGameType } from '../../features/aiLadder/gameType';
import { AiLadderSettlementAlert, useAiLadderSettlement } from '../../features/aiLadder/settlement';

type EngineAnalysisKind = 'area' | 'options' | 'variation';

export interface AiTurnState {
  aiColor: 'B' | 'W' | null;
  aiThinking: boolean;
  physicalConfirming: boolean;
  showThinking: boolean;
}

// Single-color human-seat derivation, shared by humanColor (turn enforcement / board
// gating) and the AI-move banner effect below (G2 fix). `platform_engine_color`
// (Task 1: WebKaTrain state field, "B"|"W"|null = the remote engine's color) is
// authoritative for engine games (Golaxy 人机对弈 via the genmove tunnel) — BOTH
// seats carry a bare "human" player_type literal there (session.py:80/82), so the
// player_type-based checks below can't tell which seat is the AI. Absent/null in
// every other game shape (local HvAI, PVP, multiplayer) — falls through unchanged.
// eslint-disable-next-line react-refresh/only-export-components
export function deriveHumanColor(gameState: GameState): 'B' | 'W' | null {
  // Both-human (local PvP, server.py 'pvp_local'): null lets EITHER side play, so the
  // touchscreen fallback works for BOTH colors. Must precede the single-human checks
  // below, which would otherwise collapse to 'B' and block White from moving. Uses the
  // exact 'player:human' literal both seats carry in local PvP; the engine fixture's bare
  // 'human' seats don't match, so engine games still resolve via platform_engine_color.
  if (
    gameState.players_info?.B?.player_type === 'player:human' &&
    gameState.players_info?.W?.player_type === 'player:human'
  ) return null;
  if (gameState.platform_engine_color === 'B') return 'W';
  if (gameState.platform_engine_color === 'W') return 'B';
  return gameState.players_info?.B?.player_type === 'player:human' ? 'B'
    : gameState.players_info?.W?.player_type === 'player:human' ? 'W'
    : null;
}

// Single-owner AI-turn arbitration (state A source for B1.4). Exported as a pure
// function so it's unit-testable without rendering the page, and so B1.4 can reuse it.
// Per-color AI detection — accept BOTH literals: 'player:ai' (kiosk HvAI, server.py:723/727)
// AND bare 'ai' (multiplayer session.py:80/82 + tests), PLUS the engine's color per
// `platform_engine_color` (G2 fix — engine games carry bare "human" on both seats, so
// the literal checks alone can't find the AI seat there). Do NOT infer AI from "the
// non-human color". Pure helper co-located here (not split into a new file) for unit
// testability; deliberate, not a component — see GamePage.test.tsx.
// eslint-disable-next-line react-refresh/only-export-components
export function deriveAiTurnState(gameState: GameState, latestEventType: string | null | undefined): AiTurnState {
  const isAI = (c: 'B' | 'W') => {
    const pt = gameState.players_info[c].player_type;
    return pt === 'player:ai' || pt === 'ai' || c === gameState.platform_engine_color;
  };
  const aiColor = isAI('B') ? 'B' : isAI('W') ? 'W' : null;
  const aiThinking = !!aiColor && gameState.player_to_move === aiColor && !gameState.end_result;
  // One owner for the AI-turn indicator: while the physical layer is confirming a
  // move (chip shows 确认中), suppress the 思考中 banner so they never stack.
  const physicalConfirming = latestEventType === 'move_pending';
  const showThinking = aiThinking && !physicalConfirming;
  return { aiColor, aiThinking, physicalConfirming, showThinking };
}

interface EndgameCardProps {
  gameState: GameState;
  t: (key: string, fallback?: string) => string;
  onExit: () => void;
  onReview: () => void;
}

// State C (design.md §5.1): result card + score breakdown + territory coloring (forced via
// GamePage's boardAnalysisToggles). 继续对弈 only hides this card via LOCAL `dismissed` state —
// the game stays ended; useGameSession.handleAction has no 'resume' branch, so it is
// deliberately never called here. 确认终局 calls the `onExit` prop (GamePage's handleExit).
// `dismissed` is local rather than lifted to GamePage/reset via a useEffect, because GamePage
// remounts this component with `key={sessionId}` on every new session/game (React's
// "reset state via key" pattern — https://react.dev/learn/you-might-not-need-an-effect —
// avoids a useEffect + setState, keeping this repo's react-hooks/set-state-in-effect gate clean).
// DESCOPED: dead-stone dimming + red-X needs a backend dead_stones field + a kiosk-only
// overlay (Gate S); not shipped in this cut, and shared Board.tsx is left untouched.
const EndgameCard = ({ gameState, t, onExit, onReview }: EndgameCardProps) => {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <Box data-testid="endgame-card" sx={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 70,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, px: 3, py: 2, borderRadius: 3,
          bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
      <EmojiEvents sx={{ color: 'primary.main' }} />
      <KioskResultBadge result={gameState.end_result!} rules={gameState.ruleset} />
      {/* Score breakdown — komi + captures only (display only). Full territory-adjusted
          目/子 breakdown needs dead-stone data from the backend; deferred (Gate S). */}
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {t('Komi', '贴目')} {gameState.komi} · {t('Captures', '提子')} {t('Black', '黑')} {gameState.prisoner_count.B} / {t('White', '白')} {gameState.prisoner_count.W}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1.5 }}>
        <Button variant="outlined" onClick={() => setDismissed(true)}>{t('Resume game', '继续对弈')}</Button>
        <Button variant="outlined" onClick={onReview}>{t('Review this game', '复盘本局')}</Button>
        <Button variant="contained" onClick={onExit} sx={{ bgcolor: 'primary.main' }}>{t('Confirm result', '确认终局')}</Button>
      </Box>
    </Box>
  );
};

const GamePage = ({ engineMode = false }: { engineMode?: boolean }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const { token, user } = useAuth();
  const session = useGameSession({ token: token ?? undefined });
  // B2/D5 (engine-move commit protocol): while a Golaxy 人机对弈 move is in flight
  // (genmove tunnel, up to ~180s), the backend already 409s undo/redo/nav — this
  // mirrors that in the UI so the button doesn't sit there inviting a rejected tap.
  const { pendingMove: platformPendingMove } = usePlatformEvents(session.wsRef, {});
  const [analysisToggles, setAnalysisToggles] = useState(() => ({
    ownership: false,
    hints: false,
    numbers: false,
    coords: true,
    score: true,
  }));

  const [showResignConfirm, setShowResignConfirm] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [aiMoveBanner, setAiMoveBanner] = useState<string | null>(null);
  const [cameraDisconnectToast, setCameraDisconnectToast] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  // Lazy-init from session.physicalReminder (not a plain `useState(false)`): if the page is
  // (re)mounted while already mid-escalation, escalationOpen must be true from the very FIRST
  // render — otherwise RecalibrationModal (state B, B1.4) would compute `open=true` for one
  // frame before the effect below catches up, flashing over the escalation dialog it's
  // supposed to defer to (board-loss precedence: escalation > recalibration > board-lost).
  const [escalationOpen, setEscalationOpen] = useState(() => session.physicalReminder?.kind === 'escalation');
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [hintError, setHintError] = useState<string | null>(null);
  const [engineErrorToast, setEngineErrorToast] = useState(false);
  const [countError, setCountError] = useState<string | null>(null);
  const [resignError, setResignError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState(false);
  const [resyncing, setResyncing] = useState(false);
  const [resyncError, setResyncError] = useState(false);
  const [syncStuck, setSyncStuck] = useState(false);

  // Golaxy 人机对弈 is the only engine-play platform today (§13). Revisit if/when
  // another platform gets engine-play analysis tunnels.
  const platform = 'golaxy';
  const [engineOverlay, setEngineOverlay] = useState<EngineOverlay | null>(null);
  const [activeEngineKind, setActiveEngineKind] = useState<EngineAnalysisKind | null>(null);
  const [insufficientKind, setInsufficientKind] = useState<EngineAnalysisKind | null>(null);
  // In-flight guard: a touchscreen double-tap must not fire two paid 星阵 analysis
  // calls before the first resolves (double quota spend + last-response-wins races).
  // Does NOT gate insufficientKind — that dialog is user-dismissed, not auto-cleared.
  const [pendingEngineKind, setPendingEngineKind] = useState<EngineAnalysisKind | null>(null);
  // Remaining-uses badges (领地N/支招N/变化图N). null until the first fetch resolves → "—".
  const [engineItemCounts, setEngineItemCounts] = useState<EngineItemCounts | null>(null);

  // refreshStatus drives the 重置识别 recovery button clearing immediately on success.
  const { visionStatus, isVisionEnabled, refreshStatus } = useVision();
  const visionSync = useVisionSync(isVisionEnabled ? sessionId ?? null : null);

  useEffect(() => {
    if (!session.physicalReminder) return;
    if (session.physicalReminder.kind === 'escalation') setEscalationOpen(true);
    else setReminderOpen(true);
  }, [session.physicalReminder]);

  // Dedicated hint-dismiss unmount cleanup. NOTE: this does NOT own vision bind/unbind —
  // useVisionSync is the sole owner of that (Task 9 M1 fix removed GamePage's old
  // visionBind/unbind effect to avoid a double-bind bug). Keep this effect scoped to
  // the hint lifecycle only.
  useEffect(() => () => { API.hintDismiss().catch(() => undefined); }, []);

  useEffect(() => {
    if (sessionId) session.setSessionId(sessionId);
  }, [sessionId]);

  // activeSession write-on-load / clear-on-end (design.md §5.1: 继续上一局 clears on end).
  // Covers ai/pvp/cross entry routes uniformly.
  useEffect(() => {
    const gs = session.gameState;
    if (!gs || !sessionId) return;
    if (gs.end_result) { clearActiveSession('game'); return; }
    writeActiveSession({
      kind: 'game',
      label: `${gs.players_info.B.name} vs ${gs.players_info.W.name}`,
      route: window.location.pathname,
      ts: Date.now(),
    });
  }, [session.gameState?.current_node_id, session.gameState?.end_result, sessionId]);

  // Persistent amber banner when AI makes a move (vision mode: physical board player
  // needs a coordinate hint to place the matching stone). Cleared on the human's own move.
  useEffect(() => {
    if (!isVisionEnabled || !session.gameState) return;
    const gs = session.gameState;
    const human = deriveHumanColor(gs);
    if (gs.last_move && gs.end_result === null && human && gs.player_to_move === human) {
      setAiMoveBanner(formatGtpCoord(gs.last_move[0], gs.last_move[1], gs.board_size[0]));
    }
  }, [isVisionEnabled, session.gameState?.current_node_id]);

  // Camera disconnect fallback
  useEffect(() => {
    if (isVisionEnabled && !visionStatus.cameraConnected) {
      setCameraDisconnectToast(true);
    }
  }, [isVisionEnabled, visionStatus.cameraConnected]);

  // Invalidate the 星阵 analysis overlay when the board position advances (a move
  // played, human or AI) — otherwise stale 领地/支招/变化图 markers keep drawing over
  // the new position and the button stays stuck "active". Keyed on position identity
  // only, so it never fires on unrelated re-renders. Does NOT touch insufficientKind —
  // that dialog is dismissed by the user, not by position changes. engineMode only.
  useEffect(() => {
    setEngineOverlay(null);
    setActiveEngineKind(null);
  }, [session.gameState?.current_node_id]);

  // Task 11: the physical white hint LEDs (Task 10, PhysicalPlayOrchestrator.show_hint)
  // mirror the 支招 (options) overlay above. Whenever activeEngineKind moves AWAY from
  // 'options' — however that happens (the position-change effect above clearing it, the
  // user toggling 支招 off, or the user switching to a different kind) — the LEDs must
  // turn off in sync. A single ref-compared effect catches all three causes uniformly,
  // rather than duplicating the dismiss call at each call site. Gated to engine games with
  // vision enabled: screen-only sessions and non-engine free-play don't drive the LEDs, so
  // dismissing there would be a pointless network call (the endpoint is idempotent, but
  // there's nothing to gain). Does NOT replace the unmount cleanup above — that already
  // covers "leaving the page" unconditionally.
  const prevEngineOptionsKindRef = useRef<EngineAnalysisKind | null>(null);
  useEffect(() => {
    const prevKind = prevEngineOptionsKindRef.current;
    prevEngineOptionsKindRef.current = activeEngineKind;
    if (engineMode && isVisionEnabled && prevKind === 'options' && activeEngineKind !== 'options') {
      API.hintDismiss().catch(() => undefined);
    }
  }, [activeEngineKind, engineMode, isVisionEnabled]);

  // Local free-play on-demand analysis for 领地(ownership)/图表(winrate/score). Board mode
  // suppresses per-move auto-eval, so the current position has no analysis until we ask.
  // Trigger when either toggle is on, and re-trigger when the current node changes. The
  // result streams back over the game WebSocket (get_state broadcast). Ranked/rated games
  // block this server-side (analysis_allowed). Not used in engineMode (star阵 tunnel instead).
  const wantAnalysis = analysisToggles.ownership || analysisToggles.score;
  const gs = session.gameState;
  useEffect(() => {
    if (engineMode || !wantAnalysis || !sessionId || !gs) return;
    if (isRankedGameType(gs.game_type)) return;
    API.analyzeCurrent(sessionId).catch(() => undefined);
  }, [engineMode, wantAnalysis, sessionId, gs?.current_node_id, gs?.game_type]);

  const closeHint = useCallback(() => {
    setHint(null);
    API.hintDismiss().catch(() => undefined);
  }, []);

  // Always-available fallback when vision sync gets stuck (blue-LED / 确认中 deadlock):
  // re-baseline to the digital board, drop the stuck removal, resume detection. Refresh
  // status on success so the button clears immediately instead of after the ≤3s poll;
  // surface a failure instead of silently swallowing it.
  const handleResetSync = useCallback(async () => {
    setResyncing(true);
    try {
      await API.visionResetSync();
      await refreshStatus();
    } catch {
      setResyncError(true);
    } finally {
      setResyncing(false);
    }
  }, [refreshStatus]);

  // Offer the 重置识别 button only for genuinely-blocked sync states, and only after they
  // PERSIST — a routine capture (capture_pending self-clears in a few seconds) or a hand
  // over the board (board_lost) must not flash the warning button, while a real deadlock
  // still recovers well under the 30s reminder / 120s escalation. 'unbound' / 'calibrating'
  // / 'setup_in_progress' / 'synced' are never "stuck".
  const stuckEligible =
    isVisionEnabled && !session.gameState?.end_result &&
    ['mismatch_warning', 'capture_pending', 'board_lost', 'degraded'].includes(visionStatus.syncState);
  useEffect(() => {
    if (!stuckEligible) {
      setSyncStuck(false);
      return;
    }
    const id = setTimeout(() => setSyncStuck(true), 10000);
    return () => clearTimeout(id);
  }, [stuckEligible]);

  // Remaining-道具 counts for the button badges. Account-level (not per-game),
  // so it's safe to fetch once on mount and re-fetch after each analysis settles
  // (each call consumes a use; 7003 means it hit 0). Best-effort: a failed fetch
  // leaves the prior counts (or null → "—") and never blocks play.
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !token) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, token]);

  useEffect(() => {
    void refreshItemCounts();
  }, [refreshItemCounts]);

  const settlementFeedback = useAiLadderSettlement(
    sessionId, session.gameState?.game_type, session.gameState?.end_result, token ?? undefined,
    String(user?.id ?? user?.username ?? 'anonymous'),
  );

  if (!session.gameState) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  const gameState = session.gameState;
  const gameTitle = `${gameState.players_info.B.name} vs ${gameState.players_info.W.name}`;
  const isGameOver = !!gameState.end_result;
  // Ranked/rated games forbid undo server-side (anti-cheat); hide the controls too.
  const isRanked = isRankedGameType(gameState.game_type);


  // Determine which color the human plays (for turn enforcement). deriveHumanColor now
  // returns null for both-human local PvP so Board lets whichever side is to move play
  // (touchscreen fallback works for BOTH colors — see the helper's both-human guard).
  const humanColor = deriveHumanColor(gameState);

  // showThinking is the single-owner gate for the "AI 思考中" surface (state A, B1.4).
  // aiColor also gates the persistent move banner above; physicalConfirming is folded
  // into showThinking already (see deriveAiTurnState) so PhysicalPlayStatusChip's 确认中
  // chip and the ai-thinking banner never stack.
  const { aiColor, showThinking } = deriveAiTurnState(gameState, visionSync.latestEvent?.type ?? null);

  // Board-loss precedence (state B + consolidation, B1.4): escalation is the ceiling —
  // PhysicalSyncEscalationDialog needs no suppression prop and always wins. Below it,
  // RecalibrationModal (pose specifically lost) takes priority over VisionSyncOverlay's
  // generic 10s "board detection abnormal" dialog: recalOpen both gates RecalibrationModal
  // itself (further suppressed `&& !escalationOpen`) AND feeds into VisionSyncOverlay's
  // suppressBoardLost, so at most one board-loss surface is ever visible at a time.
  const recalOpen = isVisionEnabled && !visionStatus.poseLocked && !isGameOver;

  // State C: force territory coloring while scoring, without mutating the user's own
  // analysisToggles selection (so the toggle panel keeps reflecting their real picks).
  const boardAnalysisToggles = isGameOver ? { ...analysisToggles, ownership: true } : analysisToggles;

  const handleAction = async (action: string) => {
    if (isRanked && ['undo', 'back', 'back-10', 'start'].includes(action)) return;
    if (action === 'resign') {
      setShowResignConfirm(true);
      return;
    }
    if (action === 'count') {
      // 数子: for human-vs-AI the backend counts immediately and ends the game (no opponent
      // handshake, no auth). Errors are usually the min-move guard or an already-finished game.
      if (!sessionId) return;
      try {
        const res = await API.requestCount(sessionId);
        if (res?.state) session.setGameState(res.state);
      } catch {
        setCountError(t('Cannot count yet (not enough moves, or the game is over)', '暂时不能数子（对局手数不足或已结束）'));
      }
      return;
    }
    void (async () => { try { await session.handleAction(action); } catch { /* surfaced by session.error */ } })();
  };

  const handleBoardMove = async (x: number, y: number) => {
    try {
      await session.onMove(x, y);
      setAiMoveBanner(null);
    } catch (e) {
      console.error(e);
      if (engineMode) setEngineErrorToast(true);
    }
  };

  const handleExit = () => {
    if (!isGameOver) {
      setShowExitConfirm(true);
    } else {
      navigate(gameState.game_type === 'ai_ladder_ranked' ? '/kiosk/play/ai/setup/ranked' : '/kiosk/play');
    }
  };

  const hintVisible =
    isVisionEnabled &&
    gameState.game_type === 'free' &&
    gameState.analysis_allowed !== false;

  const handleHint = async () => {
    if (!sessionId) return;
    try {
      setHint(await API.hint(sessionId));
    } catch (e) {
      const msg = String(e);
      setHintError(
        msg.includes('ranked_forbidden') ? t('Not available in ranked games', '升降级对局不可用')
        : msg.includes('disabled') ? t('Hint is not enabled', '支招功能未开放')
        : msg.includes('insufficient') ? t('Insufficient balance', '余额不足')
        : t('Hint failed', '支招失败，请稍后再试')
      );
    }
  };

  // 星阵隧道分析 (领地/支招/变化图) — engineMode only. Mutually exclusive: a new kind
  // replaces any prior overlay; clicking the already-active kind toggles it off.
  const handleEngineAnalysis = async (kind: EngineAnalysisKind) => {
    if (pendingEngineKind) return; // in-flight guard: ignore double-taps until the current call settles
    if (activeEngineKind === kind) {
      setActiveEngineKind(null);
      setEngineOverlay(null);
      return;
    }
    if (!sessionId || !token) return;
    // Capture the position identity at call time — if the board advances (a move
    // played) while this request is in flight, the response below is for a stale
    // position and must be discarded rather than resurrecting an old overlay.
    const requestedNodeId = session.gameState?.current_node_id;
    setPendingEngineKind(kind);
    try {
      const res = await API.platformEngineAnalysis(platform, sessionId, kind, token);
      // A settled call changed the balance (ok → one consumed; insufficient → it's 0);
      // resync the badges. Fire-and-forget, and BEFORE the stale-position early return
      // below so a discarded overlay still updates the count that was actually spent.
      void refreshItemCounts();
      if (res.ok) {
        if (session.gameState?.current_node_id !== requestedNodeId) return; // stale position — discard
        const overlay: EngineOverlay =
          kind === 'area' ? { kind: 'area', ownership: (res.data as { ownership: OwnershipPoint[] }).ownership }
          : kind === 'options' ? { kind: 'options', candidates: (res.data as { candidates: AnalysisCandidate[] }).candidates }
          : { kind: 'variation', sequence: (res.data as { sequence: AnalysisPoint[] }).sequence };
        setEngineOverlay(overlay);
        setActiveEngineKind(kind);
      } else {
        setInsufficientKind(kind);
      }
    } catch (e) {
      console.error(e);
      setEngineErrorToast(true);
    } finally {
      setPendingEngineKind(null);
    }
  };

  const ENGINE_KIND_LABEL: Record<EngineAnalysisKind, string> = {
    area: t('Territory', '领地'),
    options: t('Suggest', '支招'),
    variation: t('Variation Line', '变化图'),
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default', position: 'relative' }}>
      <Box sx={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', zIndex: 90, minWidth: 300 }}>
        <AiLadderSettlementAlert feedback={settlementFeedback} />
      </Box>
      {/* Persistent AI-move banner: physical board player needs a coordinate hint.
          Single-owner gate: vision on + an AI seat exists + a banner label is pending. */}
      {isVisionEnabled && aiColor !== null && aiMoveBanner && (
        <Box
          data-testid="ai-move-banner"
          sx={{
            position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 60,
            px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1.5,
            bgcolor: 'var(--raise2)', borderTop: '2px solid', borderColor: 'warning.main',
          }}
        >
          <Lightbulb sx={{ color: 'warning.main' }} />
          <Typography sx={{ color: 'text.primary' }}>
            {t('AI played', 'AI 已落子')} <b>{aiMoveBanner}</b> · {aiColor === 'B'
              ? t('place the black stone at the matching point on the board', '请在实体棋盘对应交叉点摆放黑子')
              : t('place the white stone at the matching point on the board', '请在实体棋盘对应交叉点摆放白子')}
          </Typography>
        </Box>
      )}

      {/* State A: AI 思考中 — jade spinner banner (design.md §5.1 state A). Single-owner
          gate via showThinking (deriveAiTurnState): suppressed for PVP (aiColor===null)
          and while the physical layer is confirming a move (move_pending), so it never
          stacks with PhysicalPlayStatusChip's 确认中 chip. Board interaction is already
          gated by playerColor={humanColor} (Board.tsx, consume-only) — no extra disable needed. */}
      {showThinking && (
        <Box data-testid="ai-thinking"
          sx={{ position: 'absolute', top: 44, left: '50%', transform: 'translateX(-50%)', zIndex: 55,
                display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 0.75, borderRadius: 2,
                bgcolor: 'var(--raise2)', border: '1px solid', borderColor: 'primary.main' }}>
          <CircularProgress size={16} sx={{ color: 'primary.main' }} />
          <Typography sx={{ color: 'primary.main' }}>{t('AI is thinking…', 'AI 思考中…')}</Typography>
        </Box>
      )}

      {/* Error display */}
      {session.error && <Alert severity="error" sx={{ mx: 2, mt: 1 }}>{session.error}</Alert>}

      {isVisionEnabled && (
        <PhysicalPlayStatusChip
          latestEvent={visionSync.latestEvent}
          currentNodeId={session.gameState?.current_node_id ?? null}
        />
      )}

      {/* State B: RecalibrationModal (pose lost). Gated `&& !escalationOpen` so the
          escalation dialog (highest-priority board-loss surface) wins — see the
          precedence comment above recalOpen. */}
      {isVisionEnabled && (
        <RecalibrationModal
          key={String(visionStatus.poseLocked)}
          open={recalOpen && !escalationOpen}
          // Intentionally inert: RecalibrationModal is not fully controlled — it owns its
          // own dismissal (local `dismissed` state set by 仍要继续/Escape/backdrop) and
          // relies on the `key` above to remount (and thus reset `dismissed`) on a fresh
          // pose-loss. GamePage has no state of its own to clear here.
          onClose={() => undefined}
        />
      )}

      {/* Header — kiosk-ui-redesign 方案A: title (left) · inline vision chips (right, no longer a
          floating overlay that collided with the buttons) · 退出. AI 支招 is folded into the
          right-panel 建议 button (GameControlPanel), so there is no standalone hint button here. */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, px: 2, py: 1, minHeight: 46 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {gameTitle}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexShrink: 0 }}>
          {isVisionEnabled && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mr: 0.5 }}>
              <Videocam titleAccess={t('Camera', '摄像头')}
                sx={{ fontSize: 20, color: visionStatus.cameraConnected ? 'success.main' : 'error.main' }} />
              <GpsFixed titleAccess={t('Calibration', '标定')}
                sx={{ fontSize: 20, color: visionStatus.poseLocked ? 'success.main' : 'warning.main' }} />
              <Lightbulb titleAccess="LED"
                sx={{
                  fontSize: 20,
                  color: visionStatus.ledConnected === false ? 'error.main'
                    : visionStatus.ledConnected ? 'success.main' : 'text.disabled',
                }} />
            </Box>
          )}
          {syncStuck && (
            <Button variant="outlined" size="small" color="warning" disabled={resyncing}
              startIcon={resyncing ? <CircularProgress size={16} color="inherit" /> : <Refresh />}
              onClick={handleResetSync}>
              {t('Re-sync', '重置识别')}
            </Button>
          )}
          <Button variant="outlined" size="small" startIcon={<ExitToApp />} onClick={handleExit}>
            {t('Exit', '退出')}
          </Button>
        </Box>
      </Box>
      {/* Board + Panel */}
      <Box sx={{ display: 'flex', flexDirection: 'row', flex: 1, overflow: 'hidden' }}>
        <Box sx={{ height: '100%', aspectRatio: '1', position: 'relative' }}>
          <Board
            gameState={gameState}
            onMove={handleBoardMove}
            analysisToggles={boardAnalysisToggles}
            playerColor={humanColor}
            engineOverlay={engineOverlay}
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <GameControlPanel
            gameState={gameState}
            onAction={handleAction}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            onToggleAnalysis={(key) => setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
            onHint={handleHint}
            hintEnabled={hintVisible}
            isGameOver={isGameOver}
            disableUndo={isRanked || !!platformPendingMove}
            engineMode={engineMode}
            activeEngineKind={activeEngineKind}
            onEngineAnalysis={handleEngineAnalysis}
            engineItemCounts={engineItemCounts}
          />
        </Box>
      </Box>

      {/* State C: 终局数子 — territory coloring is forced via boardAnalysisToggles above.
          继续对弈 ONLY flips EndgameCard's own local `dismissed` state to hide the card — the
          game stays ended (useGameSession's handleAction has no 'resume' branch; calling it
          would be a silent no-op). 确认终局 (handleExit) navigates out. `key={sessionId}`
          remounts EndgameCard fresh (dismissed=false) whenever a new session/game loads.
          DESCOPED: dead-stone dimming + red-X needs a backend dead_stones field + a
          kiosk-only overlay (Gate S) — not shipped in this cut; Board.tsx is untouched. */}
      {isGameOver && (
        <EndgameCard
          key={sessionId}
          gameState={gameState}
          t={t}
          onExit={handleExit}
          onReview={async () => {
            if (!sessionId) return;
            try {
              const { sgf } = await API.saveSGF(sessionId);
              sessionStorage.setItem('kioskReviewSgf', sgf);
              navigate('/kiosk/research');
            } catch (e) { console.error(e); setReviewError(true); }
          }}
        />
      )}

      {/* Resign confirmation (state D) */}
      <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
        <DialogTitle sx={{ color: 'text.primary' }}>{t('Confirm resign?', '确认认输？')}</DialogTitle>
        <DialogActions>
          <Button onClick={() => setShowResignConfirm(false)}>{t('Cancel', '取消')}</Button>
          <Button
            color="error"
            onClick={async () => {
              try {
                await session.handleAction('resign');
                setShowResignConfirm(false);
              } catch (error) {
                setResignError(error instanceof Error ? error.message : t('Resign failed, retry', '认输失败，请重试'));
                return;
              }
              // Finding 2 (HIGH): a CONFIRMED resign always ends the game — whether or
              // not it was reached via EngineMoveErrorDialog's 认输 button — so the
              // physical engine-error recovery dialog (if open) is now irrelevant.
              // No-op if it was never open (clearPhysicalEngineError just sets null->null).
              session.clearPhysicalEngineError();
            }}
          >
            {t('Resign', '认输')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Exit confirmation */}
      <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
        <DialogTitle>{t('Game in progress. Resign and exit?', '对局进行中，认输并退出？')}</DialogTitle>
        <DialogActions>
          <Button onClick={() => setShowExitConfirm(false)}>{t('Cancel', '取消')}</Button>
          <Button
            color="error"
            onClick={async () => {
              try {
                await session.handleAction('resign');
              } catch (error) {
                setResignError(error instanceof Error ? error.message : t('Resign failed, retry', '认输失败，请重试'));
                return;
              }
              // Same as the resign-confirm dialog above: this is another path that
              // confirms a resign, so the engine-error recovery dialog (if open) must
              // close too — no-op if it wasn't open.
              session.clearPhysicalEngineError();
              navigate('/kiosk/play');
            }}
          >
            {t('Exit', '退出')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 星阵道具次数不足 (7003) — 本终端不代充，引导去星阵充值 */}
      <Dialog open={insufficientKind !== null} onClose={() => setInsufficientKind(null)}>
        <DialogTitle>
          {insufficientKind && t('{item} exhausted', '{item}道具已用尽').replace('{item}', ENGINE_KIND_LABEL[insufficientKind])}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {insufficientKind && t(
              '{item} quota is insufficient — please recharge in the Golaxy app; this terminal cannot recharge for you.',
              '{item}次数不足 · 请在星阵 App 充值 · 本终端不代充'
            ).replace('{item}', ENGINE_KIND_LABEL[insufficientKind])}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInsufficientKind(null)}>{t('Close', '关闭')}</Button>
        </DialogActions>
      </Dialog>

      {/* Vision sync overlay — suppressBoardLost consolidates the board-loss surfaces
          (see the precedence comment above recalOpen): its own board_lost modal is
          suppressed whenever the escalation dialog OR the recalibration modal is up. */}
      {isVisionEnabled && (
        <VisionSyncOverlay
          syncEvents={visionSync.syncEvents}
          sessionId={sessionId ?? null}
          boardSize={session.gameState?.board_size?.[0] ?? 19}
          playerToMove={session.gameState?.player_to_move ?? null}
          suppressBoardLost={escalationOpen || recalOpen}
        />
      )}

      {/* AI hint panel + error */}
      {hint && <HintPanel moves={hint.moves} timeoutS={hint.timeout_s} onClose={closeHint} />}
      <Snackbar open={!!hintError} autoHideDuration={5000} onClose={() => setHintError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }} message={hintError} />

      {/* Camera disconnect toast */}
      <Snackbar open={cameraDisconnectToast} autoHideDuration={5000} onClose={() => setCameraDisconnectToast(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="warning" onClose={() => setCameraDisconnectToast(false)}>
          {t('Camera disconnected, switched to touch mode', '摄像头断开，已切换为触屏模式')}
        </Alert>
      </Snackbar>

      {/* Physical catch-up reminder toast */}
      <Snackbar
        open={reminderOpen}
        autoHideDuration={8000}
        onClose={() => setReminderOpen(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        message={t('Please place the AI stone at the lit point first', '请先将 AI 棋子摆到棋盘亮灯处')}
      />

      {/* Physical desync escape hatch */}
      <PhysicalSyncEscalationDialog
        open={escalationOpen}
        toPlace={session.physicalReminder?.to_place ?? []}
        toRemove={session.physicalReminder?.to_remove ?? []}
        onClose={() => setEscalationOpen(false)}
      />

      {/* Physical engine-move (Golaxy 隧道) bounded-retry failure — physical mode only;
          pure-screen engine games keep the existing engineErrorToast path (handleBoardMove)
          untouched. Gate the ERROR PROP (not the mount) on isVisionEnabled so the dialog
          component itself stays mounted across any isVisionEnabled flap without losing its
          local dismissed-token bookkeeping (mirrors PhysicalSyncEscalationDialog's always-
          mounted pattern). */}
      <EngineMoveErrorDialog
        error={isVisionEnabled ? session.physicalEngineError : null}
        sessionId={sessionId ?? null}
        token={token ?? undefined}
        boardSize={gameState.board_size[0]}
        reminderTick={session.awaitingRemovalReminder}
        onDismiss={session.clearPhysicalEngineError}
        onResign={() => setShowResignConfirm(true)}
      />

      {/* Count (数子) error toast */}
      <Snackbar open={!!countError} autoHideDuration={5000} onClose={() => setCountError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="warning" onClose={() => setCountError(null)}>{countError}</Alert>
      </Snackbar>
      <Snackbar open={!!resignError} autoHideDuration={5000} onClose={() => setResignError(null)}>
        <Alert severity="error" onClose={() => setResignError(null)}>{resignError}</Alert>
      </Snackbar>

      {/* Re-sync (重置识别) failure toast */}
      <Snackbar open={resyncError} autoHideDuration={5000} onClose={() => setResyncError(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setResyncError(false)}>
          {t('Re-sync failed, please retry', '重置识别失败，请重试')}
        </Alert>
      </Snackbar>

      {/* Review (复盘) save-SGF failure toast */}
      <Snackbar open={reviewError} autoHideDuration={5000} onClose={() => setReviewError(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setReviewError(false)}>
          {t('Could not open review, please retry', '无法进入复盘，请重试')}
        </Alert>
      </Snackbar>

      {/* Engine error toast */}
      <Snackbar open={engineErrorToast} autoHideDuration={6000} onClose={() => setEngineErrorToast(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setEngineErrorToast(false)}>
          {t('AI connection error — please retry your move, or exit to abandon the game.', 'AI 连接出错，请重试落子，或退出以放弃对局。')}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default GamePage;
