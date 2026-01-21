import React, { useRef } from 'react';
import { Box, Typography, Paper, IconButton, Divider, Stack, Tooltip } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import { type PlayerInfo } from '../api';
import { useTranslation } from '../hooks/useTranslation';
import { internalToRank } from '../galaxy/utils/rankUtils';

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
  isFollowed?: boolean;
  onToggleFollow?: () => void;
  showFollowButton?: boolean;
}

const formatTime = (seconds: number) => {
  const totalSeconds = Math.ceil(Math.max(0, seconds));
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const PlayerCard: React.FC<PlayerCardProps> = ({ 
  player, info, captures, active, timer, onPauseTimer, onPlaySound, 
  isFollowed, onToggleFollow, showFollowButton 
}) => {
  const { t } = useTranslation();
  const isBlack = player === 'B';
  const [clientElapsed, setClientElapsed] = React.useState(0);
  const soundTriggeredRef = useRef<number | null>(null);
  const lastActiveTimeRef = useRef<number>(Date.now());
  const lastMainTimeUsedRef = useRef<number>(info.main_time_used);

  React.useEffect(() => {
    // Reset the timer start time when becoming active or when time tracking values change
    if (active && !timer?.paused) {
      lastActiveTimeRef.current = Date.now();
      lastMainTimeUsedRef.current = info.main_time_used;
      setClientElapsed(0);
    }

    if (!active || !timer || timer.paused) {
      setClientElapsed(0);
      return;
    }

    const interval = setInterval(() => {
      const elapsed = (Date.now() - lastActiveTimeRef.current) / 1000;
      setClientElapsed(elapsed);
    }, 100);

    return () => clearInterval(interval);
    // Only depend on truly changing values, not object references
  }, [active, timer?.paused, info.main_time_used]);

  const displayRank = internalToRank(info.calculated_rank);
  const displayName = info.name || (isBlack ? t('Black') : t('White'));

  // Timer Breakdown
  let mainTimeLeft = 0;
  let byoyomiLeft = 0;
  let periodsLeft = 0;
  let showTimer = false;

  if (timer && timer.settings && (timer.settings.main_time > 0 || timer.settings.byo_length > 0)) {
    showTimer = true;
    const byoNum = timer.settings.byo_periods;
    const byoLen = timer.settings.byo_length;
    const mainTimeTotal = timer.settings.main_time * 60; // Minutes to seconds

    const currentMainUsed = info.main_time_used + (active && mainTimeTotal > info.main_time_used ? clientElapsed : 0);
    mainTimeLeft = Math.max(0, mainTimeTotal - currentMainUsed);

    if (mainTimeLeft > 0) {
        byoyomiLeft = byoLen;
        periodsLeft = byoNum - info.periods_used;
    } else {
        let effectiveNodeTimeUsed = timer.current_node_time_used + (active ? clientElapsed : 0);
        let currentPeriodsUsed = info.periods_used;
        
        while (effectiveNodeTimeUsed > byoLen && currentPeriodsUsed < byoNum) {
            effectiveNodeTimeUsed -= byoLen;
            currentPeriodsUsed += 1;
        }
        
        byoyomiLeft = Math.max(0, byoLen - effectiveNodeTimeUsed);
        periodsLeft = Math.max(0, byoNum - currentPeriodsUsed);

        // Sound Logic
        if (active && timer.settings.sound && onPlaySound && currentPeriodsUsed < byoNum) {
            if (byoyomiLeft > 0 && byoyomiLeft <= 5.2 && soundTriggeredRef.current !== currentPeriodsUsed) {
                onPlaySound('countdownbeep');
                soundTriggeredRef.current = currentPeriodsUsed;
            }
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
        border: active ? '2px solid #4a6b5c' : '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 2,
        transition: 'all 250ms',
        boxShadow: active ? '0 0 12px rgba(74, 107, 92, 0.3)' : 'none',
      }}
    >
      {/* Player Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{
              width: 16, height: 16, borderRadius: '50%',
              bgcolor: isBlack ? '#000' : '#fff',
              border: '1px solid #666'
          }} />
          <Typography variant="body2" fontWeight={700} noWrap sx={{ maxWidth: 150 }}>
            {displayName}
          </Typography>
          {showFollowButton && onToggleFollow && (
              <Tooltip title={isFollowed ? t("Unfollow") : t("Follow")}>
                  <IconButton size="small" onClick={onToggleFollow} sx={{ ml: 0.5, p: 0.2, color: isFollowed ? 'secondary.main' : 'primary.main' }}>
                      {isFollowed ? <PersonRemoveIcon fontSize="inherit" /> : <PersonAddIcon fontSize="inherit" />}
                  </IconButton>
              </Tooltip>
          )}
        </Box>
        <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 700 }}>
          {displayRank}
        </Typography>
      </Box>

      {/* Timer Display */}
      {showTimer && (
          <Box sx={{ mb: 1.5, p: 1, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
                  <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ fontSize: '0.6rem', color: '#7a7772', display: 'block' }}>MAIN</Typography>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700, color: mainTimeLeft > 0 ? '#e89639' : '#555' }}>
                          {formatTime(mainTimeLeft)}
                      </Typography>
                  </Box>
                  <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.1)' }} />
                  <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ fontSize: '0.6rem', color: '#7a7772', display: 'block' }}>BYO</Typography>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700, color: mainTimeLeft === 0 ? '#e89639' : '#7a7772' }}>
                          {Math.ceil(byoyomiLeft)}s
                      </Typography>
                  </Box>
                  <Divider orientation="vertical" flexItem sx={{ bgcolor: 'rgba(255,255,255,0.1)' }} />
                  <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" sx={{ fontSize: '0.6rem', color: '#7a7772', display: 'block' }}>PRD</Typography>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700, color: mainTimeLeft === 0 ? '#e89639' : '#7a7772' }}>
                          {periodsLeft}x
                      </Typography>
                  </Box>
              </Stack>
          </Box>
      )}

      {/* Footer Info */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="caption" sx={{ color: '#7a7772' }}>
          {t("Captures")}: {captures}
        </Typography>
        {active && timer && onPauseTimer && (
            <IconButton size="small" onClick={onPauseTimer} sx={{ p: 0, color: 'primary.main' }}>
                {timer.paused ? <PlayArrowIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
            </IconButton>
        )}
      </Box>
    </Paper>
  );
};

export default PlayerCard;