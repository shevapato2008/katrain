import { Box, Typography, ButtonBase, Divider, Chip, CircularProgress, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useLiveMatches } from '../../hooks/live/useLiveMatches';

const LivePage = () => {
  const navigate = useNavigate();
  const { matches, liveCount, loading, error } = useLiveMatches();

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><CircularProgress /></Box>;
  if (error) return <Box sx={{ p: 2 }}><Alert severity="error">{error.message}</Alert></Box>;

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', bgcolor: 'background.paper', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.3 }}>直播预览</Typography>
      </Box>
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 2, pb: 1, flexShrink: 0 }}>
          <Typography variant="h5">直播</Typography>
          {liveCount > 0 && <Typography variant="body2" color="text.secondary">{liveCount} 场正在直播</Typography>}
        </Box>
        <Divider />
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {matches.length === 0 ? (
            <Box sx={{ p: 3, textAlign: 'center' }}>
              <Typography color="text.secondary">暂无直播</Typography>
            </Box>
          ) : (
            matches.map((match) => (
              <ButtonBase
                key={match.id}
                onClick={() => navigate(`/kiosk/live/${match.id}`)}
                sx={{
                  display: 'flex',
                  width: '100%',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  p: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  textAlign: 'left',
                  '&:active': { bgcolor: 'rgba(92, 181, 122, 0.08)' },
                }}
              >
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {match.player_black} vs {match.player_white}
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    {match.tournament}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {match.status === 'live' && (
                    <Typography variant="body2" sx={{ fontFamily: "'JetBrains Mono', monospace", color: 'text.secondary' }}>
                      第{match.move_count}手
                    </Typography>
                  )}
                  <Chip
                    label={match.status === 'live' ? '直播中' : '已结束'}
                    size="small"
                    color={match.status === 'live' ? 'success' : 'default'}
                    variant={match.status === 'live' ? 'filled' : 'outlined'}
                  />
                </Box>
              </ButtonBase>
            ))
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default LivePage;
