import React from 'react';
import { Box, IconButton, Typography, Tooltip } from '@mui/material';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import FastRewindIcon from '@mui/icons-material/FastRewind';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FastForwardIcon from '@mui/icons-material/FastForward';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import RotateRightIcon from '@mui/icons-material/RotateRight';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FlagIcon from '@mui/icons-material/Flag';
import UndoIcon from '@mui/icons-material/Undo';
import { i18n } from '../i18n';

interface ControlBarProps {
  onAction: (action: string) => void;
  nextPlayer: string;
}

const ControlBar: React.FC<ControlBarProps> = ({ onAction, nextPlayer }) => {
  const iconButtonStyles = {
    color: '#b8b5b0',
    '&:hover': {
      bgcolor: 'rgba(255, 255, 255, 0.05)',
      color: '#f5f3f0',
    },
  };

  const accentButtonStyles = {
    color: '#4a6b5c',
    '&:hover': {
      bgcolor: 'rgba(74, 107, 92, 0.1)',
      color: '#5d8270',
    },
  };

  return (
    <Box
      sx={{
        height: 60,
        borderTop: '1px solid rgba(255, 255, 255, 0.05)',
        display: 'flex',
        alignItems: 'center',
        px: 2,
        bgcolor: '#1a1a1a',
        backdropFilter: 'blur(10px)',
      }}
    >
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title={i18n.t("Pass")}>
          <IconButton onClick={() => onAction('pass')} size="small" sx={iconButtonStyles}>
            <Typography
              variant="button"
              sx={{
                fontWeight: 600,
                fontSize: '0.75rem',
                color: 'inherit',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {i18n.t("PASS")}
            </Typography>
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Resign")}>
          <IconButton
            onClick={() => onAction('resign')}
            size="small"
            sx={{
              color: '#e16b5c',
              '&:hover': {
                bgcolor: 'rgba(225, 107, 92, 0.1)',
                color: '#f07565',
              },
            }}
          >
            <FlagIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5 }}>
        <Tooltip title={i18n.t("Previous Mistake")}>
          <IconButton onClick={() => onAction('mistake-prev')} size="small" sx={iconButtonStyles}>
            <WarningAmberIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Start of Game")}>
          <IconButton onClick={() => onAction('start')} size="small" sx={iconButtonStyles}>
            <SkipPreviousIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Back 10 Moves")}>
          <IconButton onClick={() => onAction('back-10')} size="small" sx={iconButtonStyles}>
            <FastRewindIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Undo (Smart)")}>
          <IconButton onClick={() => onAction('undo')} size="small" sx={accentButtonStyles}>
            <UndoIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Back 1 Move")}>
          <IconButton onClick={() => onAction('back')} size="small" sx={iconButtonStyles}>
            <ArrowBackIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Box sx={{ mx: 1, display: 'flex', alignItems: 'center' }}>
          <Box
            sx={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              bgcolor: nextPlayer === 'B' ? '#0a0a0a' : '#f8f6f3',
              border: '2px solid',
              borderColor: '#4a6b5c',
              boxShadow: '0 0 8px rgba(74, 107, 92, 0.4)',
              transition: 'all 250ms cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        </Box>

        <Tooltip title={i18n.t("Forward 1 Move")}>
          <IconButton onClick={() => onAction('forward')} size="small" sx={iconButtonStyles}>
            <ArrowForwardIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Forward 10 Moves")}>
          <IconButton onClick={() => onAction('forward-10')} size="small" sx={iconButtonStyles}>
            <FastForwardIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("End of Game")}>
          <IconButton onClick={() => onAction('end')} size="small" sx={iconButtonStyles}>
            <SkipNextIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("AI Move")}>
          <IconButton onClick={() => onAction('ai-move')} size="small" sx={accentButtonStyles}>
            <PsychologyIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Next Mistake")}>
          <IconButton onClick={() => onAction('mistake-next')} size="small" sx={iconButtonStyles}>
            <WarningAmberIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={i18n.t("Rotate Board")}>
          <IconButton onClick={() => onAction('rotate')} size="small" sx={iconButtonStyles}>
            <RotateRightIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Typography
        variant="caption"
        sx={{
          minWidth: 80,
          textAlign: 'right',
          color: '#7a7772',
          fontSize: '0.75rem',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {i18n.t("Engine")}: {i18n.t("Idle")}
      </Typography>
    </Box>
  );
};

export default ControlBar;