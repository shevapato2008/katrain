import { Box, Paper, Typography } from '@mui/material';

interface Props {
  player: 'B' | 'W';
  name: string;
  rank: string;
  mainTimeLeft: number;
  byoyomiLeft: number;
  periodsLeft: number;
  captures: number;
  active: boolean;
  isWarning: boolean;
  isCritical: boolean;
}

const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const KioskPlayerCard = ({
  player, name, rank, mainTimeLeft, byoyomiLeft, periodsLeft,
  captures, active, isWarning, isCritical,
}: Props) => {
  const stoneColor = player === 'B' ? '#111' : '#eee';
  const stoneBorder = player === 'B' ? '1px solid #333' : '1px solid #999';

  let borderColor = 'transparent';
  if (isCritical) borderColor = 'error.main';
  else if (isWarning) borderColor = 'warning.main';
  else if (active) borderColor = 'primary.main';

  return (
    <Paper
      sx={{
        flex: 1,
        p: 1.5,
        border: 2,
        borderColor,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
      }}
    >
      {/* Header: stone + name + rank */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box
          sx={{
            width: 16, height: 16, borderRadius: '50%',
            bgcolor: stoneColor, border: stoneBorder, flexShrink: 0,
          }}
        />
        <Typography
          variant="body2"
          sx={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}
        >
          {name}
        </Typography>
        <Typography variant="body2" sx={{ color: 'primary.main', fontWeight: 600, flexShrink: 0 }}>
          {rank}
        </Typography>
      </Box>

      {/* Timer */}
      <Box
        sx={{
          bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 2, px: 1.5, py: 0.5,
          display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: 1,
        }}
      >
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '1.4rem',
            fontWeight: 700,
            color: isCritical ? 'error.main' : isWarning ? 'warning.main' : 'text.primary',
          }}
        >
          {formatTime(mainTimeLeft)}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            color: 'text.secondary',
          }}
        >
          {Math.ceil(byoyomiLeft)}s
          <Typography component="sup" variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
            x{periodsLeft}
          </Typography>
        </Typography>
      </Box>

      {/* Captures */}
      <Typography variant="caption" sx={{ color: 'text.secondary', textAlign: 'center' }}>
        提子: {captures}
      </Typography>
    </Paper>
  );
};

export default KioskPlayerCard;
