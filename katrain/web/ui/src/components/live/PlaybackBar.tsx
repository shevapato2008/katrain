import { Box, IconButton, Slider, Typography, Tooltip, ToggleButton } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import KeyboardDoubleArrowLeftIcon from '@mui/icons-material/KeyboardDoubleArrowLeft';
import KeyboardDoubleArrowRightIcon from '@mui/icons-material/KeyboardDoubleArrowRight';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SyncIcon from '@mui/icons-material/Sync';
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '../../hooks/useTranslation';

interface PlaybackBarProps {
  currentMove: number;
  totalMoves: number;
  onMoveChange: (move: number) => void;
  isLive?: boolean;
  touchSized?: boolean;
}

export default function PlaybackBar({
  currentMove,
  totalMoves,
  onMoveChange,
  isLive = false,
  touchSized = false,
}: PlaybackBarProps) {
  const { t } = useTranslation();
  const [isPlaying, setIsPlaying] = useState(false);
  const [followLatest, setFollowLatest] = useState(isLive); // Auto-follow latest in live mode
  const [playSpeed] = useState(1000); // ms per move
  const touchButtonSx = touchSized ? { minWidth: 48, width: 48, minHeight: 48, height: 48 } : undefined;

  /* 窄容器（统一版式的 320 右栏，内宽 ~288）下把控件收窄，让走子键、播放键、
     自动跟进和手数**一行装完**。以前这里是换行，手数被挤到第二行。
     只在 board-rail 这个具名容器里生效 —— 没有这个容器的调用方
     （kiosk 五个页面、直播列表页的旧版式）宽度本来就够，保持 40px 触摸尺寸不变。
     touchSized（盒端 48px）优先级更高，写在后面覆盖。 */
  const NARROW = '@container board-rail (max-width: 340px)';
  const compactIconSx = { [NARROW]: { width: 30, height: 30, padding: '3px' } };
  const compactPlaySx = { [NARROW]: { width: 42, height: 42, padding: '6px' } };

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
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reaching the final move must stop active autoplay immediately
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
    <Box sx={{ pt: 1, pb: 1.5, px: 1, borderTop: 1, borderColor: 'divider' }}>
      {/* Slider */}
      <Box sx={{ px: 1, mb: 0.5 }}>
        <Slider
          value={currentMove}
          min={0}
          max={totalMoves}
          onChange={handleSliderChange}
          sx={{
            ...(touchSized ? {
              minHeight: 48,
              boxSizing: 'border-box',
              '& .MuiSlider-thumb input': {
                width: '48px !important',
                height: '48px !important',
                margin: '0 !important',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                clip: 'auto !important',
                opacity: 0,
              },
            } : {}),
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
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.25,
          flexWrap: 'nowrap',
        }}
      >
        <Tooltip title={t('live:first_move')}>
          <span><IconButton aria-label={t('live:first_move')} onClick={handleFirst} size="small" disabled={currentMove === 0} sx={{ ...compactIconSx, ...(touchButtonSx || {}) }}>
            <KeyboardDoubleArrowLeftIcon />
          </IconButton></span>
        </Tooltip>

        <Tooltip title={t('live:previous')}>
          <span><IconButton aria-label={t('live:previous')} onClick={handlePrev} size="small" disabled={currentMove === 0} sx={{ ...compactIconSx, ...(touchButtonSx || {}) }}>
            <ChevronLeftIcon />
          </IconButton></span>
        </Tooltip>

        <IconButton
          aria-label={isPlaying ? t('live:pause', '暂停') : t('live:play', '播放')}
          onClick={handlePlayPause}
          size="large"
          color="primary"
          sx={{
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': { bgcolor: 'primary.dark' },
            ...compactPlaySx,
            ...(touchButtonSx || {}),
          }}
        >
          {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
        </IconButton>

        <Tooltip title={t('live:next')}>
          <span><IconButton aria-label={t('live:next')} onClick={handleNext} size="small" disabled={currentMove >= totalMoves} sx={{ ...compactIconSx, ...(touchButtonSx || {}) }}>
            <ChevronRightIcon />
          </IconButton></span>
        </Tooltip>

        <Tooltip title={t('live:latest')}>
          <span><IconButton aria-label={t('live:latest')} onClick={handleLast} size="small" disabled={currentMove >= totalMoves} sx={{ ...compactIconSx, ...(touchButtonSx || {}) }}>
            <KeyboardDoubleArrowRightIcon />
          </IconButton></span>
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
                border: 'none',
                '&.Mui-selected': {
                  bgcolor: 'success.main',
                  color: 'success.contrastText',
                  '&:hover': { bgcolor: 'success.dark' },
                },
                ...compactIconSx,
                ...(touchButtonSx || {}),
              }}
            >
              <SyncIcon fontSize="small" />
            </ToggleButton>
          </Tooltip>
        )}

        {/* Move counter - inline with controls */}
        <Typography
          data-testid="playback-move-counter"
          variant="body2"
          color="text.secondary"
          noWrap
          sx={{
            minWidth: 87,
            [NARROW]: {
              /* 不再另起一行，跟控件同行；只把字号和保底宽度收掉 */
              minWidth: 0,
              fontSize: '0.72rem',
              ml: 0.5,
            },
          }}
        >
          {currentMove} / {totalMoves} {t('live:moves')}
        </Typography>
      </Box>
    </Box>
  );
}
