import { Box, Card, CardActionArea, Typography, Chip, LinearProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import type { MatchSummary } from '../../types/live';

interface MatchCardProps {
  match: MatchSummary;
  compact?: boolean;
  selected?: boolean;  // Whether this card is selected
  onSelect?: (match: MatchSummary) => void;  // Callback when selected (doesn't navigate)
}

export default function MatchCard({ match, compact = false, selected = false, onSelect }: MatchCardProps) {
  const navigate = useNavigate();
  const isLive = match.status === 'live';

  // Format winrate as percentage
  const winratePercent = Math.round(match.current_winrate * 100);
  const blackAdvantage = match.current_winrate > 0.5;

  // Format date
  const matchDate = new Date(match.date);
  const dateStr = matchDate.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  });

  const handleClick = () => {
    if (onSelect) {
      onSelect(match);
    } else {
      navigate(`/galaxy/live/${match.id}`);
    }
  };

  if (compact) {
    return (
      <Card sx={{
        mb: 1,
        bgcolor: selected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255, 255, 255, 0.05)',
        border: selected ? 2 : 1,
        borderColor: selected ? 'primary.main' : 'rgba(255, 255, 255, 0.1)',
      }}>
        <CardActionArea onClick={handleClick} sx={{ p: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            {isLive && (
              <FiberManualRecordIcon sx={{ fontSize: 10, color: 'error.main', animation: 'pulse 1.5s infinite' }} />
            )}
            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
              {match.tournament}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {match.move_count}手
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
              {match.player_black}
            </Typography>
            <Typography variant="body2" color="text.secondary">vs</Typography>
            <Typography variant="body2" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
              {match.player_white}
            </Typography>
          </Box>
          <Box sx={{ mt: 1 }}>
            <LinearProgress
              variant="determinate"
              value={winratePercent}
              sx={{
                height: 4,
                borderRadius: 2,
                bgcolor: '#fff',  // Pure white for white player
                '& .MuiLinearProgress-bar': {
                  bgcolor: '#000',  // Pure black for black player
                },
              }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold' }}>{winratePercent}%</Typography>
              <Typography variant="caption" sx={{ fontWeight: 'bold' }}>{100 - winratePercent}%</Typography>
            </Box>
          </Box>
        </CardActionArea>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2, bgcolor: 'background.paper' }}>
      <CardActionArea onClick={handleClick} sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {isLive ? (
            <Chip
              icon={<FiberManualRecordIcon sx={{ fontSize: 10 }} />}
              label="直播中"
              size="small"
              color="error"
              sx={{ '& .MuiChip-icon': { animation: 'pulse 1.5s infinite' } }}
            />
          ) : (
            <Chip label="已结束" size="small" variant="outlined" />
          )}
          <Typography variant="caption" color="text.secondary">
            {dateStr}
          </Typography>
          {match.result && (
            <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
              {match.result}
            </Typography>
          )}
        </Box>

        <Typography variant="subtitle2" color="text.secondary" gutterBottom noWrap>
          {match.tournament} {match.round_name && `· ${match.round_name}`}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, my: 1.5 }}>
          <Box sx={{ flex: 1, textAlign: 'center' }}>
            <Typography variant="h6" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
              {match.player_black}
            </Typography>
            {match.black_rank && (
              <Typography variant="caption" color="text.secondary">
                {match.black_rank}
              </Typography>
            )}
          </Box>
          <Box sx={{ textAlign: 'center', px: 2 }}>
            <Typography variant="h5" fontWeight="bold" color="text.secondary">
              VS
            </Typography>
          </Box>
          <Box sx={{ flex: 1, textAlign: 'center' }}>
            <Typography variant="h6" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
              {match.player_white}
            </Typography>
            {match.white_rank && (
              <Typography variant="caption" color="text.secondary">
                {match.white_rank}
              </Typography>
            )}
          </Box>
        </Box>

        <Box sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" fontWeight={blackAdvantage ? 'bold' : 'normal'} sx={{ color: '#000' }}>
              黑 {winratePercent}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {match.move_count}手
            </Typography>
            <Typography variant="caption" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
              白 {100 - winratePercent}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={winratePercent}
            sx={{
              height: 8,
              borderRadius: 4,
              bgcolor: 'grey.200',
              '& .MuiLinearProgress-bar': {
                bgcolor: '#000',  // Pure black for black player
                borderRadius: 4,
              },
            }}
          />
        </Box>
      </CardActionArea>
    </Card>
  );
}
