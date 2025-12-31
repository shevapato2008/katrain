import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import { i18n } from '../i18n';

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
      <DialogTitle>{i18n.t("Game Report")}</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">{i18n.t("Summary Statistics")}</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{i18n.t("Player")}</TableCell>
                  <TableCell align="right">{i18n.t("Avg Pt Loss")}</TableCell>
                  <TableCell align="right">{i18n.t("Mistakes")}</TableCell>
                  <TableCell align="right">{i18n.t("Blunders")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {['B', 'W'].map(bw => (
                  <TableRow key={bw}>
                    <TableCell sx={{ fontWeight: 'bold' }}>{bw === 'B' ? i18n.t("Black") : i18n.t("White")}</TableCell>
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
          <Typography variant="subtitle1" gutterBottom fontWeight="bold">{i18n.t("Move Quality Distribution")}</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{i18n.t("Threshold (pts)")}</TableCell>
                  <TableCell align="right">{i18n.t("Black")}</TableCell>
                  <TableCell align="right">{i18n.t("White")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {thresholds.map((t: number, i: number) => (
                  <TableRow key={i}>
                    <TableCell>{t === 0 ? i18n.t("Best") : `< ${t}`}</TableCell>
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
        <Button onClick={onClose} color="primary">{i18n.t("Close")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default GameReportDialog;