import { Box, Typography, Chip, LinearProgress } from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import type { MatchDetail, MoveAnalysis } from '../../types/live';

interface MatchInfoProps {
  match: MatchDetail;
  currentMove?: number;
  analysis?: MoveAnalysis | null;  // KataGo analysis for current position
}

export default function MatchInfo({ match, currentMove, analysis }: MatchInfoProps) {
  const isLive = match.status === 'live';
  const displayMove = currentMove ?? match.move_count;

  // Use KataGo analysis data if available, otherwise fall back to match data
  const winrate = analysis?.winrate ?? match.current_winrate;
  const scoreLead = analysis?.score_lead ?? match.current_score;
  const winratePercent = Math.round(winrate * 100);
  const blackAdvantage = winrate > 0.5;

  // Format date
  const matchDate = new Date(match.date);
  const dateStr = matchDate.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
      {/* Status and tournament */}
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
      </Box>

      {/* Tournament name */}
      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
        {match.tournament}
        {match.round_name && ` · ${match.round_name}`}
      </Typography>

      {/* Players */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, my: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                bgcolor: '#000',  // Pure black stone
                boxShadow: '0 1px 2px rgba(0,0,0,0.3)',
              }}
            />
            <Typography variant="body1" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
              {match.player_black}
            </Typography>
            {match.black_rank && (
              <Typography variant="caption" color="text.secondary">
                {match.black_rank}
              </Typography>
            )}
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary">vs</Typography>
        <Box sx={{ flex: 1, textAlign: 'right' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
            {match.white_rank && (
              <Typography variant="caption" color="text.secondary">
                {match.white_rank}
              </Typography>
            )}
            <Typography variant="body1" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
              {match.player_white}
            </Typography>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                bgcolor: '#fff',  // Pure white stone
                border: '1px solid',
                borderColor: 'grey.400',
                boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
              }}
            />
          </Box>
        </Box>
      </Box>

      {/* Winrate bar */}
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
            {winratePercent}%
          </Typography>
          {analysis && (
            <Typography
              variant="caption"
              color={scoreLead > 0 ? 'text.primary' : 'text.secondary'}
              fontWeight="bold"
            >
              {scoreLead > 0 ? '+' : ''}{scoreLead.toFixed(1)}目
            </Typography>
          )}
          <Typography variant="caption" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
            {100 - winratePercent}%
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
              bgcolor: 'grey.800',
              borderRadius: 4,
            },
          }}
        />
      </Box>

      {/* Move count and result */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          第 {displayMove}/{match.move_count} 手
        </Typography>
        {match.result && (
          <Typography variant="caption" color="text.secondary">
            {match.result}
          </Typography>
        )}
      </Box>

      {/* Rules and komi */}
      <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {match.rules === 'japanese' ? '日本规则' : match.rules === 'korean' ? '韩国规则' : '中国规则'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          贴目: {match.komi}目
        </Typography>
      </Box>
    </Box>
  );
}
