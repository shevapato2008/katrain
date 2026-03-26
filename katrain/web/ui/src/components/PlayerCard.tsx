import React, { useRef, useEffect } from 'react';
import { Box, Typography, Paper, IconButton, Tooltip } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import { type PlayerInfo } from '../api';
import { useTranslation } from '../hooks/useTranslation';
import { localizedRank } from '../galaxy/utils/rankUtils';

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
  onTimeout?: () => void;
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
  player, info, captures, active, timer, onPauseTimer, onPlaySound, onTimeout,
  isFollowed, onToggleFollow, showFollowButton
}) => {
  const { t, lang } = useTranslation();
  const isBlack = player === 'B';
  const [clientElapsed, setClientElapsed] = React.useState(0);
  const lastCountdownSecondRef = useRef<number | null>(null);
  const lastActiveTimeRef = useRef<number>(Date.now());
  const lastMainTimeUsedRef = useRef<number>(info.main_time_used);
  const timeoutTriggeredRef = useRef<boolean>(false);

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

  // Localized rank display
  const rawRank = localizedRank(info.calculated_rank, lang);
  const displayRank = rawRank === "No Rank" ? t("No Rank", "No Rank") : rawRank;
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
        // Main time available at start of this node
        const mainTimeAvailableAtNodeStart = Math.max(0, mainTimeTotal - info.main_time_used);
        // Total time spent on this node
        const totalNodeTime = timer.current_node_time_used + (active ? clientElapsed : 0);
        // Only time BEYOND main time goes into byoyomi
        let effectiveNodeTimeUsed = Math.max(0, totalNodeTime - mainTimeAvailableAtNodeStart);
        let currentPeriodsUsed = info.periods_used;

        while (effectiveNodeTimeUsed > byoLen && currentPeriodsUsed < byoNum) {
            effectiveNodeTimeUsed -= byoLen;
            currentPeriodsUsed += 1;
        }

        // Check if all periods are exhausted
        if (currentPeriodsUsed >= byoNum) {
            // All periods exhausted - no time left
            byoyomiLeft = 0;
            periodsLeft = 0;
        } else {
            byoyomiLeft = Math.max(0, byoLen - effectiveNodeTimeUsed);
            periodsLeft = byoNum - currentPeriodsUsed;

            // Countdown beep in last 5 seconds of byoyomi
            if (active && timer.settings.sound && onPlaySound) {
                const secondsRemaining = Math.ceil(byoyomiLeft);

                if (secondsRemaining <= 5 && secondsRemaining >= 1 && secondsRemaining !== lastCountdownSecondRef.current) {
                    onPlaySound('countdownbeep');
                    lastCountdownSecondRef.current = secondsRemaining;
                }

                // Reset when exiting countdown zone (entering new period or time > 6s)
                if (byoyomiLeft > 6) {
                    lastCountdownSecondRef.current = null;
                }
            }
        }
    }
  }

  // Timeout detection - trigger forfeit when time exhausted
  const hasTimedOut = showTimer && mainTimeLeft <= 0 && periodsLeft <= 0 && byoyomiLeft <= 0;
  useEffect(() => {
    if (active && hasTimedOut && onTimeout && !timeoutTriggeredRef.current) {
      timeoutTriggeredRef.current = true;
      onTimeout();
    }
    // Reset the trigger when game state changes (not timed out anymore)
    if (!hasTimedOut) {
      timeoutTriggeredRef.current = false;
    }
  }, [active, hasTimedOut, onTimeout]);

  // Timer state for styling
  const isCritical = mainTimeLeft <= 0 && byoyomiLeft <= 5;
  const isWarning = mainTimeLeft <= 0;

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
          <Typography variant="body2" fontWeight={700} noWrap sx={{ maxWidth: 140 }}>
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

      {/* Timer Display - Always show, greyed out when no timing */}
      <Box sx={{
          mb: 1.5,
          p: 1,
          bgcolor: 'rgba(0,0,0,0.3)',
          borderRadius: 2,
          border: showTimer && active ? '2px solid' : '1px solid transparent',
          borderColor: showTimer ? (isCritical ? '#e16b5c' : isWarning ? '#e89639' : '#4a6b5c') : 'transparent',
          transition: 'all 200ms',
          animation: showTimer && active && isCritical ? 'timerPulse 0.5s ease-in-out infinite' :
                     showTimer && active && isWarning ? 'timerPulse 1s ease-in-out infinite' : 'none',
          '@keyframes timerPulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.7 },
          },
      }}>
          {/* Main Time - Large and prominent */}
          <Typography
              sx={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  textAlign: 'center',
                  color: showTimer ? (mainTimeLeft > 0 ? '#e89639' : '#4a4845') : '#3a3835',
                  lineHeight: 1.2,
              }}
          >
              {showTimer ? formatTime(mainTimeLeft) : '0:00'}
          </Typography>

          {/* Byoyomi with periods as superscript */}
          <Box sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'baseline',
              mt: 0.5,
          }}>
              <Typography
                  sx={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: '1rem',
                      fontWeight: 600,
                      color: showTimer ? (isWarning ? '#e89639' : '#7a7772') : '#3a3835',
                  }}
              >
                  {showTimer ? `${Math.ceil(byoyomiLeft)}s` : '0s'}
              </Typography>
              <Typography
                  component="sup"
                  sx={{
                      fontSize: '0.65rem',
                      fontWeight: 600,
                      ml: 0.3,
                      color: showTimer ? '#7a7772' : '#3a3835',
                  }}
              >
                  ×{showTimer ? periodsLeft : 0}
              </Typography>
          </Box>
      </Box>

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