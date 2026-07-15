import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import MapIcon from '@mui/icons-material/Map';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';

import { ReportsAPI } from '../../api/reportApi';
import AiAnalysis from '../../components/live/AiAnalysis';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import PlaybackBar from '../../components/live/PlaybackBar';
import TrendChart from '../../components/live/TrendChart';
import { useAuth } from '../../context/AuthContext';
import { useReportDetail } from '../../features/report/useReportDetail';
import { useSound } from '../../hooks/useSound';
import { useTranslation } from '../../hooks/useTranslation';
import { sgfToMoves } from '../../utils/sgfSerializer';
import ReportMetaPanel from '../components/report/ReportMetaPanel';
import SubPageBar from '../components/layout/SubPageBar';
import { useImmersive } from '../context/ImmersiveContext';

const BACK_PATH = '/kiosk/report';
const TOUCH_ACTION_SX = { minWidth: 48, minHeight: 48 } as const;

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

type Translate = (key: string, fallback?: string) => string;

function taskStatusLabel(status: string | undefined, t: Translate): string {
  if (status === 'pending') return t('report:queuing', '排队中');
  if (status === 'running') return t('report:generating', '生成中');
  if (status === 'completed') return t('report:completed', '已完成');
  if (status === 'failed') return t('report:failed', '失败');
  return t('report:unknown_status', '状态未知');
}

function reportTypeLabel(reportType: string | undefined, t: Translate): string {
  if (reportType === 'deep') return t('report:deep', '深度复盘');
  if (reportType === 'normal') return t('report:normal', '普通复盘');
  return t('report:unknown_type', '类型未知');
}

