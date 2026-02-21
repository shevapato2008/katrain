import { Box, Typography, Tabs, Tab, Button, CircularProgress } from '@mui/material';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLiveMatches } from '../../../hooks/live/useLiveMatches';
import { useLiveMatch } from '../../../hooks/live/useLiveMatch';
import MatchList from '../../components/live/MatchList';
import LiveBoard from '../../../components/live/LiveBoard';
import PlaybackBar from '../../components/live/PlaybackBar';
import UpcomingList from '../../components/live/UpcomingList';
import type { MatchSummary } from '../../../types/live';
import { useTranslation } from '../../../hooks/useTranslation';

export default function LivePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [rightTab, setRightTab] = useState(0);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  const { matches, liveCount, loading } = useLiveMatches({ limit: 50 });

  // Get detailed match data for the selected match
  const {
    match: selectedMatch,
    loading: matchLoading,
    currentMove,
    setCurrentMove,
  } = useLiveMatch(selectedMatchId || undefined, { pollInterval: 5000 });

  // Auto-select first match when matches load
  useEffect(() => {
    if (matches.length > 0 && !selectedMatchId) {
      // Prefer live matches, otherwise first match
      const liveMatch = matches.find((m) => m.status === 'live');
      setSelectedMatchId(liveMatch?.id || matches[0].id);
    }
  }, [matches, selectedMatchId]);

  const handleSelectMatch = useCallback((match: MatchSummary) => {
    setSelectedMatchId(match.id);
  }, []);

  const handleEnterMatch = () => {
    if (selectedMatchId) {
      navigate(`/galaxy/live/${selectedMatchId}`);
    }
  };

  // Split matches for display
  const liveMatches = matches.filter((m) => m.status === 'live');
  const finishedMatches = matches.filter((m) => m.status === 'finished');

  return (
    <Box sx={{ display: 'flex', flexGrow: 1, overflow: 'hidden', height: '100%' }}>
      {/* Main content area - Board */}
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
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h4" fontWeight="bold">
            {t('Live')}
          </Typography>
        </Box>

        {/* Board area */}
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {loading && !selectedMatch ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
              <CircularProgress />
            </Box>
          ) : selectedMatch ? (
            <>
              <Box sx={{ flex: 1, minHeight: 0 }}>
                <LiveBoard
                  moves={selectedMatch.moves}
                  currentMove={currentMove}
                  showMoveNumbers={false}
                />
              </Box>

              {/* Playback controls */}
              <PlaybackBar
                currentMove={currentMove}
                totalMoves={selectedMatch.move_count}
                onMoveChange={setCurrentMove}
                isLive={selectedMatch.status === 'live'}
              />
            </>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
              <Typography color="text.secondary">
                {matches.length === 0 ? t('live:no_matches') : t('live:select_match')}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>

      {/* Right sidebar - matches list */}
      <Box
        sx={{
          width: 500,
          borderLeft: 1,
          borderColor: 'divider',
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          overflow: 'hidden',
          bgcolor: 'rgba(40, 40, 45, 0.95)',
        }}
      >
        {/* Tabs */}
        <Box sx={{ px: 2, pt: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={rightTab} onChange={(_, v) => setRightTab(v)}>
            <Tab label={t('live:top_matches')} />
            <Tab label={t('live:upcoming')} />
          </Tabs>
        </Box>

        {/* Match list */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {rightTab === 0 ? (
            <>
              {liveCount > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                    {t('live:now_live')} ({liveCount})
                  </Typography>
                  <MatchList
                    matches={liveMatches}
                    compact
                    selectedId={selectedMatchId || undefined}
                    onSelect={handleSelectMatch}
                  />
                </Box>
              )}
              <Box>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                  {t('live:history')}
                </Typography>
                <MatchList
                  matches={finishedMatches.slice(0, 10)}
                  loading={loading}
                  compact
                  selectedId={selectedMatchId || undefined}
                  onSelect={handleSelectMatch}
                />
              </Box>
            </>
          ) : (
            <UpcomingList limit={20} />
          )}
        </Box>

        {/* Enter match button - only show for Top Matches tab */}
        {rightTab === 0 && (
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
            <Button
              variant="contained"
              fullWidth
              size="large"
              onClick={handleEnterMatch}
              disabled={!selectedMatchId || matchLoading}
              sx={{ py: 1.5 }}
            >
              {selectedMatch?.status === 'live' ? t('live:enter_live') : t('live:view_game')}
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
}
