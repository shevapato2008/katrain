import React from 'react';
import { Box, Typography, Divider, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { type GameState } from '../api';

interface AnalysisPanelProps {
  gameState: GameState | null;
}

const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ gameState }) => {
  if (!gameState || !gameState.analysis) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="textSecondary">No analysis data available.</Typography>
      </Box>
    );
  }

  const analysis = gameState.analysis;
  const topMoves = analysis.moves || [];

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 1, bgcolor: '#f0f0f0' }}>
        <Typography variant="subtitle2">ANALYSIS</Typography>
      </Box>
      <Divider />
      
      <Box sx={{ p: 1, display: 'flex', justifyContent: 'space-around' }}>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="caption" color="textSecondary">Winrate</Typography>
          <Typography variant="body2" fontWeight="bold">{(analysis.winrate * 100).toFixed(1)}%</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="caption" color="textSecondary">Score</Typography>
          <Typography variant="body2" fontWeight="bold">{analysis.score.toFixed(1)}</Typography>
        </Box>
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="caption" color="textSecondary">Visits</Typography>
          <Typography variant="body2" fontWeight="bold">{analysis.visits}</Typography>
        </Box>
      </Box>
      <Divider />

      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 0 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }}>Move</TableCell>
                <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }} align="right">Loss</TableCell>
                <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }} align="right">Win%</TableCell>
                <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }} align="right">Visits</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {topMoves.slice(0, 10).map((move: any, index: number) => (
                <TableRow key={index} hover>
                  <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }}>{move.move}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.75rem', py: 0.5, color: move.scoreLoss > 2 ? 'error.main' : 'text.primary' }}>
                    {move.scoreLoss.toFixed(1)}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }} align="right">{(move.winrate * 100).toFixed(1)}%</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', py: 0.5 }} align="right">{move.visits}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Box>
  );
};

export default AnalysisPanel;
