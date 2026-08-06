import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { Alert, Box, Button, Chip, CircularProgress, Skeleton } from '@mui/material';
import { useParams } from 'react-router-dom';

import AiAnalysis from '../../../components/live/AiAnalysis';
import LiveBoard, { type AiMoveMarker } from '../../../components/live/LiveBoard';
import MatchInfo from '../../../components/live/MatchInfo';
import PlaybackBar from '../../../components/live/PlaybackBar';
import TrendChart from '../../../components/live/TrendChart';
import { useLiveMatch } from '../../../hooks/live/useLiveMatch';
import { useSound } from '../../../hooks/useSound';
import { useTranslation } from '../../../hooks/useTranslation';
import { i18n } from '../../../i18n';
import BoardPageShell from '../../components/board/BoardPageShell';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import ModulePlate from '../../components/layout/ModulePlate';
import LiveMatchDisplayControls from './LiveMatchDisplayControls';

const LoadingControls = () => (
  <Box sx={{ p: 2, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 0.5 }}>
    {Array.from({ length: 5 }, (_, index) => (
      <Button key={index} disabled sx={{ minHeight: 40 }}><Skeleton width="70%" /></Button>
    ))}
  </Box>
);

const LoadingActions = () => (
  <Box sx={{ p: 2 }}>
    <Button fullWidth disabled sx={{ minHeight: 40 }}><Skeleton width="60%" /></Button>
  </Box>
);

export default function LiveMatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const { t } = useTranslation();
  const { match, loading, error, currentMove, setCurrentMove, analysis, refresh } = useLiveMatch(matchId);
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const [boardEdge, setBoardEdge] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const coordinates = useBoardCoordinates(boardEdge);

  const { play: playSound } = useSound();
  const prevMoveRef = useRef<number | null>(null);
  useEffect(() => {
    if (match && currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, match, playSound]);

  const currentAnalysis = analysis[currentMove];
  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((topMove, index) => ({
      move: topMove.move,
      rank: index + 1,
      visits: topMove.visits,
      winrate: topMove.winrate ?? 0,
      score_lead: topMove.score_lead ?? 0,
    }));
  }, [currentAnalysis]);
  const ownership = currentAnalysis?.ownership || null;

  const handleRetry = useCallback(async () => {
    setRetrying(true);
    try {
      await refresh();
    } finally {
      setRetrying(false);
    }
  }, [refresh]);

  if (loading) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={<Skeleton data-testid="board-loading-skeleton" variant="rectangular" width="100%" height="100%" />}
        modulePlate={(
          <ModulePlate
            title={t('live:loading_match', 'Loading live match')}
            subtitle={<Skeleton width={180} />}
            status={<CircularProgress size={22} />}
            backTo="/galaxy/live"
          />
        )}
        railBody={<Box sx={{ p: 2 }}><Skeleton height={120} /><Skeleton height={160} /><Skeleton height={180} /></Box>}
        displayControls={<LoadingControls />}
        actions={<LoadingActions />}
      />
    );
  }

  if (error || !match) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={<Skeleton data-testid="board-error-skeleton" variant="rectangular" width="100%" height="100%" />}
        modulePlate={<ModulePlate title={t('live:match', 'Live match')} backTo="/galaxy/live" />}
        railBody={(
          <Box sx={{ p: 2 }}>
            <Alert severity="error" sx={{ mb: 2 }}>
              {error?.message || t('live:load_error', 'Failed to load match data')}
            </Alert>
            <Button
              variant="outlined"
              aria-label={t('Retry', 'Retry')}
              disabled={retrying}
              onClick={() => void handleRetry()}
              sx={{ minWidth: 96, minHeight: 40 }}
            >
              {retrying ? <CircularProgress size={20} /> : t('Retry', 'Retry')}
            </Button>
          </Box>
        )}
        displayControls={<LoadingControls />}
        actions={<LoadingActions />}
      />
    );
  }

  const tournament = i18n.translateTournament(match.tournament);
  const round = match.round_name ? i18n.translateRound(match.round_name) : null;
  const subtitle = `${tournament}${round ? ` · ${round}` : ''} · ${currentMove} / ${match.move_count} ${t('live:moves')}`;
  const status = match.status === 'live' ? (
    <Chip
      icon={<FiberManualRecordIcon sx={{ fontSize: 10 }} />}
      label={t('live:status_live')}
      size="small"
      color="error"
      sx={{ '& .MuiChip-icon': { animation: 'pulse 1.5s infinite' } }}
    />
  ) : (
    <Chip label={t('live:status_finished')} size="small" variant="outlined" />
  );

  return (
    <BoardPageShell
      onBoardSizeChange={setBoardEdge}
      board={(
        <LiveBoard
          moves={match.moves}
          currentMove={currentMove}
          pvMoves={pvMoves}
          aiMarkers={aiMarkers}
          showAiMarkers={showAiMarkers}
          showMoveNumbers={showMoveNumbers}
          showTerritory={showTerritory}
          showCoordinates={coordinates.visible}
          ownership={ownership}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? (move: string) => setTryMoves((previous) => [...previous, move]) : undefined}
          minimumCanvasSize={0}
          minContainerHeight={0}
        />
      )}
      modulePlate={(
        <ModulePlate
          title={`${i18n.translatePlayer(match.player_black)} vs ${i18n.translatePlayer(match.player_white)}`}
          subtitle={subtitle}
          status={status}
          backTo="/galaxy/live"
        />
      )}
      railBody={(
        <>
          <MatchInfo match={match} currentMove={currentMove} analysis={currentAnalysis} headingMode="metadata-only" />
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <AiAnalysis currentMove={currentMove} analysis={analysis} onMoveHover={setPvMoves} />
          </Box>
          <Box data-testid="live-match-trend-region" sx={{ flex: 'none' }}>
            <TrendChart
              analysis={analysis}
              totalMoves={match.move_count}
              currentMove={currentMove}
              onMoveClick={setCurrentMove}
            />
          </Box>
        </>
      )}
      displayControls={(
        <LiveMatchDisplayControls
          tryMoveMode={tryMoveMode}
          showTerritory={showTerritory}
          showMoveNumbers={showMoveNumbers}
          showAiMarkers={showAiMarkers}
          showCoordinates={coordinates.visible}
          ownershipAvailable={ownership != null}
          tryMoves={tryMoves}
          onTryMoveToggle={() => {
            setTryMoveMode((enabled) => !enabled);
            if (tryMoveMode) setTryMoves([]);
          }}
          onTerritoryToggle={() => setShowTerritory((visible) => !visible)}
          onMoveNumbersToggle={() => setShowMoveNumbers((visible) => !visible)}
          onAiMarkersToggle={() => setShowAiMarkers((visible) => !visible)}
          onCoordinatesToggle={coordinates.toggle}
          onClearTryMoves={() => setTryMoves([])}
        />
      )}
      actions={(
        <PlaybackBar
          currentMove={currentMove}
          totalMoves={match.move_count}
          onMoveChange={setCurrentMove}
          isLive={match.status === 'live'}
        />
      )}
    />
  );
}
