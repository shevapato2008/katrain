/**
 * TsumegoProblemControls - Control panel for tsumego problem solving
 *
 * Displays:
 * - Problem info (level, category)
 * - Hint toggle
 * - Timer and attempts
 * - Undo/Reset buttons
 * - Result display (correct/incorrect)
 * - Navigation to next/previous problems
 */

import React from 'react';
import {
  Box,
  Typography,
  Button,
  IconButton,
  Chip,
  Divider,
  Tooltip
} from '@mui/material';
import UndoIcon from '@mui/icons-material/Undo';
import RefreshIcon from '@mui/icons-material/Refresh';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TimerIcon from '@mui/icons-material/Timer';
import { useTranslation } from '../../../hooks/useTranslation';

interface TsumegoProblemControlsProps {
  level: string;
  category: string;
  hint?: string;
  showHint: boolean;
  isSolved: boolean;
  isFailed: boolean;
  elapsedTime: number;
  attempts: number;
  nextPlayer: 'B' | 'W';
  canUndo: boolean;
  onUndo: () => void;
  onReset: () => void;
  onToggleHint: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
  hasPrevious?: boolean;
  hasNext?: boolean;
}

const TsumegoProblemControls: React.FC<TsumegoProblemControlsProps> = ({
  level,
  category,
  hint,
  showHint,
  isSolved,
  isFailed,
  elapsedTime,
  attempts,
  nextPlayer,
  canUndo,
  onUndo,
  onReset,
  onToggleHint,
  onPrevious,
  onNext,
  hasPrevious = false,
  hasNext = false
}) => {
  const { t } = useTranslation();

  // Format elapsed time as mm:ss
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Box
      sx={{
        p: 2,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        overflow: 'auto'
      }}
    >
      {/* Problem Info */}
      <Box>
        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
          <Chip
            label={level.toUpperCase()}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Chip
            label={t(`tsumego:${category}`)}
            size="small"
            variant="outlined"
          />
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />

      {/* Status */}
      <Box>
        {isSolved ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#4caf50' }}>
            <CheckCircleIcon />
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              {t('tsumego:solved')}
            </Typography>
          </Box>
        ) : isFailed ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#e16b5c' }}>
            <CancelIcon />
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              {t('tsumego:incorrect')}
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
                border: '1px solid',
                borderColor: nextPlayer === 'B' ? '#333' : '#ccc'
              }}
            />
            <Typography variant="body1">
              {nextPlayer === 'B' ? t('tsumego:blackToPlay') : t('tsumego:whiteToPlay')}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Timer and Attempts */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
          <TimerIcon fontSize="small" />
          <Typography variant="body2">{formatTime(elapsedTime)}</Typography>
        </Box>
        {attempts > 0 && (
          <Typography variant="body2" color="text.secondary">
            {t('tsumego:attempts')}: {attempts}
          </Typography>
        )}
      </Box>

      <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />

      {/* Hint */}
      {hint && (
        <Box>
          <Button
            variant="outlined"
            size="small"
            startIcon={<LightbulbIcon />}
            onClick={onToggleHint}
            sx={{
              mb: 1,
              borderColor: showHint ? '#e89639' : 'rgba(255,255,255,0.3)',
              color: showHint ? '#e89639' : 'inherit'
            }}
          >
            {showHint ? t('tsumego:hideHint') : t('tsumego:showHint')}
          </Button>
          {showHint && (
            <Typography
              variant="body2"
              sx={{
                p: 1.5,
                bgcolor: 'rgba(232, 150, 57, 0.1)',
                borderRadius: 1,
                borderLeft: '3px solid #e89639'
              }}
            >
              {hint}
            </Typography>
          )}
        </Box>
      )}

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Tooltip title={t('tsumego:undo')}>
          <span>
            <IconButton
              onClick={onUndo}
              disabled={!canUndo || isSolved}
              sx={{
                bgcolor: 'rgba(255,255,255,0.1)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' }
              }}
            >
              <UndoIcon />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={t('tsumego:reset')}>
          <IconButton
            onClick={onReset}
            sx={{
              bgcolor: 'rgba(255,255,255,0.1)',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' }
            }}
          >
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Spacer */}
      <Box sx={{ flexGrow: 1 }} />

      {/* Navigation */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<NavigateBeforeIcon />}
          onClick={onPrevious}
          disabled={!hasPrevious}
        >
          {t('tsumego:previousProblem')}
        </Button>
        <Button
          variant={isSolved ? 'contained' : 'outlined'}
          size="small"
          endIcon={<NavigateNextIcon />}
          onClick={onNext}
          disabled={!hasNext}
          color={isSolved ? 'success' : 'primary'}
        >
          {t('tsumego:nextProblem')}
        </Button>
      </Box>
    </Box>
  );
};

export default TsumegoProblemControls;
