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
// x: 0 (left) to boardSize-1 (right)
// y: 0 (bottom) to boardSize-1 (top) - inverted from SGF
function sgfToCoord(sgf: string, boardSize: number): [number, number] {
  const x = SGF_COORD.indexOf(sgf[0]);
  const y = boardSize - 1 - SGF_COORD.indexOf(sgf[1]);
  return [x, y];
}

// Get star point (hoshi) coordinates for a given board size
function getStarPoints(boardSize: number): [number, number][] {
  if (boardSize === 19) {
    // 19x19: 9 star points at 4th line (index 3), 10th line (index 9), 16th line (index 15)
    return [
      [3, 3], [3, 9], [3, 15],   // left column
      [9, 3], [9, 9], [9, 15],   // center column
      [15, 3], [15, 9], [15, 15] // right column
    ];
  } else if (boardSize === 13) {
    // 13x13: 5 star points at 4th line (index 3), 7th line (index 6), 10th line (index 9)
    return [
      [3, 3], [3, 9],
      [6, 6],
      [9, 3], [9, 9]
    ];
  } else if (boardSize === 9) {
    // 9x9: 5 star points at 3rd line (index 2), 5th line (index 4), 7th line (index 6)
    return [
      [2, 2], [2, 6],
      [4, 4],
      [6, 2], [6, 6]
    ];
  }
  return [];
}

// Determine which view region to show based on stone positions
// Returns the bounds of the region to display
function getViewRegion(blacks: string[], whites: string[], boardSize: number): { minX: number; maxX: number; minY: number; maxY: number } {
  const allCoords = [...blacks, ...whites].map(s => sgfToCoord(s, boardSize));

  if (allCoords.length === 0) {
    // No stones, show top-left quarter by default
    const halfSize = Math.ceil(boardSize / 2);
    return { minX: 0, maxX: halfSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 };
  }

  const xs = allCoords.map(c => c[0]);
  const ys = allCoords.map(c => c[1]);
  const stoneMinX = Math.min(...xs);
  const stoneMaxX = Math.max(...xs);
  const stoneMinY = Math.min(...ys);
  const stoneMaxY = Math.max(...ys);

  // Define quarter boundaries (for 19x19, each quarter is roughly 10x10)
  const halfSize = Math.ceil(boardSize / 2);  // 10 for 19x19

  // Define the four quarters with their bounds
  // After sgfToCoord: high y = top, low y = bottom
  const quarters = [
    {
      // Top-left: small x, high y
      fits: stoneMaxX <= halfSize - 1 && stoneMinY >= boardSize - halfSize,
      region: { minX: 0, maxX: halfSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 }
    },
    {
      // Top-right: large x, high y
      fits: stoneMinX >= boardSize - halfSize && stoneMinY >= boardSize - halfSize,
      region: { minX: boardSize - halfSize, maxX: boardSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 }
    },
    {
      // Bottom-left: small x, low y
      fits: stoneMaxX <= halfSize - 1 && stoneMaxY <= halfSize - 1,
      region: { minX: 0, maxX: halfSize - 1, minY: 0, maxY: halfSize - 1 }
    },
    {
      // Bottom-right: large x, low y
      fits: stoneMinX >= boardSize - halfSize && stoneMaxY <= halfSize - 1,
      region: { minX: boardSize - halfSize, maxX: boardSize - 1, minY: 0, maxY: halfSize - 1 }
    }
  ];

  // Find a quarter that contains all stones
  for (const quarter of quarters) {
    if (quarter.fits) {
      return quarter.region;
    }
  }

  // Stones don't fit in any quarter, show full board
  return { minX: 0, maxX: boardSize - 1, minY: 0, maxY: boardSize - 1 };
}

const MiniBoard = ({ size = 100, boardSize = 19, blackStones, whiteStones }: MiniBoardProps) => {
  const { minX, maxX, minY, maxY } = useMemo(
    () => getViewRegion(blackStones, whiteStones, boardSize),
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

  // Get star points that are visible in the current view region
  const visibleStarPoints = useMemo(() => {
    const allStarPoints = getStarPoints(boardSize);
    return allStarPoints.filter(([x, y]) =>
      x >= minX && x <= maxX && y >= minY && y <= maxY
    );
  }, [boardSize, minX, maxX, minY, maxY]);

  const starPointRadius = cellSize * 0.12;

  // Determine which edges are actual board edges vs. "cut" edges
  const isLeftEdge = minX === 0;
  const isRightEdge = maxX === boardSize - 1;
  const isTopEdge = maxY === boardSize - 1;
  const isBottomEdge = minY === 0;

  // Extension amount for lines on non-edge sides (to hint board continues)
  const lineExtension = cellSize * 0.35;

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
        {/* Vertical grid lines */}
        {Array.from({ length: visibleWidth }).map((_, i) => (
          <line
            key={`v${i}`}
            x1={(i + 0.5) * cellSize}
            y1={isTopEdge ? cellSize * 0.5 : -lineExtension}
            x2={(i + 0.5) * cellSize}
            y2={isBottomEdge ? (visibleHeight - 0.5) * cellSize : size + lineExtension}
            stroke="#8B7355"
            strokeWidth={0.5}
          />
        ))}
        {/* Horizontal grid lines */}
        {Array.from({ length: visibleHeight }).map((_, i) => (
          <line
            key={`h${i}`}
            x1={isLeftEdge ? cellSize * 0.5 : -lineExtension}
            y1={(i + 0.5) * cellSize}
            x2={isRightEdge ? (visibleWidth - 0.5) * cellSize : size + lineExtension}
            y2={(i + 0.5) * cellSize}
            stroke="#8B7355"
            strokeWidth={0.5}
          />
        ))}

        {/* Star points (hoshi) */}
        {visibleStarPoints.map(([x, y], i) => (
          <circle
            key={`star${i}`}
            cx={(x - minX + 0.5) * cellSize}
            cy={(maxY - y + 0.5) * cellSize}
            r={starPointRadius}
            fill="#5D4E37"
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
