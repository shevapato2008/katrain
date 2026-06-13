import { Box, Typography, Card, CardActionArea } from '@mui/material';
import MiniBoard from '../../../components/MiniBoard';
import { useTranslation } from '../../../hooks/useTranslation';
import { useTsumegoProgress } from '../../../context/TsumegoProgressContext';

/**
 * ProblemCard — kiosk version. Self-contained: reads its own progress entry from the
 * unified useTsumegoProgress source (no progress prop passed down).
 *
 * Completion-state visual (D6, matching galaxy):
 *   border green  = completed
 *   border orange = attempted but not completed
 *   border gray   = untouched
 * Shows a touch-sized MiniBoard thumbnail + problem number + "上次用时" when available.
 */

interface ProblemCardProps {
  problemId: string;
  /** Zero-based index within the category (display = index + 1). */
  index: number;
  initialBlack?: string[];
  initialWhite?: string[];
  onClick: () => void;
  /** MiniBoard thumbnail size in px (default 120 — larger than galaxy's 100 for touch). */
  thumbSize?: number;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
}

const ProblemCard = ({
  problemId,
  index,
  initialBlack = [],
  initialWhite = [],
  onClick,
  thumbSize = 120,
}: ProblemCardProps) => {
  const { t } = useTranslation();
  const { progress } = useTsumegoProgress();
  const entry = progress[problemId];

  const isCompleted = !!entry?.completed;
  const isAttempted = !!entry && entry.attempts > 0;

  const borderColor = isCompleted
    ? '#5cb57a' // jade-glow (green = completed)
    : isAttempted
      ? '#c49a3c' // wood-amber (orange = attempted, not completed)
      : 'rgba(232,228,220,0.10)'; // gray = untouched

  return (
    <Card
      sx={{
        bgcolor: 'rgba(255,255,255,0.05)',
        border: `2px solid ${borderColor}`,
        borderRadius: 2.5,
        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
        '&:hover': { transform: 'scale(1.02)', boxShadow: '0 4px 12px rgba(0,0,0,0.35)' },
      }}
    >
      <CardActionArea onClick={onClick} sx={{ p: 1.25 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
          <MiniBoard size={thumbSize} blackStones={initialBlack} whiteStones={initialWhite} />
        </Box>

        <Typography variant="body1" align="center" sx={{ fontWeight: 600 }}>
          {t('tsumego:problem_n', `第 ${index + 1} 题`).replace('{n}', String(index + 1))}
        </Typography>

        {/* Progress stats — fixed min height to keep grid rows aligned */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 1,
            mt: 0.5,
            minHeight: 22,
          }}
        >
          {isCompleted && entry?.lastDuration != null && (
            <Typography variant="caption" sx={{ color: '#c49a3c' }}>
              {t('tsumego:lastTime', '上次用时')} {formatDuration(entry.lastDuration)}
            </Typography>
          )}
          {entry && entry.attempts > 0 && (
            <Typography
              variant="caption"
              sx={{ color: isCompleted ? 'text.secondary' : '#c45d3e' }}
            >
              x{entry.attempts}
            </Typography>
          )}
        </Box>
      </CardActionArea>
    </Card>
  );
};

export default ProblemCard;
