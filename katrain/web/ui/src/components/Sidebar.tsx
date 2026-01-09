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
    <Box sx={{ width: 280, borderRight: '1px solid rgba(255, 255, 255, 0.05)', height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#252525', overflowY: 'auto' }}>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".sgf,.ngf,.gib"
        onChange={handleFileChange}
      />
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom sx={{ color: '#f5f3f0', fontWeight: 600 }}>KaTrain Web</Typography>
        <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.1)' }} />
      </Box>

      <Box sx={{ p: 2, flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" sx={{ color: '#7a7772', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>{t('menu:playersetup').toUpperCase()}</Typography>
          <Tooltip title={t("Swap Players")}>
            <IconButton size="small" onClick={onSwapPlayers} sx={{ p: 0.5, color: '#b8b5b0', '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)', color: '#4a6b5c' } }}>
              <SwapCallsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Box sx={{ mb: 2, bgcolor: '#2a2a2a', p: 1.5, borderRadius: 1, border: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 20, height: 20, bgcolor: '#0a0a0a', borderRadius: '50%', mr: 1, border: '1px solid #444' }} />
              <Typography variant="body2" sx={{ fontWeight: 600, color: '#f5f3f0' }}>{t('Black')}</Typography>
            </Box>
            <Typography variant="caption" sx={{ bgcolor: 'rgba(255, 255, 255, 0.05)', px: 0.75, py: 0.25, borderRadius: 0.5, color: '#b8b5b0', fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>{getPlayerDisplay('B')}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ width: 20, height: 20, bgcolor: '#f8f6f3', border: '1px solid #888', borderRadius: '50%', mr: 1 }} />
              <Typography variant="body2" sx={{ fontWeight: 600, color: '#f5f3f0' }}>{t('White')}</Typography>
            </Box>
            <Typography variant="caption" sx={{ bgcolor: 'rgba(255, 255, 255, 0.05)', px: 0.75, py: 0.25, borderRadius: 0.5, color: '#b8b5b0', fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>{getPlayerDisplay('W')}</Typography>
          </Box>
        </Box>

        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2, color: '#7a7772', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>{t('GAME')}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onNewGame} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><PlayArrowIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:newgame')}
                secondary="Ctrl-N"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onSaveSGF} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><SaveIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:save')}
                secondary="Ctrl-S"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={() => fileInputRef.current?.click()} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><FileOpenIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:load')}
                secondary="Ctrl-L"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2, color: '#7a7772', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>{t('menu:settings').toUpperCase()}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAISettings} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:aisettings')}
                secondary="F7"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a4845' }}><TimerIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:clocksettings')}
                secondary="F5"
                primaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a4845' }}><SchoolIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:teachsettings')}
                secondary="F6"
                primaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a4845' }}><EngineeringIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:settings')}
                secondary="F8"
                primaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a4845' }}><HubIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('menu:distributed')}
                secondary="F9"
                primaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#4a4845', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2, color: '#7a7772', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>{t('ANALYSIS')}</Typography>
        <List dense sx={{ py: 0 }}>
          <ListItem disablePadding>
            <ListItemButton onClick={onAnalyzeGame} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><AnalyticsIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('analysis:extra')}
                secondary="F2"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onGameReport} sx={{ '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' } }}>
              <ListItemIcon sx={{ minWidth: 36, color: '#4a6b5c' }}><AssessmentIcon fontSize="small" /></ListItemIcon>
              <ListItemText
                primary={t('analysis:report')}
                secondary="F3"
                primaryTypographyProps={{ sx: { color: '#f5f3f0', fontSize: '0.875rem' } }}
                secondaryTypographyProps={{ sx: { color: '#7a7772', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' } }}
              />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2, color: '#7a7772', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>{t('menu:lang').toUpperCase()}</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, p: 1 }}>
          {LANGUAGES.map(lang => (
            <Tooltip key={lang.code} title={lang.name}>
              <IconButton
                size="small"
                onClick={() => onLanguageChange(lang.code)}
                sx={{
                  p: 0.5,
                  bgcolor: gameState?.language === lang.code ? 'rgba(74, 107, 92, 0.2)' : 'transparent',
                  borderRadius: 1,
                  border: gameState?.language === lang.code ? '1px solid #4a6b5c' : '1px solid transparent',
                  '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' }
                }}
              >
                <img src={`/assets/img/flags/${lang.flag}`} alt={lang.name} style={{ width: 24, height: 16, objectFit: 'cover' }} />
              </IconButton>
            </Tooltip>
          ))}
        </Box>
      </Box>

      <Box sx={{ p: 2, borderTop: '1px solid rgba(255, 255, 255, 0.1)', bgcolor: '#1a1a1a' }}>
        <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 0.5, color: '#7a7772', fontSize: '0.75rem', letterSpacing: '0.5px' }}>
          {t('CAPTURES').toUpperCase()}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="caption" sx={{ color: '#b8b5b0', fontFamily: 'var(--font-mono)' }}>{t('Black')}: {gameState?.prisoner_count.B}</Typography>
          <Typography variant="caption" sx={{ color: '#b8b5b0', fontFamily: 'var(--font-mono)' }}>{t('White')}: {gameState?.prisoner_count.W}</Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Sidebar;
