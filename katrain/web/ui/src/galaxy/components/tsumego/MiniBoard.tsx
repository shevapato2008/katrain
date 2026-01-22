import { useMemo } from 'react';
import { Box } from '@mui/material';

interface MiniBoardProps {
  size?: number;  // Canvas size in pixels
  boardSize?: number;  // Go board size (9, 13, 19)
  blackStones: string[];  // SGF coords like ["pa", "rd"]
  whiteStones: string[];
}

const SGF_COORD = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

// Convert SGF coordinate to [x, y]
function sgfToCoord(sgf: string, boardSize: number): [number, number] {
  const x = SGF_COORD.indexOf(sgf[0]);
  const y = boardSize - 1 - SGF_COORD.indexOf(sgf[1]);
  return [x, y];
}

// Find bounding box of stones with padding
function getBoundingBox(blacks: string[], whites: string[], boardSize: number, padding: number = 2) {
  const allCoords = [...blacks, ...whites].map(s => sgfToCoord(s, boardSize));
  if (allCoords.length === 0) {
    return { minX: 0, maxX: boardSize - 1, minY: 0, maxY: boardSize - 1 };
  }

  let minX = Math.min(...allCoords.map(c => c[0]));
  let maxX = Math.max(...allCoords.map(c => c[0]));
  let minY = Math.min(...allCoords.map(c => c[1]));
  let maxY = Math.max(...allCoords.map(c => c[1]));

  // Add padding
  minX = Math.max(0, minX - padding);
  maxX = Math.min(boardSize - 1, maxX + padding);
  minY = Math.max(0, minY - padding);
  maxY = Math.min(boardSize - 1, maxY + padding);

  return { minX, maxX, minY, maxY };
}

const MiniBoard = ({ size = 100, boardSize = 19, blackStones, whiteStones }: MiniBoardProps) => {
  const { minX, maxX, minY, maxY } = useMemo(
    () => getBoundingBox(blackStones, whiteStones, boardSize),
    [blackStones, whiteStones, boardSize]
  );

  const visibleWidth = maxX - minX + 1;
  const visibleHeight = maxY - minY + 1;
  const cellSize = size / Math.max(visibleWidth, visibleHeight);
  const stoneRadius = cellSize * 0.45;

  const blackCoords = useMemo(
    () => blackStones.map(s => sgfToCoord(s, boardSize)),
    [blackStones, boardSize]
  );
  const whiteCoords = useMemo(
    () => whiteStones.map(s => sgfToCoord(s, boardSize)),
    [whiteStones, boardSize]
  );

  return (
    <Box
      sx={{
        width: size,
        height: size,
        bgcolor: '#DEB887',
        borderRadius: 1,
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      <svg width={size} height={size}>
        {/* Grid lines */}
        {Array.from({ length: visibleWidth }).map((_, i) => (
          <line
            key={`v${i}`}
            x1={(i + 0.5) * cellSize}
            y1={cellSize * 0.5}
            x2={(i + 0.5) * cellSize}
            y2={size - cellSize * 0.5}
            stroke="#8B7355"
            strokeWidth={0.5}
          />
        ))}
        {Array.from({ length: visibleHeight }).map((_, i) => (
          <line
            key={`h${i}`}
            x1={cellSize * 0.5}
            y1={(i + 0.5) * cellSize}
            x2={size - cellSize * 0.5}
            y2={(i + 0.5) * cellSize}
            stroke="#8B7355"
            strokeWidth={0.5}
          />
        ))}

        {/* Black stones */}
        {blackCoords.map(([x, y], i) => (
          <circle
            key={`b${i}`}
            cx={(x - minX + 0.5) * cellSize}
            cy={(maxY - y + 0.5) * cellSize}
            r={stoneRadius}
            fill="#1a1a1a"
          />
        ))}

        {/* White stones */}
        {whiteCoords.map(([x, y], i) => (
          <circle
            key={`w${i}`}
            cx={(x - minX + 0.5) * cellSize}
            cy={(maxY - y + 0.5) * cellSize}
            r={stoneRadius}
            fill="#f5f5f5"
            stroke="#333"
            strokeWidth={0.5}
          />
        ))}
      </svg>
    </Box>
  );
};

export default MiniBoard;