export default function ReportDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
  const { setImmersive } = useImmersive();
  const {
    task,
    game,
    analysisByMove,
    currentMove,
    setCurrentMove,
    loading,
    error,
    refresh,
  } = useReportDetail(isAuthenticated ? token : null, taskId);

  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const reportIdentity = `${taskId || ''}:${task?.id || ''}:${game?.id || ''}`;
  const identityRef = useRef(reportIdentity);
  useLayoutEffect(() => {
    identityRef.current = reportIdentity;
  }, [reportIdentity]);
  const [tryModeState, setTryModeState] = useState<{ identity: string; enabled: boolean } | null>(null);
  const [tryState, setTryState] = useState<{ identity: string; baseMove: number; moves: string[] } | null>(null);
  const [activeVariation, setActiveVariation] = useState<{
    identity: string;
    position: number;
    move: string;
  } | null>(null);
  const [retryFailure, setRetryFailure] = useState<{ identity: string; message: string } | null>(null);
  const [retryingIdentity, setRetryingIdentity] = useState<string | null>(null);
  const tryMoveMode = tryModeState?.identity === reportIdentity && tryModeState.enabled;
  const tryMoves = tryState?.identity === reportIdentity
    && tryState.baseMove === currentMove
    ? tryState.moves
    : [];
  const retryError = retryFailure?.identity === reportIdentity ? retryFailure.message : null;
  const retrying = retryingIdentity === reportIdentity;

  useEffect(() => {
    setImmersive(true);
    return () => setImmersive(false);
  }, [setImmersive]);

  const previousPosition = useRef<{ identity: string; move: number } | null>(null);
  useEffect(() => {
    if (!game) {
      previousPosition.current = null;
      return;
    }
    const soundIdentity = `${task?.id || taskId || ''}:${game.id}`;
    const previous = previousPosition.current;
    if (previous?.identity === soundIdentity && currentMove > 0 && previous.move !== currentMove) {
      playSound('stone');
    }
    previousPosition.current = { identity: soundIdentity, move: currentMove };
  }, [currentMove, game, playSound, task?.id, taskId]);

  const previewData = useMemo(() => {
    if (!game?.sgf_content) return null;
    try {
      return sgfToMoves(game.sgf_content);
    } catch {
      return null;
    }
  }, [game]);
  const currentAnalysis = analysisByMove[currentMove] ?? null;
  const recommendationSignature = currentAnalysis?.top_moves?.map((move) => move.move).join('\u0000') || '';
  const variationCandidate = activeVariation?.identity === reportIdentity
    && activeVariation.position === currentMove
    ? activeVariation.move
    : null;
  const activeMove = variationCandidate && currentAnalysis?.top_moves?.some((move) => move.move === variationCandidate)
    ? variationCandidate
    : null;

  // Mask stale local interactions during render (above), then permanently discard
  // them only after this report/cursor/analysis snapshot has committed. An aborted
  // concurrent render therefore cannot invalidate the currently displayed state.
  useEffect(() => {
    setTryModeState((previous) => previous?.identity === reportIdentity ? previous : null);
    setTryState((previous) => (
      previous?.identity === reportIdentity && previous.baseMove === currentMove ? previous : null
    ));
    setActiveVariation((previous) => (
      previous?.identity === reportIdentity
      && previous.position === currentMove
      && recommendationSignature.split('\u0000').includes(previous.move)
        ? previous
        : null
    ));
    setRetryFailure((previous) => previous?.identity === reportIdentity ? previous : null);
  }, [currentMove, recommendationSignature, reportIdentity]);
  const boardSize = previewData?.metadata.boardSize || game?.board_size || 19;
  const totalMoves = previewData?.moves.length || game?.move_count || 0;
  const ownership = currentAnalysis?.ownership || null;

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((move, index) => ({
      move: move.move,
      rank: index + 1,
      visits: move.visits,
      winrate: move.winrate ?? 0,
      score_lead: move.score_lead ?? 0,
    }));
  }, [currentAnalysis]);

  const pvMoves = useMemo(() => {
    if (!activeMove) return null;
    return currentAnalysis?.top_moves?.find((move) => move.move === activeMove)?.pv ?? null;
  }, [activeMove, currentAnalysis]);

  const handleMoveChange = useCallback((move: number) => {
    setActiveVariation(null);
    setCurrentMove(move);
  }, [setCurrentMove]);

  const handleTryToggle = useCallback(() => {
    setTryModeState({ identity: reportIdentity, enabled: !tryMoveMode });
    if (tryMoveMode) setTryState(null);
    setActiveVariation(null);
  }, [reportIdentity, tryMoveMode]);

  const handleRefresh = useCallback(async () => {
    const requestIdentity = reportIdentity;
    await refresh();
    if (identityRef.current === requestIdentity) setRetryFailure(null);
  }, [refresh, reportIdentity]);

  const handleRetryReport = useCallback(async () => {
    const id = Number(taskId);
    if (!token || !Number.isSafeInteger(id) || id <= 0) return;
    const requestIdentity = reportIdentity;
    setRetryingIdentity(requestIdentity);
    setRetryFailure(null);
    try {
      await refresh();
      if (identityRef.current !== requestIdentity) return;
      await ReportsAPI.retry(token, id);
      if (identityRef.current !== requestIdentity) return;
      await refresh();
      if (identityRef.current === requestIdentity) setRetryFailure(null);
    } catch (retryFailure) {
      if (identityRef.current === requestIdentity) {
        setRetryFailure({ identity: requestIdentity, message: messageFrom(retryFailure) });
      }
    } finally {
      if (identityRef.current === requestIdentity) setRetryingIdentity(null);
    }
  }, [refresh, reportIdentity, taskId, token]);

  const backButton = (
    <Button sx={TOUCH_ACTION_SX} onClick={() => navigate(BACK_PATH)}>{t('report:back_to_list', '返回复盘列表')}</Button>
  );

  if (!isAuthenticated) {
    return (
      <Box sx={{ p: 3, bgcolor: 'background.default', height: '100%' }}>
        <Alert severity="info">{t('report:login_required_detail', '请登录后查看复盘详情。')}</Alert>
        {backButton}
      </Box>
    );
  }

  if (loading && !game) {
    return (
      <Box sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress aria-label={t('report:loading_detail', '正在加载复盘')} />
      </Box>
    );
  }

  if (!game) {
    return (
      <Box sx={{ p: 3, bgcolor: 'background.default', height: '100%' }}>
        <Alert severity="error">{error || t('report:not_found', '未找到复盘。')}</Alert>
        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
          <Button sx={TOUCH_ACTION_SX} variant="contained" onClick={() => void handleRefresh()}>{t('report:retry_load', '重试加载')}</Button>
          {backButton}
        </Box>
      </Box>
    );
  }

  if (!previewData) {
    return (
      <Box sx={{ p: 3, bgcolor: 'background.default', height: '100%' }}>
        <Alert severity="warning">{t('report:no_sgf', '暂无棋谱数据，无法复盘。')}</Alert>
        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
          <Button sx={TOUCH_ACTION_SX} variant="contained" onClick={() => void handleRefresh()}>{t('report:reload', '重新加载')}</Button>
          {backButton}
        </Box>
      </Box>
    );
  }

  const playerMatchup = `${game.player_black || t('report:black', '黑方')} vs ${game.player_white || t('report:white', '白方')}`;
  const title = game.title?.trim() || playerMatchup;
  const taskStatus = taskStatusLabel(task?.status, t);
  const reportType = reportTypeLabel(task?.report_type, t);

  return (
    <Box sx={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>
      <Box
        data-testid="report-detail-board"
        sx={{ height: '100%', aspectRatio: '1', flexShrink: 0, position: 'relative' }}
      >
        <LiveBoard
          moves={previewData.moves}
          stoneColors={previewData.stoneColors}
          currentMove={currentMove}
          boardSize={boardSize}
          pvMoves={pvMoves}
          aiMarkers={aiMarkers}
          showAiMarkers={showAiMarkers}
          showMoveNumbers={showMoveNumbers}
          showTerritory={showTerritory}
          ownership={showTerritory ? ownership : null}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? (move) => setTryState((previous) => ({
            identity: reportIdentity,
            baseMove: currentMove,
            moves: [
              ...(previous?.identity === reportIdentity
                && previous.baseMove === currentMove
                ? previous.moves
                : []),
              move,
            ],
          })) : undefined}
          onIntersectionClick={!tryMoveMode && activeMove ? () => setActiveVariation(null) : undefined}
        />
        {activeMove && (
          <Box sx={{ position: 'absolute', top: 8, left: 8, zIndex: 2, display: 'flex', gap: 0.5, alignItems: 'center' }}>
            <Chip label={t('report:variation_preview', '变化预览 · 点击棋盘关闭')} sx={{ bgcolor: 'var(--raise2)' }} />
            <Button sx={TOUCH_ACTION_SX} variant="contained" onClick={() => setActiveVariation(null)}>
              {t('report:clear_variation', '清除变化')}
            </Button>
          </Box>
        )}
      </Box>

      <Box
        data-testid="report-detail-right"
        sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: 1, borderColor: 'divider' }}
      >
        <SubPageBar
          title={title}
          to={BACK_PATH}
          right={(
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
              {task && <Typography data-testid="report-detail-status" variant="caption" color="text.secondary" noWrap>{taskStatus} · {reportType}</Typography>}
              <Button
                variant="outlined"
                sx={{ ...TOUCH_ACTION_SX, flexShrink: 0, whiteSpace: 'nowrap' }}
                onClick={() => {
                  const params = new URLSearchParams({ user_game_id: game.id });
                  navigate(`/kiosk/research?${params.toString()}`);
                }}
              >
                {t('report:enter_research', '在研究中打开')}
              </Button>
            </Box>
          )}
        />

        <Box
          data-testid="report-detail-analysis-scroll"
          sx={{ flex: 1, minHeight: 0, overflowY: 'auto', overscrollBehavior: 'contain' }}
        >
        {(error || retryError) && (
          <Alert
            severity="error"
            action={<Button sx={TOUCH_ACTION_SX} color="inherit" onClick={() => void handleRefresh()}>{t('report:retry_load', '重试加载')}</Button>}
            sx={{ flexShrink: 0, py: 0 }}
          >
            {retryError || error}
          </Alert>
        )}

        <ReportMetaPanel game={game} task={task} currentMove={currentMove} currentAnalysis={currentAnalysis} />

        {task?.status === 'failed' && (
          <Box sx={{ px: 1.5, py: 0.5, flexShrink: 0 }}>
            <Button sx={TOUCH_ACTION_SX} variant="contained" disabled={retrying} onClick={() => void handleRetryReport()}>
              {retrying ? t('report:retrying', '正在重试…') : t('report:retry', '重试复盘')}
            </Button>
          </Box>
        )}

        <Box sx={{ px: 1.5, py: 0.75, borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
          <ToggleButtonGroup size="small" sx={{ width: '100%', display: 'flex' }}>
            <ToggleButton aria-label={t('report:try', '试下')} value="try" selected={tryMoveMode} onChange={handleTryToggle} sx={{ flex: 1, ...TOUCH_ACTION_SX }}>
              <TouchAppIcon fontSize="small" /><Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:try', '试下')}</Typography>
            </ToggleButton>
            <ToggleButton aria-label={t('report:territory', '形势')} value="territory" selected={showTerritory} disabled={!ownership} onChange={() => setShowTerritory((shown) => !shown)} sx={{ flex: 1, ...TOUCH_ACTION_SX }}>
              <MapIcon fontSize="small" /><Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:territory', '形势')}</Typography>
            </ToggleButton>
            <ToggleButton aria-label={t('report:move_numbers', '手数')} value="numbers" selected={showMoveNumbers} onChange={() => setShowMoveNumbers((shown) => !shown)} sx={{ flex: 1, ...TOUCH_ACTION_SX }}>
              <FormatListNumberedIcon fontSize="small" /><Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:move_numbers', '手数')}</Typography>
            </ToggleButton>
            <ToggleButton aria-label={t('report:suggestions', 'AI')} value="ai" selected={showAiMarkers} onChange={() => setShowAiMarkers((shown) => !shown)} sx={{ flex: 1, ...TOUCH_ACTION_SX }}>
              <TipsAndUpdatesIcon fontSize="small" /><Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:suggestions', 'AI')}</Typography>
            </ToggleButton>
          </ToggleButtonGroup>
          {tryMoveMode && tryMoves.length > 0 && (
            <Box sx={{ mt: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary">{t('report:try', '试下')}: {tryMoves.join(' → ')}</Typography>
              <Button sx={TOUCH_ACTION_SX} size="small" onClick={() => setTryState(null)}>{t('report:clear', '清空')}</Button>
            </Box>
          )}
        </Box>

        <Box sx={{ borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
          <AiAnalysis
            currentMove={currentMove}
            analysis={analysisByMove}
            onMoveSelect={(move) => setActiveVariation(move ? {
              identity: reportIdentity,
              position: currentMove,
              move,
            } : null)}
            activeMove={activeMove}
          />
        </Box>
        <Box sx={{ height: 180, minHeight: 180, overflow: 'hidden' }}>
          <TrendChart analysis={analysisByMove} totalMoves={totalMoves} currentMove={currentMove} onMoveClick={handleMoveChange} />
        </Box>
        </Box>
        <Box data-testid="report-detail-playback-fixed" sx={{ flexShrink: 0 }}>
          <PlaybackBar currentMove={currentMove} totalMoves={totalMoves} onMoveChange={handleMoveChange} touchSized />
        </Box>
      </Box>
    </Box>
  );
}
