import { Box } from '@mui/material';

/**
 * ProgressDots — kiosk version. 5 dots representing completion percentage.
 *
 * Thresholds match galaxy TsumegoUnitsPage EXACTLY (D7):
 *   0% → 0 dots / ≤20% → 1 / ≤40% → 2 / ≤60% → 3 / ≤80% → 4 / >80% → 5.
 *
 * Dots are sized larger than galaxy (touch-friendly kiosk terminals).
 */

interface ProgressDotsProps {
  completed: number;
  total: number;
  /** Dot diameter in px (default 12 — larger than galaxy's 8 for touch readability). */
  dotSize?: number;
}

function filledDotsFor(completed: number, total: number): number {
  const percentage = total > 0 ? completed / total : 0;
  if (percentage === 0) return 0;
  if (percentage <= 0.2) return 1;
  if (percentage <= 0.4) return 2;
  if (percentage <= 0.6) return 3;
  if (percentage <= 0.8) return 4;
  return 5;
}

const ProgressDots = ({ completed, total, dotSize = 12 }: ProgressDotsProps) => {
  const filledDots = filledDotsFor(completed, total);

  return (
    <Box sx={{ display: 'flex', gap: 0.75 }}>
      {[0, 1, 2, 3, 4].map((i) => (
        <Box
          key={i}
          sx={{
            width: dotSize,
            height: dotSize,
            borderRadius: '50%',
            bgcolor: i < filledDots ? '#5cb57a' : 'rgba(232,228,220,0.18)',
          }}
        />
      ))}
    </Box>
  );
};

export default ProgressDots;
