import React from 'react';
import { Box, IconButton, Typography, Tooltip } from '@mui/material';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import FastRewindIcon from '@mui/icons-material/FastRewind';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FastForwardIcon from '@mui/icons-material/FastForward';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import RotateLeftIcon from '@mui/icons-material/RotateLeft';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PsychologyIcon from '@mui/icons-material/Psychology';

interface ControlBarProps {
  onAction: (action: string) => void;
  nextPlayer: string;
}

const ControlBar: React.FC<ControlBarProps> = ({ onAction, nextPlayer }) => {
  return (
    <Box sx={{ height: 60, borderTop: '1px solid #ddd', display: 'flex', alignItems: 'center', px: 2, bgcolor: '#fff' }}>
      <Tooltip title="Pass">
        <IconButton onClick={() => onAction('pass')}>
          <Typography variant="button">PASS</Typography>
        </IconButton>
      </Tooltip>

      <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1 }}>
        <IconButton onClick={() => onAction('mistake-prev')} disabled><WarningAmberIcon /></IconButton>
        <IconButton onClick={() => onAction('start')}><SkipPreviousIcon /></IconButton>
        <IconButton onClick={() => onAction('back-10')}><FastRewindIcon /></IconButton>
        <IconButton onClick={() => onAction('back')}><ArrowBackIcon /></IconButton>
        
        <Box sx={{ mx: 2, display: 'flex', alignItems: 'center' }}>
          <Box sx={{ 
            width: 30, height: 30, borderRadius: '50%', 
            bgcolor: nextPlayer === 'B' ? 'black' : 'white',
            border: '2px solid',
            borderColor: '#3f51b5',
            boxShadow: '0 0 5px rgba(63, 81, 181, 0.5)'
          }} />
        </Box>

        <IconButton onClick={() => onAction('forward')}><ArrowForwardIcon /></IconButton>
        <IconButton onClick={() => onAction('forward-10')}><FastForwardIcon /></IconButton>
        <IconButton onClick={() => onAction('end')}><SkipNextIcon /></IconButton>
        <Tooltip title="AI Move">
          <IconButton onClick={() => onAction('ai-move')} color="primary">
            <PsychologyIcon />
          </IconButton>
        </Tooltip>
        <IconButton onClick={() => onAction('mistake-next')} disabled><WarningAmberIcon /></IconButton>
        <IconButton onClick={() => onAction('rotate')} disabled><RotateLeftIcon /></IconButton>
      </Box>

      <Typography variant="body2" color="textSecondary">Engine: Idle</Typography>
    </Box>
  );
};

export default ControlBar;
