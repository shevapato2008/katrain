import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogActions, Snackbar } from '@mui/material';
import { ExitToApp, Videocam, Lightbulb, TipsAndUpdates, EmojiEvents } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';
import KioskResultBadge from '../components/game/KioskResultBadge';
import RecalibrationModal from '../components/game/RecalibrationModal';
import VisionSyncOverlay from '../components/vision/VisionSyncOverlay';
import { useVision } from '../context/VisionContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { useTranslation } from '../../hooks/useTranslation';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';
import HintPanel from '../components/physical/HintPanel';
import { API, type HintResponse, type GameState } from '../../api';
import { writeActiveSession, clearActiveSession } from '../utils/activeSession';

export interface AiTurnState {
  aiColor: 'B' | 'W' | null;
  aiThinking: boolean;
  physicalConfirming: boolean;
  showThinking: boolean;
}

// Single-owner AI-turn arbitration (state A source for B1.4). Exported as a pure
// function so it's unit-testable without rendering the page, and so B1.4 can reuse it.
// Per-color AI detection — accept BOTH literals: 'player:ai' (kiosk HvAI, server.py:723/727)
// AND bare 'ai' (multiplayer session.py:80/82 + tests). Do NOT infer AI from "the non-human color".
// Pure helper co-located here (not split into a new file) for unit testability; deliberate,
// not a component — see GamePage.test.tsx.
// eslint-disable-next-line react-refresh/only-export-components
export function deriveAiTurnState(gameState: GameState, latestEventType: string | null | undefined): AiTurnState {
  const isAI = (c: 'B' | 'W') => {
    const pt = gameState.players_info[c].player_type;
    return pt === 'player:ai' || pt === 'ai';
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
const EndgameCard = ({ gameState, t, onExit }: EndgameCardProps) => {
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
        <Button variant="contained" onClick={onExit} sx={{ bgcolor: 'primary.main' }}>{t('Confirm result', '确认终局')}</Button>
      </Box>
    </Box>
  );
};

const GamePage = ({ engineMode = false }: { engineMode?: boolean }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const { token } = useAuth();
  const session = useGameSession({ token: token ?? undefined });
  const [analysisToggles, setAnalysisToggles] = useState({
    ownership: false,
    hints: false,
    numbers: false,
    coords: true,
    score: true,
  });
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

  const { visionStatus, isVisionEnabled } = useVision();
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
    const human: 'B' | 'W' | null =
      gs.players_info?.B?.player_type === 'player:human' ? 'B'
      : gs.players_info?.W?.player_type === 'player:human' ? 'W'
      : null;
    if (gs.last_move && gs.end_result === null && human && gs.player_to_move === human) {
      const col = String.fromCharCode(65 + (gs.last_move[0] >= 8 ? gs.last_move[0] + 1 : gs.last_move[0]));
      const row = gs.board_size[0] - gs.last_move[1];
      setAiMoveBanner(`${col}${row}`);
    }
  }, [isVisionEnabled, session.gameState?.current_node_id]);

  // Camera disconnect fallback
  useEffect(() => {
    if (isVisionEnabled && !visionStatus.cameraConnected) {
      setCameraDisconnectToast(true);
    }
  }, [isVisionEnabled, visionStatus.cameraConnected]);

  const closeHint = useCallback(() => {
    setHint(null);
    API.hintDismiss().catch(() => undefined);
  }, []);

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
  const isRanked = gameState.game_type === 'ranked' || gameState.game_type === 'rated';

  // Determine which color the human plays (for turn enforcement)
  const humanColor: 'B' | 'W' | null =
    gameState.players_info?.B?.player_type === 'player:human' ? 'B'
    : gameState.players_info?.W?.player_type === 'player:human' ? 'W'
    : null;

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

  const handleAction = (action: string) => {
    if (isRanked && ['undo', 'back', 'back-10', 'start'].includes(action)) return;
    if (action === 'resign') {
      setShowResignConfirm(true);
    } else {
      session.handleAction(action);
    }
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
      navigate('/kiosk/play');
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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default', position: 'relative' }}>
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
            {t('AI played', 'AI 已落子')} <b>{aiMoveBanner}</b> · {t('place the white stone at the matching point on the board', '请在实体棋盘对应交叉点摆放白子')}
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

      {/* Floating vision status (fullscreen GamePage has no KioskLayout/StatusBar) */}
      {isVisionEnabled && (
        <Box sx={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 0.5, opacity: 0.8, zIndex: 10 }}>
          <Videocam sx={{ color: visionStatus.cameraConnected ? 'success.main' : 'error.main', fontSize: 20 }} />
          <Lightbulb
            sx={{
              color: visionStatus.ledConnected === false ? 'error.main'
                : visionStatus.ledConnected ? 'success.main' : 'text.disabled',
            }}
          />
        </Box>
      )}

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

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 2, py: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>{gameTitle}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {hintVisible && (
            <Button variant="outlined" size="small" startIcon={<TipsAndUpdates />} onClick={handleHint}
              sx={{ borderColor: 'divider', color: 'text.secondary' }}>
              {t('AI Hint', 'AI 支招')}
            </Button>
          )}
          <Button variant="outlined" size="small" startIcon={<ExitToApp />}
            onClick={handleExit} sx={{ borderColor: 'divider', color: 'text.secondary' }}>
            {t('Exit', '退出')}
          </Button>
        </Box>
      </Box>
      {/* Board + Panel */}
      <Box sx={{ display: 'flex', flexDirection: 'row', flex: 1, overflow: 'hidden' }}>
        <Box sx={{ height: '100%', aspectRatio: '1' }}>
          <Board
            gameState={gameState}
            onMove={handleBoardMove}
            onNavigate={session.onNavigate}
            analysisToggles={boardAnalysisToggles}
            playerColor={humanColor}
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <GameControlPanel
            gameState={gameState}
            onAction={handleAction}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            onToggleAnalysis={(key) => setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
            isGameOver={isGameOver}
            disableUndo={isRanked}
            disableSpecialActions={engineMode}
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
      {isGameOver && <EndgameCard key={sessionId} gameState={gameState} t={t} onExit={handleExit} />}

      {/* Resign confirmation (state D) */}
      <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
        <DialogTitle sx={{ color: 'text.primary' }}>{t('Confirm resign?', '确认认输？')}</DialogTitle>
        <DialogActions>
          <Button onClick={() => setShowResignConfirm(false)}>{t('Cancel', '取消')}</Button>
          <Button color="error" onClick={() => { setShowResignConfirm(false); session.handleAction('resign'); }}>
            {t('Resign', '认输')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Exit confirmation */}
      <Dialog open={showExitConfirm} onClose={() => setShowExitConfirm(false)}>
        <DialogTitle>{t('Game in progress. Resign and exit?', '对局进行中，认输并退出？')}</DialogTitle>
        <DialogActions>
          <Button onClick={() => setShowExitConfirm(false)}>{t('Cancel', '取消')}</Button>
          <Button color="error" onClick={() => { session.handleAction('resign'); navigate('/kiosk/play'); }}>
            {t('Exit', '退出')}
          </Button>
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
