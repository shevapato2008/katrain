import React, { useState } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box, Typography, Divider 
} from '@mui/material';
import { type GameState } from '../api';

interface AISettingsDialogProps {
  open: boolean;
  gameState: GameState | null;
  onClose: () => void;
  onConfirm: (bw: 'B' | 'W', strategy: string) => void;
}

const STRATEGIES = [
  { value: 'ai:default', label: 'Recommended' },
  { value: 'ai:human', label: 'Human Style' },
  { value: 'ai:pro', label: 'Pro Style' },
  { value: 'ai:p:rank', label: 'Rank Based' },
  { value: 'ai:handicap', label: 'Handicap' },
  { value: 'ai:scoreloss', label: 'Score Loss' },
];

const AISettingsDialog: React.FC<AISettingsDialogProps> = ({ open, gameState, onClose, onConfirm }) => {
  const [bStrategy, setBStrategy] = useState(gameState?.players_info.B.player_subtype || 'ai:default');
  const [wStrategy, setWStrategy] = useState(gameState?.players_info.W.player_subtype || 'ai:default');

  const handleConfirm = () => {
    onConfirm('B', bStrategy);
    onConfirm('W', wStrategy);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>AI Settings</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>Black Player AI</Typography>
            <TextField
              select
              value={bStrategy}
              onChange={(e) => setBStrategy(e.target.value)}
              fullWidth
              size="small"
            >
              {STRATEGIES.map((s) => (
                <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
              ))}
            </TextField>
          </Box>
          
          <Divider />

          <Box>
            <Typography variant="subtitle2" gutterBottom>White Player AI</Typography>
            <TextField
              select
              value={wStrategy}
              onChange={(e) => setWStrategy(e.target.value)}
              fullWidth
              size="small"
            >
              {STRATEGIES.map((s) => (
                <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
              ))}
            </TextField>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleConfirm} variant="contained">Apply</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AISettingsDialog;
