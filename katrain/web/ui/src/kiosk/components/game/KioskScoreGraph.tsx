import { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import type { KioskAnalysisPoint } from '../../data/mocks';

interface Props {
  history: KioskAnalysisPoint[];
  currentMoveIndex: number;
  currentWinrate: number;
  currentScore: number;
}

const WIDTH = 420;
const HEIGHT = 180;
const LEFT_PAD = 42;
const RIGHT_PAD = 42;
const TOP_PAD = 16;
const BOTTOM_PAD = 12;
const CHART_W = WIDTH - LEFT_PAD - RIGHT_PAD;
const CHART_H = HEIGHT - TOP_PAD - BOTTOM_PAD;

const KioskScoreGraph = ({ history, currentMoveIndex, currentWinrate, currentScore }: Props) => {
  const { winrateLine, scoreLine, scoreScale, currentX } = useMemo(() => {
    if (history.length === 0) return { winrateLine: '', scoreLine: '', scoreScale: 30, currentX: LEFT_PAD };

    const maxAbsScore = Math.max(...history.map((p) => Math.abs(p.score)), 1);
    const scale = Math.ceil(maxAbsScore / 10) * 10 || 30;
    const xStep = CHART_W / Math.max(history.length - 1, 15);

    const wrPoints = history.map((p, i) => {
      const x = LEFT_PAD + i * xStep;
      const y = TOP_PAD + CHART_H * (1 - p.winrate);
      return `${x},${y}`;
    });

    const scPoints = history.map((p, i) => {
      const x = LEFT_PAD + i * xStep;
      const normalized = p.score / scale; // -1 to 1
      const y = TOP_PAD + CHART_H * (0.5 - normalized * 0.5);
      return `${x},${y}`;
    });

    const curIdx = history.findIndex((p) => p.moveIndex === currentMoveIndex);
    const cx = curIdx >= 0 ? LEFT_PAD + curIdx * xStep : LEFT_PAD + (history.length - 1) * xStep;

    return { winrateLine: wrPoints.join(' '), scoreLine: scPoints.join(' '), scoreScale: scale, currentX: cx };
  }, [history, currentMoveIndex]);

  if (history.length === 0) return null;

  const gridY50 = TOP_PAD + CHART_H * 0.5;
  const gridY0 = TOP_PAD + CHART_H;
  const gridY100 = TOP_PAD;

  return (
    <Box data-testid="score-graph">
      {/* Labels */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1, mb: 0.5 }}>
        <Typography variant="caption" sx={{ color: 'rgba(76,175,80,0.9)' }}>
          黑棋胜率: {(currentWinrate * 100).toFixed(1)}%
        </Typography>
        <Typography variant="caption" sx={{ color: 'rgba(255,152,0,0.9)' }}>
          黑棋领先: {currentScore > 0 ? '+' : ''}{currentScore.toFixed(1)} 目
        </Typography>
      </Box>

      {/* SVG Chart */}
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        <line x1={LEFT_PAD} y1={gridY100} x2={WIDTH - RIGHT_PAD} y2={gridY100} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
        <line x1={LEFT_PAD} y1={gridY50} x2={WIDTH - RIGHT_PAD} y2={gridY50} stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" strokeDasharray="4 3" />
        <line x1={LEFT_PAD} y1={gridY0} x2={WIDTH - RIGHT_PAD} y2={gridY0} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />

        {/* Left Y-axis labels (winrate) */}
        <text x={LEFT_PAD - 4} y={gridY100 + 4} textAnchor="end" fill="rgba(76,175,80,0.8)" fontSize="9">100%</text>
        <text x={LEFT_PAD - 4} y={gridY50 + 3} textAnchor="end" fill="rgba(76,175,80,0.8)" fontSize="9">50%</text>
        <text x={LEFT_PAD - 4} y={gridY0} textAnchor="end" fill="rgba(76,175,80,0.8)" fontSize="9">0%</text>

        {/* Right Y-axis labels (score) */}
        <text x={WIDTH - RIGHT_PAD + 4} y={gridY100 + 4} textAnchor="start" fill="rgba(255,152,0,0.8)" fontSize="9">+{scoreScale}</text>
        <text x={WIDTH - RIGHT_PAD + 4} y={gridY50 + 3} textAnchor="start" fill="rgba(255,152,0,0.8)" fontSize="9">0</text>
        <text x={WIDTH - RIGHT_PAD + 4} y={gridY0} textAnchor="start" fill="rgba(255,152,0,0.8)" fontSize="9">-{scoreScale}</text>

        {/* Score line (orange) */}
        <polyline points={scoreLine} fill="none" stroke="rgba(255,152,0,0.8)" strokeWidth="1.5" />

        {/* Winrate line (green) */}
        <polyline points={winrateLine} fill="none" stroke="rgba(76,175,80,0.9)" strokeWidth="2" />

        {/* Current move indicator */}
        <line x1={currentX} y1={TOP_PAD} x2={currentX} y2={TOP_PAD + CHART_H} stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
      </svg>
    </Box>
  );
};

export default KioskScoreGraph;
