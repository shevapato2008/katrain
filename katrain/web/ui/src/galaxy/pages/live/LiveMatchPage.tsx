import { useState, useCallback, useMemo } from 'react';
import { Box, Typography, CircularProgress, Alert, Button, IconButton, ToggleButton, ToggleButtonGroup, Tooltip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import VisibilityIcon from '@mui/icons-material/Visibility';
import MapIcon from '@mui/icons-material/Map';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import MatchInfo from '../../components/live/MatchInfo';
import PlaybackBar from '../../components/live/PlaybackBar';
import TrendChart from '../../components/live/TrendChart';
import AiAnalysis from '../../components/live/AiAnalysis';
// CommentSection import removed - Phase 7 deferred (was obscuring TrendChart)
// import CommentSection from '../../components/live/CommentSection';

export default function LiveMatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  // PV moves for preview variation display
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  // Toggle states for board features
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  // Try moves for experimentation mode
  const [tryMoves, setTryMoves] = useState<string[]>([]);

  const {
    match,
    loading,
    error,
    currentMove,
    setCurrentMove,
    analysis,
  } = useLiveMatch(matchId);

  // Handle PV hover from AI analysis panel - displays variation on board
  const handlePvHover = useCallback((pv: string[] | null) => {
    setPvMoves(pv);
  }, []);

  // Convert current analysis top_moves to AI markers for board display
  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    const currentAnalysis = analysis[currentMove];
    if (!currentAnalysis || !currentAnalysis.top_moves || currentAnalysis.top_moves.length === 0) {
      return null;
    }
    return currentAnalysis.top_moves.slice(0, 3).map((tm, index) => ({
      move: tm.move,
      rank: index + 1,
      visits: tm.visits,
      winrate: tm.winrate,
      score_lead: tm.score_lead,
    }));
  }, [analysis, currentMove]);

  // Get ownership data from current analysis for territory display
  const ownership = useMemo(() => {
    const currentAnalysis = analysis[currentMove];
    return currentAnalysis?.ownership || null;
  }, [analysis, currentMove]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !match) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error?.message || '无法加载比赛数据'}
        </Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/galaxy/live')}>
          返回直播列表
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Main area - Board */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          p: 2,
        }}
      >
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <IconButton onClick={() => navigate('/galaxy/live')} size="small">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flex: 1 }} noWrap>
            {match.player_black} vs {match.player_white}
          </Typography>
        </Box>

        {/* Board */}
        <Box sx={{ flex: 1, minHeight: 0 }}>
          <LiveBoard
            moves={match.moves}
            currentMove={currentMove}
            pvMoves={pvMoves}
            aiMarkers={aiMarkers}
            showAiMarkers={showAiMarkers}
            showMoveNumbers={showMoveNumbers}
            showTerritory={showTerritory}
            ownership={ownership}
            tryMoves={tryMoveMode ? tryMoves : undefined}
            onTryMove={tryMoveMode ? (move: string) => setTryMoves([...tryMoves, move]) : undefined}
          />
        </Box>
      </Box>

      {/* Right sidebar - use lighter background for visibility */}
      <Box
        sx={{
          width: 440,
          borderLeft: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          bgcolor: 'rgba(40, 40, 45, 0.95)', // Slightly lighter than pure black for visibility
        }}
      >
        {/* Match info */}
        <MatchInfo match={match} currentMove={currentMove} analysis={analysis[currentMove]} />

        {/* Feature buttons row */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.03)' }}>
          <ToggleButtonGroup size="small" sx={{ width: '100%', display: 'flex' }}>
            <Tooltip title="试下">
              <ToggleButton
                value="tryMove"
                selected={tryMoveMode}
                onChange={() => {
                  setTryMoveMode(!tryMoveMode);
                  if (tryMoveMode) setTryMoves([]);
                }}
                sx={{ flex: 1, py: 0.5 }}
              >
                <TouchAppIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>试下</Typography>
              </ToggleButton>
            </Tooltip>
            <Tooltip title={ownership ? '领地' : '领地 (需要分析数据)'}>
              <ToggleButton
                value="territory"
                selected={showTerritory}
                onChange={() => setShowTerritory(!showTerritory)}
                sx={{ flex: 1, py: 0.5 }}
                disabled={!ownership}
              >
                <MapIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>领地</Typography>
              </ToggleButton>
            </Tooltip>
            <Tooltip title="手数">
              <ToggleButton
                value="numbers"
                selected={showMoveNumbers}
                onChange={() => setShowMoveNumbers(!showMoveNumbers)}
                sx={{ flex: 1, py: 0.5 }}
              >
                <FormatListNumberedIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>手数</Typography>
              </ToggleButton>
            </Tooltip>
            <Tooltip title={showAiMarkers ? '隐藏AI选点' : '显示AI选点'}>
              <ToggleButton
                value="aiMarkers"
                selected={showAiMarkers}
                onChange={() => setShowAiMarkers(!showAiMarkers)}
                sx={{ flex: 1, py: 0.5 }}
              >
                <VisibilityIcon fontSize="small" />
                <Typography variant="caption" sx={{ ml: 0.5 }}>AI</Typography>
              </ToggleButton>
            </Tooltip>
          </ToggleButtonGroup>
          {tryMoveMode && tryMoves.length > 0 && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary">
                试下: {tryMoves.join(' → ')}
              </Typography>
              <Button size="small" onClick={() => setTryMoves([])}>清除</Button>
            </Box>
          )}
        </Box>

        {/* AI Analysis panel */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <AiAnalysis
            matchId={match.id}
            currentMove={currentMove}
            analysis={analysis}
            onMoveHover={handlePvHover}
          />
        </Box>

        {/* Trend chart and brilliant/mistake moves */}
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <TrendChart
            analysis={analysis}
            totalMoves={match.move_count}
            currentMove={currentMove}
            onMoveClick={setCurrentMove}
          />
        </Box>

        {/* Comment section - hidden for now (Phase 7, deferred)
            Issue: CommentSection was obscuring the TrendChart
        <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
          <CommentSection matchId={match.id} isLive={match.status === 'live'} />
        </Box>
        */}

        {/* Playback controls */}
        <PlaybackBar
          currentMove={currentMove}
          totalMoves={match.move_count}
          onMoveChange={setCurrentMove}
          isLive={match.status === 'live'}
        />
      </Box>
    </Box>
  );
}
