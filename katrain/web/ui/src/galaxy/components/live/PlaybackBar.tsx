import { Box, IconButton, Slider, Typography, Tooltip, ToggleButton } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import KeyboardDoubleArrowLeftIcon from '@mui/icons-material/KeyboardDoubleArrowLeft';
import KeyboardDoubleArrowRightIcon from '@mui/icons-material/KeyboardDoubleArrowRight';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SyncIcon from '@mui/icons-material/Sync';
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';

interface PlaybackBarProps {
  currentMove: number;
  totalMoves: number;
  onMoveChange: (move: number) => void;
  isLive?: boolean;
}

export default function PlaybackBar({
  currentMove,
  totalMoves,
  onMoveChange,
  isLive = false,
}: PlaybackBarProps) {
  const { t } = useTranslation();
  const [isPlaying, setIsPlaying] = useState(false);
  const [followLatest, setFollowLatest] = useState(isLive); // Auto-follow latest in live mode
  const [playSpeed] = useState(1000); // ms per move

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      if (currentMove < totalMoves) {
        onMoveChange(currentMove + 1);
      } else {
        setIsPlaying(false);
      }
    }, playSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, currentMove, totalMoves, playSpeed, onMoveChange]);

  // Follow latest move when in follow mode
  useEffect(() => {
    if (followLatest && isLive && currentMove < totalMoves) {
      onMoveChange(totalMoves);
    }
  }, [followLatest, isLive, totalMoves, currentMove, onMoveChange]);

  // Stop playing when reaching end
  useEffect(() => {
    if (currentMove >= totalMoves) {
      setIsPlaying(false);
    }
  }, [currentMove, totalMoves]);

  // Disable follow mode when user manually navigates
  const handleManualNavigation = useCallback((newMove: number) => {
    if (newMove < totalMoves) {
      setFollowLatest(false);
    }
    onMoveChange(newMove);
  }, [totalMoves, onMoveChange]);

  const handleFirst = useCallback(() => {
    setIsPlaying(false);
    handleManualNavigation(0);
  }, [handleManualNavigation]);

  const handlePrev = useCallback(() => {
    if (currentMove > 0) {
      handleManualNavigation(currentMove - 1);
    }
  }, [currentMove, handleManualNavigation]);

  const handlePlayPause = useCallback(() => {
    if (currentMove >= totalMoves) {
      // If at end, restart from beginning
      handleManualNavigation(0);
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying, currentMove, totalMoves, handleManualNavigation]);

  const handleNext = useCallback(() => {
    if (currentMove < totalMoves) {
      handleManualNavigation(currentMove + 1);
    }
  }, [currentMove, totalMoves, handleManualNavigation]);

  const handleLast = useCallback(() => {
    setIsPlaying(false);
    setFollowLatest(isLive); // Enable follow mode when going to latest
    onMoveChange(totalMoves);
  }, [totalMoves, onMoveChange, isLive]);

  const handleSliderChange = (_: Event, value: number | number[]) => {
    setIsPlaying(false);
    handleManualNavigation(value as number);
  };

  return (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      {/* Slider */}
      <Box sx={{ px: 1, mb: 1 }}>
        <Slider
          value={currentMove}
          min={0}
          max={totalMoves}
          onChange={handleSliderChange}
          sx={{
            '& .MuiSlider-thumb': {
              width: 16,
              height: 16,
            },
            '& .MuiSlider-track': {
              height: 4,
            },
            '& .MuiSlider-rail': {
              height: 4,
            },
          }}
        />
      </Box>

      {/* Controls with move counter inline */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
        <Tooltip title={t('live:first_move')}>
          <IconButton onClick={handleFirst} size="small" disabled={currentMove === 0}>
            <KeyboardDoubleArrowLeftIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title={t('live:previous')}>
          <IconButton onClick={handlePrev} size="small" disabled={currentMove === 0}>
            <ChevronLeftIcon />
          </IconButton>
        </Tooltip>

        <IconButton
          onClick={handlePlayPause}
          size="large"
          color="primary"
          sx={{
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.dark' },
            mx: 1,
          }}
        >
          {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
        </IconButton>

        <Tooltip title={t('live:next')}>
          <IconButton onClick={handleNext} size="small" disabled={currentMove >= totalMoves}>
            <ChevronRightIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title={t('live:latest')}>
          <IconButton onClick={handleLast} size="small" disabled={currentMove >= totalMoves}>
            <KeyboardDoubleArrowRightIcon />
          </IconButton>
        </Tooltip>

        {/* Follow latest toggle (only shown in live mode) */}
        {isLive && (
          <Tooltip title={followLatest ? t('live:auto_follow_on') : t('live:auto_follow_off')}>
            <ToggleButton
              value="follow"
              selected={followLatest}
              onChange={() => {
                setFollowLatest(!followLatest);
                if (!followLatest) {
                  onMoveChange(totalMoves);
                }
              }}
              size="small"
              sx={{
                ml: 1,
                border: 'none',
                '&.Mui-selected': {
                  bgcolor: 'success.main',
                  color: 'success.contrastText',
                  '&:hover': { bgcolor: 'success.dark' },
                },
              }}
            >
              <SyncIcon fontSize="small" />
            </ToggleButton>
          </Tooltip>
        )}

        {/* Move counter - inline with controls */}
        <Typography variant="body2" color="text.secondary" sx={{ ml: 2, minWidth: 80 }}>
          {currentMove} / {totalMoves} {t('live:moves')}
        </Typography>
      </Box>
    </Box>
  );
}
