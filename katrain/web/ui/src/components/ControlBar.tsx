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

interface ControlBarProps {
  onAction: (action: string) => void;
  nextPlayer: string;
}

const ControlBar: React.FC<ControlBarProps> = ({ onAction, nextPlayer }) => {
  return (
    <Box sx={{ height: 60, borderTop: '1px solid #ddd', display: 'flex', alignItems: 'center', px: 2, bgcolor: '#fff' }}>
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title="Pass">
          <IconButton onClick={() => onAction('pass')} size="small">
            <Typography variant="button" sx={{ fontWeight: 'bold', fontSize: '0.75rem' }}>PASS</Typography>
          </IconButton>
        </Tooltip>
        <Tooltip title="Resign">
          <IconButton onClick={() => onAction('resign')} size="small" color="error">
            <FlagIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5 }}>
        <Tooltip title="Previous Mistake">
          <IconButton onClick={() => onAction('mistake-prev')} size="small"><WarningAmberIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Start of Game">
          <IconButton onClick={() => onAction('start')} size="small"><SkipPreviousIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Back 10 Moves">
          <IconButton onClick={() => onAction('back-10')} size="small"><FastRewindIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Undo (Smart)">
          <IconButton onClick={() => onAction('undo')} color="primary" size="small"><UndoIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Back 1 Move">
          <IconButton onClick={() => onAction('back')} size="small"><ArrowBackIcon fontSize="small" /></IconButton>
        </Tooltip>
        
        <Box sx={{ mx: 1, display: 'flex', alignItems: 'center' }}>
          <Box sx={{ 
            width: 28, height: 28, borderRadius: '50%', 
            bgcolor: nextPlayer === 'B' ? 'black' : 'white',
            border: '2px solid',
            borderColor: '#3f51b5',
            boxShadow: '0 0 5px rgba(63, 81, 181, 0.5)'
          }} />
        </Box>

        <Tooltip title="Forward 1 Move">
          <IconButton onClick={() => onAction('forward')} size="small"><ArrowForwardIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Forward 10 Moves">
          <IconButton onClick={() => onAction('forward-10')} size="small"><FastForwardIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="End of Game">
          <IconButton onClick={() => onAction('end')} size="small"><SkipNextIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="AI Move">
          <IconButton onClick={() => onAction('ai-move')} color="primary" size="small">
            <PsychologyIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Next Mistake">
          <IconButton onClick={() => onAction('mistake-next')} size="small"><WarningAmberIcon fontSize="small" /></IconButton>
        </Tooltip>
        <Tooltip title="Rotate Board">
          <IconButton onClick={() => onAction('rotate')} size="small"><RotateRightIcon fontSize="small" /></IconButton>
        </Tooltip>
      </Box>

      <Typography variant="caption" color="textSecondary" sx={{ minWidth: 80, textAlign: 'right' }}>Engine: Idle</Typography>
    </Box>
  );
};

export default ControlBar;
