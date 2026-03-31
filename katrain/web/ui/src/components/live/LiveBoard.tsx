import { useEffect, useRef, useState } from 'react';
import { Box } from '@mui/material';
import {
  BOARD_ASSETS,
  calculateBoardLayout,
  canvasToGrid,
  gridToCanvas,
  drawBoardBackground,
  drawGrid,
  drawStars,
  drawCoordinates,
  drawStone,
  drawLastMoveMarker,
} from '../board/boardUtils';

// AI move marker for display on board
export interface AiMoveMarker {
  move: string;
  rank: number; // 1 = best, 2 = second best, etc.
  visits: number;
  winrate: number;
  score_lead: number;
}

interface LiveBoardProps {
  moves: string[]; // Array of moves in display format (e.g., "Q16", "D4")
  stoneColors?: ('B' | 'W')[]; // Parallel array of stone colors; if absent, alternates B/W
  currentMove: number; // Which move to display up to
  boardSize?: number; // 9, 13, or 19
  showCoordinates?: boolean;
  onIntersectionClick?: (x: number, y: number) => void;
  nextColor?: 'B' | 'W'; // Color of the next stone to place (for hover preview)
  pvMoves?: string[] | null; // Principal variation moves to display as semi-transparent stones
  aiMarkers?: AiMoveMarker[] | null; // AI recommended moves to mark on board
  showAiMarkers?: boolean; // Whether to display AI markers (default true)
  showMoveNumbers?: boolean; // Whether to display move numbers on stones
  handicapCount?: number; // Number of leading setup stones to skip when numbering
  showTerritory?: boolean; // Whether to display territory/ownership overlay
  ownership?: number[][] | null; // 2D grid of ownership values (-1 to 1, positive=Black)
  tryMoves?: string[]; // Try moves for experimentation mode
  onTryMove?: (move: string) => void; // Callback when user places a try move
}

// Convert display coordinate (e.g., "Q16") to board indices
function parseMove(move: string): [number, number] | null {
  if (!move || move.length < 2) return null;
  if (move.toLowerCase() === 'pass') return null;

  const col = move[0].toUpperCase();
  const row = parseInt(move.slice(1), 10);

  if (isNaN(row)) return null;

  // Column: A=0, B=1, ..., H=7, J=8 (skip I)
  let x = col.charCodeAt(0) - 'A'.charCodeAt(0);
  if (col > 'I') x -= 1;

  // Row: 1=bottom, 19=top → invert for array index
  const y = row - 1; // Now y=0 is bottom (row 1)

  if (x < 0 || x >= 19 || y < 0 || y >= 19) return null;

  return [x, y];
}

// Get adjacent positions (up, down, left, right)
function getNeighbors(x: number, y: number, size: number): [number, number][] {
  const neighbors: [number, number][] = [];
  if (x > 0) neighbors.push([x - 1, y]);
  if (x < size - 1) neighbors.push([x + 1, y]);
  if (y > 0) neighbors.push([x, y - 1]);
  if (y < size - 1) neighbors.push([x, y + 1]);
  return neighbors;
}

// Find all stones in a connected group starting from (x, y)
function findGroup(
  board: (string | null)[][],
  x: number,
  y: number,
  size: number
): Set<string> {
  const color = board[y][x];
  if (!color) return new Set();

  const group = new Set<string>();
  const stack: [number, number][] = [[x, y]];

  while (stack.length > 0) {
    const [cx, cy] = stack.pop()!;
    const key = `${cx},${cy}`;

    if (group.has(key)) continue;
    if (board[cy][cx] !== color) continue;

    group.add(key);

    for (const [nx, ny] of getNeighbors(cx, cy, size)) {
      if (!group.has(`${nx},${ny}`) && board[ny][nx] === color) {
        stack.push([nx, ny]);
      }
    }
  }

  return group;
}

// Count liberties (empty adjacent points) of a group
function countLiberties(
  board: (string | null)[][],
  group: Set<string>,
  size: number
): number {
  const liberties = new Set<string>();

  for (const key of group) {
    const [x, y] = key.split(',').map(Number);
    for (const [nx, ny] of getNeighbors(x, y, size)) {
      if (board[ny][nx] === null) {
        liberties.add(`${nx},${ny}`);
      }
    }
  }

  return liberties.size;
}

