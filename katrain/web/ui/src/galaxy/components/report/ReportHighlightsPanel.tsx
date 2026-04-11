import { Button, Stack, Typography } from '@mui/material';

import type { MoveAnalysis } from '../../../types/live';

interface HighlightBundle {
  biggestGain: MoveAnalysis | null;
  biggestLoss: MoveAnalysis | null;
  biggestSwing: MoveAnalysis | null;
}

interface ReportHighlightsPanelProps {
  highlights: HighlightBundle | null;
  currentMove: number;
  onMoveSelect: (moveNumber: number) => void;
}

export default function ReportHighlightsPanel({
  highlights,
  currentMove,
  onMoveSelect,
}: ReportHighlightsPanelProps) {
  if (!highlights) {
    return (
      <>
        <Typography variant="subtitle1" gutterBottom>报告摘要</Typography>
        <Typography variant="body2" color="text.secondary">当前还没有可汇总的关键手。</Typography>
      </>
    );
  }

  const rows = [
    {
      key: 'gain',
      label: '最佳收益',
      entry: highlights.biggestGain,
      color: undefined,
    },
    {
      key: 'loss',
      label: '最大失误',
      entry: highlights.biggestLoss,
      color: 'warning' as const,
    },
    {
      key: 'swing',
      label: '关键转折',
      entry: highlights.biggestSwing,
      color: undefined,
    },
  ];

  return (
    <>
      <Typography variant="subtitle1" gutterBottom>报告摘要</Typography>
      <Stack spacing={1}>
        {rows.map(({ key, label, entry, color }) =>
          entry ? (
            <Button
              key={key}
              variant={currentMove === entry.move_number ? 'contained' : 'text'}
              color={color}
              onClick={() => onMoveSelect(entry.move_number)}
              sx={{ justifyContent: 'space-between' }}
            >
              <span>{label}</span>
              <span>
                #{entry.move_number} {entry.move || 'pass'} · {entry.delta_score >= 0 ? '+' : ''}
                {entry.delta_score.toFixed(1)}
              </span>
            </Button>
          ) : null,
        )}
      </Stack>
    </>
  );
}
