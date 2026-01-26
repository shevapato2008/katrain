/**
 * Shared board drawing utilities.
 *
 * These functions provide consistent board rendering across all board components
 * (GamePage Board, LiveBoard, ResearchPage, etc.)
 */

export const BOARD_ASSETS = {
  board: "/assets/img/board.png",
  blackStone: "/assets/img/B_stone.png",
  whiteStone: "/assets/img/W_stone.png",
  lastMove: "/assets/img/inner.png",
  topMove: "/assets/img/topmove.png",
};

export interface BoardLayout {
  gridMargins: { x: [number, number]; y: [number, number] };
  gridSize: number;
  boardWidth: number;
  boardHeight: number;
  offsetX: number;
  offsetY: number;
}

/**
 * Calculate board layout parameters.
 * Uses symmetric 1.5 grid-space margins for coordinates.
 */
export function calculateBoardLayout(
  canvasWidth: number,
  canvasHeight: number,
  boardSize: number
): BoardLayout {
  const gridMargins = { x: [1.5, 1.5] as [number, number], y: [1.5, 1.5] as [number, number] };
  const xGridSpaces = boardSize - 1 + gridMargins.x[0] + gridMargins.x[1];
  const yGridSpaces = boardSize - 1 + gridMargins.y[0] + gridMargins.y[1];
  const gridSize = Math.floor(Math.min(canvasWidth / xGridSpaces, canvasHeight / yGridSpaces));
  const boardWidth = xGridSpaces * gridSize;
  const boardHeight = yGridSpaces * gridSize;
  const offsetX = Math.round((canvasWidth - boardWidth) / 2);
  const offsetY = Math.round((canvasHeight - boardHeight) / 2);
  return { gridMargins, gridSize, boardWidth, boardHeight, offsetX, offsetY };
}

/**
 * Convert grid coordinates to canvas pixel coordinates.
 * Note: Y coordinate is inverted (0 = bottom in Go, but top in canvas)
 */
export function gridToCanvas(
  layout: BoardLayout,
  x: number,
  y: number,
  boardSize: number
): { x: number; y: number } {
  const invertedY = boardSize - 1 - y;
  const px = layout.offsetX + (layout.gridMargins.x[0] + x) * layout.gridSize;
  const py = layout.offsetY + (layout.gridMargins.y[1] + invertedY) * layout.gridSize;
  return { x: px, y: py };
}

/**
 * Convert canvas pixel coordinates to grid coordinates.
 */
export function canvasToGrid(
  layout: BoardLayout,
  canvasX: number,
  canvasY: number,
  boardSize: number
): { x: number; y: number } | null {
  const relX = (canvasX - layout.offsetX) / layout.gridSize - layout.gridMargins.x[0];
  const relY = (canvasY - layout.offsetY) / layout.gridSize - layout.gridMargins.y[1];
  const gridX = Math.round(relX);
  const invertedY = Math.round(relY);
  const gridY = boardSize - 1 - invertedY;

  if (gridX >= 0 && gridX < boardSize && gridY >= 0 && gridY < boardSize) {
    return { x: gridX, y: gridY };
  }
  return null;
}

/**
 * Draw board background image.
 */
