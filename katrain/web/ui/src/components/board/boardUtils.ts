import {
  type BoardStyleId,
  type StoneAppearanceId,
  type StoneStyleId,
  getActiveBoardStyle,
  getActiveStoneStyle,
  getBoardStylePalette,
  getBoardTextureDataUrl,
  getBoardTextureUrl,
  getStoneAppearance,
  normalizeBoardStyleId,
  normalizeStoneStyleId,
  stoneSpriteUrl,
  stoneVariant,
} from "./stoneAppearance";

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

export type BoardAssets = Record<string, HTMLImageElement> & {
  board?: HTMLImageElement;
  black?: HTMLImageElement;
  white?: HTMLImageElement;
  blackStone?: HTMLImageElement;
  whiteStone?: HTMLImageElement;
  lastMove?: HTMLImageElement;
  topMove?: HTMLImageElement;
};

// One promise per URL keeps remounts and concurrent boards from fetching per stone.
const spriteImages = new Map<string, HTMLImageElement>();
const styleSpriteCache = new Map<StoneStyleId, { B: HTMLImageElement | null; W: (HTMLImageElement | null)[] }>();
const boardAssetsCache = new Map<string, BoardAssets>();
const imageLoads = new Map<string, Promise<HTMLImageElement | null>>();

function loadBoardImage(src: string): Promise<HTMLImageElement | null> {
  let pending = imageLoads.get(src);
  if (!pending) {
    pending = new Promise(resolve => {
      const image = new Image();
      image.onload = () => {
        spriteImages.set(src, image);
        resolve(image);
      };
      image.onerror = () => resolve(null);
      image.src = src;
    });
    imageLoads.set(src, pending);
    // Evict after settlement so synchronous image mocks and concurrent consumers
    // also share the initial attempt, while a later mount can retry failures.
    void pending.then(image => {
      if (!image && imageLoads.get(src) === pending) imageLoads.delete(src);
    });
  }
  return pending;
}

function loadBoardVeneerImage(boardStyle: BoardStyleId): Promise<HTMLImageElement | null> {
  const primaryUrl = getBoardTextureUrl(boardStyle);
  const fallbackDataUrl = getBoardTextureDataUrl(boardStyle);
  const existing = spriteImages.get(primaryUrl) ?? spriteImages.get(fallbackDataUrl);
  if (existing) return Promise.resolve(existing);

  let pending = imageLoads.get(primaryUrl);
  if (!pending) {
    pending = new Promise(resolve => {
      const image = new Image();
      let triedFallback = false;
      image.onload = () => {
        spriteImages.set(triedFallback ? fallbackDataUrl : primaryUrl, image);
        resolve(image);
      };
      image.onerror = () => {
        if (!triedFallback) {
          triedFallback = true;
          image.src = fallbackDataUrl;
          return;
        }
        resolve(null);
      };
      image.src = primaryUrl;
    });
    imageLoads.set(primaryUrl, pending);
    void pending.then(image => {
      if (!image && imageLoads.get(primaryUrl) === pending) imageLoads.delete(primaryUrl);
    });
  }
  return pending;
}