// Remove captured stones (groups with zero liberties)
// Returns array of captured positions for move number clearing
function removeCaptures(
  board: (string | null)[][],
  lastX: number,
  lastY: number,
  size: number
): [number, number][] {
  const captured: [number, number][] = [];
  const lastColor = board[lastY][lastX];
  if (!lastColor) return captured;

  const opponentColor = lastColor === 'B' ? 'W' : 'B';
  const checkedGroups = new Set<string>();

  // Check all neighbors of the last move for opponent groups
  for (const [nx, ny] of getNeighbors(lastX, lastY, size)) {
    if (board[ny][nx] === opponentColor) {
      const groupKey = `${nx},${ny}`;
      if (checkedGroups.has(groupKey)) continue;

      const group = findGroup(board, nx, ny, size);
      for (const key of group) {
        checkedGroups.add(key);
      }

      const liberties = countLiberties(board, group, size);
      if (liberties === 0) {
        // Remove captured stones
        for (const key of group) {
          const [gx, gy] = key.split(',').map(Number);
          board[gy][gx] = null;
          captured.push([gx, gy]);
        }
      }
    }
  }
  return captured;
}

// Jade green color for AI markers (matching play module style)
const AI_MARKER_COLOR = 'rgba(74, 107, 92, 0.85)';

// Draw AI move marker (matching play module style with winrate/visits display)
function drawAiMoveMarker(
  ctx: CanvasRenderingContext2D,
  layout: ReturnType<typeof calculateBoardLayout>,
  x: number,
  y: number,
  boardSize: number,
  rank: number,
  winrate: number,
  visits: number,
  time: number,
) {
  const { x: cx, y: cy } = gridToCanvas(layout, x, y, boardSize);
  const radius = layout.gridSize * 0.42; // Match stone size

  ctx.save();

  // Premium Radial Gradient for the marker (matching play module)
  const grad = ctx.createRadialGradient(cx - radius * 0.3, cy - radius * 0.3, radius * 0.1, cx, cy, radius);
  grad.addColorStop(0, AI_MARKER_COLOR.replace('0.85', '0.95'));
  grad.addColorStop(1, AI_MARKER_COLOR);
  ctx.fillStyle = grad;

  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fill();

  // Best move highlight - Dynamic Pulsing Ring (for rank 1)
  if (rank === 1) {
    const pulse = Math.sin(time * 3) * 0.5 + 0.5; // 0 to 1 pulse

    // Layer 1: Core White Ring
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.8 + pulse * 0.2})`;
    ctx.lineWidth = Math.max(2.5, layout.gridSize * 0.08);
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 1, 0, Math.PI * 2);
    ctx.stroke();

    // Layer 2: Outer Glow
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.2 + pulse * 0.2})`;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 3 + pulse * 2, 0, Math.PI * 2);
    ctx.stroke();

    // Layer 3: Soft Wide Aura
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.05 + pulse * 0.05})`;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 6 + pulse * 4, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Text - Two lines (matching play module style)
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const mainTextColor = 'rgba(255, 255, 255, 0.95)';
  const secondaryTextColor = 'rgba(255, 255, 255, 0.85)';
  const fontSize = Math.max(7, layout.gridSize * 0.28);

  // Top line: Winrate
  ctx.font = `bold ${fontSize}px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = mainTextColor;
  const winrateText = (winrate * 100).toFixed(1);
  ctx.fillText(winrateText, cx, cy - layout.gridSize * 0.12);

  // Bottom line: Visits
  ctx.font = `600 ${fontSize}px 'Manrope', sans-serif`;
  ctx.fillStyle = secondaryTextColor;
  const visitsText = visits >= 1000 ? `${(visits / 1000).toFixed(1)}k` : visits.toString();
  ctx.fillText(visitsText, cx, cy + layout.gridSize * 0.18);

  ctx.restore();
}

