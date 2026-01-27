import { Box, Typography, Card, CardActionArea } from '@mui/material';
import MiniBoard from './MiniBoard';
import { useTranslation } from '../../../hooks/useTranslation';

interface ProblemProgress {
  completed: boolean;
  attempts: number;
  lastDuration?: number;
}

interface ProblemCardProps {
  index: number;
  initialBlack: string[];
  initialWhite: string[];
  progress?: ProblemProgress;
  onClick: () => void;
}

const ProblemCard = ({ index, initialBlack, initialWhite, progress, onClick }: ProblemCardProps) => {
  const { t } = useTranslation();
  const isCompleted = progress?.completed;
  const isAttempted = progress && progress.attempts > 0;

  // Border color based on status
  const borderColor = isCompleted
    ? '#4caf50'  // green
    : isAttempted
      ? '#e89639'  // orange
      : 'rgba(255,255,255,0.1)';  // gray

  return (
    <Card
      sx={{
        bgcolor: 'rgba(255,255,255,0.05)',
        border: `2px solid ${borderColor}`,
        borderRadius: 2,
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'scale(1.02)',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        }
      }}
    >
      <CardActionArea onClick={onClick} sx={{ p: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
          <MiniBoard
            size={100}
            blackStones={initialBlack}
            whiteStones={initialWhite}
          />
        </Box>

        <Typography variant="body2" align="center" sx={{ fontWeight: 500 }}>
          {t('tsumego:problem_n').replace('{n}', String(index + 1))}
        </Typography>

        {/* Progress stats */}
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mt: 0.5, minHeight: 20 }}>
          {isCompleted && progress?.lastDuration && (
            <Typography variant="caption" sx={{ color: '#e89639' }}>
              {progress.lastDuration < 60
                ? `${progress.lastDuration}s`
                : `${Math.floor(progress.lastDuration / 60)}m${progress.lastDuration % 60}s`}
            </Typography>
          )}
          {progress && progress.attempts > 0 && (
            <Typography variant="caption" sx={{ color: isCompleted ? 'text.secondary' : '#e16b5c' }}>
              x{progress.attempts}
            </Typography>
          )}
        </Box>
      </CardActionArea>
    </Card>
  );
};

export default ProblemCard;
