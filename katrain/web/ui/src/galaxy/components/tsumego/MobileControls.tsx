/**
 * MobileControls - Compact controls for mobile tsumego solving
 *
 * Layout:
 * ┌─────────────────────────────────────┐
 * │ 3D • #12/354    ● 黑先    [status] │  ← Header
 * └─────────────────────────────────────┘
 *
 * ┌─────────────────────────────────────┐
 * │  [◀]  [悔棋]  [重做]  [提示]  [▶]  │  ← Bottom toolbar
 * └─────────────────────────────────────┘
 */

import React from 'react';
import { Box, IconButton, Chip, Typography } from '@mui/material';
import UndoIcon from '@mui/icons-material/Undo';
import RefreshIcon from '@mui/icons-material/Refresh';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import TouchAppIcon from '@mui/icons-material/TouchApp';

interface MobileControlsProps {
  level: string;
  problemNumber: number;
  totalProblems: number;
  hint: string;
  nextPlayer: 'B' | 'W';
  isSolved: boolean;
  isFailed: boolean;
  isTryMode: boolean;
  showHint: boolean;
  canUndo: boolean;
  hasPrevious: boolean;
  hasNext: boolean;
  onBack: () => void;
  onUndo: () => void;
  onReset: () => void;
  onToggleHint: () => void;
  onToggleTryMode: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export const MobileHeader: React.FC<Pick<
  MobileControlsProps,
  'level' | 'problemNumber' | 'totalProblems' | 'hint' | 'nextPlayer' | 'isSolved' | 'isFailed' | 'isTryMode' | 'onBack'
>> = ({
  level,
  problemNumber,
  totalProblems,
  hint,
  nextPlayer,
  isSolved,
  isFailed,
  isTryMode,
  onBack
}) => {
  return (
    <Box
      sx={{
        p: 1,
        px: 1.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        bgcolor: 'rgba(0, 0, 0, 0.4)',
        borderBottom: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      {/* Left: Back + Level + Problem number */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <IconButton onClick={onBack} size="small" sx={{ p: 0.5 }}>
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Chip
          label={level.toUpperCase()}
          size="small"
          color="primary"
          sx={{ height: 24, fontSize: '0.75rem' }}
        />
        <Typography variant="body2" color="text.secondary">
          #{problemNumber}/{totalProblems}
        </Typography>
      </Box>

      {/* Right: Status */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {isTryMode ? (
          <TouchAppIcon sx={{ color: '#2196f3', fontSize: 20 }} />
        ) : isSolved ? (
          <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />
        ) : isFailed ? (
          <CancelIcon sx={{ color: '#e16b5c', fontSize: 20 }} />
        ) : (
          <>
            <Box
              sx={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
                border: '1px solid',
                borderColor: nextPlayer === 'B' ? '#333' : '#ccc'
              }}
            />
            <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
              {hint}
            </Typography>
          </>
        )}
      </Box>
    </Box>
  );
};

export const MobileToolbar: React.FC<Pick<
  MobileControlsProps,
  'showHint' | 'canUndo' | 'hasPrevious' | 'hasNext' | 'isSolved' | 'isTryMode' | 'onUndo' | 'onReset' | 'onToggleHint' | 'onToggleTryMode' | 'onPrevious' | 'onNext'
>> = ({
  showHint,
  canUndo,
  hasPrevious,
  hasNext,
  isSolved,
  isTryMode,
  onUndo,
  onReset,
  onToggleHint,
  onToggleTryMode,
  onPrevious,
  onNext
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-around',
        alignItems: 'center',
        py: 1,
        px: 2,
        bgcolor: 'background.paper',
        borderTop: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      <IconButton
        onClick={onPrevious}
        disabled={!hasPrevious}
        size="large"
        sx={{
          bgcolor: 'rgba(255,255,255,0.05)',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' }
        }}
      >
        <NavigateBeforeIcon />
      </IconButton>

      <IconButton
        onClick={onUndo}
        disabled={!canUndo}
        size="large"
        sx={{
          bgcolor: 'rgba(255,255,255,0.05)',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' }
        }}
      >
        <UndoIcon />
      </IconButton>

      <IconButton
        onClick={onReset}
        size="large"
        sx={{
          bgcolor: 'rgba(255,255,255,0.05)',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' }
        }}
      >
        <RefreshIcon />
      </IconButton>

      <IconButton
        onClick={onToggleTryMode}
        disabled={isSolved}
        size="large"
        sx={{
          bgcolor: isTryMode ? 'rgba(33, 150, 243, 0.2)' : 'rgba(255,255,255,0.05)',
          color: isTryMode ? '#2196f3' : 'inherit',
          '&:hover': { bgcolor: isTryMode ? 'rgba(33, 150, 243, 0.3)' : 'rgba(255,255,255,0.1)' }
        }}
      >
        <TouchAppIcon />
      </IconButton>

      <IconButton
        onClick={onToggleHint}
        size="large"
        sx={{
          bgcolor: showHint ? 'rgba(232, 150, 57, 0.2)' : 'rgba(255,255,255,0.05)',
          color: showHint ? '#e89639' : 'inherit',
          '&:hover': { bgcolor: showHint ? 'rgba(232, 150, 57, 0.3)' : 'rgba(255,255,255,0.1)' }
        }}
      >
        <LightbulbIcon />
      </IconButton>

      <IconButton
        onClick={onNext}
        disabled={!hasNext}
        size="large"
        sx={{
          bgcolor: isSolved ? 'rgba(76, 175, 80, 0.2)' : 'rgba(255,255,255,0.05)',
          color: isSolved ? '#4caf50' : 'inherit',
          '&:hover': { bgcolor: isSolved ? 'rgba(76, 175, 80, 0.3)' : 'rgba(255,255,255,0.1)' }
        }}
      >
        <NavigateNextIcon />
      </IconButton>
    </Box>
  );
};

const MobileControls: React.FC<MobileControlsProps> = (props) => {
  return (
    <>
      <MobileHeader {...props} />
      <MobileToolbar {...props} />
    </>
  );
};

export default MobileControls;
