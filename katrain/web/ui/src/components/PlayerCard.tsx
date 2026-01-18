import React from 'react';
import { Box, Typography, Paper, IconButton } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import { type PlayerInfo } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface PlayerCardProps {
  player: 'B' | 'W';
  info: PlayerInfo;
  captures: number;
  active: boolean;
  timer?: {
    paused: boolean;
    main_time_used: number;
    current_node_time_used: number;
    next_player_periods_used: number;
    settings: {
      main_time: number;
      byo_length: number;
      byo_periods: number;
    };
  };
  onPauseTimer?: () => void;
}

const formatTime = (seconds: number) => {
  const m = Math.floor(Math.max(0, seconds) / 60);
  const s = Math.floor(Math.max(0, seconds) % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const PlayerCard: React.FC<PlayerCardProps> = ({ player, info, captures, active, timer, onPauseTimer }) => {
  const { t } = useTranslation();
  const isBlack = player === 'B';

  let timeDisplay = null;
  if (active && timer && timer.settings) {
    const mainTimeTotal = timer.settings.main_time * 60;
    const mainTimeLeft = mainTimeTotal - timer.main_time_used;

    if (mainTimeLeft > 0) {
      timeDisplay = formatTime(mainTimeLeft);
    } else {
      const periodsLeft = Math.max(0, timer.settings.byo_periods - timer.next_player_periods_used);
      const currentPeriodTimeLeft = Math.max(0, timer.settings.byo_length - timer.current_node_time_used);
      timeDisplay = `${formatTime(currentPeriodTimeLeft)} (${periodsLeft}x)`;
    }
  }

  return (
    <Paper
      elevation={0}
      sx={{
        p: 1.5,
        flex: 1,
        bgcolor: '#2a2a2a',
        color: '#f5f3f0',
        border: active ? '2px solid #4a6b5c' : '2px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 'var(--radius-md)',
        transition: 'all 250ms cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: active ? '0 0 12px rgba(74, 107, 92, 0.3)' : 'none',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box
            sx={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              bgcolor: isBlack ? '#0a0a0a' : '#f8f6f3',
              border: isBlack ? '1px solid #444' : '1px solid #888',
              mr: 1,
            }}
          />
          <Typography
            variant="body2"
            fontWeight={600}
            noWrap
            sx={{
              maxWidth: 80,
              color: '#f5f3f0',
              fontSize: '0.875rem',
            }}
          >
            {info.name || (isBlack ? t('Black') : t('White'))}
          </Typography>
        </Box>
        <Typography
          variant="caption"
          sx={{
            color: '#b8b5b0',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
            fontWeight: 500,
          }}
        >
          {info.calculated_rank || '?'}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <Box>
          <Typography
            variant="caption"
            sx={{
              color: '#7a7772',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
              display: 'block',
            }}
          >
            {t("Captures")}: {captures}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              fontWeight: info.player_type === 'player:ai' ? 600 : 400,
              color: info.player_type === 'player:ai' ? '#4a6b5c' : '#b8b5b0',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {info.player_type === 'player:human' ? t('player:human') : info.player_subtype.replace('ai:', '').toUpperCase()}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {timeDisplay && (
            <Typography
              variant="body2"
              sx={{
                color: '#e89639',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                fontSize: '0.9rem',
              }}
            >
              {timeDisplay}
            </Typography>
          )}
          {active && timer && onPauseTimer && (
            <IconButton 
              size="small" 
              onClick={onPauseTimer}
              sx={{ 
                p: 0.5, 
                color: '#b8b5b0', 
                '&:hover': { color: '#f5f3f0', bgcolor: 'rgba(255, 255, 255, 0.1)' } 
              }}
            >
              {timer.paused ? <PlayArrowIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
            </IconButton>
          )}
        </Box>
      </Box>
    </Paper>
  );
};

export default PlayerCard;
