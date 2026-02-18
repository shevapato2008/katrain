import { Box, Typography, Tabs, Tab } from '@mui/material';
import { useState, useMemo } from 'react';
import type { MoveAnalysis } from '../../../types/live';
import { useTranslation } from '../../../hooks/useTranslation';

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
  const { t } = useTranslation();
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

  // Calculate score range for Y-axis
  const scoreRange = useMemo(() => {
    const scores = chartData.scores.filter(s => s !== 0);
    if (scores.length === 0) return { min: -30, max: 30 };
    const maxAbs = Math.max(Math.abs(Math.min(...scores)), Math.abs(Math.max(...scores)));
    const range = Math.ceil(maxAbs / 10) * 10 || 30;
    return { min: -range, max: range };
  }, [chartData.scores]);

  // Get current values for display above chart
  const currentWinrate = useMemo(() => {
    const moveAnalysis = analysis[currentMove];
    return moveAnalysis ? moveAnalysis.winrate * 100 : 50;
  }, [analysis, currentMove]);

  const currentScoreLead = useMemo(() => {
    const moveAnalysis = analysis[currentMove];
    return moveAnalysis ? moveAnalysis.score_lead : 0;
  }, [analysis, currentMove]);

  // Dual-axis chart with winrate and score lead
  const renderDualChart = () => {
    if (chartData.winrates.length === 0) return null;

    const width = 420;
    const height = 180;
    const leftPadding = 42;
    const rightPadding = 42;
    const topPadding = 16;
    const bottomPadding = 12;
    const chartWidth = width - leftPadding - rightPadding;
    const chartHeight = height - topPadding - bottomPadding;

    const xStep = chartWidth / Math.max(1, chartData.winrates.length - 1);

    // Winrate points (0-100 -> chart coordinates)
    const winratePoints = chartData.winrates.map((value, i) => {
      const x = leftPadding + i * xStep;
      const y = topPadding + chartHeight - (value / 100) * chartHeight;
      return `${x},${y}`;
    }).join(' ');

    // Score points (scoreRange.min to scoreRange.max -> chart coordinates)
    const scorePoints = chartData.scores.map((value, i) => {
      const x = leftPadding + i * xStep;
      const normalized = (value - scoreRange.min) / (scoreRange.max - scoreRange.min);
      const y = topPadding + chartHeight - normalized * chartHeight;
      return `${x},${y}`;
    }).join(' ');

    // Current move indicator
    const currentX = leftPadding + currentMove * xStep;

    // Y-axis labels
    const winrateLabels = ['0%', '50%', '100%'];
    const scoreLabels = [`${scoreRange.min}`, '0', `+${scoreRange.max}`];

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
        {/* Grid lines and left Y-axis labels (winrate) */}
        {winrateLabels.map((label, i) => {
          const y = topPadding + chartHeight - (i / 2) * chartHeight;
          return (
            <g key={`wr-${i}`}>
              <line
                x1={leftPadding}
                y1={y}
                x2={width - rightPadding}
                y2={y}
                stroke="rgba(255,255,255,0.1)"
                strokeDasharray={i === 1 ? "4" : "0"}
              />
              <text
                x={leftPadding - 6}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                fill="rgba(76, 175, 80, 0.8)"
                fontSize="13"
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* Right Y-axis labels (score) */}
        {scoreLabels.map((label, i) => {
          const y = topPadding + chartHeight - (i / 2) * chartHeight;
          return (
            <text
              key={`sc-${i}`}
              x={width - rightPadding + 6}
              y={y}
              textAnchor="start"
              dominantBaseline="middle"
              fill="rgba(255, 152, 0, 0.8)"
              fontSize="13"
            >
              {label}
            </text>
          );
        })}

        {/* Score line (orange) */}
        <polyline
          fill="none"
          stroke="#ff9800"
          strokeWidth="1.5"
          strokeOpacity="0.8"
          points={scorePoints}
        />

        {/* Winrate line (green) */}
        <polyline
          fill="none"
          stroke="#4caf50"
          strokeWidth="2"
          points={winratePoints}
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
            const svgX = (x / rect.width) * width;
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
        <Tab label={t('live:trend_chart', 'Trend')} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`${t('live:brilliant', 'Brilliant')} (${brilliantMoves.length})`} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`${t('live:mistakes', 'Mistakes')} (${mistakeMoves.length})`} sx={{ minHeight: 36, py: 0 }} />
      </Tabs>

      {/* Scrollable content area */}
      <Box sx={{ px: 1.5, py: 1, flex: 1, overflow: 'auto' }}>
        {tab === 0 && (
          <Box>
            {/* Values display above chart */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, px: 0.5 }}>
              <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>
                {t('live:black_winrate', 'Black Winrate')}: {currentWinrate.toFixed(1)}%
              </Typography>
              <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 600 }}>
                {t('live:black_lead', 'Black Lead')}: {currentScoreLead >= 0 ? '+' : ''}{currentScoreLead.toFixed(1)} {t('live:points_unit', 'pts')}
              </Typography>
            </Box>
            <Box sx={{ bgcolor: 'background.default', borderRadius: 1, p: 0.5 }}>
              {renderDualChart()}
            </Box>
          </Box>
        )}

        {tab === 1 && (
          <Box>
            {brilliantMoves.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('live:no_brilliant', 'No brilliant moves')}
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
                      {t('live:move_number', 'Move')} {move} {a.move}
                    </Typography>
                    <Typography variant="caption" color="success.main">
                      +{a.delta_score.toFixed(1)} {t('live:points', 'pts')}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {a.player === 'B' ? t('live:black', 'B') : t('live:white', 'W')} {t('live:brilliant_move', 'brilliant move')}
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
                {t('live:no_mistakes', 'No mistakes')}
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
                      {t('live:move_number', 'Move')} {move} {a.move}
                    </Typography>
                    <Typography variant="caption" color={a.is_mistake ? 'error.main' : 'warning.main'}>
                      {a.delta_score.toFixed(1)} {t('live:points', 'pts')}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    {a.player === 'B' ? t('live:black', 'B') : t('live:white', 'W')} {a.is_mistake ? t('live:mistake', 'mistake') : t('live:questionable', 'questionable')}
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
