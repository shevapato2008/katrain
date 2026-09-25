import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar } from '@mui/material';
// TipsAndUpdates is intentionally NOT imported: the standalone header hint button is gone
// (AI 支招 is folded into the right-panel button in GameControlPanel). EmojiEvents is used
// by the endgame result card below.
// 顶条那三颗常亮状态灯(Videocam / GpsFixed)和 Refresh、ExitToApp 一起撤了 ——
// 标题与返回归页控条,状态显示归 L1 镜像栏,重置识别成了页控条上那个唯一的页级图标键。
import { EmojiEvents } from '@mui/icons-material';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board, { type EngineOverlay } from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';
import { KioskPagebar } from '../shell/KioskPagebar';
import { colsFor, rowsFor } from '../shell/goBoard';
import KioskResultBadge from '../components/game/KioskResultBadge';
import RecalibrationModal from '../components/game/RecalibrationModal';
import VisionSyncOverlay from '../components/vision/VisionSyncOverlay';
import { useVision } from '../context/VisionContext';
import { readSessionPlayOnBoard } from '../utils/playInput';
import { useVisionSync } from '../hooks/useVisionSync';
import { useTranslation } from '../../hooks/useTranslation';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';
import EngineMoveErrorDialog from '../components/physical/EngineMoveErrorDialog';
import HintPanel from '../components/physical/HintPanel';
import { API, ApiError, type HintResponse, type OwnershipPoint, type JudgePoint, type AnalysisCandidate, type AnalysisPoint, type EngineItemCounts, type GameState } from '../../api';
import { readActiveSession, writeActiveSession, clearActiveSession } from '../utils/activeSession';
import { requestFailureKind } from '../../utils/requestFailure';
import { failureLine } from '../components/report/reviewPresentation';
import { formatGtpCoord } from '../../utils/gtpCoord';
import { isRankedGameType } from '../../features/aiLadder/gameType';
import { AiLadderSettlementAlert, useAiLadderSettlement } from '../../features/aiLadder/settlement';
import { useAutoCount, autoCountEligible } from '../hooks/useAutoCount';
import { countErrorMessage } from '../utils/countErrors';
import { getCurrentKioskActivityStorage } from '../storage/kioskActivityStorage';
import { useGameCelebration } from '../hooks/useGameCelebration';

type EngineAnalysisKind = 'area' | 'options' | 'judge' | 'variation';

export interface AiTurnState {
  aiColor: 'B' | 'W' | null;
  aiThinking: boolean;
  physicalConfirming: boolean;
  showThinking: boolean;
  ladderStalled: boolean;
}

interface AiPlacementStatus {
  scopeKey: string;
  nodeId: number;
  text: string;
}

// Single-color human-seat derivation, shared by humanColor (turn enforcement / board
// gating) and the AI-placement status effect below (G2 fix). `platform_engine_color`
// (Task 1: WebKaTrain state field, "B"|"W"|null = the remote engine's color) is
// authoritative for engine games (Golaxy 人机对弈 via the genmove tunnel) — BOTH
// seats carry a bare "human" player_type literal there (`create_multiplayer_session`'s
// two update_player calls in session.py), so the
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

// kiosk 按整局终局事实冻结；旧服务端回退到游标结果。
const endResultOf = (gs: GameState): string | null => gs.end_result || gs.terminal_result || null;

const readScreenFallback = (key: string): boolean => {
  try { return sessionStorage.getItem(key) === '1'; } catch { return false; }
};

// Single-owner AI-turn arbitration (state A source for B1.4). Exported as a pure
// function so it's unit-testable without rendering the page, and so B1.4 can reuse it.
// Per-color AI detection — accept BOTH literals: 'player:ai' (kiosk HvAI, server.py:723/727)
// AND bare 'ai' (multiplayer `create_multiplayer_session` + tests), PLUS the engine's color per
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
  const aiThinking = !!aiColor && gameState.player_to_move === aiColor
    && !(endResultOf(gameState) && !gameState.awaiting_count);
  // One owner for the AI-turn indicator: while the physical layer is confirming a
  // move (chip shows 确认中), suppress the 思考中 banner so they never stack.
  const physicalConfirming = latestEventType === 'move_pending';
  // A 升降级对弈 AI that refused to move is NOT thinking, and no move is coming. Saying
  // "AI 思考中…" over a permanently stalled turn is the loading state lying about a
  // failure; the banner below says what actually happened instead.
  const ladderStalled = aiThinking && !!gameState.last_ladder_error;
  const showThinking = aiThinking && !physicalConfirming && !ladderStalled;
  return { aiColor, aiThinking, physicalConfirming, showThinking, ladderStalled };
}

interface EndgameCardProps {
  gameState: GameState;
  t: (key: string, fallback?: string) => string;
  onExit: () => void;
  onReview: () => void;
  celebrating: boolean;
  /** 升降级对弈 only: what this game did to the player's rank. null while it is
      still being fetched, and on every non-ladder game. */
}