export function drawBoardBackground(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardImg: HTMLImageElement | null
): void {
  if (boardImg) {
    ctx.drawImage(boardImg, layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
  } else {
    // Fallback wood color
    ctx.fillStyle = '#dcb35c';
    ctx.fillRect(layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
  }
}

/**
 * Draw grid lines on the board.
 */
export function drawGrid(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardSize: number
): void {
  ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
  ctx.lineWidth = 1.2;
  ctx.lineCap = "round";

  for (let i = 0; i < boardSize; i++) {
    // Vertical lines
    const vStart = gridToCanvas(layout, i, 0, boardSize);
    const vEnd = gridToCanvas(layout, i, boardSize - 1, boardSize);
    ctx.beginPath();
    ctx.moveTo(Math.round(vStart.x) + 0.5, Math.round(vStart.y) + 0.5);
    ctx.lineTo(Math.round(vEnd.x) + 0.5, Math.round(vEnd.y) + 0.5);
    ctx.stroke();

    // Horizontal lines
    const hStart = gridToCanvas(layout, 0, i, boardSize);
    const hEnd = gridToCanvas(layout, boardSize - 1, i, boardSize);
    ctx.beginPath();
    ctx.moveTo(Math.round(hStart.x) + 0.5, Math.round(hStart.y) + 0.5);
    ctx.lineTo(Math.round(hEnd.x) + 0.5, Math.round(hEnd.y) + 0.5);
    ctx.stroke();
  }
}

/**
 * Draw star points (hoshi) on the board.
 */
export function drawStars(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardSize: number
): void {
  const stars =
    boardSize === 19 ? [3, 9, 15] :
    boardSize === 13 ? [3, 6, 9] :
    boardSize === 9 ? [2, 4, 6] : [];

  ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
  const starRadius = layout.gridSize * 0.11;

  stars.forEach(x => {
    stars.forEach(y => {
      const pos = gridToCanvas(layout, x, y, boardSize);
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, starRadius, 0, Math.PI * 2);
      ctx.fill();
    });
  });
}

/**
 * Draw coordinate labels around the board.
 */
export function drawCoordinates(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardSize: number
): void {
  const letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ".split(""); // Skip I
  ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
  ctx.font = `600 ${Math.max(12, layout.gridSize * 0.45)}px 'IBM Plex Mono', monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Letters - BOTTOM
  for (let i = 0; i < boardSize; i++) {
    const pos = gridToCanvas(layout, i, 0, boardSize);
    ctx.fillText(letters[i], pos.x, layout.offsetY + layout.boardHeight - layout.gridSize * 0.5);
  }

  // Letters - TOP
  for (let i = 0; i < boardSize; i++) {
    const pos = gridToCanvas(layout, i, boardSize - 1, boardSize);
    ctx.fillText(letters[i], pos.x, layout.offsetY + layout.gridSize * 0.5);
  }

  // Numbers - LEFT
  for (let j = 0; j < boardSize; j++) {
    const pos = gridToCanvas(layout, 0, j, boardSize);
    ctx.fillText((j + 1).toString(), layout.offsetX + layout.gridSize * 0.5, pos.y);
  }

  // Numbers - RIGHT
  for (let j = 0; j < boardSize; j++) {
    const pos = gridToCanvas(layout, boardSize - 1, j, boardSize);
    ctx.fillText((j + 1).toString(), layout.offsetX + layout.boardWidth - layout.gridSize * 0.5, pos.y);
  }
}

/**
 * Draw a stone on the board.
 */
export function drawStone(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  x: number,
  y: number,
  boardSize: number,
  player: 'B' | 'W',
  blackImg: HTMLImageElement | null,
  whiteImg: HTMLImageElement | null
): void {
  const pos = gridToCanvas(layout, x, y, boardSize);
  const stoneSize = layout.gridSize * 0.505;
  const img = player === 'B' ? blackImg : whiteImg;

  if (img) {
    ctx.drawImage(img, pos.x - stoneSize, pos.y - stoneSize, stoneSize * 2, stoneSize * 2);
  } else {
    // Fallback circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, stoneSize * 0.95, 0, Math.PI * 2);
    ctx.fillStyle = player === 'B' ? '#000' : '#fff';
    ctx.fill();
    if (player === 'W') {
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }
}

/**
 * Draw last move marker.
 */
export function drawLastMoveMarker(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  x: number,
  y: number,
  boardSize: number,
  stoneColor: 'B' | 'W'
): void {
  const pos = gridToCanvas(layout, x, y, boardSize);
  const circleRadius = layout.gridSize * 0.35;

  // Outer glow
  ctx.shadowColor = stoneColor === 'B' ? "rgba(255, 255, 255, 0.4)" : "rgba(0, 0, 0, 0.4)";
  ctx.shadowBlur = 8;

  ctx.beginPath();
  ctx.arc(pos.x, pos.y, circleRadius, 0, Math.PI * 2);
  ctx.strokeStyle = stoneColor === 'B' ? "rgba(255, 255, 255, 0.95)" : "rgba(0, 0, 0, 0.95)";
  ctx.lineWidth = Math.max(2.5, layout.gridSize * 0.09);
  ctx.stroke();

  // Reset shadow
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
}
