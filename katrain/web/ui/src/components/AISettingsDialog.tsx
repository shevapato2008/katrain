import React, { useState } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box, Typography, Divider, ListSubheader
} from '@mui/material';
import { type GameState } from '../api';

interface AISettingsDialogProps {
  open: boolean;
  gameState: GameState | null;
  onClose: () => void;
  onConfirm: (bw: 'B' | 'W', strategy: string) => void;
}

const STRATEGY_GROUPS = [
  {
    label: 'Recommended',
    options: [
      { value: 'ai:default', label: 'AI: Recommended' },
      { value: 'ai:human', label: 'AI: Human Style' },
      { value: 'ai:pro', label: 'AI: Pro Style' },
      { value: 'ai:p:rank', label: 'AI: Rank Based' },
    ]
  },
  {
    label: 'Strength Based',
    options: [
      { value: 'ai:handicap', label: 'AI: Handicap' },
      { value: 'ai:scoreloss', label: 'AI: Score Loss' },
      { value: 'ai:simple', label: 'AI: Simple Ownership' },
    ]
  },
  {
    label: 'Policy Based',
    options: [
      { value: 'ai:policy', label: 'AI: Policy' },
      { value: 'ai:p:weighted', label: 'AI: Weighted' },
      { value: 'ai:jigo', label: 'AI: Jigo' },
      { value: 'ai:antimirror', label: 'AI: Antimirror' },
    ]
  },
  {
    label: 'Experimental',
    options: [
      { value: 'ai:p:pick', label: 'AI: Pick' },
      { value: 'ai:p:local', label: 'AI: Local' },
      { value: 'ai:p:tenuki', label: 'AI: Tenuki' },
      { value: 'ai:p:territory', label: 'AI: Territory' },
      { value: 'ai:p:influence', label: 'AI: Influence' },
    ]
  }
];

const AISettingsDialog: React.FC<AISettingsDialogProps> = ({ open, gameState, onClose, onConfirm }) => {
  const getInitialStrategy = (bw: 'B' | 'W') => {
    const info = gameState?.players_info[bw];
    if (info?.player_type === 'player:human') return 'player:human';
    return info?.player_subtype || 'ai:default';
  };

  const [bStrategy, setBStrategy] = useState(getInitialStrategy('B'));
  const [wStrategy, setWStrategy] = useState(getInitialStrategy('W'));

  const handleConfirm = () => {
    onConfirm('B', bStrategy);
    onConfirm('W', wStrategy);
    onClose();
  };

  const renderMenuItems = () => {
    const items = [
      <MenuItem key="player:human" value="player:human">Human</MenuItem>
    ];
    
    STRATEGY_GROUPS.forEach(group => {
      items.push(<ListSubheader key={group.label}>{group.label}</ListSubheader>);
      group.options.forEach(opt => {
        items.push(<MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>);
      });
    });
    
    return items;
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
              {renderMenuItems()}
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
              {renderMenuItems()}
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
