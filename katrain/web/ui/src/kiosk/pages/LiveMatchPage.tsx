import { useRef, useEffect } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import { useLiveMatch } from '../../hooks/live/useLiveMatch';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import LiveBoard from '../../components/live/LiveBoard';

const LiveMatchPage = () => {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
  const { match, loading, error, currentMove } = useLiveMatch(matchId);

  const prevMoveRef = useRef<number | null>(null);
  useEffect(() => {
    if (match && currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, match, playSound]);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><CircularProgress /></Box>;
  if (error) return <Box sx={{ p: 2 }}><Alert severity="error">{error.message}</Alert><Button onClick={() => navigate('/kiosk/live')} sx={{ mt: 1 }}>{t('Back', '返回')}</Button></Box>;
  if (!match) return null;

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ height: '100%', aspectRatio: '1' }}>
        <LiveBoard
          moves={match.moves}
          currentMove={currentMove}
          boardSize={match.board_size}
        />
      </Box>
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Button onClick={() => navigate('/kiosk/live')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
          <Typography variant="h6">{match.tournament}</Typography>
          <Chip
            label={match.status === 'live' ? t('Live Status', '直播中') : t('Ended', '已结束')}
            size="small"
            color={match.status === 'live' ? 'success' : 'default'}
          />
        </Box>
        <Typography variant="body1" sx={{ mb: 1 }}>
          {match.player_black} {match.black_rank && `(${match.black_rank})`} vs {match.player_white} {match.white_rank && `(${match.white_rank})`}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('Move #', '第')}{currentMove}{t('moves', '手')} / {match.move_count}{t('moves', '手')}
        </Typography>
        {match.result && (
          <Typography variant="body2" sx={{ mt: 1 }}>
            {t('Result', '结果')}: {match.result}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default LiveMatchPage;
