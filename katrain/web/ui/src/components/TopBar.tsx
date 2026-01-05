import React from 'react';
import { AppBar, Toolbar, Typography, Box, IconButton, FormControlLabel, Checkbox } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { useTranslation } from '../hooks/useTranslation';

interface TopBarProps {
  onMenuClick: () => void;
  analysisToggles: Record<string, boolean>;
  onToggleChange: (key: string) => void;
  status: string;
}

const TopBar: React.FC<TopBarProps> = ({ onMenuClick, analysisToggles, onToggleChange, status }) => {
  const { t } = useTranslation();
  return (
    <AppBar position="static" color="default" elevation={1}>
      <Toolbar variant="dense">
        <IconButton edge="start" color="inherit" aria-label="menu" onClick={onMenuClick} sx={{ mr: 2 }}>
          <MenuIcon />
        </IconButton>
        <Typography variant="h6" color="inherit" component="div" sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
          KaTrain <Typography variant="caption" sx={{ ml: 1, mt: 0.5 }}>{t('WEB UI')}</Typography>
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, mr: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          {['children', 'eval', 'hints', 'policy', 'ownership', 'coords', 'numbers', 'score', 'winrate'].map((t_key) => {
            const labels: Record<string, string> = {
              children: t('analysis:nextmoves').replace('\n', ' '),
              eval: t('analysis:dots').replace('\n', ' '),
              hints: t('analysis:topmoves').replace('\n', ' '),
              policy: t('analysis:policy').replace('\n', ' '),
              ownership: t('analysis:territory').replace('\n', ' '),
              coords: t('analysis:coordinates', 'Coordinates'),
              numbers: t('analysis:numbers', 'Numbers'),
              score: t('tab:score'),
              winrate: t('tab:winrate')
            };
            return (
              <FormControlLabel
                key={t_key}
                control={
                  <Checkbox
                    checked={analysisToggles[t_key] || false}
                    onChange={() => onToggleChange(t_key)}
                    size="small"
                    sx={{ p: 0.5 }}
                  />
                }
                label={<Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>{labels[t_key] || t_key}</Typography>}
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