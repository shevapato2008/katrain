import React, { useState } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box, Typography, Divider, ListSubheader
} from '@mui/material';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface AISettingsDialogProps {
  open: boolean;
  gameState: GameState | null;
  onClose: () => void;
  onConfirm: (bw: 'B' | 'W', strategy: string) => void;
}

const AISettingsDialog: React.FC<AISettingsDialogProps> = ({ open, gameState, onClose, onConfirm }) => {
  const { t } = useTranslation();
  const STRATEGY_GROUPS = [
    {
      label: t('Recommended'),
      options: [
        { value: 'ai:default', label: t('AI: Recommended') },
        { value: 'ai:human', label: t('AI: Human Style') },
        { value: 'ai:pro', label: t('AI: Pro Style') },
        { value: 'ai:p:rank', label: t('AI: Rank Based') },
      ]
    },
    {
      label: t('Strength Based'),
      options: [
        { value: 'ai:handicap', label: t('AI: Handicap') },
        { value: 'ai:scoreloss', label: t('AI: Score Loss') },
        { value: 'ai:simple', label: t('AI: Simple Ownership') },
      ]
    },
    {
      label: t('Policy Based'),
      options: [
        { value: 'ai:policy', label: t('AI: Policy') },
        { value: 'ai:p:weighted', label: t('AI: Weighted') },
        { value: 'ai:jigo', label: t('AI: Jigo') },
        { value: 'ai:antimirror', label: t('AI: Antimirror') },
      ]
    },
    {
      label: t('Experimental'),
      options: [
        { value: 'ai:p:pick', label: t('AI: Pick') },
        { value: 'ai:p:local', label: t('AI: Local') },
        { value: 'ai:p:tenuki', label: t('AI: Tenuki') },
        { value: 'ai:p:territory', label: t('AI: Territory') },
        { value: 'ai:p:influence', label: t('AI: Influence') },
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
      <MenuItem key="player:human" value="player:human">{t("Human")}</MenuItem>
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
      <DialogTitle>{t("AI Settings")}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>{t("Black Player AI")}</Typography>
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
            <Typography variant="subtitle2" gutterBottom>{t("White Player AI")}</Typography>
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
        <Button onClick={onClose}>{t("Cancel")}</Button>
        <Button onClick={handleConfirm} variant="contained">{t("Apply")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AISettingsDialog;
