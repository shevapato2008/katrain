import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface ScoreGraphProps {
  gameState: GameState | null;
  onNavigate: (nodeId: number) => void;
  showScore?: boolean;
  showWinrate?: boolean;
}

const ScoreGraph: React.FC<ScoreGraphProps> = ({ gameState, onNavigate, showScore = true, showWinrate = true }) => {
  const { t } = useTranslation();
  const history = gameState?.history || [];
  const currentIndex = gameState?.current_node_index ?? -1;

  // Get current winrate and score for display
  const currentWinrate = useMemo(() => {
    if (currentIndex >= 0 && currentIndex < history.length && history[currentIndex].winrate !== null) {
      return (history[currentIndex].winrate! * 100).toFixed(1);
    }
    return '--';
  }, [history, currentIndex]);

  const currentScore = useMemo(() => {
    if (currentIndex >= 0 && currentIndex < history.length && history[currentIndex].score !== null) {
      const score = history[currentIndex].score!;
      return score >= 0 ? `+${score.toFixed(1)}` : score.toFixed(1);
    }
    return '--';
  }, [history, currentIndex]);

  // Chart dimensions - larger for better visibility
  const width = 420;
  const height = 180;
  const leftPadding = 42;
  const rightPadding = 42;
  const topPadding = 16;
  const bottomPadding = 12;
  const chartWidth = width - leftPadding - rightPadding;
  const chartHeight = height - topPadding - bottomPadding;

  const { scorePoints, winratePoints, scoreScale, xStep } = useMemo(() => {
    if (history.length === 0) return { scorePoints: '', winratePoints: '', scoreScale: 30, xStep: 0 };

    const scores = history.map(h => h.score).filter((s): s is number => s !== null);

    const maxScore = Math.max(5, ...scores.map(Math.abs));
    const scoreScale = Math.ceil(maxScore / 10) * 10 || 30;

    const xStep = chartWidth / Math.max(history.length - 1, 15);

    // Score points (centered around 0, scaled to scoreScale)
    const scorePts = history.map((h, i) => {
      if (h.score === null) return null;
      const x = leftPadding + i * xStep;
      // Map score to chart: 0 at center, positive up, negative down
      const normalized = (h.score - (-scoreScale)) / (scoreScale - (-scoreScale));
      const y = topPadding + chartHeight - normalized * chartHeight;
      return `${x},${y}`;
    }).filter(p => p !== null).join(' ');

    // Winrate points (0-1 mapped to 0-100%)
    const winratePts = history.map((h, i) => {
      if (h.winrate === null) return null;
      const x = leftPadding + i * xStep;
      // Map winrate (0-1) to chart (0% at bottom, 100% at top)
      const y = topPadding + chartHeight - h.winrate * chartHeight;
      return `${x},${y}`;
    }).filter(p => p !== null).join(' ');

    return { scorePoints: scorePts, winratePoints: winratePts, scoreScale, xStep };
  }, [history, chartWidth, chartHeight, leftPadding, topPadding]);

  if (history.length === 0) return null;

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const svgX = (clickX / rect.width) * width;
    const ratio = (svgX - leftPadding) / chartWidth;
    const index = Math.round(ratio * (history.length - 1));
    if (index >= 0 && index < history.length) {
      onNavigate(history[index].node_id);
    }
  };

  // Y-axis labels
  const winrateLabels = ['0%', '50%', '100%'];
  const scoreLabels = [`${-scoreScale}`, '0', `+${scoreScale}`];

  return (
    <Box sx={{ width: '100%' }}>
      {/* Values display above chart */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, px: 0.5 }}>
        <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>
          {t('live:black_winrate', 'Black Winrate')}: {currentWinrate}%
        </Typography>
        <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 600 }}>
          {t('live:black_lead', 'Black Lead')}: {currentScore} {t('live:points_unit', 'pts')}
        </Typography>
      </Box>
      <Box sx={{ bgcolor: 'background.default', borderRadius: 1, p: 0.5 }}>
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ cursor: 'pointer', display: 'block' }}
          onClick={handleSvgClick}
        >
          {/* Grid lines and left Y-axis labels (winrate) */}
          {showWinrate && winrateLabels.map((label, i) => {
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
          {showScore && scoreLabels.map((label, i) => {
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
          {showScore && scorePoints && (
            <polyline
              fill="none"
              stroke="#ff9800"
              strokeWidth="1.5"
              strokeOpacity="0.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={scorePoints}
            />
          )}

          {/* Winrate line (green) */}
          {showWinrate && winratePoints && (
            <polyline
              fill="none"
              stroke="#4caf50"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={winratePoints}
            />
          )}

          {/* Current move indicator */}
          {currentIndex !== -1 && (
            <line
              x1={leftPadding + currentIndex * xStep}
              y1={topPadding}
              x2={leftPadding + currentIndex * xStep}
              y2={height - bottomPadding}
              stroke="rgba(255,255,255,0.5)"
              strokeWidth="1"
            />
          )}
        </svg>
      </Box>
    </Box>
  );
};

export default ScoreGraph;
