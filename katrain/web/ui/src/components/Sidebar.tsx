import React from 'react';
import { Box, Typography, Divider, List, ListItem, ListItemText, ListItemIcon, ListItemButton, Tooltip, IconButton } from '@mui/material';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';
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
import SwapCallsIcon from '@mui/icons-material/SwapCalls';

interface SidebarProps {
  gameState: GameState | null;
  onNewGame: () => void;
  onLoadSGF: (sgf: string) => void;
  onSaveSGF: () => void;
  onAISettings: () => void;
  onAnalyzeGame: () => void;
  onGameReport: () => void;
  onLanguageChange: (lang: string) => void;
  onSwapPlayers?: () => void;
}

const LANGUAGES = [
  { code: 'en', flag: 'flag-uk.png', name: 'English' },
  { code: 'de', flag: 'flag-de.png', name: 'Deutsch' },
  { code: 'fr', flag: 'flag-fr.png', name: 'Français' },
  { code: 'ru', flag: 'flag-ru.png', name: 'Русский' },
  { code: 'cn', flag: 'flag-cn.png', name: '简体中文' },
  { code: 'tw', flag: 'flag-tw.png', name: '繁體中文' },
  { code: 'ko', flag: 'flag-ko.png', name: '한국어' },
  { code: 'jp', flag: 'flag-jp.png', name: '日本語' },
  { code: 'tr', flag: 'flag-tr.png', name: 'Türkçe' },
];

const Sidebar: React.FC<SidebarProps> = ({ gameState, onNewGame, onLoadSGF, onSaveSGF, onAISettings, onAnalyzeGame, onGameReport, onLanguageChange, onSwapPlayers }) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const { t } = useTranslation();

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
    if (!info) return t('Loading...');
    if (info.player_type === 'player:human') return t('player:human');
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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" color="textSecondary">{t('menu:playersetup').toUpperCase()}</Typography>
          <Tooltip title={t("Swap Players")}>
            <IconButton size="small" onClick={onSwapPlayers} sx={{ p: 0.5 }}>
              <SwapCallsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Box sx={{ mb: 2, bgcolor: '#fff', p: 1, borderRadius: 1, border: '1px solid #ddd' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 20, height: 20, bgcolor: 'black', borderRadius: '50%', mr: 1, border: '1px solid #444' }} />
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{t('Black')}</Typography>
            </Box>
            <Typography variant="caption" sx={{ bgcolor: '#eee', px: 0.5, borderRadius: 0.5 }}>{getPlayerDisplay('B')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 20, height: 20, bgcolor: 'white', border: '1px solid #000', borderRadius: '50%', mr: 1 }} />
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{t('White')}</Typography>
            </Box>
            <Typography variant="caption" sx={{ bgcolor: '#eee', px: 0.5, borderRadius: 0.5 }}>{getPlayerDisplay('W')}</Typography>
          </Box>
        </Box>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>{t('GAME')}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onNewGame}>
              <ListItemIcon sx={{ minWidth: 36 }}><PlayArrowIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:newgame')} secondary="Ctrl-N" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onSaveSGF}>
              <ListItemIcon sx={{ minWidth: 36 }}><SaveIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:save')} secondary="Ctrl-S" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={() => fileInputRef.current?.click()}>
              <ListItemIcon sx={{ minWidth: 36 }}><FileOpenIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:load')} secondary="Ctrl-L" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>{t('menu:settings').toUpperCase()}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAISettings}>
              <ListItemIcon sx={{ minWidth: 36 }}><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:aisettings')} secondary="F7" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><TimerIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:clocksettings')} secondary="F5" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><SchoolIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:teachsettings')} secondary="F6" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><EngineeringIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:settings')} secondary="F8" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36 }}><HubIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('menu:distributed')} secondary="F9" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>{t('ANALYSIS')}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAnalyzeGame}>
              <ListItemIcon sx={{ minWidth: 36 }}><AnalyticsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('analysis:extra')} secondary="F2" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onGameReport}>
              <ListItemIcon sx={{ minWidth: 36 }}><AssessmentIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary={t('analysis:report')} secondary="F3" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 2 }}>{t('menu:lang').toUpperCase()}</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, p: 1 }}>
          {LANGUAGES.map(lang => (
            <Tooltip key={lang.code} title={lang.name}>
              <IconButton 
                size="small" 
                onClick={() => onLanguageChange(lang.code)}
                sx={{ p: 0.5, bgcolor: gameState?.language === lang.code ? '#e0e0e0' : 'transparent', borderRadius: 1 }}
              >
                <img src={`/assets/img/flags/${lang.flag}`} alt={lang.name} style={{ width: 24, height: 16, objectFit: 'cover' }} />
              </IconButton>
            </Tooltip>
          ))}
        </Box>
      </Box>

      <Box sx={{ p: 2, borderTop: '1px solid #ddd', bgcolor: '#eee' }}>
        <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}>
          {t('CAPTURES').toUpperCase()}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="caption">{t('Black')}: {gameState?.prisoner_count.B}</Typography>
          <Typography variant="caption">{t('White')}: {gameState?.prisoner_count.W}</Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Sidebar;