/** Preload the finite sprite set once; legacy images remain available on failure. */
export async function loadBoardImages(
  boardStyleOrAssets?: BoardStyleId | string | Record<string, string>,
  stoneStyle: StoneAppearanceId | string = getActiveStoneStyle(),
): Promise<BoardAssets> {
  const resolvedStoneStyle = normalizeStoneStyleId(stoneStyle);
  const appearance = getStoneAppearance(resolvedStoneStyle);
  const sprites = [appearance.sprites.B, ...appearance.sprites.W];
  const spritesLoadedPromise = Promise.all(sprites.map(loadBoardImage));

  if (typeof boardStyleOrAssets === "object" && boardStyleOrAssets !== null) {
    const resolvedBoardStyle = getActiveBoardStyle();
    const entries = await Promise.all(
      Object.entries(boardStyleOrAssets).map(async ([key, src]) => {
        if (key === "board" && src === BOARD_ASSETS.board) {
          const veneerBoard = await loadBoardVeneerImage(resolvedBoardStyle);
          if (veneerBoard) return [key, veneerBoard] as const;
        }
        return [key, await loadBoardImage(src)] as const;
      }),
    );
    const loadedSprites = await spritesLoadedPromise;
    styleSpriteCache.set(resolvedStoneStyle, {
      B: loadedSprites[0] ?? null,
      W: loadedSprites.slice(1),
    });
    return Object.fromEntries(
      entries.filter((entry): entry is readonly [string, HTMLImageElement] => entry[1] !== null),
    );
  }

  const resolvedBoardStyle = normalizeBoardStyleId(boardStyleOrAssets ?? getActiveBoardStyle());
  const cacheKey = `${resolvedBoardStyle}:${resolvedStoneStyle}`;
  const cached = boardAssetsCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  // Start board veneer and legacy marker loads in tick 0 alongside sprites so
  // synchronous pending-image test harnesses see all Image instances immediately.
  const boardVeneerPromise = loadBoardVeneerImage(resolvedBoardStyle);
  const legacyImagesPromise = Promise.all([
    loadBoardImage(BOARD_ASSETS.blackStone),
    loadBoardImage(BOARD_ASSETS.whiteStone),
    loadBoardImage(BOARD_ASSETS.lastMove),
    loadBoardImage(BOARD_ASSETS.topMove),
  ]);

  const [loadedSprites, veneerImg, [blackStoneImg, whiteStoneImg, lastMoveImg, topMoveImg]] = await Promise.all([
    spritesLoadedPromise,
    boardVeneerPromise,
    legacyImagesPromise,
  ]);
  const allSpritesSucceeded = loadedSprites.every(img => img !== null);
  styleSpriteCache.set(resolvedStoneStyle, {
    B: loadedSprites[0] ?? null,
    W: loadedSprites.slice(1),
  });

  let boardImg = veneerImg;
  if (!boardImg) {
    boardImg = await loadBoardImage(BOARD_ASSETS.board);
  }

  const blackSprite = loadedSprites[0] ?? blackStoneImg ?? null;
  const whiteSprite = loadedSprites[1] ?? whiteStoneImg ?? null;

  const result: BoardAssets = {};
  if (boardImg) result.board = boardImg;
  if (blackSprite) {
    result.black = blackSprite;
    result.blackStone = blackSprite;
  }
  if (whiteSprite) {
    result.white = whiteSprite;
    result.whiteStone = whiteSprite;
  }
  if (lastMoveImg) result.lastMove = lastMoveImg;
  if (topMoveImg) result.topMove = topMoveImg;

  if (allSpritesSucceeded && boardImg) {
    boardAssetsCache.set(cacheKey, result);
  }

  return result;
}

/** Coordinate-based selection is stable across replay, hover, and board remounts. */
export function stoneImage(
  color: "B" | "W",
  col: number,
  row: number,
  boardSize: number,
  fallback: HTMLImageElement | null | undefined,
  stoneStyle: StoneAppearanceId | string = getActiveStoneStyle(),
): HTMLImageElement | null {
  const resolvedStyle = normalizeStoneStyleId(stoneStyle);
  const url = stoneSpriteUrl(color, boardSize, col, boardSize - 1 - row, resolvedStyle);
  const byUrl = spriteImages.get(url);
  if (byUrl) return byUrl;

  const byStyle = styleSpriteCache.get(resolvedStyle);
  if (byStyle) {
    if (color === "B" && byStyle.B) return byStyle.B;
    if (color === "W" && byStyle.W.length > 0) {
      const idx = stoneVariant(boardSize, col, boardSize - 1 - row, byStyle.W.length);
      if (byStyle.W[idx]) return byStyle.W[idx];
    }
  }
  return fallback ?? null;
}

/** Draw the lit sprite as exported; move labels and selection rings stay upright. */
export function drawStoneSprite(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement,
  centerX: number,
  centerY: number,
  radius: number,
  _boardSize: number,
  _col: number,
  _rowFromBottom: number,
): void {
  ctx.drawImage(image, centerX - radius, centerY - radius, radius * 2, radius * 2);
}

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
 *
 * `margin` 是**每边留几格**。默认 1.5:那是给盘面**自己那圈坐标**留的位置。
 * 坐标交给外壳画的时候(kiosk 布局 A 的四条刻度带)必须传 **0.5**,否则:
 *   线的节距 = W/(N−1+2·margin),刻度带的节距 = W/N —— 两者只在 margin=0.5 时相等。
 *
 * `exact` 关掉取整。**这两个必须一起用**:外壳画坐标时线的节距要**逐像素等于**刻度带的
 * 轨道宽,而 `floor` 会把 24.2 砍成 24 —— 一格差 0.2,18 格累到边上就是 4px,
 * 再加上重新居中,头尾两条线各偏 ~6px,四图上一眼看得出「字和线错开」。
 * 自己画坐标时仍然取整:那时线要落在整像素上才不发虚,而刻度带不存在,没人跟它对齐。
 *
 * 同一条不变式在 `TsumegoBoard`(canvas,Task 14)、`GoBoardSvg`(SVG)和这里各有一份,
 * 判据写在 `tests/kiosk-shell-geometry.spec.ts`:头尾两条线正对刻度带头尾两个字。
 */
