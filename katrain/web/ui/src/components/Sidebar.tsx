import React from 'react';
import { Box, Typography, Divider, List, ListItem, ListItemText, ListItemIcon, ListItemButton, Tooltip } from '@mui/material';
import { type GameState } from '../api';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FileOpenIcon from '@mui/icons-material/FileOpen';
import SaveIcon from '@mui/icons-material/Save';
import SettingsIcon from '@mui/icons-material/Settings';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import TimerIcon from '@mui/icons-material/Timer';
import SchoolIcon from '@mui/icons-material/School';
import EngineeringIcon from '@mui/icons-material/Engineering';
import HubIcon from '@mui/icons-material/Hub';

interface SidebarProps {
  gameState: GameState | null;
  onNewGame: () => void;
  onLoadSGF: (sgf: string) => void;
  onSaveSGF: () => void;
  onAISettings: () => void;
  onAnalyzeGame: () => void;
  onGameReport: () => void;
}

const LANGUAGES = [
  { code: 'en', flag: '🇬🇧', name: 'English' },
  { code: 'de', flag: '🇩🇪', name: 'Deutsch' },
  { code: 'fr', flag: '🇫🇷', name: 'Français' },
  { code: 'ru', flag: '🇷🇺', name: 'Русский' },
  { code: 'cn', flag: '🇨🇳', name: '简体中文' },
  { code: 'tw', flag: '🇹🇼', name: '繁體中文' },
  { code: 'ko', flag: '🇰🇷', name: '한국어' },
  { code: 'jp', flag: '🇯🇵', name: '日本語' },
  { code: 'tr', flag: '🇹🇷', name: 'Türkçe' },
];

const Sidebar: React.FC<SidebarProps> = ({ gameState, onNewGame, onLoadSGF, onSaveSGF, onAISettings, onAnalyzeGame, onGameReport }) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        onLoadSGF(content);
      };
      reader.readAsText(file);
    }
  };

  const getPlayerDisplay = (bw: 'B' | 'W') => {
    const info = gameState?.players_info[bw];
    if (!info) return 'Loading...';
    if (info.player_type === 'player:human') return 'Human';
    return info.player_subtype.replace('ai:', '').toUpperCase();
  };

  return (
    <Box sx={{ width: 280, borderRight: '1px solid #ddd', height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#f5f5f5', overflowY: 'auto' }}>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".sgf,.ngf,.gib"
        onChange={handleFileChange}
      />
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>KaTrain Web</Typography>
        <Divider />
      </Box>

      <Box sx={{ p: 2, flexGrow: 1 }}>
        <Typography variant="subtitle2" color="textSecondary" gutterBottom>PLAYER SETUP</Typography>
        <Box sx={{ mb: 2, bgcolor: '#fff', p: 1, borderRadius: 1, border: '1px solid #ddd' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 24, height: 24, bgcolor: 'black', borderRadius: '50%', mr: 1 }} />
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>Black</Typography>
            </Box>
            <Typography variant="body2">{getPlayerDisplay('B')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 24, height: 24, bgcolor: 'white', border: '1px solid #000', borderRadius: '50%', mr: 1 }} />
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>White</Typography>
            </Box>
            <Typography variant="body2">{getPlayerDisplay('W')}</Typography>
          </Box>
        </Box>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>GAME</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onNewGame}>
              <ListItemIcon sx={{ minWidth: 36 }}><PlayArrowIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="New Game / Rules" secondary="Ctrl-N" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onSaveSGF}>
              <ListItemIcon sx={{ minWidth: 36 }}><SaveIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Save Game" secondary="Ctrl-S" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={() => fileInputRef.current?.click()}>
              <ListItemIcon sx={{ minWidth: 36 }}><FileOpenIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Load Game" secondary="Ctrl-L" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>SETTINGS</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAISettings}>
              <ListItemIcon sx={{ minWidth: 36 }}><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="AI Settings" secondary="F7" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><TimerIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Timer Settings" secondary="F5" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><SchoolIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Teaching Settings" secondary="F6" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><EngineeringIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="General Settings" secondary="F8" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><HubIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Distributed Training" secondary="F9" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>ANALYSIS</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAnalyzeGame}>
              <ListItemIcon sx={{ minWidth: 36 }}><AnalyticsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Full Game Analysis" secondary="F2" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onGameReport}>
              <ListItemIcon sx={{ minWidth: 36 }}><AssessmentIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Performance Report" secondary="F3" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>LANGUAGE</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, p: 1 }}>
          {LANGUAGES.map(lang => (
            <Tooltip key={lang.code} title={lang.name}>
              <IconButton size="small" sx={{ fontSize: '1.2rem', p: 0.5, bgcolor: gameState?.language === lang.code ? '#e0e0e0' : 'transparent' }}>
                {lang.flag}
              </IconButton>
            </Tooltip>
          ))}
        </Box>
      </Box>

      <Box sx={{ p: 2, borderTop: '1px solid #ddd', bgcolor: '#eee' }}>
        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
          CAPTURES
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="caption">Black: {gameState?.prisoner_count.B}</Typography>
          <Typography variant="caption">White: {gameState?.prisoner_count.W}</Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Sidebar;