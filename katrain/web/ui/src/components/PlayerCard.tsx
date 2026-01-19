import React, { useRef } from 'react';
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
      sound: boolean;
    };
  };
  onPauseTimer?: () => void;
  onPlaySound?: (sound: string) => void;
}

const formatTime = (seconds: number) => {
  // KaTrain rounds up (+0.99 logic). Math.ceil is a close approximation.
  const totalSeconds = Math.ceil(Math.max(0, seconds));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const PlayerCard: React.FC<PlayerCardProps> = ({ player, info, captures, active, timer, onPauseTimer, onPlaySound }) => {
  const { t } = useTranslation();
  const isBlack = player === 'B';
  const [clientElapsed, setClientElapsed] = React.useState(0);
  const soundTriggeredRef = useRef<number | null>(null);

  React.useEffect(() => {
    setClientElapsed(0);
    if (!active || !timer || timer.paused) return;

    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      setClientElapsed(elapsed);
    }, 100);

    return () => clearInterval(interval);
  }, [active, timer?.paused, info.main_time_used, timer?.current_node_time_used, info.periods_used]);

  let timeDisplay = null;
  if (timer && timer.settings) {
    const byoNum = timer.settings.byo_periods;
    const byoLen = timer.settings.byo_length;
    const mainTimeTotal = timer.settings.main_time * 60;

    if (active) {
      // Apply elapsed time to main time first, then to current node time (byoyomi)
      const effectiveMainTimeUsed = info.main_time_used + (mainTimeTotal > info.main_time_used ? clientElapsed : 0);
      const mainTimeLeft = mainTimeTotal - effectiveMainTimeUsed;

      if (mainTimeLeft > 0) {
        timeDisplay = formatTime(mainTimeLeft);
      } else {
        let effectiveNodeTimeUsed = timer.current_node_time_used;
        if (info.main_time_used >= mainTimeTotal) {
            effectiveNodeTimeUsed += clientElapsed;
        } else {
            // Transition phase: some client elapsed consumed remaining main time, rest to node time
            const overrun = effectiveMainTimeUsed - mainTimeTotal;
            if (overrun > 0) {
                effectiveNodeTimeUsed += overrun;
            }
        }

        let periodsUsed = info.periods_used;
        while (effectiveNodeTimeUsed > byoLen && periodsUsed < byoNum) {
            effectiveNodeTimeUsed -= byoLen;
            periodsUsed += 1;
        }

        const periodsLeft = Math.max(0, byoNum - periodsUsed);
        const currentPeriodTimeLeft = periodsUsed === byoNum ? 0 : Math.max(0, byoLen - effectiveNodeTimeUsed);
        timeDisplay = `${formatTime(currentPeriodTimeLeft)} (${periodsLeft}x)`;

        // Sound Logic: last 5 seconds (5.2 in Kivy)
        if (timer.settings.sound && onPlaySound && periodsUsed < byoNum) {
            if (currentPeriodTimeLeft > 0 && currentPeriodTimeLeft <= 5.2 && soundTriggeredRef.current !== periodsUsed) {
                onPlaySound('countdownbeep');
                soundTriggeredRef.current = periodsUsed;
            }
        }
      }
    } else {
      // Inactive player: show remaining main time or periods left
      const mainTimeLeft = mainTimeTotal - info.main_time_used;
      const periodsLeft = Math.max(0, byoNum - info.periods_used);
      if (mainTimeLeft > 0) {
        timeDisplay = formatTime(mainTimeLeft);
      } else {
        timeDisplay = `${formatTime(byoLen)} (${periodsLeft}x)`;
      }
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
