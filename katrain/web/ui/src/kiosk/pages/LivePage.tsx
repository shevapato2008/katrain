import { useState, useCallback } from 'react';
import { Box, Typography, Tabs, Tab, Button, CircularProgress, Alert, Chip } from '@mui/material';
import { LiveTv } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import MatchList from '../../components/live/MatchList';
import LiveBoard from '../../components/live/LiveBoard';
import PlaybackBar from '../../components/live/PlaybackBar';
import UpcomingList from '../../components/live/UpcomingList';
import type { MatchSummary } from '../../types/live';
import { useTranslation } from '../../hooks/useTranslation';

const LivePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [rightTab, setRightTab] = useState(0);
  // null = no explicit user choice yet; we fall back to the first live match below.
  const [pickedMatchId, setPickedMatchId] = useState<string | null>(null);

  const { matches, liveCount, loading, error } = useLiveMatches({ limit: 50 });

  // Effective selection: explicit user pick, else first live match, else first match.
  // Derived (no effect) so the preview shows immediately and we avoid a setState-in-effect.
  const selectedMatchId =
    pickedMatchId ?? matches.find((m) => m.status === 'live')?.id ?? matches[0]?.id;

  // Board preview only needs moves + playback. analysisMode 'none' keeps the
  // kiosk a strict thin client on the list screen: no preload, no analysis poll.
  const {
    match: selectedMatch,
    loading: matchLoading,
    currentMove,
    setCurrentMove,
  } = useLiveMatch(selectedMatchId || undefined, { pollInterval: 5000, analysisMode: 'none' });

  const handleSelectMatch = useCallback((match: MatchSummary) => {
    setPickedMatchId(match.id);
  }, []);

  const handleEnterMatch = () => {
    if (selectedMatchId) navigate(`/kiosk/live/${selectedMatchId}`);
  };

  const liveMatches = matches.filter((m) => m.status === 'live');
  const finishedMatches = matches.filter((m) => m.status === 'finished');

  if (loading && matches.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', bgcolor: 'background.default' }}>
      {/* Board preview + playback */}
      <Box
        sx={{
          height: '100%', width: '52%', flexShrink: 0, borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          p: 2,
        }}
      >
        {selectedMatch ? (
          <>
            {selectedMatch.status === 'live' && (
              <Box sx={{ mb: 1 }}>
                <Chip
                  label={t('Live', '直播中')}
                  size="small"
                  sx={{
                    bgcolor: 'transparent',
                    color: 'error.main',
                    '& .MuiChip-label': { pl: 0.5 },
                    '&::before': {
                      content: '""',
                      display: 'inline-block',
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      backgroundColor: 'error.main',
                      boxShadow: '0 0 7px',
                      mr: 0.75,
                    },
                  }}
                />
              </Box>
            )}
            {selectedMatch.status === 'finished' && (
              <Box sx={{ mb: 1 }}>
                <Chip
                  label={t('Ended', '已结束')}
                  size="small"
                  sx={{
                    bgcolor: 'var(--raise2)',
                    color: 'text.secondary',
                  }}
                />
              </Box>
            )}
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <LiveBoard
                moves={selectedMatch.moves}
                currentMove={currentMove}
                boardSize={selectedMatch.board_size}
                showMoveNumbers={false}
              />
            </Box>
            <PlaybackBar
              currentMove={currentMove}
              totalMoves={selectedMatch.move_count}
              onMoveChange={setCurrentMove}
              isLive={selectedMatch.status === 'live'}
            />
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {matchLoading ? (
              <CircularProgress />
            ) : (
              <Typography color="text.secondary">{t('Select a match', '请选择对局')}</Typography>
            )}
          </Box>
        )}
      </Box>

      {/* Right panel: header + tabs + lists + enter button */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ px: 2, pt: 2, pb: 1, flexShrink: 0 }}>
          <Typography variant="h5" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500 }}>{t('Live', '直播')}</Typography>
        </Box>
        <Box sx={{ px: 2, borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
          <Tabs
            value={rightTab}
            onChange={(_, v) => setRightTab(v)}
            sx={{
              minHeight: 36,
              '& .MuiTabs-indicator': { bgcolor: 'primary.main' },
              '& .Mui-selected': { color: 'primary.main' },
            }}
            textColor="inherit"
          >
            <Tab label={t('Top Matches', '热门对局')} />
            <Tab label={t('Upcoming', '即将开始')} />
          </Tabs>
        </Box>

        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {rightTab === 0 ? (
            <>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: 'error.main', boxShadow: '0 0 7px' }} />
                  {t('Now Live', '直播中')} ({liveCount})
                </Typography>
                {liveMatches.length > 0 ? (
                  <MatchList
                    matches={liveMatches}
                    compact
                    selectedId={selectedMatchId || undefined}
                    onSelect={handleSelectMatch}
                  />
                ) : (
                  <Box
                    sx={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 1.5,
                      p: 3,
                      border: '1px dashed',
                      borderColor: 'divider',
                      borderRadius: 2,
                      bgcolor: 'background.paper',
                    }}
                  >
                    <LiveTv sx={{ fontSize: 40, color: 'divider' }} />
                    <Typography color="text.secondary">
                      {t('No live matches', '暂无直播')}
                    </Typography>
                  </Box>
                )}
              </Box>
              <Box>
                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                  {t('History', '历史')}
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
            // The "即将开始" empty state is owned by UpcomingList shared component (rendered internally, not duplicated here)
            <UpcomingList limit={20} />
          )}
        </Box>

        {rightTab === 0 && (
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', flexShrink: 0 }}>
            <Button
              variant="contained"
              fullWidth
              size="large"
              onClick={handleEnterMatch}
              disabled={!selectedMatchId || matchLoading}
              sx={{ py: 1.5 }}
            >
              {selectedMatch?.status === 'live' ? t('Enter Live', '进入直播') : t('Review', '复盘')}
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default LivePage;
