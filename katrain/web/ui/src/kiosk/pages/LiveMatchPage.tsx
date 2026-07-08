import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import MatchInfo from '../../components/live/MatchInfo';
import PlaybackBar from '../../components/live/PlaybackBar';
import TrendChart from '../../components/live/TrendChart';
import AiAnalysis from '../../components/live/AiAnalysis';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useImmersive } from '../context/ImmersiveContext';

const LiveMatchPage = () => {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
  const { setImmersive } = useImmersive();

  // Full-screen session/observing view — hide the kiosk Header + Dock like
  // ResearchPage; this page already has its own back button (below).
  useEffect(() => {
    setImmersive(true);
    return () => setImmersive(false);
  }, [setImmersive]);

  // Board feature toggles
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  // Touch PV preview: which recommended move is tapped-open (parent-owned so the
  // derived PV auto-resets when currentMove/analysis change — no effects).
  const [activeMove, setActiveMove] = useState<string | null>(null);

  const { match, loading, error, currentMove, setCurrentMove, analysis } = useLiveMatch(matchId);

  // Stone sound on move change (navigation or new live moves)
  const prevMoveRef = useRef<number | null>(null);
  useEffect(() => {
    if (match && currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, match, playSound]);

  // AI markers + ownership from the current position's analysis (mirrors Galaxy).
  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    const a = analysis[currentMove];
    if (!a?.top_moves || a.top_moves.length === 0) return null;
    return a.top_moves.slice(0, 3).map((tm, index) => ({
      move: tm.move,
      rank: index + 1,
      visits: tm.visits,
      winrate: tm.winrate ?? 0,
      score_lead: tm.score_lead ?? 0,
    }));
  }, [analysis, currentMove]);

  const ownership = useMemo(() => analysis[currentMove]?.ownership || null, [analysis, currentMove]);

  // Derived PV for the tapped recommended move at this position. If activeMove is
  // not among this position's top moves (e.g. after navigation), it resolves to null.
  const pvMoves = useMemo(() => {
    if (!activeMove) return null;
    return analysis[currentMove]?.top_moves?.find((m) => m.move === activeMove)?.pv ?? null;
  }, [activeMove, analysis, currentMove]);

  // Navigation clears the tapped PV (the variation belongs to a single position).
  const handleMoveChange = useCallback(
    (move: number) => {
      setActiveMove(null);
      setCurrentMove(move);
    },
    [setCurrentMove]
  );

  const handleToggleTry = useCallback(() => {
    setTryMoveMode((on) => {
      if (on) setTryMoves([]); // leaving try mode clears the experiment
      return !on;
    });
    setActiveMove(null);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error || !match) {
    return (
      <Box sx={{ p: 2, bgcolor: 'background.default' }}>
        <Alert severity="error">{error?.message || t('Failed to load match', '加载对局失败')}</Alert>
        <Button onClick={() => navigate('/kiosk/live')} startIcon={<ArrowBackIcon />} sx={{ mt: 1 }}>
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', bgcolor: 'background.default' }}>
      {/* Board */}
      <Box
        sx={{ height: '100%', aspectRatio: '1', flexShrink: 0, position: 'relative' }}
      >
        <LiveBoard
          moves={match.moves}
          currentMove={currentMove}
          boardSize={match.board_size}
          pvMoves={pvMoves}
          aiMarkers={aiMarkers}
          showAiMarkers={showAiMarkers}
          showMoveNumbers={showMoveNumbers}
          showTerritory={showTerritory}
          ownership={ownership}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? (move: string) => setTryMoves((prev) => [...prev, move]) : undefined}
          onIntersectionClick={!tryMoveMode && activeMove ? () => setActiveMove(null) : undefined}
        />
        {activeMove !== null && (
          <Chip
            label={t('Variation preview · tap board to close', '变化预览 · 点击棋盘关闭')}
            sx={{
              position: 'absolute',
              top: 8,
              left: 8,
              zIndex: 2,
              bgcolor: 'var(--raise2)',
              color: 'text.secondary',
            }}
          />
        )}
      </Box>

      {/* Right (or bottom) panel */}
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid', borderTop: 'none', borderColor: 'divider' }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1, flexShrink: 0 }}>
          <IconButton onClick={() => navigate('/kiosk/live')} size="small">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flex: 1, fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500 }} noWrap>
            {match.player_black} vs {match.player_white}
          </Typography>
          <Chip
            label={match.status === 'live' ? t('Live Status', '直播中') : t('Ended', '已结束')}
            size="small"
            color={match.status === 'live' ? 'success' : 'default'}
          />
        </Box>

        {/* Match info */}
        <MatchInfo match={match} currentMove={currentMove} analysis={analysis[currentMove]} />

        {/* Feature toggles — persistent text labels (no hover tooltips on touch) */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', flexShrink: 0 }}>
          <ToggleButtonGroup size="small" sx={{ width: '100%', display: 'flex' }}>
            <ToggleButton value="tryMove" selected={tryMoveMode} onChange={handleToggleTry} sx={{ flex: 1, py: 0.75 }}>
              <TouchAppIcon fontSize="small" />
              <Typography variant="caption" sx={{ ml: 0.5 }}>{t('Try', '试下')}</Typography>
            </ToggleButton>
            <ToggleButton
              value="territory"
              selected={showTerritory}
              onChange={() => setShowTerritory((v) => !v)}
              disabled={!ownership}
              sx={{ flex: 1, py: 0.75 }}
            >
              <MapIcon fontSize="small" />
              <Typography variant="caption" sx={{ ml: 0.5 }}>{t('Territory', '形势')}</Typography>
            </ToggleButton>
            <ToggleButton value="numbers" selected={showMoveNumbers} onChange={() => setShowMoveNumbers((v) => !v)} sx={{ flex: 1, py: 0.75 }}>
              <FormatListNumberedIcon fontSize="small" />
              <Typography variant="caption" sx={{ ml: 0.5 }}>{t('Numbers', '手数')}</Typography>
            </ToggleButton>
            <ToggleButton value="aiMarkers" selected={showAiMarkers} onChange={() => setShowAiMarkers((v) => !v)} sx={{ flex: 1, py: 0.75 }}>
              <TipsAndUpdatesIcon fontSize="small" />
              <Typography variant="caption" sx={{ ml: 0.5 }}>{t('AI', 'AI')}</Typography>
            </ToggleButton>
          </ToggleButtonGroup>
          {tryMoveMode && tryMoves.length > 0 && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="caption" color="text.secondary">
                {t('Try', '试下')}: {tryMoves.join(' → ')}
              </Typography>
              <Button size="small" onClick={() => setTryMoves([])}>{t('Clear', '清空')}</Button>
            </Box>
          )}
        </Box>

        {/* AI recommendations — tap a row to preview its variation */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
          <AiAnalysis
            currentMove={currentMove}
            analysis={analysis}
            onMoveSelect={setActiveMove}
            activeMove={activeMove}
          />
        </Box>

        {/* Trend chart */}
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <TrendChart analysis={analysis} totalMoves={match.move_count} currentMove={currentMove} onMoveClick={handleMoveChange} />
        </Box>

        {/* Playback */}
        <PlaybackBar currentMove={currentMove} totalMoves={match.move_count} onMoveChange={handleMoveChange} isLive={match.status === 'live'} />
      </Box>
    </Box>
  );
};

export default LiveMatchPage;
