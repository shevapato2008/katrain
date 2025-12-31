import React, { useState } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box, Typography, Divider, ListSubheader
} from '@mui/material';
import { type GameState } from '../api';
import { i18n } from '../i18n';

interface AISettingsDialogProps {
  open: boolean;
  gameState: GameState | null;
  onClose: () => void;
  onConfirm: (bw: 'B' | 'W', strategy: string) => void;
}

const AISettingsDialog: React.FC<AISettingsDialogProps> = ({ open, gameState, onClose, onConfirm }) => {
  const STRATEGY_GROUPS = [
    {
      label: i18n.t('Recommended'),
      options: [
        { value: 'ai:default', label: i18n.t('AI: Recommended') },
        { value: 'ai:human', label: i18n.t('AI: Human Style') },
        { value: 'ai:pro', label: i18n.t('AI: Pro Style') },
        { value: 'ai:p:rank', label: i18n.t('AI: Rank Based') },
      ]
    },
    {
      label: i18n.t('Strength Based'),
      options: [
        { value: 'ai:handicap', label: i18n.t('AI: Handicap') },
        { value: 'ai:scoreloss', label: i18n.t('AI: Score Loss') },
        { value: 'ai:simple', label: i18n.t('AI: Simple Ownership') },
      ]
    },
    {
      label: i18n.t('Policy Based'),
      options: [
        { value: 'ai:policy', label: i18n.t('AI: Policy') },
        { value: 'ai:p:weighted', label: i18n.t('AI: Weighted') },
        { value: 'ai:jigo', label: i18n.t('AI: Jigo') },
        { value: 'ai:antimirror', label: i18n.t('AI: Antimirror') },
      ]
    },
    {
      label: i18n.t('Experimental'),
      options: [
        { value: 'ai:p:pick', label: i18n.t('AI: Pick') },
        { value: 'ai:p:local', label: i18n.t('AI: Local') },
        { value: 'ai:p:tenuki', label: i18n.t('AI: Tenuki') },
        { value: 'ai:p:territory', label: i18n.t('AI: Territory') },
        { value: 'ai:p:influence', label: i18n.t('AI: Influence') },
      ]
    }
  ];

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
      <MenuItem key="player:human" value="player:human">{i18n.t("Human")}</MenuItem>
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
      <DialogTitle>{i18n.t("AI Settings")}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>{i18n.t("Black Player AI")}</Typography>
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
            <Typography variant="subtitle2" gutterBottom>{i18n.t("White Player AI")}</Typography>
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
        <Button onClick={onClose}>{i18n.t("Cancel")}</Button>
        <Button onClick={handleConfirm} variant="contained">{i18n.t("Apply")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AISettingsDialog;
