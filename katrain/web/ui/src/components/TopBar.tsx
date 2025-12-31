import React from 'react';
import { AppBar, Toolbar, Typography, Box, IconButton, FormControlLabel, Checkbox } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { i18n } from '../i18n';

interface TopBarProps {
  onMenuClick: () => void;
  analysisToggles: Record<string, boolean>;
  onToggleChange: (key: string) => void;
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
          KaTrain <Typography variant="caption" sx={{ ml: 1, mt: 0.5 }}>{i18n.t('WEB UI')}</Typography>
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, mr: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {['children', 'eval', 'hints', 'policy', 'ownership', 'coords', 'numbers', 'score', 'winrate'].map((t) => {
            const labels: Record<string, string> = {
              children: i18n.t('analysis:nextmoves').replace('\n', ' '),
              eval: i18n.t('analysis:dots').replace('\n', ' '),
              hints: i18n.t('analysis:topmoves').replace('\n', ' '),
              policy: i18n.t('analysis:policy').replace('\n', ' '),
              ownership: i18n.t('analysis:territory').replace('\n', ' '),
              coords: i18n.t('analysis:coordinates') || 'Coords',
              numbers: i18n.t('analysis:numbers') || 'Numbers',
              score: i18n.t('Score'),
              winrate: i18n.t('Win Rate')
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