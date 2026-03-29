import { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
} from '@mui/material';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CaptureGuideProps {
  positions: Array<{ row: number; col: number; color: number }>; // color: 1=black, 2=white
  onDismiss?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const COL_LETTERS = 'ABCDEFGHJKLMNOPQRST'; // GTP skips 'I'

/** Convert (row, col) on a 19x19 board to GTP notation, e.g. "D4". */
function toGTP(row: number, col: number): string {
  const letter = COL_LETTERS[col] ?? '?';
  const number = 19 - row;
  return `${letter}${number}`;
}

function colorLabel(color: number): string {
  return color === 1 ? '黑' : '白';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SKIP_DELAY_MS = 30_000;

const CaptureGuide = ({ positions, onDismiss }: CaptureGuideProps) => {
  const [showSkip, setShowSkip] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timerRef.current = setTimeout(() => setShowSkip(true), SKIP_DELAY_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  if (positions.length === 0) return null;

  // Determine the dominant color for the summary label.
  const colorCounts = positions.reduce<Record<number, number>>((acc, p) => {
    acc[p.color] = (acc[p.color] ?? 0) + 1;
    return acc;
  }, {});

  const summaryParts = Object.entries(colorCounts).map(
    ([color, count]) => `${count} 颗${colorLabel(Number(color))}子`,
  );

  const gtpList = positions.map((p) => toGTP(p.row, p.col)).join(', ');

  return (
    <Dialog
      open
      fullScreen
      PaperProps={{
        sx: {
          bgcolor: 'rgba(0, 0, 0, 0.85)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
        },
      }}
    >
      <DialogTitle
        sx={{
          color: 'warning.main',
          textAlign: 'center',
          fontSize: '1.5rem',
          pt: 4,
        }}
      >
        请提走棋子
      </DialogTitle>

      <DialogContent sx={{ textAlign: 'center', maxWidth: 600 }}>
        <Typography variant="h6" sx={{ color: '#fff', mb: 2 }}>
          请提走 {summaryParts.join('、')}
        </Typography>

        <Box
          sx={{
            bgcolor: 'rgba(255,255,255,0.08)',
            borderRadius: 2,
            px: 3,
            py: 2,
            mb: 2,
          }}
        >
          <Typography
            variant="body1"
            sx={{ color: 'grey.300', fontFamily: 'monospace', wordBreak: 'break-word' }}
          >
            {gtpList}
          </Typography>
        </Box>
      </DialogContent>

      {showSkip && onDismiss && (
        <DialogActions sx={{ justifyContent: 'center', pb: 4 }}>
          <Button variant="outlined" color="warning" size="large" onClick={onDismiss}>
            跳过
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
};

export default CaptureGuide;
