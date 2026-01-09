import React, { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { type GameState } from '../api';

interface ScoreGraphProps {
  gameState: GameState | null;
  onNavigate: (nodeId: number) => void;
  showScore?: boolean;
  showWinrate?: boolean;
}

const ScoreGraph: React.FC<ScoreGraphProps> = ({ gameState, onNavigate, showScore = true, showWinrate = true }) => {
  const history = gameState?.history || [];
  const currentIndex = gameState?.current_node_index ?? -1;

  const { scorePoints, winratePoints, scoreScale, winrateScale, xStep } = useMemo(() => {
    if (history.length === 0) return { scorePoints: '', winratePoints: '', scoreScale: 10, winrateScale: 10, xStep: 0 };

    const scores = history.map(h => h.score).filter((s): s is number => s !== null);
    const winrates = history.map(h => h.winrate).filter((w): w is number => w !== null);

    const maxScore = Math.max(5, ...scores.map(Math.abs));
    const scoreScale = Math.ceil(maxScore / 5) * 5;

    const maxWinrateDiff = Math.max(10, ...winrates.map(w => Math.abs(w - 0.5) * 100));
    const winrateScale = Math.ceil(maxWinrateDiff / 10) * 10;

    const width = 300; // Fixed width for now
    const height = 150;
    const xStep = width / Math.max(history.length - 1, 15);

    const scorePts = history.map((h, i) => {
      if (h.score === null) return null;
      const x = i * xStep;
      const y = height / 2 - (height / 2) * (h.score / scoreScale);
      return `${x},${y}`;
    }).filter(p => p !== null).join(' ');

    const winratePts = history.map((h, i) => {
      if (h.winrate === null) return null;
      const x = i * xStep;
      // mapped to -winrateScale to +winrateScale
      // Wait, winrate in backend is 0 to 1. 
      // Kivy: val = (n.winrate - 0.5) * 100. scale is like 10, 20...
      // y = height/2 + (height/2) * (val / winrate_scale)
      // If winrate is 1.0 (B wins), val = 50. If scale is 50, y = height/2 + height/2 = height (bottom in SVG is high Y)
      // In SVG, y=0 is top. So B wins should be top.
      const val = (h.winrate - 0.5) * 100;
      const svgY = height / 2 - (height / 2) * (val / winrateScale);
      return `${x},${svgY}`;
    }).filter(p => p !== null).join(' ');

    return { scorePoints: scorePts, winratePoints: winratePts, scoreScale, winrateScale, xStep };
  }, [history]);

  if (history.length === 0) return null;

  const width = 300;
  const height = 150;

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const index = Math.round(x / xStep);
    if (index >= 0 && index < history.length) {
      onNavigate(history[index].node_id);
    }
  };

  return (
    <Box sx={{ width: '100%', mt: 1, bgcolor: '#2a2a2a', borderRadius: 1, p: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1, mb: 1 }}>
        {showScore ? (
          <Typography
            variant="caption"
            sx={{
              color: '#7a9cc6',
              fontSize: '0.7rem',
              fontWeight: 500,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.5px'
            }}
          >
            Score: {scoreScale}
          </Typography>
        ) : <Box />}
        {showWinrate ? (
          <Typography
            variant="caption"
            sx={{
              color: '#5d8270',
              fontSize: '0.7rem',
              fontWeight: 500,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.5px'
            }}
          >
            Winrate: {50+winrateScale}%
          </Typography>
        ) : <Box />}
      </Box>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{
          backgroundColor: '#1a1a1a',
          cursor: 'pointer',
          display: 'block',
          borderRadius: '4px',
          border: '1px solid rgba(255, 255, 255, 0.05)'
        }}
        onClick={handleSvgClick}
      >
        {/* Grid lines - horizontal center and quarters */}
        <line x1="0" y1={height/2} x2={width} y2={height/2} stroke="rgba(255, 255, 255, 0.1)" strokeWidth="1" />
        <line x1="0" y1={height/4} x2={width} y2={height/4} stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" strokeDasharray="3,3" />
        <line x1="0" y1={3*height/4} x2={width} y2={3*height/4} stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" strokeDasharray="3,3" />

        {/* Score line */}
        {showScore && scorePoints && (
          <polyline
            fill="none"
            stroke="#7a9cc6"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={scorePoints}
            style={{ filter: 'drop-shadow(0 0 2px rgba(122, 156, 198, 0.3))' }}
          />
        )}

        {/* Winrate line */}
        {showWinrate && winratePoints && (
          <polyline
            fill="none"
            stroke="#5d8270"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={winratePoints}
            style={{ filter: 'drop-shadow(0 0 3px rgba(93, 130, 112, 0.4))' }}
          />
        )}

        {/* Current move marker */}
        {currentIndex !== -1 && (
          <>
            <line
              x1={currentIndex * xStep} y1="0"
              x2={currentIndex * xStep} y2={height}
              stroke="#4a6b5c"
              strokeWidth="2"
              opacity="0.8"
            />
            <circle
              cx={currentIndex * xStep}
              cy={height/2}
              r="4"
              fill="#4a6b5c"
              stroke="#f5f3f0"
              strokeWidth="1.5"
              style={{ filter: 'drop-shadow(0 0 4px rgba(74, 107, 92, 0.6))' }}
            />
          </>
        )}
      </svg>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1, mt: 1 }}>
        {showScore ? (
          <Typography
            variant="caption"
            sx={{
              color: '#7a9cc6',
              fontSize: '0.7rem',
              fontWeight: 500,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.5px'
            }}
          >
            Score: -{scoreScale}
          </Typography>
        ) : <Box />}
        {showWinrate ? (
          <Typography
            variant="caption"
            sx={{
              color: '#5d8270',
              fontSize: '0.7rem',
              fontWeight: 500,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.5px'
            }}
          >
            Winrate: {50-winrateScale}%
          </Typography>
        ) : <Box />}
      </Box>
    </Box>
  );
};

export default ScoreGraph;