// Draw a semi-transparent PV (principal variation) stone with move number
function drawPvStone(
  ctx: CanvasRenderingContext2D,
  layout: ReturnType<typeof calculateBoardLayout>,
  x: number,
  y: number,
  boardSize: number,
  color: 'B' | 'W',
  moveNumber: number,
  blackImg: HTMLImageElement | null,
  whiteImg: HTMLImageElement | null,
) {
  // Use gridToCanvas to get center coordinates (handles Y inversion)
  const { x: cx, y: cy } = gridToCanvas(layout, x, y, boardSize);
  const stoneSize = layout.gridSize * 0.505; // Match actual stone size

  ctx.save();
  ctx.globalAlpha = 0.6; // Semi-transparent

  const img = color === 'B' ? blackImg : whiteImg;
  if (img) {
    // Draw stone image (matching drawStone in boardUtils.ts)
    ctx.drawImage(img, cx - stoneSize, cy - stoneSize, stoneSize * 2, stoneSize * 2);
  } else {
    // Fallback: draw circle
    ctx.beginPath();
    ctx.arc(cx, cy, stoneSize * 0.95, 0, Math.PI * 2);
    ctx.fillStyle = color === 'B' ? '#1a1a1a' : '#f5f5f5';
    ctx.fill();
    ctx.strokeStyle = color === 'B' ? '#000' : '#ccc';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  ctx.globalAlpha = 1.0;

  // Draw move number on the stone
  const textColor = color === 'B' ? '#fff' : '#000';
  const fontSize = Math.max(10, Math.min(14, layout.gridSize * 0.4));
  ctx.font = `bold ${fontSize}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = textColor;
  ctx.fillText(String(moveNumber), cx, cy);

  ctx.restore();
}

export default function LiveBoard({
  moves,
  stoneColors,
  currentMove,
  boardSize = 19,
  showCoordinates = true,
  onIntersectionClick,
  nextColor,
  pvMoves,
  aiMarkers,
  showAiMarkers = true,
  showMoveNumbers = false,
  handicapCount = 0,
  showTerritory = false,
  ownership,
  tryMoves,
  onTryMove,
}: LiveBoardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imagesRef = useRef<Record<string, HTMLImageElement>>({});
  const [canvasSize, setCanvasSize] = useState(600);
  const [imagesLoaded, setImagesLoaded] = useState(false);
  // Animation ref for pulsing effect timing
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);

  // Load images
  useEffect(() => {
    const loadImages = async () => {
      const entries = Object.entries(BOARD_ASSETS);
      await Promise.all(
        entries.map(
          ([key, src]) =>
            new Promise<void>((resolve) => {
              const img = new Image();
              img.onload = () => {
                imagesRef.current[key] = img;
                resolve();
              };
              img.onerror = () => resolve(); // Continue even if image fails
              img.src = src;
            })
        )
      );
      setImagesLoaded(true);
    };
    loadImages();
  }, []);

  // Track container size
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        const size = Math.floor(Math.min(width, height) - 8);
        setCanvasSize(Math.max(400, Math.min(1200, size)));
      }
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    return () => observer.disconnect();
  }, []);

  // Build board state from moves (with capture handling)
  const buildBoardState = () => {
    const board: (string | null)[][] = Array(boardSize)
      .fill(null)
      .map(() => Array(boardSize).fill(null));
    // Track move numbers for each position
    const moveNumbers: (number | null)[][] = Array(boardSize)
      .fill(null)
      .map(() => Array(boardSize).fill(null));

    let lastMove: [number, number] | null = null;
    let lastPlayer: 'B' | 'W' = 'B';

    for (let i = 0; i < Math.min(currentMove, moves.length); i++) {
      const coords = parseMove(moves[i]);
      if (coords) {
        const [x, y] = coords;
        if (x >= 0 && x < boardSize && y >= 0 && y < boardSize) {
          const player = stoneColors?.[i] ?? (i % 2 === 0 ? 'B' : 'W');
          board[y][x] = player;
          // Handicap setup stones (indices 0..handicapCount-1) get no number.
          // Game moves are numbered starting from 1.
          moveNumbers[y][x] = i < handicapCount ? null : (i + 1 - handicapCount);

          // Remove captured opponent stones (also clear their move numbers)
          const capturedPositions = removeCaptures(board, x, y, boardSize);
          for (const pos of capturedPositions) {
            moveNumbers[pos[1]][pos[0]] = null;
          }

          lastMove = coords;
          lastPlayer = player;
        }
      }
    }

    return { board, moveNumbers, lastMove, lastPlayer };
  };

  // Render board function
  const renderBoard = () => {
    const canvas = canvasRef.current;
    if (!canvas || !imagesLoaded) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { board, moveNumbers, lastMove, lastPlayer } = buildBoardState();
    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    const time = (Date.now() - startTimeRef.current) / 1000; // time in seconds for animation

    // Clear canvas
    ctx.clearRect(0, 0, canvasSize, canvasSize);

    // Draw board background
    drawBoardBackground(ctx, layout, imagesRef.current['board'] || null);

    // Draw grid lines
    drawGrid(ctx, layout, boardSize);

    // Draw star points
    drawStars(ctx, layout, boardSize);

    // Draw coordinates
    if (showCoordinates) {
      drawCoordinates(ctx, layout, boardSize);
    }

    // Draw ownership/territory overlay
    if (showTerritory && ownership && ownership.length === boardSize) {
      for (let y = 0; y < boardSize; y++) {
        for (let x = 0; x < boardSize; x++) {
          // ownership is stored with y=0 as top row (screen convention)
          // but gridToCanvas expects y in Go convention (y=0 is bottom)
          // so we invert the y index when reading ownership data
          const ownershipY = boardSize - 1 - y;
          const val = ownership[ownershipY]?.[x] ?? 0;
          if (Math.abs(val) > 0.05) {
            const pos = gridToCanvas(layout, x, y, boardSize);
            const alpha = Math.abs(val) * 0.4;
            // Positive = Black territory, Negative = White territory
            ctx.fillStyle = val > 0 ? `rgba(0, 0, 0, ${alpha})` : `rgba(255, 255, 255, ${alpha})`;
            ctx.fillRect(
              pos.x - layout.gridSize / 2,
              pos.y - layout.gridSize / 2,
              layout.gridSize,
              layout.gridSize
            );
          }
        }
      }
    }

    // Draw stones
    const blackImg = imagesRef.current['blackStone'] || null;
    const whiteImg = imagesRef.current['whiteStone'] || null;

    for (let y = 0; y < boardSize; y++) {
      for (let x = 0; x < boardSize; x++) {
        const stone = board[y][x];
        if (stone) {
          drawStone(ctx, layout, x, y, boardSize, stone as 'B' | 'W', blackImg, whiteImg);

          // Draw move number on stone if enabled
          if (showMoveNumbers && moveNumbers[y][x]) {
            const pos = gridToCanvas(layout, x, y, boardSize);
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = stone === 'B' ? '#fff' : '#000';
            // Larger font size for better readability
            ctx.font = `bold ${Math.max(11, layout.gridSize * 0.38)}px sans-serif`;
            // Center the text on the stone consistently for all moves
            ctx.fillText(String(moveNumbers[y][x]), pos.x, pos.y);
            ctx.restore();
          }
        }
      }
    }

    // Draw try moves (semi-transparent stones for experimentation)
    if (tryMoves && tryMoves.length > 0) {
      let tryPlayer: 'B' | 'W' = lastPlayer === 'B' ? 'W' : 'B';
      if (currentMove === 0) tryPlayer = 'B';

      for (let i = 0; i < tryMoves.length; i++) {
        const coords = parseMove(tryMoves[i]);
        if (coords) {
          const [x, y] = coords;
          if (x >= 0 && x < boardSize && y >= 0 && y < boardSize && !board[y][x]) {
            drawPvStone(ctx, layout, x, y, boardSize, tryPlayer, i + 1, blackImg, whiteImg);
          }
        }
        tryPlayer = tryPlayer === 'B' ? 'W' : 'B';
      }
    }

    // Draw last move marker (always show, even with move numbers)
    if (lastMove) {
      const [x, y] = lastMove;
      drawLastMoveMarker(ctx, layout, x, y, boardSize, lastPlayer);
    }

    // Draw AI move markers (colored circles on empty intersections)
    if (showAiMarkers && aiMarkers && aiMarkers.length > 0 && !pvMoves) {
      // Only show AI markers when not hovering on PV (PV takes precedence)
      // Limit to top 3 to match play module
      const markersToShow = aiMarkers.slice(0, 3);
      for (const marker of markersToShow) {
        const coords = parseMove(marker.move);
        if (coords) {
          const [x, y] = coords;
          // Only draw on empty intersections
          if (x >= 0 && x < boardSize && y >= 0 && y < boardSize && !board[y][x]) {
            drawAiMoveMarker(ctx, layout, x, y, boardSize, marker.rank, marker.winrate, marker.visits, time);
          }
        }
      }
    }

    // Draw PV (principal variation) stones if hovering
    if (pvMoves && pvMoves.length > 0) {
      // Determine the starting player for PV moves (opposite of last player)
      let pvPlayer: 'B' | 'W' = lastPlayer === 'B' ? 'W' : 'B';
      // If we're at move 0 (empty board), black plays first
      if (currentMove === 0) {
        pvPlayer = 'B';
      }

      // Track positions already used by PV stones
      const pvOccupied = new Set<string>();
      let displayNumber = 1;

      for (let i = 0; i < pvMoves.length; i++) {
        const coords = parseMove(pvMoves[i]);
        if (coords) {
          const [x, y] = coords;
          const posKey = `${x},${y}`;
          // Only draw if position is empty (not occupied by real stones or previous PV stones)
          if (x >= 0 && x < boardSize && y >= 0 && y < boardSize && !board[y][x] && !pvOccupied.has(posKey)) {
            drawPvStone(ctx, layout, x, y, boardSize, pvPlayer, displayNumber, blackImg, whiteImg);
            pvOccupied.add(posKey);
            displayNumber++;
          }
        }
        // Alternate colors for each move in the sequence
        pvPlayer = pvPlayer === 'B' ? 'W' : 'B';
      }
    }

    // Draw hover ghost stone preview
    if (hoverPosRef.current && onIntersectionClick) {
      const { x: hx, y: hy } = hoverPosRef.current;
      if (hx >= 0 && hx < boardSize && hy >= 0 && hy < boardSize && !board[hy][hx]) {
        // Determine ghost color: use nextColor prop, or infer from lastPlayer
        const ghostColor = nextColor ?? (lastPlayer === 'B' ? 'W' : 'B');
        const { x: cx, y: cy } = gridToCanvas(layout, hx, hy, boardSize);
        const stoneSize = layout.gridSize * 0.505;
        ctx.save();
        ctx.globalAlpha = 0.5;
        const img = ghostColor === 'B' ? blackImg : whiteImg;
        if (img) {
          ctx.drawImage(img, cx - stoneSize, cy - stoneSize, stoneSize * 2, stoneSize * 2);
        } else {
          ctx.beginPath();
          ctx.arc(cx, cy, stoneSize * 0.95, 0, Math.PI * 2);
          ctx.fillStyle = ghostColor === 'B' ? '#000' : '#fff';
          ctx.fill();
          if (ghostColor === 'W') {
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
        ctx.restore();
      }
    }
  };

  // Render on state change; animate only when AI markers need pulsing
  useEffect(() => {
    if (!imagesLoaded) return;
    renderBoard();

    const needsAnimation = showAiMarkers && aiMarkers && aiMarkers.length > 0;
    if (needsAnimation) {
      const interval = setInterval(renderBoard, 100); // ~10fps for pulse
      return () => clearInterval(interval);
    }
  }, [moves, stoneColors, currentMove, boardSize, canvasSize, imagesLoaded, showCoordinates, pvMoves, aiMarkers, showAiMarkers, showMoveNumbers, showTerritory, ownership, tryMoves, nextColor]);

  // Convert grid coordinates to move notation (e.g., Q16)
  const coordsToMove = (x: number, y: number): string => {
    const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // Skip I
    const col = letters[x];
    const row = y + 1;
    return `${col}${row}`;
  };

  // Handle mouse move for hover ghost stone
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !onIntersectionClick) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvasSize / rect.width;
    const scaleY = canvasSize / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    const gridPos = canvasToGrid(layout, mx, my, boardSize);
    if (gridPos) {
      hoverPosRef.current = gridPos;
    } else {
      hoverPosRef.current = null;
    }
    renderBoard();
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
    renderBoard();
  };

  // Handle click
  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvasSize / rect.width;
    const scaleY = canvasSize / rect.height;

    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    const gridPos = canvasToGrid(layout, clickX, clickY, boardSize);

    if (gridPos) {
      // Handle try move mode
      if (onTryMove) {
        const move = coordsToMove(gridPos.x, gridPos.y);
        onTryMove(move);
        return;
      }

      // Regular intersection click
      if (onIntersectionClick) {
        onIntersectionClick(gridPos.x, gridPos.y);
      }
    }
  };

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 400,
        padding: '4px',
      }}
    >
      <canvas
        ref={canvasRef}
        width={canvasSize}
        height={canvasSize}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px rgba(212, 165, 116, 0.05)',
          cursor: onIntersectionClick ? 'pointer' : 'default',
        }}
      />
    </Box>
  );
}
