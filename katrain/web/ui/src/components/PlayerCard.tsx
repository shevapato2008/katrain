import React from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { type PlayerInfo } from '../api';
import { i18n } from '../i18n';

interface PlayerCardProps {
  player: 'B' | 'W';
  info: PlayerInfo;
  captures: number;
  active: boolean;
}

const PlayerCard: React.FC<PlayerCardProps> = ({ player, info, captures, active }) => {
  const isBlack = player === 'B';
  return (
    <Paper 
      elevation={active ? 4 : 1} 
      sx={{ 
        p: 1, 
        flex: 1, 
        bgcolor: active ? (isBlack ? '#333' : '#fff') : (isBlack ? '#000' : '#eee'),
        color: isBlack ? '#fff' : '#000',
        border: active ? '2px solid #3f51b5' : '2px solid transparent',
        transition: 'all 0.2s'
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box sx={{ 
            width: 24, height: 24, borderRadius: '50%', 
            bgcolor: isBlack ? 'black' : 'white',
            border: '1px solid #888',
            mr: 1
          }} />
          <Typography variant="body2" fontWeight="bold" noWrap sx={{ maxWidth: 80 }}>
            {info.name || (isBlack ? i18n.t('Black') : i18n.t('White'))}
          </Typography>
        </Box>
        <Typography variant="caption" sx={{ opacity: 0.8 }}>
          {info.calculated_rank || '?' }
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
        <Typography variant="caption">{i18n.t("Captures")}: {captures}</Typography>
        <Typography variant="caption">{i18n.t(info.player_type)}</Typography>
      </Box>
    </Paper>
  );
};

export default PlayerCard;