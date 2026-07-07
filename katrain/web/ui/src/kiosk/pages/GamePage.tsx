import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogActions, Snackbar } from '@mui/material';
import { ExitToApp, Videocam, Lightbulb, TipsAndUpdates } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';
import VisionSyncOverlay from '../components/vision/VisionSyncOverlay';
import { useVision } from '../context/VisionContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { useTranslation } from '../../hooks/useTranslation';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';
import PoseLostBanner from '../components/physical/PoseLostBanner';
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
  const [escalationOpen, setEscalationOpen] = useState(false);
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

  // aiThinking/showThinking are the single-owner gate for the "AI 思考中" surface added
  // in B1.4-A; this task only derives+exports them (no visible surface here yet — see
  // PhysicalPlayStatusChip above for the 确认中 chip, which remains the sole owner of
  // that indicator). Only aiColor is consumed here, to gate the persistent move banner.
  const { aiColor } = deriveAiTurnState(gameState, visionSync.latestEvent?.type ?? null);

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

      {isVisionEnabled && (
        <PoseLostBanner visible={!visionStatus.poseLocked && !!session.gameState && !session.gameState.end_result} />
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
            analysisToggles={analysisToggles}
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

      {/* Resign confirmation */}
      <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
        <DialogTitle>{t('Confirm resign?', '确认认输？')}</DialogTitle>
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

      {/* Vision sync overlay */}
      {isVisionEnabled && (
        <VisionSyncOverlay
          syncEvents={visionSync.syncEvents}
          sessionId={sessionId ?? null}
          boardSize={session.gameState?.board_size?.[0] ?? 19}
          playerToMove={session.gameState?.player_to_move ?? null}
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
