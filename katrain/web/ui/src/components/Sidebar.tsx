import React from 'react';
import { Box, Typography, Divider, List, ListItem, ListItemText, ListItemIcon, ListItemButton } from '@mui/material';
import { type GameState } from '../api';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FileOpenIcon from '@mui/icons-material/FileOpen';
import SaveIcon from '@mui/icons-material/Save';
import SettingsIcon from '@mui/icons-material/Settings';

interface SidebarProps {
  gameState: GameState | null;
  onNewGame: () => void;
  onLoadSGF: (sgf: string) => void;
  onSaveSGF: () => void;
  onAISettings: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ gameState, onNewGame, onLoadSGF, onSaveSGF, onAISettings }) => {
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

  return (
    <Box sx={{ width: 280, borderRight: '1px solid #ddd', height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#f5f5f5' }}>
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
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Box sx={{ width: 20, height: 20, bgcolor: 'black', borderRadius: '50%', mr: 1 }} />
            <Typography variant="body2">Black: {gameState?.players_info.B.name || 'Human'}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Box sx={{ width: 20, height: 20, bgcolor: 'white', border: '1px solid #000', borderRadius: '50%', mr: 1 }} />
            <Typography variant="body2">White: {gameState?.players_info.W.name || 'AI'}</Typography>
          </Box>
        </Box>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 3 }}>GAME</Typography>
        <List>
          <ListItem disablePadding>
            <ListItemButton onClick={onNewGame}>
              <ListItemIcon><PlayArrowIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="New Game" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={() => fileInputRef.current?.click()}>
              <ListItemIcon><FileOpenIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Load SGF" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton onClick={onSaveSGF}>
              <ListItemIcon><SaveIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Save SGF" />
            </ListItemButton>
          </ListItem>
        </List>

        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ mt: 3 }}>SETTINGS</Typography>
        <List>
          <ListItem disablePadding>
            <ListItemButton onClick={onAISettings}>
              <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="AI Settings" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton disabled>
              <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="General Settings" />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>

      <Box sx={{ p: 2, borderTop: '1px solid #ddd' }}>
        <Typography variant="caption" color="textSecondary">
          Captures: B {gameState?.prisoner_count.B} / W {gameState?.prisoner_count.W}
        </Typography>
      </Box>
    </Box>
  );
};

export default Sidebar;
