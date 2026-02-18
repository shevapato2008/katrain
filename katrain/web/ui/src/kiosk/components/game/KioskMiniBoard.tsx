import { useMemo } from 'react';
import { Box } from '@mui/material';

interface KioskMiniBoardProps {
  size?: number;
  boardSize?: number;
  blackStones: string[];
  whiteStones: string[];
}

const SGF_COORD = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

function sgfToCoord(sgf: string, boardSize: number): [number, number] {
  const x = SGF_COORD.indexOf(sgf[0]);
  const y = boardSize - 1 - SGF_COORD.indexOf(sgf[1]);
  return [x, y];
}

function getStarPoints(boardSize: number): [number, number][] {
  if (boardSize === 19) {
    return [
      [3, 3], [3, 9], [3, 15],
      [9, 3], [9, 9], [9, 15],
      [15, 3], [15, 9], [15, 15],
    ];
  } else if (boardSize === 13) {
    return [[3, 3], [3, 9], [6, 6], [9, 3], [9, 9]];
  } else if (boardSize === 9) {
    return [[2, 2], [2, 6], [4, 4], [6, 2], [6, 6]];
  }
  return [];
}

function getViewRegion(blacks: string[], whites: string[], boardSize: number) {
  const allCoords = [...blacks, ...whites].map(s => sgfToCoord(s, boardSize));

  if (allCoords.length === 0) {
    const halfSize = Math.ceil(boardSize / 2);
    return { minX: 0, maxX: halfSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 };
  }

  const xs = allCoords.map(c => c[0]);
  const ys = allCoords.map(c => c[1]);
  const stoneMinX = Math.min(...xs);
  const stoneMaxX = Math.max(...xs);
  const stoneMinY = Math.min(...ys);
  const stoneMaxY = Math.max(...ys);

  const halfSize = Math.ceil(boardSize / 2);

  const quarters = [
    { fits: stoneMaxX <= halfSize - 1 && stoneMinY >= boardSize - halfSize,
      region: { minX: 0, maxX: halfSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 } },
    { fits: stoneMinX >= boardSize - halfSize && stoneMinY >= boardSize - halfSize,
      region: { minX: boardSize - halfSize, maxX: boardSize - 1, minY: boardSize - halfSize, maxY: boardSize - 1 } },
    { fits: stoneMaxX <= halfSize - 1 && stoneMaxY <= halfSize - 1,
      region: { minX: 0, maxX: halfSize - 1, minY: 0, maxY: halfSize - 1 } },
    { fits: stoneMinX >= boardSize - halfSize && stoneMaxY <= halfSize - 1,
      region: { minX: boardSize - halfSize, maxX: boardSize - 1, minY: 0, maxY: halfSize - 1 } },
  ];

  for (const quarter of quarters) {
    if (quarter.fits) return quarter.region;
  }

  return { minX: 0, maxX: boardSize - 1, minY: 0, maxY: boardSize - 1 };
}

const KioskMiniBoard = ({ size = 100, boardSize = 19, blackStones, whiteStones }: KioskMiniBoardProps) => {
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

  const visibleStarPoints = useMemo(() => {
    return getStarPoints(boardSize).filter(([x, y]) =>
      x >= minX && x <= maxX && y >= minY && y <= maxY
    );
  }, [boardSize, minX, maxX, minY, maxY]);

  const starPointRadius = cellSize * 0.12;

  const isLeftEdge = minX === 0;
  const isRightEdge = maxX === boardSize - 1;
  const isTopEdge = maxY === boardSize - 1;
  const isBottomEdge = minY === 0;
  const lineExtension = cellSize * 0.35;

  return (
    <Box
      data-testid="mini-board"
      sx={{
        width: size,
        height: size,
        bgcolor: '#DEB887',
        borderRadius: 1,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <svg width={size} height={size}>
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
        {visibleStarPoints.map(([x, y], i) => (
          <circle
            key={`star${i}`}
            cx={(x - minX + 0.5) * cellSize}
            cy={(maxY - y + 0.5) * cellSize}
            r={starPointRadius}
            fill="#5D4E37"
          />
        ))}
        {blackCoords.map(([x, y], i) => (
          <circle
            key={`b${i}`}
            cx={(x - minX + 0.5) * cellSize}
            cy={(maxY - y + 0.5) * cellSize}
            r={stoneRadius}
            fill="#1a1a1a"
          />
        ))}
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

export default KioskMiniBoard;
