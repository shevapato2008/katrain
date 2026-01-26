import { Box, Typography, Tabs, Tab } from '@mui/material';
import { useState, useMemo } from 'react';
import type { MoveAnalysis } from '../../types/live';

interface TrendChartProps {
  analysis: Record<number, MoveAnalysis>;
  totalMoves: number;
  currentMove: number;
  onMoveClick?: (move: number) => void;
}

export default function TrendChart({
  analysis,
  totalMoves,
  currentMove,
  onMoveClick,
}: TrendChartProps) {
  const [tab, setTab] = useState(0);

  // Extract data for chart
  const chartData = useMemo(() => {
    const moves: number[] = [];
    const winrates: number[] = [];
    const scores: number[] = [];

    for (let i = 0; i <= totalMoves; i++) {
      moves.push(i);
      const moveAnalysis = analysis[i];
      if (moveAnalysis) {
        winrates.push(moveAnalysis.winrate * 100);
        scores.push(moveAnalysis.score_lead);
      } else {
        // Interpolate or use default
        winrates.push(50);
        scores.push(0);
      }
    }

    return { moves, winrates, scores };
  }, [analysis, totalMoves]);

  // SVG chart with Y-axis labels (XingZhen style)
  const renderChart = (data: number[], min: number, max: number, color: string, yLabels: string[]) => {
    if (data.length === 0) return null;

    const width = 340;
    const height = 120;
    const leftPadding = 35; // Space for Y-axis labels
    const rightPadding = 10;
    const topPadding = 10;
    const bottomPadding = 10;
    const chartWidth = width - leftPadding - rightPadding;
    const chartHeight = height - topPadding - bottomPadding;

    const range = max - min;
    const xStep = chartWidth / Math.max(1, data.length - 1);

    const points = data.map((value, i) => {
      const x = leftPadding + i * xStep;
      const y = topPadding + chartHeight - ((value - min) / range) * chartHeight;
      return `${x},${y}`;
    }).join(' ');

    // Current move indicator
    const currentX = leftPadding + currentMove * xStep;

    // Y-axis positions (0%, 50%, 100% for 3 labels)
    const yAxisPositions = yLabels.map((_, i) => {
      return topPadding + chartHeight - (i / (yLabels.length - 1)) * chartHeight;
    });

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {/* Y-axis labels and grid lines */}
        {yLabels.map((label, i) => (
          <g key={i}>
            {/* Grid line */}
            <line
              x1={leftPadding}
              y1={yAxisPositions[i]}
              x2={width - rightPadding}
              y2={yAxisPositions[i]}
              stroke="rgba(255,255,255,0.15)"
              strokeDasharray={i === 1 ? "4" : "0"} // Dashed line for middle (50%)
            />
            {/* Label */}
            <text
              x={leftPadding - 5}
              y={yAxisPositions[i]}
              textAnchor="end"
              dominantBaseline="middle"
              fill="rgba(255,255,255,0.6)"
              fontSize="10"
            >
              {label}
            </text>
          </g>
        ))}

        {/* Chart line */}
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          points={points}
        />

        {/* Current move indicator */}
        <line
          x1={currentX}
          y1={topPadding}
          x2={currentX}
          y2={height - bottomPadding}
          stroke="rgba(255,255,255,0.5)"
          strokeWidth="1"
        />

        {/* Click area */}
        <rect
          x={leftPadding}
          y={0}
          width={chartWidth}
          height={height}
          fill="transparent"
          style={{ cursor: 'pointer' }}
          onClick={(e) => {
            if (!onMoveClick) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const svgX = (x / rect.width) * width; // Convert to SVG coordinates
            const ratio = (svgX - leftPadding) / chartWidth;
            const move = Math.round(ratio * totalMoves);
            onMoveClick(Math.max(0, Math.min(totalMoves, move)));
          }}
        />
      </svg>
    );
  };

  // Get brilliant and mistake moves
  const brilliantMoves = useMemo(() => {
    return Object.entries(analysis)
      .filter(([_, a]) => a.is_brilliant)
      .map(([move, a]) => ({ move: parseInt(move), analysis: a }));
  }, [analysis]);

  const mistakeMoves = useMemo(() => {
    return Object.entries(analysis)
      .filter(([_, a]) => a.is_mistake || a.is_questionable)
      .map(([move, a]) => ({ move: parseInt(move), analysis: a }));
  }, [analysis]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Sticky tabs header */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          minHeight: 36,
          flexShrink: 0,
          bgcolor: 'background.paper',
        }}
      >
        <Tab label="走势图" sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`妙手 (${brilliantMoves.length})`} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`问题手 (${mistakeMoves.length})`} sx={{ minHeight: 36, py: 0 }} />
      </Tabs>

      {/* Scrollable content area */}
      <Box sx={{ p: 2, flex: 1, overflow: 'auto' }}>
        {tab === 0 && (
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              胜率走势
            </Typography>
            <Box sx={{ bgcolor: 'background.default', borderRadius: 1, p: 1 }}>
              {renderChart(chartData.winrates, 0, 100, '#4caf50', ['0%', '50%', '100%'])}
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5, pl: '35px', pr: '10px' }}>
              <Typography variant="caption" color="text.secondary">0</Typography>
              <Typography variant="caption" color="text.secondary">{totalMoves}手</Typography>
            </Box>
          </Box>
        )}

        {tab === 1 && (
          <Box>
            {brilliantMoves.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                暂无妙手
              </Typography>
            ) : (
              brilliantMoves.map(({ move, analysis: a }) => (
                <Box
                  key={move}
                  sx={{
                    p: 1.5,
                    mb: 1,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' },
                    borderLeft: 3,
                    borderColor: 'success.main',
                  }}
                  onClick={() => onMoveClick?.(move)}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" fontWeight="bold">
                      第 {move} 手 {a.move}
                    </Typography>
                    <Typography variant="caption" color="success.main">
                      +{a.delta_score.toFixed(1)} 目
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {a.player === 'B' ? '黑' : '白'}方妙手
                  </Typography>
                </Box>
              ))
            )}
          </Box>
        )}

        {tab === 2 && (
          <Box>
            {mistakeMoves.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                暂无问题手
              </Typography>
            ) : (
              mistakeMoves.map(({ move, analysis: a }) => (
                <Box
                  key={move}
                  sx={{
                    p: 1.5,
                    mb: 1,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' },
                    borderLeft: 3,
                    borderColor: a.is_mistake ? 'error.main' : 'warning.main',
                  }}
                  onClick={() => onMoveClick?.(move)}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2" fontWeight="bold">
                      第 {move} 手 {a.move}
                    </Typography>
                    <Typography variant="caption" color={a.is_mistake ? 'error.main' : 'warning.main'}>
                      {a.delta_score.toFixed(1)} 目
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {a.player === 'B' ? '黑' : '白'}方{a.is_mistake ? '问题手' : '疑问手'}
                  </Typography>
                </Box>
              ))
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
