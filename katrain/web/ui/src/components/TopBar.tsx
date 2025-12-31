import React from 'react';
import { AppBar, Toolbar, Typography, Box, IconButton, FormControlLabel, Checkbox } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';

interface TopBarProps {
  onMenuClick: () => void;
  analysisToggles: Record<string, boolean>;
  onToggleChange: (toggle: string) => void;
  status: string;
}

const TopBar: React.FC<TopBarProps> = ({ onMenuClick, analysisToggles, onToggleChange, status }) => {
  return (
    <AppBar position="static" color="default" elevation={1}>
      <Toolbar variant="dense">
        <IconButton edge="start" color="inherit" aria-label="menu" onClick={onMenuClick} sx={{ mr: 2 }}>
          <MenuIcon />
        </IconButton>
        <Typography variant="h6" color="inherit" component="div" sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
          KaTrain <Typography variant="caption" sx={{ ml: 1, mt: 0.5 }}>WEB UI</Typography>
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, mr: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {['children', 'eval', 'hints', 'policy', 'ownership', 'coords', 'numbers', 'score', 'winrate'].map((t) => {
            const labels: Record<string, string> = {
              children: 'Next Move',
              eval: 'Show Dots',
              hints: 'Top Moves',
              policy: 'Policy Moves',
              ownership: 'Expected Territory',
              coords: 'Coords',
              numbers: 'Numbers',
              score: 'Score',
              winrate: 'Win Rate'
            };
            return (
              <FormControlLabel
                key={t}
                control={
                  <Checkbox
                    checked={analysisToggles[t] || false}
                    onChange={() => onToggleChange(t)}
                    size="small"
                    sx={{ p: 0.5 }}
                  />
                }
                label={<Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>{labels[t] || t}</Typography>}
                sx={{ mr: 0, ml: 0.5 }}
              />
            );
          })}
        </Box>

        <Typography variant="body2" color="textSecondary" noWrap sx={{ maxWidth: 300 }}>
          {status}
        </Typography>
      </Toolbar>
    </AppBar>
  );
};

export default TopBar;
