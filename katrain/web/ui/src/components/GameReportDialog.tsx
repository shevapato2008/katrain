import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';

interface GameReportDialogProps {
  open: boolean;
  onClose: () => void;
  report: any;
}

const GameReportDialog: React.FC<GameReportDialogProps> = ({ open, onClose, report }) => {
  if (!report) return null;

  const { sum_stats, player_ptloss, thresholds } = report;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Game Report</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">Summary Statistics</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Player</TableCell>
                  <TableCell align="right">Avg Pt Loss</TableCell>
                  <TableCell align="right">Mistakes</TableCell>
                  <TableCell align="right">Blunders</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {['B', 'W'].map(bw => (
                  <TableRow key={bw}>
                    <TableCell sx={{ fontWeight: 'bold' }}>{bw === 'B' ? 'Black' : 'White'}</TableCell>
                    <TableCell align="right">{sum_stats[bw]?.avg_loss?.toFixed(2)}</TableCell>
                    <TableCell align="right">{sum_stats[bw]?.mistakes}</TableCell>
                    <TableCell align="right">{sum_stats[bw]?.blunders}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        <Box>
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">Move Quality Distribution</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Threshold (pts)</TableCell>
                  <TableCell align="right">Black</TableCell>
                  <TableCell align="right">White</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {thresholds.map((t: number, i: number) => (
                  <TableRow key={i}>
                    <TableCell>{t === 0 ? 'Best' : `< ${t}`}</TableCell>
                    <TableCell align="right">{player_ptloss['B']?.[i] || 0}</TableCell>
                    <TableCell align="right">{player_ptloss['W']?.[i] || 0}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default GameReportDialog;
