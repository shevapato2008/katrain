import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar } from '@mui/material';
import { ExitToApp, Videocam, Lightbulb, TipsAndUpdates } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board, { type EngineOverlay } from '../../components/Board';
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
import { API, type HintResponse, type OwnershipPoint, type AnalysisCandidate, type AnalysisPoint } from '../../api';

type EngineAnalysisKind = 'area' | 'options' | 'variation';

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

  // Invalidate the 星阵 analysis overlay when the board position advances (a move
  // played, human or AI) — otherwise stale 领地/支招/变化图 markers keep drawing over
  // the new position and the button stays stuck "active". Keyed on position identity
  // only, so it never fires on unrelated re-renders. Does NOT touch insufficientKind —
  // that dialog is dismissed by the user, not by position changes.
  useEffect(() => {
    setEngineOverlay(null);
    setActiveEngineKind(null);
  }, [session.gameState?.current_node_id]);

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
            onMove={handleBoardMove}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            playerColor={humanColor}
            engineOverlay={engineOverlay}
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
            disableSpecialActions={engineMode}
            engineMode={engineMode}
            activeEngineKind={activeEngineKind}
            onEngineAnalysis={handleEngineAnalysis}
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
