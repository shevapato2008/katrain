import React from 'react';
import { AppBar, Toolbar, Typography, Button, Box, IconButton } from '@mui/material';
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

        <Box sx={{ display: 'flex', gap: 1, mr: 2 }}>
          {['children', 'eval', 'hints', 'policy', 'ownership', 'coords', 'numbers', 'score', 'winrate'].map((t) => (
            <Button 
              key={t}
              size="small" 
              variant={analysisToggles[t] ? "contained" : "outlined"}
              onClick={() => onToggleChange(t)}
              sx={{ px: 1, minWidth: 0 }}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Button>
          ))}
        </Box>

        <Typography variant="body2" color="textSecondary" noWrap sx={{ maxWidth: 300 }}>
          {status}
        </Typography>
      </Toolbar>
    </AppBar>
  );
};

export default TopBar;
