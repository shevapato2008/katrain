import {
  Box,
  Button,
  LinearProgress,
  Typography,
} from '@mui/material';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BoardSetupGuideProps {
  matched: number;
  total: number;
  missing: Array<[number, number]>; // [row, col] positions
  isComplete: boolean;
  onStartProblem: () => void;
  onSkip: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const BoardSetupGuide = ({
  matched,
  total,
  missing: _missing,
  isComplete,
  onStartProblem,
  onSkip,
}: BoardSetupGuideProps) => {
  const progress = total > 0 ? (matched / total) * 100 : 0;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        p: 2,
        bgcolor: 'background.paper',
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Progress label */}
      <Typography variant="body1" sx={{ fontWeight: 500 }}>
        已匹配 {matched}/{total} 颗子
      </Typography>

      {/* Progress bar */}
      <LinearProgress
        variant="determinate"
        value={progress}
        sx={{ height: 8, borderRadius: 1 }}
      />

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5 }}>
        <Button
          variant="outlined"
          size="medium"
          onClick={onSkip}
          sx={{ flex: 1 }}
        >
          跳过设置
        </Button>

        <Button
          variant="contained"
          size="medium"
          disabled={!isComplete}
          onClick={onStartProblem}
          sx={{ flex: 1 }}
        >
          开始答题
        </Button>
      </Box>
    </Box>
  );
};

export default BoardSetupGuide;