// State C (design.md §5.1): result card + score breakdown + territory coloring (forced via
// GamePage's boardAnalysisToggles). 留在棋盘 only hides this card via LOCAL `dismissed` state —
// the game stays ended; useGameSession.handleAction has no 'resume' branch, so it is
// deliberately never called here. 确认终局 calls the `onExit` prop (GamePage's handleExit).
// `dismissed` is local rather than lifted to GamePage/reset via a useEffect, because GamePage
// remounts this component with `key={sessionId}` on every new session/game (React's
// "reset state via key" pattern — https://react.dev/learn/you-might-not-need-an-effect —
// avoids a useEffect + setState, keeping this repo's react-hooks/set-state-in-effect gate clean).
// DESCOPED: dead-stone dimming + red-X needs a backend dead_stones field + a kiosk-only
// overlay (Gate S); not shipped in this cut, and shared Board.tsx is left untouched.
const EndgameCard = ({ gameState, t, onExit, onReview, celebrating }: EndgameCardProps) => {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <Box data-testid="endgame-card" sx={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 70,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, px: 3, py: 2, borderRadius: 3,
          bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
      <EmojiEvents data-testid="result-trophy" className={celebrating ? 'game-win-trophy' : undefined}
        sx={{ color: 'primary.main', fontSize: 32 }} />
      <KioskResultBadge result={endResultOf(gameState)!} rules={gameState.ruleset} />
      {gameState.game_type === 'ai_ladder_ranked' && /^[BW]\+\d/.test(endResultOf(gameState) ?? '') && (
        <Typography variant="caption" sx={{ color: 'text.secondary', textAlign: 'center' }}>
          {t('game:ranked_ai_adjudication', '未完成棋盘由云端 AI 按中国规则估分判定')}
        </Typography>
      )}
      {/* 未识别的平台终局哨兵仍以无胜负 `Void` 收口；已知的停一手和认输会走各自语义。 */}
      {endResultOf(gameState) === 'Void' && gameState.platform_engine_color && (
        <Typography
          variant="caption"
          data-testid="endgame-no-result"
          sx={{ color: 'text.secondary', textAlign: 'center', maxWidth: 320 }}
        >
          {t('game:engine_ended_no_result', '星阵返回了无法识别的终局信号 · 这盘不判断输赢')}
        </Typography>
      )}
      {/* Score breakdown — komi + captures only (display only). Full territory-adjusted
          目/子 breakdown needs dead-stone data from the backend; deferred (Gate S). */}
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {t('Komi', '贴目')} {gameState.komi} · {t('Captures', '提子')} {t('game:black_short', '黑')} {gameState.prisoner_count.B} / {t('game:white_short', '白')} {gameState.prisoner_count.W}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1.5 }}>
        <Button variant="outlined" onClick={() => setDismissed(true)}>{t('game:stay_on_board', '留在棋盘')}</Button>
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
  const { token, user, isAuthenticated } = useAuth();
  const session = useGameSession({ token: token ?? undefined, deferMoveSoundUntilPaint: true });
  const [analysisToggles, setAnalysisToggles] = useState(() => ({
    ownership: false,
    hints: false,
    numbers: false,
    coords: true,
    score: true,
  }));

  const [showResignConfirm, setShowResignConfirm] = useState(false);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  // 升降级结算: what this game did to the player's rank. Asked once, when the game
  // ends, and only for a server-issued ladder game. The answer comes from the
  // server rather than from diffing two /api/ladder/me reads, because a game that
  // did not score has to be able to say so.
  const [aiPlacementStatus, setAiPlacementStatus] = useState<AiPlacementStatus | null>(null);
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
  const [timeoutError, setTimeoutError] = useState<{ scope: string; message: string } | null>(null);
  const timeoutRequestRef = useRef(false);
  const timeoutAttemptRef = useRef<{
    key: string; checks: number; retries: number; timer: number | null;
  } | null>(null);
  const timeoutState = session.gameState;
  const timeoutScope = `${sessionId}|${timeoutState?.game_id}|${timeoutState?.current_node_id}|${timeoutState?.player_to_move}|${timeoutState?.end_result}|${timeoutState?.terminal_result}|${timeoutState?.children?.length}|${timeoutState?.last_ladder_error}|${timeoutState?.game_type}|${timeoutState ? deriveHumanColor(timeoutState) : ""}`;
  const sessionIsGameOver = !!timeoutState && !!endResultOf(timeoutState) && !timeoutState.awaiting_count;
  useEffect(() => () => {
    const attempt = timeoutAttemptRef.current;
    if (attempt?.timer != null) window.clearTimeout(attempt.timer);
    timeoutAttemptRef.current = null;
  }, [timeoutScope]);

  // 终局是权威状态：若倒计时恰好落在「退出确认」已打开期间，不能留下看似还可继续下的旧弹窗。
  // This must stay above the loading return so the first game-state update never changes
  // GamePage's Hook sequence (a production build otherwise leaves the kiosk black).
  useEffect(() => {
    if (sessionIsGameOver) setShowExitConfirm(false);
  }, [sessionIsGameOver]);

  const [countError, setCountError] = useState<string | null>(null);
  // A12:数子可能要等几秒(当前手没有分数时服务端先补一次分析,上限 15 秒)。
  // ref 挡同一帧里的连点(state 要等下一次渲染才看得见),state 负责屏上那句「正在数子…」。
  const countingRef = useRef(false);
  const [counting, setCounting] = useState(false);
  const [resignError, setResignError] = useState<string | null>(null);
  const [gameGoneAcknowledged, setGameGoneAcknowledged] = useState(false);
  const sessionGone = session.connectionLost === 'gone';

  // 一个信号,一处反应。三条通道(WS 关闭 / 404 / 200 session_gone)都汇进 `connectionLost`,
  // 所以这里不用关心是哪条先发现的。清 resume 指针**只在这一支**做:这局在服务端确实没了,
  // 不清的话「继续上一局」会转回这个死会话。
  useEffect(() => {
    if (!sessionGone) return;
    setShowExitConfirm(false);
    setShowResignConfirm(false);
    clearActiveSession('game');
  }, [sessionGone]);

  const [reviewError, setReviewError] = useState(false);
  // 重置识别的「在制中」走 ref 不走 state:页控条那个图标键没有忙碌态可显示,
  // 这个值不进渲染 —— 放进 state 就是一次没人看的重渲染。
  const resyncingRef = useRef(false);
  const [resyncError, setResyncError] = useState(false);
  const [connectionNoticeDismissed, setConnectionNoticeDismissed] = useState(false);

  // Golaxy 人机对弈 is the only engine-play platform today (§13). Revisit if/when
  // another platform gets engine-play analysis tunnels.
  const platform = 'golaxy';
  const [engineOverlay, setEngineOverlay] = useState<EngineOverlay | null>(null);
  const [engineEvaluation, setEngineEvaluation] = useState<{ winrate: number; delta: number } | null>(null);
  const [activeEngineKind, setActiveEngineKind] = useState<EngineAnalysisKind | null>(null);
  const [insufficientKind, setInsufficientKind] = useState<EngineAnalysisKind | null>(null);
  // In-flight guard: a touchscreen double-tap must not fire two paid 星阵 analysis
  // calls before the first resolves (double quota spend + last-response-wins races).
  // Does NOT gate insufficientKind — that dialog is user-dismissed, not auto-cleared.
  const engineAnalysisPendingRef = useRef(false);
  const enginePositionKey = `${sessionId}|${session.gameState?.game_id}|${session.gameState?.current_node_id}|${session.gameState?.end_result}|${session.gameState?.terminal_result}`;
  const enginePositionRef = useRef(enginePositionKey);
  enginePositionRef.current = enginePositionKey;
  // Remaining-uses badges (领地N/支招N/变化图N). null until the first fetch resolves → "—".
  const [engineItemCounts, setEngineItemCounts] = useState<EngineItemCounts | null>(null);

  // refreshStatus drives the 重置识别 recovery button clearing immediately on success.
  const { visionStatus, isVisionEnabled, refreshStatus } = useVision();

  // ── 这一局到底落在哪儿 ────────────────────────────────────────────────
  // **`isVisionEnabled` 只是设备那一段。** 2026-08-23 起开局设置屏上有一颗真的
  // 「屏幕 / 实体盘」,偏好存在 `utils/playInput.ts`;这一屏下面**每一处**实体盘 UI
  // (识别绑定、AI 落子横幅、重标定弹层、硬件故障条、重置识别键、识别浮层、
  // 引擎落子错误弹层)认的都得是**两段之和**,不是设备那一段。
  //
  // 偏好只在**挂载时读一次**:这一局落在哪儿是开局那一刻定的(开局设置屏上写着
  // 「开局后不可改」),中途跟着 localStorage 变会把人从一块已经摆着子的盘上赶下来。
  // 路数同理并进来 —— 盒子上那块盘是 19 路的,9 路 / 13 路的局本来就落不到盘上,
  // 而开局设置屏正是这么答的,两边不能给出两个答案。
  // 开局那一刻定下的值优先(见 `readSessionPlayOnBoard`),与 `PlayInputGuard` 读同一个函数。
  // 回落分支保留今天的三段式:从房间 / 跨平台引擎进来的局没有开局屏写下的 onBoard。
  const { pathname } = useLocation();
  const [playOnBoard] = useState(() => readSessionPlayOnBoard(pathname));
  // 本局降级刷新后仍保留；路由复用 GamePage 时，降级与锁定历史都不能带进下一局。
  const screenFallbackKey = `kiosk_screen_fallback:${sessionId ?? ''}`;
  const [physicalSession, setPhysicalSession] = useState(() => ({
    sessionId, screenFallback: readScreenFallback(screenFallbackKey), poseEverLocked: false,
  }));
  if (physicalSession.sessionId !== sessionId) {
    setPhysicalSession({ sessionId, screenFallback: readScreenFallback(screenFallbackKey), poseEverLocked: false });
  }
  const fallBackToScreen = useCallback(() => {
    try { sessionStorage.setItem(screenFallbackKey, '1'); } catch { /* 本页仍降级，刷新后可能无法保留 */ }
    setPhysicalSession((previous) => ({ ...previous, screenFallback: true }));
  }, [screenFallbackKey]);
  const physicalPlay = !physicalSession.screenFallback && isVisionEnabled
    && playOnBoard.onBoard
    && (playOnBoard.fromSession || (session.gameState?.board_size?.[0] ?? 19) === 19);
  const poseEverLocked = physicalSession.poseEverLocked;
  // 初次等待识别不是棋盘移动；只在本 session 锁定过之后提醒。
  if (physicalSession.sessionId === sessionId && physicalPlay && visionStatus.poseLocked && !poseEverLocked) {
    setPhysicalSession({ ...physicalSession, poseEverLocked: true });
  }
  const visionSync = useVisionSync(physicalPlay ? sessionId ?? null : null);

  // Exact-board acknowledgements can race the game-state WebSocket in either order.
  // Keep a small versioned cache and consume the vision stream by monotonic `seq`
  // rather than array position (the hook trims its rolling window at 100 events).
  const acknowledgedNodeIdsRef = useRef(new Set<number>());
  const acknowledgedNodeOrderRef = useRef<number[]>([]);
  const lastProcessedVisionSeqRef = useRef<number | null>(null);
  const ignoredVisionEventsRef = useRef<typeof visionSync.syncEvents | null>(null);
  const staleGameStateAfterSessionChangeRef = useRef<GameState | null>(null);
  const visionBindingKey = physicalPlay ? sessionId ?? null : null;
  const visionBindingKeyRef = useRef(visionBindingKey);
  const visionConnectedRef = useRef(visionSync.connected);

  useEffect(() => {
    const bindingChanged = visionBindingKeyRef.current !== visionBindingKey;
    const reconnected = visionConnectedRef.current === false && visionSync.connected === true;
    if (bindingChanged || reconnected) {
      acknowledgedNodeIdsRef.current.clear();
      acknowledgedNodeOrderRef.current = [];
      if (bindingChanged) {
        const changedBetweenSessions = visionBindingKeyRef.current !== null && visionBindingKey !== null;
        lastProcessedVisionSeqRef.current = null;
        // useVisionSync clears its list after a binding change. Ignore this render's
        // previous-binding array so an old acknowledgement cannot leak into the new session.
        ignoredVisionEventsRef.current = visionSync.syncEvents;
        staleGameStateAfterSessionChangeRef.current = changedBetweenSessions ? session.gameState : null;
        setAiPlacementStatus(null);
      }
    }
    visionBindingKeyRef.current = visionBindingKey;
    visionConnectedRef.current = visionSync.connected;
  }, [visionBindingKey, visionSync.connected, visionSync.syncEvents]);

  useEffect(() => {
    if (visionSync.syncEvents === ignoredVisionEventsRef.current) return;
    ignoredVisionEventsRef.current = null;

    const newEvents = visionSync.syncEvents
      .filter((event) => typeof event.seq === 'number'
        && (lastProcessedVisionSeqRef.current === null || event.seq > lastProcessedVisionSeqRef.current))
      .sort((a, b) => a.seq - b.seq);
    for (const event of newEvents) {
      lastProcessedVisionSeqRef.current = event.seq;
      const expectedNodeId = event.type === 'synced' ? event.data.expected_node_id : undefined;
      if (typeof expectedNodeId !== 'number') continue;
      if (!acknowledgedNodeIdsRef.current.has(expectedNodeId)) {
        acknowledgedNodeIdsRef.current.add(expectedNodeId);
        acknowledgedNodeOrderRef.current.push(expectedNodeId);
        while (acknowledgedNodeOrderRef.current.length > 128) {
          const expired = acknowledgedNodeOrderRef.current.shift();
          if (expired !== undefined) acknowledgedNodeIdsRef.current.delete(expired);
        }
      }
      setAiPlacementStatus((current) => current?.nodeId === expectedNodeId ? null : current);
    }
  }, [visionSync.syncEvents]);

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
    if (endResultOf(gs) && !gs.awaiting_count) { clearActiveSession('game'); return; }
    const route = window.location.pathname;
    const previous = readActiveSession('game');
    writeActiveSession({
      kind: 'game',
      label: `${gs.players_info.B.name} vs ${gs.players_info.W.name}`,
      route,
      ts: Date.now(),
      ...(previous?.route === route && typeof previous.onBoard === 'boolean' ? { onBoard: previous.onBoard } : {}),
    });
  }, [session.gameState?.current_node_id, session.gameState?.end_result, session.gameState?.terminal_result, sessionId]);

  // 没有取到局面且请求失败时，清掉失效的「继续上一局」入口。
  // 已有局面后的连接错误由对局屏处理，不切换成打不开状态。
  const loadFailed = !session.gameState && !!session.error;
  useEffect(() => {
    if (loadFailed) clearActiveSession('game');
  }, [loadFailed]);

  // AI move placement instruction. Keep scope, causal node and text together so a
  // late render from another game/session can never surface stale coordinates.
  useEffect(() => {
    if (!physicalPlay || !session.gameState) {
      setAiPlacementStatus(null);
      return;
    }
    const gs = session.gameState;
    if (gs === staleGameStateAfterSessionChangeRef.current) {
      setAiPlacementStatus(null);
      return;
    }
    staleGameStateAfterSessionChangeRef.current = null;
    const human = deriveHumanColor(gs);
    const ai = deriveAiTurnState(gs, null).aiColor;
    if (!gs.last_move || endResultOf(gs) || !human || !ai || gs.player_to_move !== human) {
      setAiPlacementStatus(null);
      return;
    }
    const nodeId = gs.current_node_id;
    if (acknowledgedNodeIdsRef.current.has(nodeId)) {
      setAiPlacementStatus((current) => current?.nodeId === nodeId ? null : current);
      return;
    }
    const scopeKey = `${sessionId ?? ''}|${gs.game_id}`;
    const coord = formatGtpCoord(gs.last_move[0], gs.last_move[1], gs.board_size[0]);
    const text = `${t('AI played', 'AI 已落子')} ${coord} · ${ai === 'B'
      ? t('place the black stone at the matching point on the board', '请在实体棋盘对应交叉点摆放黑子')
      : t('place the white stone at the matching point on the board', '请在实体棋盘对应交叉点摆放白子')}`;
    setAiPlacementStatus((current) => current?.scopeKey === scopeKey && current.nodeId === nodeId && current.text === text
      ? current
      : { scopeKey, nodeId, text });
  }, [physicalPlay, session.gameState?.current_node_id, session.gameState?.game_id,
    session.gameState?.end_result, session.gameState?.terminal_result, sessionId, t]);

  // Camera disconnect fallback
  useEffect(() => {
    if (physicalPlay && !visionStatus.cameraConnected) {
      setCameraDisconnectToast(true);
    }
  }, [physicalPlay, visionStatus.cameraConnected]);

  // Invalidate the 星阵 analysis overlay when the board position advances (a move
  // played, human or AI) — otherwise stale 领地/支招/变化图 markers keep drawing over
  // the new position and the button stays stuck "active". Keyed on position identity
  // only, so it never fires on unrelated re-renders. Does NOT touch insufficientKind —
  // that dialog is dismissed by the user, not by position changes. engineMode only.
  useEffect(() => {
    setEngineOverlay(null);
    setEngineEvaluation(null);
    setActiveEngineKind(null);
  }, [enginePositionKey]);

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
    if (engineMode && physicalPlay && prevKind === 'options' && activeEngineKind !== 'options') {
      API.hintDismiss().catch(() => undefined);
    }
  }, [activeEngineKind, engineMode, physicalPlay]);

  // Local free-play on-demand analysis for 领地(ownership)/图表(winrate/score). Board mode
  // suppresses per-move auto-eval, so the current position has no analysis until we ask.
  // Trigger when either toggle is on, and re-trigger when the current node changes. The
  // result streams back over the game WebSocket (get_state broadcast). Ranked/rated games
  // block this server-side (analysis_allowed). Not used in engineMode (star阵 tunnel instead).
  // 本地双人局虽然不展示分析控件，数子仍读取同一份后台分析结果；因此图表默认开启时
  // 也继续请求当前手分析。界面是否展示胜率块由 GameControlPanel 独立决定。
  const wantAnalysis = analysisToggles.ownership || analysisToggles.score;
  const gs = session.gameState;
  useEffect(() => {
    if (engineMode || !wantAnalysis || !sessionId || !gs) return;
    if (isRankedGameType(gs.game_type)) return;
    // 无人认领的会话:服务端**算了但不交付**(`analysis_delivered`)。开关那边已经灰了,
    // 这里再早退一次是因为**这条 `.catch(() => undefined)` 会把失败整个吞掉** ——
    // 不早退的话,每换一手就往一个注定拿不回结果的端点打一发,屏上和日志里都没有痕迹。
    if (gs.analysis_delivered === false) return;
    API.analyzeCurrent(sessionId).catch(() => undefined);
  }, [engineMode, wantAnalysis, sessionId, gs?.current_node_id, gs?.game_type, gs?.analysis_delivered]);

  // 双 pass 之后自动数子(v2-design §3.4)。只给本地对局与人机自由对弈(`autoCountEligible`);
  // 判据取服务端下发的 `awaiting_count`,前端不自己数 pass。
  const autoCount = useAutoCount({
    sessionId,
    awaitingCount: !!gs && !!gs.awaiting_count && autoCountEligible(gs, engineMode),
    nodeId: gs?.current_node_id,
    onState: session.setGameState,
  });

  const closeHint = useCallback(() => {
    setHint(null);
    API.hintDismiss().catch(() => undefined);
  }, []);

  // Always-available fallback when vision sync gets stuck (blue-LED / 确认中 deadlock):
  // re-baseline to the digital board, drop the stuck removal, resume detection. Refresh
  // status on success so the button clears immediately instead of after the ≤3s poll;
  // surface a failure instead of silently swallowing it.
  const handleResetSync = useCallback(async () => {
    if (resyncingRef.current) return;   // 双击守卫:页控条那个图标键没有忙碌态可显示
    resyncingRef.current = true;
    try {
      await API.visionResetSync();
      await refreshStatus();
    } catch {
      setResyncError(true);
    } finally {
      resyncingRef.current = false;
    }
  }, [refreshStatus]);

  // 「卡了 10 秒才把重置识别键放出来」那一整套(`stuckEligible` + `syncStuck` 计时器)撤了:
  // 它存在的唯一理由是「别在例行拍照时闪一个警告按钮」—— 而现在这个键不是警告,是页控条上
  // 常驻的那个页级图标键(§11),实体模式下一直在。**必须先卡住一次才能自救**是上一版的形状。
  // Remaining-道具 counts for the button badges. Account-level (not per-game),
  // so it's safe to fetch once on mount and re-fetch after each analysis settles
  // (each call consumes a use; 7003 means it hit 0). Best-effort: a failed fetch
  // leaves the prior counts (or null → "—") and never blocks play.
  const refreshItemCounts = useCallback(async () => {
    if (!engineMode || !isAuthenticated) return;
    try {
      setEngineItemCounts(await API.platformEngineItems(platform, token));
    } catch (e) {
      console.error(e);
    }
  }, [engineMode, isAuthenticated, token]);

  useEffect(() => {
    void refreshItemCounts();
  }, [refreshItemCounts]);

  const settlementFeedback = useAiLadderSettlement(
    sessionId, session.gameState?.game_type, session.gameState?.end_result, token ?? undefined,
    String(user?.id ?? user?.username ?? 'anonymous'),
  );
  const celebrating = useGameCelebration(
    sessionId, session.gameState, session.gameState ? deriveHumanColor(session.gameState) : null,
  );

  if (!session.gameState) {
    // 盒上全屏没有浏览器后退入口，加载中和加载失败都要能回到对弈。
    return (
      <Box
        data-testid={loadFailed ? 'game-unavailable' : 'game-loading'}
        sx={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 2, height: '100%', px: 4, textAlign: 'center',
        }}
      >
        {loadFailed ? (
          <>
            <Typography sx={{ color: 'text.primary', fontSize: 18, fontWeight: 600 }}>
              {t('game:unavailable_title', '这一局已经打不开了')}
            </Typography>
            <Typography sx={{ color: 'text.secondary', fontSize: 14, maxWidth: 520 }}>
              {t('game:unavailable_reason', '可能是盒子重启过、这一局闲置太久被清理，或者它属于另一个账号。')}
            </Typography>
          </>
        ) : (
          <CircularProgress />
        )}
        <button type="button" className="kiosk-btn kiosk-btn--secondary" onClick={() => navigate('/kiosk/play')}>
          {t('game:back_to_play', '回到对弈')}
        </button>
      </Box>
    );
  }

  const gameState = session.gameState;
  const isGameOver = !!endResultOf(gameState) && !gameState.awaiting_count;
  // 本地对局(两个人面对面):退出 = 删会话不存谱;认输要说是哪一方(v2 D2)。
  const localGame = gameState.game_type === 'pvp_local';
  const boardSize = gameState.board_size[0];
  // 超时判负后(spec §3.3 步骤 3):`end_result` 由 `_do_timeout` 写成 `{赢家}+T`
  // (`current_node.player` = 上一手落子方 = 赢家,见 `interface.py:_do_timeout`)。
  // 只在本地对局说这句话 —— Global Constraints #1:钟/超时判负只对 `pvp_local` 生效。
  const timeoutResult = localGame && isGameOver && gameState.end_result?.endsWith('+T') ? gameState.end_result : null;
  const timeoutWinnerColor = (timeoutResult?.[0] as 'B' | 'W' | undefined) ?? null;
  const timeoutLoserColor = timeoutWinnerColor === 'B' ? 'W' : timeoutWinnerColor === 'W' ? 'B' : null;

  // 页控条标题 = **这一局是哪种对弈**,不是「张三 vs KataGo」。
  // 名字在玩家卡里各占一行(还带段位、执色、提子),标题再写一遍是把 460 宽的一行
  // 花在已经能看见的东西上;而「自由对弈 / 升降级对弈」是这一屏唯一说不出别处的事
  // (悔棋能不能用、胜率图有没有,全跟它走)。
  const gameTitle = engineMode ? t('game:golaxy_ai', '星阵围棋 · 人机')
    : gameState.game_type === 'ai_ladder_ranked' ? t('Ranked Game', '升降级对弈')
    : gameState.game_type === 'pvp_local' ? t('game:local_pvp', '本地对局')
    : gameState.game_type === 'pvp_online' ? t('game:online_pvp', '在线对局')
    : t('Free Game', '自由对弈');
  // 副标 = **开局时定死的那几条**(路数 / 规则 / 贴目 / 让子)。它们不是过程量,
  // 写在这里一次就够,不必像上一版那样占一整条 `Game info bar`。
  const gameSetupLine = [
    t('game:board_lines', '{n} 路').replace('{n}', String(boardSize)),
    `${t(gameState.ruleset, gameState.ruleset)} ${t('Rules', '规则')}`,
    `${t('Komi', '贴目')} ${gameState.komi}`,
    gameState.handicap > 0
      ? t('game:handicap_n', '让 {n} 子').replace('{n}', String(gameState.handicap))
      : t('game:no_handicap', '不让子'),
  ].join(' · ');
  // Ranked/rated games forbid undo server-side (anti-cheat); hide the controls too.
  const isRanked = isRankedGameType(gameState.game_type);

  // A12:数子失败**按服务端给的原因**说话。从前一律「对局手数不足或已结束」,
  // 把盒上最常见的「这一手还没有分数」也说成了手数不够。
  const countFailureMessage = (message: string) =>
    message.includes('Cannot count before') ? t('game:count_too_early', '手数还不够，暂时不能数子')
    : message.includes('already over') ? t('game:count_game_over', '这一局已经结束了')
    : message.includes('Position changed') ? t('game:count_position_changed', '数子这几秒里局面变了，请重新数子')
    : message.includes('only allowed on the human turn') ? t('game:count_not_your_turn', '轮到你落子时才能数子')
    : message.includes('Analysis not available') ? (isRanked
      ? t('game:count_ranked_unscored', '升降级对局现在数不了子（本局不做形势分析）')
      : t('game:count_no_score', '形势分析没算出来，暂时数不了子，请稍后再试'))
    /* `game:count_failed` 在 cn PO 里是「数子没有完成」—— 那是下面状态条上那个**标签**
       (`:905` 在用),不是这里要说的**带重试建议的报错**。复用的话翻译表赢,
       屏上把「请稍后再试」吃掉。另铸一个键。 */
    : t('game:count_failed_retry', '数子没有成功，请稍后再试');


  // Determine which color the human plays (for turn enforcement). deriveHumanColor now
  // returns null for both-human local PvP so Board lets whichever side is to move play
  // (touchscreen fallback works for BOTH colors — see the helper's both-human guard).
  const humanColor = deriveHumanColor(gameState);
  const handleClockExpired = (color: 'B' | 'W') => {
    if (!sessionId || isGameOver || gameState.player_to_move !== color || gameState.children.length > 0) return;
    if (gameState.last_ladder_error || (isRanked && humanColor !== color)) return;
    const key = `${gameState.game_id}|${gameState.current_node_id}|${color}`;
    if (timeoutAttemptRef.current?.key === key) return;
    const attempt = { key, checks: 1, retries: 0, timer: null as number | null };
    timeoutAttemptRef.current = attempt;
    const expect = { expected_game_id: gameState.game_id, expected_node_id: gameState.current_node_id, color };
    const current = () => timeoutAttemptRef.current === attempt;
    const later = (ms: number) => {
      attempt.timer = window.setTimeout(() => { if (current()) void send(); }, ms);
    };
    const retryDelivery = () => {
      if (!current()) return;
      const delay = [2000, 5000, 10000][attempt.retries++];
      if (delay !== undefined) later(delay);
      else setTimeoutError({ scope: timeoutScope, message: t('game:timeout_not_delivered', '超时判定没有送达，请检查连接后重新进入这一局') });
    };
    const send = async (): Promise<void> => {
      if (!current()) return;
      try {
        const res = await API.timeout(sessionId, token ?? undefined, expect);
        if (!current()) return;
        // Task 2's 200 空回执：这局在服务端已经没了。retryDelivery 重发救不回一个被
        // 回收的会话 —— 落到这里必须直接报出去,不能再走下面的 setTimeoutError(null)
        // (那条路以前只在真的送达成功时才走,现在会把「没了」悄悄当成「送达了」)。
        // `'status' in res` alone is the complete discriminant: SessionResponse never
        // has a `status` key, and `'session_gone'` is the only value SessionGoneResponse
        // ever carries. Adding `&& res.status === 'session_gone'` here defeats TS's
        // narrowing on the fall-through branch below (verified against tsc directly).
        if ('status' in res) {
          session.reportSessionGone();
          return;
        }
        if (res.state) session.setGameState(res.state);
        setTimeoutError(null);
      } catch (e) {
        if (!current()) return;
        if (e instanceof ApiError && (e.status === 409 || e.status === 403)) {
          try {
            const fresh = await API.getState(sessionId, token ?? undefined);
            if (!current()) return;
            if (fresh?.state) session.setGameState(fresh.state);
            if (e.message.includes('clock_not_expired') && attempt.checks < 2) {
              attempt.checks += 1;
              later(1000);
            }
          } catch { retryDelivery(); }
        } else retryDelivery();
      }
    };
    setTimeoutError(null);
    void send();
  };

  // 本地双人局沿用 v2 的简单契约：钟到点后发一次无绑定 timeout，由后端在锁内按
  // 当前局面和权威时钟核实。409/time_not_expired 带回的新状态直接用于重算；真正的
  // 网络或服务错误才提示失败。GameControlPanel 会在钟仍停在 00:00 时隔 5 秒再触发。
  const handleTimeExpired = async () => {
    if (!sessionId || timeoutRequestRef.current) return;
    timeoutRequestRef.current = true;
    try {
      const res = await API.timeout(sessionId);
      // Same gone shape as the bound-timeout `send()` above: no `.state`, and retrying
      // cannot bring an evicted session back. Report it and stop — do not clear
      // timeoutError as if the timeout had been delivered.
      if ('status' in res) {
        session.reportSessionGone();
        return;
      }
      if (res.state) session.setGameState(res.state);
      setTimeoutError(null);
    } catch (error) {
      const detail = error instanceof ApiError && error.status === 409
        ? (error.detail as { code?: string; state?: GameState } | undefined)
        : undefined;
      if (detail?.code === 'time_not_expired' && detail.state) {
        session.setGameState(detail.state);
      } else {
        setTimeoutError({ scope: timeoutScope, message: failureLine(t('game:timeout_failed', '超时判定没有完成'), requestFailureKind(error), t) });
      }
    } finally {
      timeoutRequestRef.current = false;
    }
  };

  // 本地双人局按轮到落子的一方认输，人机局始终按人的座位认输。
  const bothHuman = gameState.players_info.B.player_type === 'player:human'
    && gameState.players_info.W.player_type === 'player:human';
  const resignSide = gameState.player_to_move === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方');
  const resignTitle = bothHuman
    ? t('game:resign_confirm_side', '{side}认输？').replace('{side}', resignSide)
    : t('Confirm resign?', '确认认输？');
  const exitResignTitle = bothHuman
    ? t('game:exit_resign_confirm_side', '对局进行中，{side}认输并退出？').replace('{side}', resignSide)
    : t('Game in progress. Resign and exit?', '对局进行中，认输并退出？');

  // showThinking is the single-owner gate for the "AI 思考中" surface (state A, B1.4).
  // aiColor also gates the physical placement status; physicalConfirming is folded
  // into showThinking already (see deriveAiTurnState) so PhysicalPlayStatusChip's 确认中
  // chip and the ai-thinking banner never stack.
  const { aiColor, showThinking, ladderStalled } = deriveAiTurnState(
    gameState,
    visionSync.latestEvent?.type ?? null,
  );
  const placementScopeKey = `${sessionId ?? ''}|${gameState.game_id}`;
  const physicalStatus = physicalPlay && aiColor !== null && aiPlacementStatus?.scopeKey === placementScopeKey
    ? aiPlacementStatus.text
    : null;

  // Board-loss precedence (state B + consolidation, B1.4): escalation is the ceiling —
  // PhysicalSyncEscalationDialog needs no suppression prop and always wins. Below it,
  // RecalibrationModal (pose specifically lost) takes priority over VisionSyncOverlay's
  // generic 10s "board detection abnormal" dialog: recalOpen both gates RecalibrationModal
  // itself (further suppressed `&& !escalationOpen`) AND feeds into VisionSyncOverlay's
  // suppressBoardLost, so at most one board-loss surface is ever visible at a time.
  const recalOpen = physicalPlay && poseEverLocked && !visionStatus.poseLocked && !isGameOver;

  // State C: force territory coloring while scoring, without mutating the user's own
  // analysisToggles selection (so the toggle panel keeps reflecting their real picks).
  const boardAnalysisToggles = isGameOver ? { ...analysisToggles, ownership: true } : analysisToggles;

  // 刻度带的字。`坐标` 关掉时给空数组 —— **带还在,只是没字**(撤了带落子区会从 460 跳成 516)。
  const rulerCols = analysisToggles.coords ? colsFor(boardSize) : [];
  const rulerRows = analysisToggles.coords ? rowsFor(boardSize) : [];

  // 硬件故障那一句。上一版是顶条上**三颗常亮的灯**;§5 说状态显示归 L1 镜像栏,L3 上没它们的位置。
  // 但「LED 掉线」在这一屏原来只有那颗灯说得出来 —— 撤了灯就等于撤了唯一的信号,那不行。
  // ⇒ 只在**真出故障时**说一句,落在开关排右端那个本来就用来解释「为什么它是灰的」的位置,
  //    平时不占地方。三条的优先级按「不修就没法下」排:摄像头 > 标定 > LED。
  //    `ledConnected === null` 是**后端没说**,不是「没连上」—— 不报(见 `GoConsoleRail`)。
  const hardwareFault = !physicalPlay ? null
    : visionStatus.cameraConnected === false ? t('vision:camera_down', '摄像头未连接 · 已转触屏')
    : poseEverLocked && visionStatus.poseLocked === false ? t('vision:pose_lost', '标定丢失 · 请重新标定')
    : visionStatus.ledConnected === false ? t('vision:led_down', 'LED 未连接 · 不再亮灯引导')
    : null;

  const handleAction = async (action: string) => {
    if (isRanked && ['undo', 'back', 'back-10', 'start'].includes(action)) return;
    if (action === 'resign') {
      setShowResignConfirm(true);
      return;
    }
    if (action === 'count') {
      // 数子:人机 / 本地对局由服务端当场数完并结束对局(没有对手握手)。
      if (!sessionId || countingRef.current) return;
      countingRef.current = true;
      setCountError(null);
      setCounting(true);
      try {
        const res = await API.requestCount(sessionId);
        if (res?.state) session.setGameState(res.state);
      } catch (error) {
        // 结构化原因来自本地对局 v2；旧服务端/统一终局冲突仍由字符串回退覆盖。
        setCountError(error instanceof ApiError
          ? countErrorMessage(error, t)
          : countFailureMessage(error instanceof Error ? error.message : ''));
      } finally {
        countingRef.current = false;
        setCounting(false);
      }
      return;
    }
    void (async () => { try { await session.handleAction(action); } catch { /* surfaced by session.error */ } })();
  };

  const handleBoardMove = async (x: number, y: number) => {
    // 服务端允许退回历史后另开分支，kiosk 终局后只允许查看。
    if (isGameOver) return;
    try {
      await session.onMove(x, y);
      setAiPlacementStatus(null);
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

  // 本地对局「退出不保存」。这是 pvp_local 唯一的出口，所以 DELETE 失败也照样离开 ——
  // 删不掉时服务端状态和「卡住不让走」时完全一样(会话都还挂在进程里)，攥着用户不放清理不出
  // 任何东西，只是把 R1 那个「服务端调用失败 = 出不去」的陷阱换个触发点重演一遍。best-effort
  // 发出去就算数：`delete_session`(server.py)只做 end_session + remove_session，
  // `SessionManager.remove_session` 弹出字典、停引擎；`API.deleteSession` 这条请求本来就不持久化
  // 任何东西，所以退出弹层那句
  // 「这局还没下完，退出后不会保存」依旧成立。孤儿会话不可见也会自愈：clearActiveSession('game')
  // 杀掉「继续上一局」指针，pvp_local 从不出现在 /api/v1/games/active/multiplayer 里，
  // cleanup_expired 在 SESSION_TIMEOUT(3600s) 后照常回收它。
  const handleExitWithoutSaving = () => {
    if (sessionId) {
      API.deleteSession(sessionId).catch((error) => {
        console.warn('[game] delete-on-exit failed (best-effort, leaving anyway):', error);
      });
    }
    setShowExitConfirm(false);
    clearActiveSession('game');
    navigate('/kiosk/play');
  };

  const handleLocalResign = async (color: 'B' | 'W') => {
    try {
      await session.handleAction('resign', { color });
      setShowResignConfirm(false);
    } catch (error) {
      setResignError(failureLine(t('game:resign_failed', '认输没成'), requestFailureKind(error), t));
    }
  };

  // 复盘本局:终局卡与(超时判负后的)右栏状态条**共用同一个入口**(v2-plan S3-5:
  // 「有复盘本局键(复用终局已有的复盘入口)」)—— 存的是当前对局的 SGF,不是持久化的
  // user_games id(那时可能还没落库),同一份 SGF 塞进 sessionStorage 给研究页读。
  const handleReview = async () => {
    if (!sessionId) return;
    try {
      const { sgf } = await API.saveSGF(sessionId);
      getCurrentKioskActivityStorage().setItem('kioskReviewSgf', sgf);
      navigate('/kiosk/research?from=game');
    } catch (e) { console.error(e); setReviewError(true); }
  };

  /* 三个操作数,各挡各的:`physicalPlay` 是「实体盘在不在」,`analysis_allowed` 是
     「这一局允不允许分析」(升降级反作弊),`analysis_delivered` 是「算了交不交给你」
     (无人认领的会话)。少了最后一条,游客的支招键是亮的,按下去 401 ——
     而 `handleHint` 的 catch 只认得 `ranked_forbidden`/`disabled`/`insufficient`,
     401 会落到那句「支招失败,请稍后再试」上,把一个**登录就能解决**的事说成了故障。 */
  const hintVisible =
    physicalPlay &&
    gameState.game_type === 'free' &&
    gameState.analysis_allowed !== false &&
    gameState.analysis_delivered !== false;

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

  // 星阵隧道分析 (领地/支招/变化图/数子) — engineMode only. Mutually exclusive: a new kind
  // replaces any prior overlay; clicking the already-active kind toggles it off.
  const handleEngineAnalysis = async (kind: EngineAnalysisKind) => {
    if (engineAnalysisPendingRef.current) return;
    if (activeEngineKind === kind) {
      setActiveEngineKind(null);
      setEngineOverlay(null);
      setEngineEvaluation(null);
      return;
    }
    if (!sessionId || !isAuthenticated) return;
    // Capture the position identity at call time — if the board advances (a move
    // played) while this request is in flight, the response below is for a stale
    // position and must be discarded rather than resurrecting an old overlay.
    const requestedPosition = enginePositionKey;
    engineAnalysisPendingRef.current = true;
    try {
      const res = await API.platformEngineAnalysis(platform, sessionId, kind, token);
      // A settled call changed the balance (ok → one consumed; insufficient → it's 0);
      // resync the badges. Fire-and-forget, and BEFORE the stale-position early return
      // below so a discarded overlay still updates the count that was actually spent.
      void refreshItemCounts();
      if (res.ok) {
        if (enginePositionRef.current !== requestedPosition) return;
        const overlay: EngineOverlay =
          kind === 'area' ? { kind: 'area', ownership: (res.data as { ownership: OwnershipPoint[] }).ownership }
          : kind === 'options' ? { kind: 'options', candidates: (res.data as { candidates: AnalysisCandidate[] }).candidates }
          : kind === 'judge' ? { kind: 'judge', ownership: (res.data as { ownership: JudgePoint[] }).ownership }
          : { kind: 'variation', sequence: (res.data as { sequence: AnalysisPoint[] }).sequence };
        setEngineOverlay(overlay);
        setEngineEvaluation(kind === 'area' ? res.data as { winrate: number; delta: number } : null);
        setActiveEngineKind(kind);
      } else {
        setInsufficientKind(kind);
      }
    } catch (e) {
      console.error(e);
      setEngineErrorToast(true);
    } finally {
      engineAnalysisPendingRef.current = false;
    }
  };

  const ENGINE_KIND_LABEL: Record<EngineAnalysisKind, string> = {
    area: t('Territory', '领地'),
    options: t('Suggest', '支招'),
    judge: t('Score', '数子'),
    variation: t('Variation Line', '变化图'),
  };

  // 右栏状态条(F4,设计稿 05 附 B/C):**开关行之上、右栏里的一块常驻区块**,不是弹出的
  // Snackbar/Alert —— 进行中与失败都不自动消失,失败那句是这一局唯一的出路说明,重试键挂在它上面。
  // 通过 `statusSlot` 传给 `GameControlPanel`,由它渲染在开关行之前(设计稿的位置)。
  const statusSlot = (timeoutLoserColor || autoCount.status !== 'idle') ? (
    <div className="gstatus" data-testid="auto-count-status" data-tone={timeoutLoserColor || autoCount.status === 'failed' ? 'bad' : undefined}>
      {!timeoutLoserColor && autoCount.status === 'counting' && <CircularProgress size={14} />}
      <div>
        <b>
          {timeoutLoserColor
            ? (timeoutLoserColor === 'B' ? t('game:black_side', '黑方') : t('game:white_side', '白方')) + t('game:timeout_loss_suffix', '超时负')
            : autoCount.status === 'failed' ? t('game:count_failed', '数子没有完成')
            : t('game:counting', '正在数子…')}
        </b>
        <span>
          {timeoutLoserColor
            ? (timeoutWinnerColor === 'B' ? t('game:black_short', '黑') : t('game:white_short', '白')) + t('game:timeout_win_suffix', '超时胜')
              + ' · ' + t('game:move_n', '第 {n} 手').replace('{n}', String((gameState.current_node_index ?? 0) + 1))
              + ' · ' + t('game:saved_to_history', '已存进历史对局')
            : autoCount.status === 'failed' ? `${autoCount.reason} · ${t('game:check_network_retry', '检查网络后重试')}`
            : null}
        </span>
      </div>
      {(timeoutLoserColor || autoCount.status === 'failed') && (
        <button
          type="button"
          className="kiosk-btn kiosk-btn--pill"
          onClick={() => { if (timeoutLoserColor) void handleReview(); else autoCount.retry(); }}
        >
          {timeoutLoserColor ? t('Review this game', '复盘本局') : t('game:retry', '重试')}
        </button>
      )}
    </div>
  ) : activeEngineKind === 'area' && engineEvaluation ? (
    <div className="gstatus" data-testid="engine-analysis-summary" role="status">
      <div>
        <b>{t('game:golaxy_ai', '星阵围棋 · 人机')} · {t('Territory', '领地')}</b>
        <span style={{ fontSize: 14, color: 'var(--text)' }}>
          {t('live:black_winrate', '黑棋胜率')} {Number.isFinite(engineEvaluation.winrate) && engineEvaluation.winrate >= 0 && engineEvaluation.winrate <= 1
            ? `${(engineEvaluation.winrate * 100).toFixed(1)}%` : '—'}
          {' · '}
          {Number.isFinite(engineEvaluation.delta)
            ? `${engineEvaluation.delta < 0 ? t('game:white_short', '白') : t('game:black_short', '黑')}${t('live:lead_pts', '领先')} ${Math.abs(engineEvaluation.delta).toFixed(1)} ${t('game:points_unit', '目')}`
            : `${t('research:col_score_diff', '目差')} —`}
        </span>
      </div>
    </div>
  ) : null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default', position: 'relative' }}>
      <Box sx={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', zIndex: 90, minWidth: 300 }}>
        <AiLadderSettlementAlert feedback={settlementFeedback} />
      </Box>
      {/* 位置走 `.gthink`(go-screens.css)—— **居中在棋盘上,不是整页上**。
          这两块共用同一个槽(构造上互斥,见 deriveAiTurnState),所以位置也共用一个类:
          分开写过一次,结果是两处各写一遍 `left:'50%'`,改一处漏一处不会有人红。 */}
      {/* State A: AI 思考中 — jade spinner banner (design.md §5.1 state A). Single-owner
          gate via showThinking (deriveAiTurnState): suppressed for PVP (aiColor===null)
          and while the physical layer is confirming a move (move_pending), so it never
          stacks with PhysicalPlayStatusChip's 确认中 chip. Board interaction is already
          gated by playerColor={humanColor} (Board.tsx, consume-only) — no extra disable needed. */}
      {showThinking && (
        <Box data-testid="ai-thinking" className="gthink"
          sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 0.75, borderRadius: 2,
                bgcolor: 'var(--raise2)', border: '1px solid', borderColor: 'primary.main' }}>
          <CircularProgress size={16} sx={{ color: 'primary.main' }} />
          <Typography sx={{ color: 'primary.main' }}>{t('AI is thinking…', 'AI 思考中…')}</Typography>
        </Box>
      )}

      {/* The ladder AI refused to move: the engine cannot serve this rung at the strength
          its rank name promises, so it plays nothing rather than an uncalibrated move.
          Occupies the same slot as the thinking banner (they are mutually exclusive by
          construction — see deriveAiTurnState) and says the two things the player needs:
          no move is coming, and this game will not touch their rank. */}
      {ladderStalled && (
        <Box data-testid="ladder-stalled" className="gthink"
          sx={{ px: 2, py: 0.75, borderRadius: 2,
                bgcolor: 'var(--raise2)', border: '1px solid', borderColor: 'warning.main' }}>
          <Typography sx={{ color: 'warning.main', fontSize: 14, textAlign: 'center' }}>
            {t('ladder:engine_stalled', '阶梯引擎不可用，AI 无法落子 · 本局不计入升降级，请退出本局')}
          </Typography>
        </Box>
      )}

      {/*
        对局出错 —— **走浮层,不占流内高度。**
        这一屏是布局 A 的固定画布:盘 516 贴 (16,70),整屏一共就 600 高。
        原来这条是一块流内的 `<Alert>`(2026-03-26 从 galaxy 搬过来时就在),
        平时 `session.error` 是空的所以看不出问题;`dc55f32e`(对局 WS 补上凭据)让
        「实时连接被拒绝(Invalid token)」真的会填进来之后,它就成了盘上面 48+8 高的一条 ——
        **盘被顶到 y=126、底边 642 掉出 600 的屏外**,右栏一起下移。
        (`kiosk-screen-05-game.spec.ts` 的「盘顶不在 y=70」当场红,2026-08-25 逮到。)
        这一屏另外六条错都在 `Snackbar` 里,这条本来就是那六条的同类。
        ⚠️ **不自动消失**(`autoHideDuration={null}`):Fan 2026-08-21 裁过掉线 toast 这一条 ——
        连接断了是持续状态,不是一闪而过的事件。
      */}
      {/* 一次性操作失败说人话，6 秒后清除，也可手动关闭。 */}
      <Snackbar
        open={!!session.error && !session.connectionLost}
        autoHideDuration={6000}
        onClose={() => session.clearError()}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => session.clearError()}>
          {t('game:action_failed', '这一步没有成功，请再试一次')}
        </Alert>
      </Snackbar>

      {/* 断线持续显示。三档都是固定文案，不接 session.error —— connectionLost 一旦置位就不会自动
          清空，后续任何一次失败的 HTTP 动作都会把 ApiError 的原文写进 session.error，原来的
          fallback 分支会把它原样印在这里(R2 的泄漏点，已经封死)。'rejected' 不复述服务端给的
          1008 reason：如今只可能是 Invalid token / Session not found / Session unavailable
          之一(server.py:3156/3162/3170)，7 寸屏上没有一条是用户能采取行动的。
          'dropped' / 'gone' 都不点名对局屏当下具体哪个按钮能离开 —— 本地对局(pvp_local)的
          退出弹层只有「继续下 / 退出不保存」，没有「先离开，不认输」那个键；而 'gone' 这一档自己的
          说明弹层开着时，底下整块页面(含页控条的「退出对局」)都在遮罩之下点不到，指哪个具体按钮
          都会指错。 */}
      <Snackbar
        open={!!session.connectionLost && !connectionNoticeDismissed}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setConnectionNoticeDismissed(true)}>
          {session.connectionLost === 'dropped'
            ? t('game:connection_dropped', '实时连接断了，棋盘不会自动更新，可以点「退出对局」离开这一局')
            : session.connectionLost === 'gone'
              ? t('game:session_gone_notice', '这一局在服务器上已经没有了，可以离开这一页。')
              : t('game:connection_rejected', '实时连接被拒绝，棋盘不会自动更新，请重新登录后重试')}
        </Alert>
      </Snackbar>

      {physicalPlay && (
        <PhysicalPlayStatusChip
          latestEvent={visionSync.latestEvent}
          currentNodeId={session.gameState?.current_node_id ?? null}
        />
      )}

      {/* State B: RecalibrationModal (pose lost). Gated `&& !escalationOpen` so the
          escalation dialog (highest-priority board-loss surface) wins — see the
          precedence comment above recalOpen. */}
      {physicalPlay && (
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

      {/* §11 布局 A:盘 516 贴 x16 + 16 + 右栏 460。三个数一个都不写死 ——
          `.kiosk-layout-a` / `.kiosk-board` 用的是 `tokens.css` 的 `--board-size` / `--content-x`。

          上一版这里是**一条 46 高的自定义顶条**(标题 + 三颗视觉状态灯 + 重置识别 + 退出)
          加一个 `flex` 的盘/面板并排。两处不对:
            · 标题和返回属于**页控条**(§11 恒在 y70–114),不许各屏自己搭一条;
            · 三颗常亮状态灯是 **L1 镜像栏**的东西(§5),L3 上没有它们的位置。
              它们**没有白丢**:出故障时那句话落在下面开关排右端的 `.ghint` 上
              (`GameControlPanel`),平时不占地方 —— 比三颗一直亮着的灯说得还清楚。 */}
      <div className="kiosk-layout-a">
        <div className="kiosk-board" data-testid="game-board">
          {/* 四条 28 刻度带。`坐标` 开关关掉时**只清字、不撤带** ——
              撤了带落子区就从 460 变 516,盘会当场跳一下。 */}
          <div className="kiosk-board__ruler kiosk-board__ruler--top">
            {rulerCols.map((c) => <span key={`t${c}`}>{c}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--left">
            {rulerRows.map((r) => <span key={`l${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__play">
            <Board
              gameState={gameState}
              onMove={handleBoardMove}
              analysisToggles={boardAnalysisToggles}
              playerColor={humanColor}
              engineOverlay={engineOverlay}
              externalRulers
              suppressEndResultOverlay={!!timeoutLoserColor}
              onPaintedNode={session.acknowledgePaintedNode}
            />
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--right">
            {rulerRows.map((r) => <span key={`r${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
            {rulerCols.map((c) => <span key={`b${c}`}>{c}</span>)}
          </div>
        </div>

        <div className="kiosk-rail">
          <KioskPagebar
            testId="game-pagebar"
            backLabel={t('game:exit_game', '退出对局')}
            onBack={handleExit}
            title={gameTitle}
            sub={gameSetupLine}
            // §11 只允许一个页级图标按钮。重置识别在这一屏是**唯一**那个:
            // 以屏幕上的数字棋盘为权威重建识别基线。上一版它只在 `syncStuck` 之后才出现 ——
            // 也就是必须先卡住一次才能自救;实体模式下它现在一直在。
            action={physicalPlay ? {
              icon: 'arrows-clockwise',
              label: t('vision:resync_screen_authority', '重置识别 · 以屏幕上的数字棋盘局面为准'),
              visibleLabel: t('Re-sync', '重置识别'),
              onClick: () => { void handleResetSync(); },
            } : undefined}
          />
          <GameControlPanel
            onTimeout={localGame ? undefined : handleClockExpired}
            onTimeExpired={localGame ? handleTimeExpired : undefined}
            gameState={gameState}
            onAction={handleAction}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            onToggleAnalysis={(key) => setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
            onHint={handleHint}
            hintEnabled={hintVisible}
            /* 判据取**服务端说的那一句**,不是本地有没有 token:决定交不交付的是
               「这个会话有没有主人」,而一个登录用户照样可能打开一个无主会话。
               老服务端不带这个字段 ⇒ undefined ⇒ `=== false` 为假 ⇒ 一切照旧。 */
            analysisRequiresLogin={gameState.analysis_delivered === false}
            isGameOver={isGameOver}
            isRanked={isRanked}
            engineMode={engineMode}
            activeEngineKind={activeEngineKind}
            onEngineAnalysis={handleEngineAnalysis}
            engineItemCounts={engineItemCounts}
            hardwareFault={hardwareFault}
            physicalStatus={physicalStatus}
            counting={autoCount.status === 'counting'}
            statusSlot={statusSlot}
          />
        </div>
      </div>

      {/* State C: 终局数子 — territory coloring is forced via boardAnalysisToggles above.
          留在棋盘 ONLY flips EndgameCard's own local `dismissed` state to hide the card — the
          game stays ended (useGameSession's handleAction has no 'resume' branch; calling it
          would be a silent no-op). 确认终局 (handleExit) navigates out. `key={sessionId}`
          remounts EndgameCard fresh (dismissed=false) whenever a new session/game loads.
          DESCOPED: dead-stone dimming + red-X needs a backend dead_stones field + a
          kiosk-only overlay (Gate S) — not shipped in this cut; Board.tsx is untouched.

          `!timeoutLoserColor`:超时判负那一态已经在右栏状态条里说完了(设计稿 05b 就是
          只有状态条、没有这张居中卡),两处同时出现会是两个「复盘本局」键叠在一起。 */}
      {isGameOver && !timeoutLoserColor && (
        <EndgameCard
          celebrating={celebrating}
          key={sessionId}
          gameState={gameState}
          t={t}
          onExit={handleExit}
          onReview={handleReview}
        />
      )}

      {/* Resign confirmation (state D) */}
      {localGame ? (
        /* 本地对局:两个人都在屏前,「认输」不能默认判轮到走的那一方(P5)—— 先问谁认输。 */
        <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
          <DialogTitle sx={{ color: 'text.primary' }}>{t('game:which_side_resigns', '哪一方认输？')}</DialogTitle>
          <DialogContent><Typography>{t('game:resign_local_body', '对方记中盘胜，这局会存进历史对局。')}</Typography></DialogContent>
          <DialogActions disableSpacing sx={{ flexDirection: 'column', alignItems: 'stretch', gap: 1 }}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button variant="contained" color="error" sx={{ flex: 1 }} startIcon={<span className="disc b" />} onClick={() => { void handleLocalResign('B'); }}>
                {t('game:black_resigns', '黑方认输')}
              </Button>
              <Button variant="contained" color="error" sx={{ flex: 1 }} startIcon={<span className="disc w" />} onClick={() => { void handleLocalResign('W'); }}>
                {t('game:white_resigns', '白方认输')}
              </Button>
            </Box>
            <Button variant="outlined" fullWidth onClick={() => setShowResignConfirm(false)}>{t('Cancel', '取消')}</Button>
          </DialogActions>
        </Dialog>
      ) : (
        <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
          <DialogTitle sx={{ color: 'text.primary' }}>{resignTitle}</DialogTitle>
          <DialogActions>
            <Button onClick={() => setShowResignConfirm(false)}>{t('Cancel', '取消')}</Button>
            <Button
              color="error"
              onClick={async () => {
                try {
                  await session.handleAction('resign');
                  setShowResignConfirm(false);
                } catch (error) {
                  setResignError(failureLine(t('game:resign_failed', '认输没成'), requestFailureKind(error), t));
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
      )}

      {/* Exit confirmation */}
      {localGame ? (
        /* 本地对局退出 = 删会话、不存谱(v2 D2)。已终局不会走到这里(handleExit 直接离开)。 */
        <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
          <DialogTitle>{t('game:exit_confirm_title', '退出这局？')}</DialogTitle>
          <DialogContent><Typography>{t('game:exit_unsaved_body', '这局还没下完，退出后不会保存。')}</Typography></DialogContent>
          <DialogActions sx={{ display: 'flex', gap: 1 }}>
            <Button variant="outlined" sx={{ flex: 1, whiteSpace: 'nowrap' }} onClick={() => setShowExitConfirm(false)}>{t('game:keep_playing', '继续下')}</Button>
            <Button variant="outlined" color="error" sx={{ flex: 1, whiteSpace: 'nowrap' }} onClick={handleExitWithoutSaving}>
              {t('game:exit_unsaved', '退出不保存')}
            </Button>
          </DialogActions>
        </Dialog>
      ) : (
        <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
          <DialogTitle>{exitResignTitle}</DialogTitle>
          <DialogActions>
            <Button onClick={() => setShowExitConfirm(false)}>{t('Cancel', '取消')}</Button>
            <Button data-testid="exit-leave-keep" onClick={() => {
              setShowExitConfirm(false);
              navigate('/kiosk/play');
            }}>
              {t('game:leave_keep_game', '先离开，不认输')}
            </Button>
            <Button
              color="error"
              onClick={async () => {
                try {
                  await session.handleAction('resign');
                } catch (error) {
                  setResignError(failureLine(t('game:resign_failed', '认输没成'), requestFailureKind(error), t));
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
      )}

      {/* 这局在服务端已经没了。说人话 + 给出口。说的是「本机没有这一局了」,不是「你认输了」:
          回收会话不会结束远端对局(真正的远端认输在 gateway.py:399-420)。 */}
      <Dialog open={sessionGone && !gameGoneAcknowledged}
              onClose={() => { setGameGoneAcknowledged(true); navigate('/kiosk/play'); }}>
        <DialogTitle sx={{ color: 'text.primary' }}>{t('game:unavailable_title', '这一局已经打不开了')}</DialogTitle>
        <DialogContent>
          {/* 这里**不能**复用载入失败那一屏的 `game:unavailable_reason` —— 它第三条说
              「或者它属于另一个账号」,而那种局根本产不出 `gone` 这个信号:别人的会话是
              403 / `1008 "Session unavailable"`,落的是 `rejected`。只说能产出它的那两种。 */}
          <Typography>{t('game:gone_reason', '可能是盒子重启过，或者这一局闲置太久被清理了。')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button data-testid="game-gone-leave"
                  onClick={() => { setGameGoneAcknowledged(true); navigate('/kiosk/play'); }}>
            {t('game:back_to_play', '回到对弈')}
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
      {/* 终局后整个卸掉,不只是「不再新弹」。`visionRecovery` 里**唯一**能清掉 blocking 的
          路径是收到 `synced`(visionRecovery.ts:84),而终局后那 26 分钟里 `synced` 是 0 条
          (RK3562 2026-09-20 实测) ⇒ 后端停止比对也清不掉已经开着的那个弹窗,只有卸载能。 */}
      {physicalPlay && !isGameOver && (
        <VisionSyncOverlay
          syncEvents={visionSync.syncEvents}
          sessionId={sessionId ?? null}
          boardSize={session.gameState?.board_size?.[0] ?? 19}
          playerToMove={session.gameState?.player_to_move ?? null}
          currentNodeId={session.gameState?.current_node_id ?? null}
          platformPendingStone={engineMode && session.platformPendingMove ? {
            row: boardSize - 1 - session.platformPendingMove.row,
            col: session.platformPendingMove.col,
            color: gameState.player_to_move === 'B' ? 1 : 2,
          } : null}
          suppressBoardLost={escalationOpen || recalOpen}
        />
      )}

      {/* AI hint panel + error */}
      {hint && <HintPanel moves={hint.moves} timeoutS={hint.timeout_s} onClose={closeHint} />}
      <Snackbar open={!!hintError} autoHideDuration={5000} onClose={() => setHintError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }} message={hintError} />

      {/* Camera disconnect toast */}
      <Snackbar open={physicalPlay && cameraDisconnectToast} autoHideDuration={5000} onClose={() => setCameraDisconnectToast(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="warning" onClose={() => setCameraDisconnectToast(false)}>
          {t('Camera disconnected, switched to touch mode', '摄像头断开，已切换为触屏模式')}
        </Alert>
      </Snackbar>

      {/* Physical catch-up reminder toast */}
      <Snackbar
        open={physicalPlay && reminderOpen}
        autoHideDuration={8000}
        onClose={() => setReminderOpen(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        message={t('Please place the AI stone at the lit point first', '请先将 AI 棋子摆到棋盘亮灯处')}
      />

      {/* Physical desync escape hatch */}
      <PhysicalSyncEscalationDialog
        open={physicalPlay && escalationOpen}
        toPlace={session.physicalReminder?.to_place ?? []}
        toRemove={session.physicalReminder?.to_remove ?? []}
        onClose={() => setEscalationOpen(false)}
        onScreenPlay={fallBackToScreen}
      />

      {/* Physical engine-move (Golaxy 隧道) bounded-retry failure — physical mode only;
          pure-screen engine games keep the existing engineErrorToast path (handleBoardMove)
          untouched. Gate the ERROR PROP (not the mount) on physicalPlay so the dialog
          component itself stays mounted across any physicalPlay flap without losing its
          local dismissed-token bookkeeping (mirrors PhysicalSyncEscalationDialog's always-
          mounted pattern). */}
      <EngineMoveErrorDialog
        error={physicalPlay ? session.physicalEngineError : null}
        sessionId={sessionId ?? null}
        token={token ?? undefined}
        boardSize={gameState.board_size[0]}
        reminderTick={session.awaitingRemovalReminder}
        onDismiss={session.clearPhysicalEngineError}
        onResign={() => setShowResignConfirm(true)}
      />

      {/* 数子在途 —— 服务端可能正在给这一手补分析,这几秒里屏上不能什么都不说 */}
      <Snackbar open={counting} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="info">{t('game:counting', '正在数子…')}</Alert>
      </Snackbar>

      {/* Count (数子) error toast */}
      <Snackbar open={!!countError} autoHideDuration={5000} onClose={() => setCountError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="warning" onClose={() => setCountError(null)}>{countError}</Alert>
      </Snackbar>
      <Snackbar open={!!timeoutError && timeoutError.scope === timeoutScope}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }} onClose={() => setTimeoutError(null)}>
        <Alert severity="error" onClose={() => setTimeoutError(null)}>{timeoutError?.message}</Alert>
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

      {/* 星阵掉线 —— **这一屏唯一说得出「连不上了」的地方**(平台条那三个值一个都喂不了,
          见 scope.md 屏 10),所以它**不自动消失**:`autoHideDuration={null}`。
          兄弟几条 toast 照旧 5–8 秒自己走,它们说的是「这一次操作失败了,再试一次」;
          这一条说的是「对面没了,你现在要么重试落子、要么退出弃局」——
          6 秒之后屏上什么都不剩,而那盘棋还卡在那儿,用户不知道自己在等什么。
          `<Alert onClose>` 那颗 × 是唯一的关法,右上角,手指够得到。 */}
      <Snackbar open={engineErrorToast} autoHideDuration={null} onClose={() => setEngineErrorToast(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setEngineErrorToast(false)}>
          {t('AI connection error — please retry your move, or exit to abandon the game.', 'AI 连接出错，请重试落子，或退出以放弃对局。')}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default GamePage;
