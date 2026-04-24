import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MapIcon from '@mui/icons-material/Map';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';

import LiveBoard, { type AiMoveMarker } from '../../../components/live/LiveBoard';
import { useAuth } from '../../../context/AuthContext';
import { useSound } from '../../../hooks/useSound';
import { useTranslation } from '../../../hooks/useTranslation';
import { sgfToMoves } from '../../../utils/sgfSerializer';
import type { MoveAnalysis } from '../../../types/live';
import { UserGamesAPI, type UserGameDetail } from '../../api/userGamesApi';
import { ReportsAPI, type ReportTaskMove, type ReportTaskSummary } from '../../api/reportApi';
import AiAnalysis from '../../components/live/AiAnalysis';
import PlaybackBar from '../../components/live/PlaybackBar';
import TrendChart from '../../components/live/TrendChart';
import ReportMetaPanel from '../../components/report/ReportMetaPanel';

export default function ReportDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();

  const [task, setTask] = useState<ReportTaskSummary | null>(null);
  const [game, setGame] = useState<UserGameDetail | null>(null);
  const [moves, setMoves] = useState<ReportTaskMove[]>([]);
  const [currentMove, setCurrentMove] = useState(0);
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const analyzedMovesRef = useRef(0);

  // Sound on move navigation
  const { play: playSound } = useSound();
  const prevMoveRef = useRef<number | null>(null);

  useEffect(() => {
    if (currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, playSound]);

  const loadReport = useCallback(async () => {
    if (!token || !isAuthenticated || !taskId) {
      setLoading(false);
      return { shouldPoll: false };
    }

    const taskResp = await ReportsAPI.get(token, Number(taskId));
    const [movesResp, gameResp] = await Promise.all([
      ReportsAPI.getMoves(token, Number(taskId)),
      UserGamesAPI.get(token, taskResp.user_game_id),
    ]);

    setTask(taskResp);
    setMoves(movesResp);
    setGame(gameResp);
    setError(null);

    const latestMove = movesResp.length > 0 ? Math.min(movesResp.length, taskResp.analyzed_moves) : 0;
    setCurrentMove((prev) => {
      if (prev === 0 || prev >= analyzedMovesRef.current) {
        return latestMove;
      }
      return Math.min(prev, latestMove);
    });
    analyzedMovesRef.current = latestMove;

    return { shouldPoll: taskResp.status === 'pending' || taskResp.status === 'running' };
  }, [isAuthenticated, taskId, token]);

  useEffect(() => {
    let cancelled = false;
    let intervalId: number | null = null;

    const bootstrap = async () => {
      try {
        setLoading(true);
        const { shouldPoll } = await loadReport();
        if (!cancelled && shouldPoll) {
          intervalId = window.setInterval(async () => {
            try {
              const refresh = await loadReport();
              if (!refresh.shouldPoll && intervalId != null) {
                window.clearInterval(intervalId);
                intervalId = null;
              }
            } catch (err) {
              if (!cancelled) {
                setError(err instanceof Error ? err.message : t('report:refresh_failed', 'Failed to refresh report'));
              }
            }
          }, 2000);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t('report:load_failed', 'Failed to load report'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    bootstrap();

    return () => {
      cancelled = true;
      if (intervalId != null) {
        window.clearInterval(intervalId);
      }
    };
  }, [loadReport]);

  const previewData = useMemo(() => {
    if (!game?.sgf_content) return null;
    return sgfToMoves(game.sgf_content);
  }, [game]);

  const analysisByMove = useMemo<Record<number, MoveAnalysis>>(() => {
    const map: Record<number, MoveAnalysis> = {};
    for (const move of moves) {
      if (move.winrate == null || move.score_lead == null) continue;
      map[move.move_number] = {
        match_id: task?.user_game_id || '',
        move_number: move.move_number,
        move: move.actual_move,
        player: move.actual_player,
        winrate: move.winrate,
        score_lead: move.score_lead,
        top_moves: move.top_moves || [],
        ownership: move.ownership,
        is_brilliant: (move.delta_score || 0) >= 2,
        is_mistake: (move.delta_score || 0) <= -3,
        is_questionable: (move.delta_score || 0) <= -1.5,
        delta_score: move.delta_score || 0,
        delta_winrate: move.delta_winrate || 0,
      };
    }
    return map;
  }, [moves, task]);

  const currentAnalysis = analysisByMove[currentMove] || null;

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!showAiMarkers || !currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((topMove, index) => ({
      move: topMove.move,
      rank: index + 1,
      visits: topMove.visits,
      winrate: topMove.winrate ?? 0,
      score_lead: topMove.score_lead ?? 0,
    }));
  }, [currentAnalysis, showAiMarkers]);

  const ownership = showTerritory ? currentAnalysis?.ownership || null : null;
  const boardSize = previewData?.metadata.boardSize || game?.board_size || 19;

  if (!isAuthenticated) {
    return (
      <Box p={4}>
        <Alert severity="info">{t('report:login_required_detail', 'Please log in to view report details.')}</Alert>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box p={4}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={4}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button variant="outlined" onClick={() => navigate('/galaxy/report')}>{t('report:back_to_list', 'Back to review list')}</Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 2.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <IconButton onClick={() => navigate('/galaxy/report')} size="small">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flex: 1 }} noWrap>
            {game?.player_black || t('report:black', 'Black')} vs {game?.player_white || t('report:white', 'White')}
          </Typography>
          <Button variant="outlined" size="small" onClick={() => navigate('/galaxy/research')}>
            {t('report:enter_research', 'Open in Research')}
          </Button>
        </Box>

        <Box sx={{ flex: 1, minHeight: 0 }}>
          {previewData ? (
            <LiveBoard
              moves={previewData.moves}
              stoneColors={previewData.stoneColors}
              currentMove={currentMove}
              pvMoves={pvMoves}
              boardSize={boardSize}
              aiMarkers={aiMarkers}
              showAiMarkers={showAiMarkers}
              showMoveNumbers={showMoveNumbers}
              showTerritory={showTerritory}
              ownership={ownership}
              tryMoves={tryMoveMode ? tryMoves : undefined}
              onTryMove={tryMoveMode ? (move: string) => setTryMoves((prev) => [...prev, move]) : undefined}
            />
          ) : (
            <Alert severity="info">{t('report:no_sgf', 'No SGF data available for review.')}</Alert>
          )}
        </Box>
      </Box>

      <Box
        sx={{
          width: 500,
          borderLeft: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          bgcolor: 'rgba(40, 40, 45, 0.95)',
        }}
      >
        <ReportMetaPanel
          game={game}
          task={task}
          currentMove={currentMove}
          currentAnalysis={currentAnalysis}
        />

        <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.03)' }}>
          <ToggleButtonGroup size="small" sx={{ width: '100%', display: 'flex' }}>
            <Tooltip title={t('report:try', 'Try')}>
              <ToggleButton
                value="tryMove"
                selected={tryMoveMode}
                onChange={() => {
                  setTryMoveMode(!tryMoveMode);
                  if (tryMoveMode) {
                    setTryMoves([]);
                  }
                }}
                sx={{ flex: 1, py: 0.5 }}
              >
                <TouchAppIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:try', 'Try')}</Typography>
              </ToggleButton>
            </Tooltip>
            {currentAnalysis?.ownership ? (
              <Tooltip title={t('report:territory', 'Territory')}>
                <ToggleButton
                  value="territory"
                  selected={showTerritory}
                  onChange={() => setShowTerritory(!showTerritory)}
                  sx={{ flex: 1, py: 0.5 }}
                >
                  <MapIcon fontSize="small" />
                  <Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:territory', 'Territory')}</Typography>
                </ToggleButton>
              </Tooltip>
            ) : (
              <ToggleButton
                value="territory"
                selected={showTerritory}
                onChange={() => setShowTerritory(!showTerritory)}
                sx={{ flex: 1, py: 0.5 }}
                disabled
              >
                <MapIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:territory', 'Territory')}</Typography>
              </ToggleButton>
            )}
            <Tooltip title={t('report:move_numbers', 'Move #')}>
              <ToggleButton
                value="numbers"
                selected={showMoveNumbers}
                onChange={() => setShowMoveNumbers(!showMoveNumbers)}
                sx={{ flex: 1, py: 0.5 }}
              >
                <FormatListNumberedIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:move_numbers', 'Move #')}</Typography>
              </ToggleButton>
            </Tooltip>
            <Tooltip title={showAiMarkers ? t('report:hide_suggestions', 'Hide hints') : t('report:show_suggestions', 'Show hints')}>
              <ToggleButton
                value="advice"
                selected={showAiMarkers}
                onChange={() => setShowAiMarkers(!showAiMarkers)}
                sx={{ flex: 1, py: 0.5 }}
              >
                <TipsAndUpdatesIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>{t('report:suggestions', 'Hints')}</Typography>
              </ToggleButton>
            </Tooltip>
          </ToggleButtonGroup>
          {tryMoveMode && tryMoves.length > 0 && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary">
                TRY: {tryMoves.join(' → ')}
              </Typography>
              <Button size="small" onClick={() => setTryMoves([])}>{t('report:clear', 'Clear')}</Button>
            </Box>
          )}
        </Box>

        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <AiAnalysis currentMove={currentMove} analysis={analysisByMove} onMoveHover={setPvMoves} />
        </Box>

        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <TrendChart
            analysis={analysisByMove}
            totalMoves={previewData?.moves.length || 0}
            currentMove={currentMove}
            onMoveClick={setCurrentMove}
          />
        </Box>

        <PlaybackBar
          currentMove={currentMove}
          totalMoves={previewData?.moves.length || 0}
          onMoveChange={setCurrentMove}
        />
      </Box>
    </Box>
  );
}