export function calculateBoardLayout(
  canvasWidth: number,
  canvasHeight: number,
  boardSize: number,
  options: { margin?: number; exact?: boolean } = {},
): BoardLayout {
  const { margin = 1.5, exact = false } = options;
  const gridMargins = { x: [margin, margin] as [number, number], y: [margin, margin] as [number, number] };
  const xGridSpaces = boardSize - 1 + gridMargins.x[0] + gridMargins.x[1];
  const yGridSpaces = boardSize - 1 + gridMargins.y[0] + gridMargins.y[1];
  const raw = Math.min(canvasWidth / xGridSpaces, canvasHeight / yGridSpaces);
  const gridSize = exact ? raw : Math.floor(raw);
  const boardWidth = xGridSpaces * gridSize;
  const boardHeight = yGridSpaces * gridSize;
  const offsetX = exact ? (canvasWidth - boardWidth) / 2 : Math.round((canvasWidth - boardWidth) / 2);
  const offsetY = exact ? (canvasHeight - boardHeight) / 2 : Math.round((canvasHeight - boardHeight) / 2);
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
  boardSize: number,
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
  boardSize: number,
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
 * Draw board background image or wood palette fallback fill.
 */
export function drawBoardBackground(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardImg: HTMLImageElement | null,
  boardStyle: BoardStyleId | string = getActiveBoardStyle(),
): void {
  const palette = getBoardStylePalette(boardStyle);
  ctx.fillStyle = palette.woodFill;
  ctx.fillRect?.(layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
  if (boardImg) {
    ctx.drawImage(boardImg, layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
  }
}

/**
 * Draw grid lines on the board.
 */
export function drawGrid(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardSize: number,
  boardStyle: BoardStyleId | string = getActiveBoardStyle(),
): void {
  const palette = getBoardStylePalette(boardStyle);
  ctx.strokeStyle = palette.gridColor;
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
  boardSize: number,
  boardStyle: BoardStyleId | string = getActiveBoardStyle(),
): void {
  const stars =
    boardSize === 19 ? [3, 9, 15] :
    boardSize === 13 ? [3, 6, 9] :
    boardSize === 9 ? [2, 4, 6] : [];

  const palette = getBoardStylePalette(boardStyle);
  ctx.fillStyle = palette.starColor;
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
  boardSize: number,
  coordColor?: string,
  boardStyle: BoardStyleId | string = getActiveBoardStyle(),
): void {
  const letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ".split(""); // Skip I
  const palette = getBoardStylePalette(boardStyle);
  ctx.fillStyle = coordColor || palette.coordColor;
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
 * Draw grid lines, star points, and coordinates using the board style palette.
 */
export function drawBoardGrid(
  ctx: CanvasRenderingContext2D,
  layout: BoardLayout,
  boardSize: number,
  coordColor?: string,
  boardStyle: BoardStyleId | string = getActiveBoardStyle(),
): void {
  drawGrid(ctx, layout, boardSize, boardStyle);
  drawStars(ctx, layout, boardSize, boardStyle);
  drawCoordinates(ctx, layout, boardSize, coordColor, boardStyle);
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
  player: "B" | "W",
  blackImg: HTMLImageElement | null,
  whiteImg: HTMLImageElement | null,
  stoneStyle: StoneAppearanceId | string = getActiveStoneStyle(),
): void {
  const resolvedStyle = normalizeStoneStyleId(stoneStyle);
  const pos = gridToCanvas(layout, x, y, boardSize);
  const stoneSize = layout.gridSize * 0.505;
  const img = stoneImage(player, x, y, boardSize, player === "B" ? blackImg : whiteImg, resolvedStyle);

  // For translucent white jade-agate stones, draw a warm lower-right lens caustic glow
  // on the board beneath the semi-transparent chalcedony sprite.
  if (player === "W" && resolvedStyle === "jade-agate") {
    ctx.save?.();
    ctx.beginPath?.();
    ctx.arc?.(pos.x + stoneSize * 0.14, pos.y + stoneSize * 0.16, stoneSize * 0.86, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255, 243, 210, 0.28)";
    ctx.fill?.();
    ctx.restore?.();
  }

  if (img) {
    drawStoneSprite(ctx, img, pos.x, pos.y, stoneSize, boardSize, x, y);
  } else {
    // Fallback circle
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, stoneSize * 0.95, 0, Math.PI * 2);
    ctx.fillStyle = player === "B" ? "#000" : "#fff";
    ctx.fill();
    if (player === "W") {
      ctx.strokeStyle = "#000";
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
  stoneColor: "B" | "W",
): void {
  const pos = gridToCanvas(layout, x, y, boardSize);
  const circleRadius = layout.gridSize * 0.35;

  // Outer glow
  ctx.shadowColor = stoneColor === "B" ? "rgba(255, 255, 255, 0.4)" : "rgba(0, 0, 0, 0.4)";
  ctx.shadowBlur = 8;

  ctx.beginPath();
  ctx.arc(pos.x, pos.y, circleRadius, 0, Math.PI * 2);
  ctx.strokeStyle = stoneColor === "B" ? "rgba(255, 255, 255, 0.95)" : "rgba(0, 0, 0, 0.95)";
  ctx.lineWidth = Math.max(2.5, layout.gridSize * 0.09);
  ctx.stroke();

  // Reset shadow
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
}
