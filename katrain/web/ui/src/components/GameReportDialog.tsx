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
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#252525',
          backgroundImage: 'none',
        }
      }}
    >
      <DialogTitle sx={{ color: '#f5f3f0', fontWeight: 600, borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
        {i18n.t("Game Report")}
      </DialogTitle>
      <DialogContent sx={{ bgcolor: '#1a1a1a', pt: 3 }}>
        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle1"
            gutterBottom
            fontWeight="bold"
            sx={{ color: '#f5f3f0', mb: 1.5 }}
          >
            {i18n.t("Summary Statistics")}
          </Typography>
          <TableContainer
            component={Paper}
            elevation={0}
            sx={{
              bgcolor: '#2a2a2a',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: 1
            }}
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Player")}
                  </TableCell>
                  <TableCell align="right" sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Avg Pt Loss")}
                  </TableCell>
                  <TableCell align="right" sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Mistakes")}
                  </TableCell>
                  <TableCell align="right" sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Blunders")}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {['B', 'W'].map(bw => (
                  <TableRow key={bw}>
                    <TableCell sx={{ fontWeight: 600, color: '#f5f3f0', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {bw === 'B' ? i18n.t("Black") : i18n.t("White")}
                    </TableCell>
                    <TableCell align="right" sx={{ color: '#b8b5b0', fontFamily: 'var(--font-mono)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {sum_stats[bw]?.avg_loss?.toFixed(2)}
                    </TableCell>
                    <TableCell align="right" sx={{ color: '#d4a574', fontFamily: 'var(--font-mono)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {sum_stats[bw]?.mistakes}
                    </TableCell>
                    <TableCell align="right" sx={{ color: '#e16b5c', fontFamily: 'var(--font-mono)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {sum_stats[bw]?.blunders}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>

        <Box>
          <Typography
            variant="subtitle1"
            gutterBottom
            fontWeight="bold"
            sx={{ color: '#f5f3f0', mb: 1.5 }}
          >
            {i18n.t("Move Quality Distribution")}
          </Typography>
          <TableContainer
            component={Paper}
            elevation={0}
            sx={{
              bgcolor: '#2a2a2a',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: 1
            }}
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Threshold (pts)")}
                  </TableCell>
                  <TableCell align="right" sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("Black")}
                  </TableCell>
                  <TableCell align="right" sx={{ color: '#7a7772', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {i18n.t("White")}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {thresholds.map((t: number, i: number) => (
                  <TableRow key={i}>
                    <TableCell sx={{ color: '#b8b5b0', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {t === 0 ? i18n.t("Best") : `< ${t}`}
                    </TableCell>
                    <TableCell align="right" sx={{ color: '#b8b5b0', fontFamily: 'var(--font-mono)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {player_ptloss['B']?.[i] || 0}
                    </TableCell>
                    <TableCell align="right" sx={{ color: '#b8b5b0', fontFamily: 'var(--font-mono)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      {player_ptloss['W']?.[i] || 0}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </DialogContent>
      <DialogActions sx={{ bgcolor: '#252525', borderTop: '1px solid rgba(255, 255, 255, 0.05)', px: 3, py: 2 }}>
        <Button
          onClick={onClose}
          sx={{
            color: '#4a6b5c',
            fontWeight: 600,
            '&:hover': { bgcolor: 'rgba(74, 107, 92, 0.1)' }
          }}
        >
          {i18n.t("Close")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default GameReportDialog;