import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogActions, Snackbar } from '@mui/material';
import { ExitToApp, Videocam, Lightbulb, GpsFixed, Refresh } from '@mui/icons-material';
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

const GamePage = ({ engineMode = false }: { engineMode?: boolean }) => {
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
  const [engineErrorToast, setEngineErrorToast] = useState(false);
  const [countError, setCountError] = useState<string | null>(null);
  const [resyncing, setResyncing] = useState(false);
  const [resyncError, setResyncError] = useState(false);
  const [syncStuck, setSyncStuck] = useState(false);

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

  // On-demand analysis for 领地(ownership)/图表(winrate/score). Board mode suppresses per-move
  // auto-eval, so the current position has no analysis until we ask. Trigger when either toggle
  // is on, and re-trigger when the current node changes. The result streams back over the game
  // WebSocket (get_state broadcast). Ranked/rated games block this server-side (analysis_allowed).
  const wantAnalysis = analysisToggles.ownership || analysisToggles.score;
  const gs = session.gameState;
  useEffect(() => {
    if (!wantAnalysis || !sessionId || !gs) return;
    if (gs.game_type === 'ranked' || gs.game_type === 'rated') return;
    API.analyzeCurrent(sessionId).catch(() => undefined);
  }, [wantAnalysis, sessionId, gs?.current_node_id, gs?.game_type]);

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
    session.handleAction(action);
  };

  const handleBoardMove = async (x: number, y: number) => {
    try {
      await session.onMove(x, y);
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
      {/* Error display */}
      {session.error && <Alert severity="error" sx={{ mx: 2, mt: 1 }}>{session.error}</Alert>}

      {isVisionEnabled && (
        <PhysicalPlayStatusChip
          latestEvent={visionSync.latestEvent}
          currentNodeId={session.gameState?.current_node_id ?? null}
        />
      )}

      {isVisionEnabled && (
        <PoseLostBanner visible={!visionStatus.poseLocked && !!session.gameState && !session.gameState.end_result} />
      )}

      {/* Header — kiosk-ui-redesign 方案A: title (left) · inline vision chips (right, no longer a
          floating overlay that collided with the buttons) · 退出. AI 支招 is folded into the
          right-panel 建议 button, so there is no standalone hint button here anymore. */}
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
      <Box sx={{ display: 'flex', flexDirection: isPortrait ? 'column' : 'row', flex: 1, overflow: 'hidden' }}>
        <Box sx={isPortrait ? { width: '100%', maxHeight: '50%', aspectRatio: '1' } : { height: '100%', aspectRatio: '1' }}>
          <Board
            gameState={gameState}
            onMove={handleBoardMove}
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
            onHint={handleHint}
            hintEnabled={hintVisible}
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

      {/* Count (数子) error toast */}
      <Snackbar open={!!countError} autoHideDuration={5000} onClose={() => setCountError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="warning" onClose={() => setCountError(null)}>{countError}</Alert>
      </Snackbar>

      {/* Re-sync (重置识别) failure toast */}
      <Snackbar open={resyncError} autoHideDuration={5000} onClose={() => setResyncError(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setResyncError(false)}>
          {t('Re-sync failed, please retry', '重置识别失败，请重试')}
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
