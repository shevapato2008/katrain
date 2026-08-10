import { Box, Button, CircularProgress, Stack, Typography } from '@mui/material';
import type { SettlementFeedback } from '../../../features/aiLadder/settlement';

interface AiLadderSettlementPanelProps {
  feedback: SettlementFeedback;
  onPlayAgain: () => void;
  onReturn: () => void;
}

const AiLadderSettlementPanel = ({ feedback, onPlayAgain, onReturn }: AiLadderSettlementPanelProps) => {
  const pending = feedback.kind === 'pending';
  const failed = feedback.kind === 'error';
  const settled = !pending && !failed;
  const title = pending ? '正在确认结算' : failed ? '结算暂不可用' : '本局已结算';

  return (
    <Box
      component="section"
      aria-labelledby="ai-ladder-settlement-title"
      data-testid="ai-ladder-settlement-panel"
      sx={{ p: 2, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
    >
      <Stack direction="row" alignItems="center" spacing={1}>
        {pending && <CircularProgress size={18} thickness={5} />}
        <Typography id="ai-ladder-settlement-title" component="h2" variant="subtitle1" sx={{ fontWeight: 700 }}>
          {title}
        </Typography>
      </Stack>
      <Typography
        variant="body2"
        sx={{
          mt: 0.75,
          color: failed ? 'error.main' : feedback.kind === 'not_counted' || feedback.kind === 'demotion' ? 'warning.main' : 'text.primary',
        }}
      >
        {feedback.message}
      </Typography>
      {(feedback.retry || settled) && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          {feedback.retry && (
            <Button variant="outlined" onClick={feedback.retry} sx={{ minHeight: 44, flex: 1 }}>重试</Button>
          )}
          {settled && (
            <>
              <Button variant="contained" onClick={onPlayAgain} sx={{ minHeight: 44, flex: 1 }}>再来一局</Button>
              <Button variant="outlined" onClick={onReturn} sx={{ minHeight: 44, flex: 1 }}>返回对局</Button>
            </>
          )}
        </Stack>
      )}
    </Box>
  );
};

export default AiLadderSettlementPanel;
