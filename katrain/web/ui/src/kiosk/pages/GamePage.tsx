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
import { useOrientation } from '../context/OrientationContext';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';
import PoseLostBanner from '../components/physical/PoseLostBanner';
import HintPanel from '../components/physical/HintPanel';
import { API, type HintResponse } from '../../api';

const GamePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const { token } = useAuth();
  const { isPortrait } = useOrientation();
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
  const [aiMoveToast, setAiMoveToast] = useState<string | null>(null);
  const [cameraDisconnectToast, setCameraDisconnectToast] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [escalationOpen, setEscalationOpen] = useState(false);
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [hintError, setHintError] = useState<string | null>(null);

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

  // Show toast when AI makes a move (vision mode: physical board player needs coordinate hint)
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
      setAiMoveToast(`AI 落子: ${col}${row}`);
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

  const handleAction = (action: string) => {
    if (isRanked && ['undo', 'back', 'back-10', 'start'].includes(action)) return;
    if (action === 'resign') {
      setShowResignConfirm(true);
    } else {
      session.handleAction(action);
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
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{gameTitle}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {hintVisible && (
            <Button variant="outlined" size="small" startIcon={<TipsAndUpdates />} onClick={handleHint}>
              {t('AI Hint', 'AI 支招')}
            </Button>
          )}
          <Button variant="outlined" size="small" startIcon={<ExitToApp />}
            onClick={handleExit}>
            {t('Exit', '退出')}
          </Button>
        </Box>
      </Box>
      {/* Board + Panel */}
      <Box sx={{ display: 'flex', flexDirection: isPortrait ? 'column' : 'row', flex: 1, overflow: 'hidden' }}>
        <Box sx={isPortrait ? { width: '100%', maxHeight: '50%', aspectRatio: '1' } : { height: '100%', aspectRatio: '1' }}>
          <Board
            gameState={gameState}
            onMove={session.onMove}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            playerColor={humanColor}
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {/* TEMP DEBUG: live recognition preview. Green box = accepted (>= threshold), red = detected but below threshold. */}
          {isVisionEnabled && (
            <Box sx={{ p: 1 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                实时识别（调试）· 绿框=已识别 · 红框=检测到但低于阈值
              </Typography>
              <Box
                component="img"
                src="/api/v1/vision/stream"
                alt="live recognition"
                sx={{ width: '100%', aspectRatio: '1', objectFit: 'contain', bgcolor: '#000', borderRadius: 1, display: 'block' }}
              />
            </Box>
          )}
          <GameControlPanel
            gameState={gameState}
            onAction={handleAction}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            onToggleAnalysis={(key) => setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
            isGameOver={isGameOver}
            disableUndo={isRanked}
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

      {/* AI move toast */}
      <Snackbar open={!!aiMoveToast} autoHideDuration={8000} onClose={() => setAiMoveToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="info" onClose={() => setAiMoveToast(null)}>{aiMoveToast}</Alert>
      </Snackbar>

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
    </Box>
  );
};

export default GamePage;
