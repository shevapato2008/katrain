/**
 * TsumegoBoard - Interactive board component for solving tsumego problems
 *
 * A specialized board component that:
 * - Renders stones on a Go board
 * - Handles click events for placing stones
 * - Shows last move indicator
 * - Can highlight hint positions
 * - Supports disabled state when solved/failed
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box } from '@mui/material';

interface Stone {
  player: 'B' | 'W';
  coords: [number, number];
}

interface TsumegoBoardProps {
  boardSize: number;
  stones: Stone[];
  lastMove: [number, number] | null;
  hintCoords?: [number, number] | null;
  showHint?: boolean;
  disabled?: boolean;
  /** Moves made during solving (for displaying move numbers) */
  moveHistory?: Stone[];
  /** Show move numbers on stones */
  showMoveNumbers?: boolean;
  /**
   * 画不画自己那一圈坐标(默认画)。
   *
   * kiosk 的 L2 布局 A 把盘放进共享外壳的木框里,而那个框**自带四条刻度带**
   * (`.kiosk-board__ruler`,四棋类同一套几何)。两边都画就是**两套坐标**:
   * 一套在木框上、一套在盘面里,而且字号字色都不是同一套。
   * ⇒ kiosk 做题屏传 `false`,坐标交给外壳;galaxy 那边不传,行为一个字节不变。
   */
  showCoordinates?: boolean;
  /** Board coords [x, y] of wrong/extra physical stones to flag with a red ✕ (occlusion-proof
   *  screen cue — the physical LED under the stone is hidden by the stone itself). */
  extraMarkers?: [number, number][];
  onPlaceStone: (x: number, y: number) => void;
}

const ASSETS = {
  board: "/assets/img/board.png",
  blackStone: "/assets/img/B_stone.png",
  whiteStone: "/assets/img/W_stone.png",
};

const TsumegoBoard: React.FC<TsumegoBoardProps> = ({
  boardSize,
  stones,
  lastMove,
  hintCoords,
  showHint = false,
  disabled = false,
  moveHistory = [],
  showMoveNumbers = false,
  showCoordinates = true,
  extraMarkers = [],
  onPlaceStone
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imagesRef = useRef<Record<string, HTMLImageElement>>({});
  const [canvasSize, setCanvasSize] = useState(800);
  const [imagesLoaded, setImagesLoaded] = useState(false);

  // Load images on mount
  useEffect(() => {
    const loadImages = async () => {
      const entries = Object.entries(ASSETS);
      await Promise.all(
        entries.map(
          ([key, src]) =>
            new Promise<void>((resolve) => {
              const img = new Image();
              img.onload = () => {
                imagesRef.current[key] = img;
                resolve();
              };
              img.onerror = () => {
                console.warn(`Failed to load ${src}`);
                resolve();
              };
              img.src = src;
            })
        )
      );
      setImagesLoaded(true);
    };
    loadImages();
  }, []);

  // Track container size for responsive canvas
  useEffect(() => {
    const updateCanvasSize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        // Use the smaller dimension to keep the board square, minus padding.
        // 外壳画坐标时(kiosk 布局 A)那 4px 内边距要收掉:落子区是 460,盘就得是 460 ——
        // 差 8px 摊到 18 个格上,线和外壳刻度带的字就对不上了。
        const size = Math.floor(Math.min(width, height) - (showCoordinates ? 8 : 0));
        // Clamp between 200 and 1200 for reasonable bounds (matching main Board component)
        setCanvasSize(Math.max(200, Math.min(1200, size)));
      }
    };

    updateCanvasSize();

    // ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(updateCanvasSize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    // Window resize event for cross-monitor moves and DPI changes
    window.addEventListener('resize', updateCanvasSize);

    // Handle visibility changes (e.g., tab switching, monitor changes)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // Delay to let layout settle after monitor change
        setTimeout(updateCanvasSize, 100);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateCanvasSize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // `showCoordinates` 决定要不要减那 8px ⇒ 它变了就得重新量一次。
    // (实际上它每屏是常量,这条依赖是为了让「读的是当前值」这件事由 React 保证,
    //  而不是靠一个在 render 里写的 ref —— 那条 lint 规则骂的正是后者。)
  }, [showCoordinates]);

  // Board layout calculations
  const boardLayout = useCallback((canvas: HTMLCanvasElement) => {
    // 边距 1.5 格是**给盘面里那圈坐标留的位置**。坐标交给外壳画时(kiosk 布局 A)那圈字不在了,
    // 边距要收回 0.5 —— 不然线的节距是 W/(N−1+3),而外壳刻度带的节距是 W/N,
    // **两者不等 ⇒ 字和线对不上**(19 路 460 宽实测差 2.3px/格,累到边上是 20px)。
    // go-screens.css 那段把这条写成了不变式:**刻度带的节距必须等于盘的线节距**。
    const m = showCoordinates ? 1.5 : 0.5;
    const gridMargins = { x: [m, m], y: [m, m] };
    const xGridSpaces = boardSize - 1 + gridMargins.x[0] + gridMargins.x[1];
    const yGridSpaces = boardSize - 1 + gridMargins.y[0] + gridMargins.y[1];
    // ⚠️ **取整只在自己画坐标时做。** 外壳画坐标时线的节距必须**逐像素等于**刻度带的轨道宽
    // (460 / 19),而 `floor` 会把 24.2 砍成 24 —— 一格差 0.2,18 格累到边上就是 4px,
    // 加上盘被重新居中,头尾两条线各偏 ~6px。四图对比一眼看得出「字和线错开」。
    const raw = Math.min(canvas.width / xGridSpaces, canvas.height / yGridSpaces);
    const gridSize = showCoordinates ? Math.floor(raw) : raw;
    const boardWidth = xGridSpaces * gridSize;
    const boardHeight = yGridSpaces * gridSize;
    const offsetX = showCoordinates ? Math.round((canvas.width - boardWidth) / 2) : (canvas.width - boardWidth) / 2;
    const offsetY = showCoordinates ? Math.round((canvas.height - boardHeight) / 2) : (canvas.height - boardHeight) / 2;
    return { gridMargins, gridSize, boardWidth, boardHeight, offsetX, offsetY };
  }, [boardSize, showCoordinates]);

  const gridToCanvas = useCallback((layout: ReturnType<typeof boardLayout>, x: number, y: number) => {
    const invertedY = boardSize - 1 - y;
    const px = layout.offsetX + (layout.gridMargins.x[0] + x) * layout.gridSize;
    const py = layout.offsetY + (layout.gridMargins.y[1] + invertedY) * layout.gridSize;
    return { x: px, y: py };
  }, [boardSize]);

  // Render the board
  const renderBoard = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imagesLoaded) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const layout = boardLayout(canvas);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    if (imagesRef.current.board) {
      ctx.drawImage(imagesRef.current.board, layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
    } else {
      // Fallback background
      ctx.fillStyle = '#DEB887';
      ctx.fillRect(layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
    }

    // Draw grid
    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.lineWidth = 1.2;
    ctx.lineCap = "round";

    for (let i = 0; i < boardSize; i++) {
      const start = gridToCanvas(layout, i, 0);
      const end = gridToCanvas(layout, i, boardSize - 1);
      ctx.beginPath();
      ctx.moveTo(Math.round(start.x) + 0.5, Math.round(start.y) + 0.5);
      ctx.lineTo(Math.round(end.x) + 0.5, Math.round(end.y) + 0.5);
      ctx.stroke();
    }
    for (let j = 0; j < boardSize; j++) {
      const start = gridToCanvas(layout, 0, j);
      const end = gridToCanvas(layout, boardSize - 1, j);
      ctx.beginPath();
      ctx.moveTo(Math.round(start.x) + 0.5, Math.round(start.y) + 0.5);
      ctx.lineTo(Math.round(end.x) + 0.5, Math.round(end.y) + 0.5);
      ctx.stroke();
    }

    // Draw star points
    const stars = boardSize === 19 ? [3, 9, 15] : boardSize === 13 ? [3, 6, 9] : boardSize === 9 ? [2, 4, 6] : [];
    ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
    const starRadius = layout.gridSize * 0.11;
    stars.forEach(x => stars.forEach(y => {
      const pos = gridToCanvas(layout, x, y);
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, starRadius, 0, Math.PI * 2);
      ctx.fill();
    }));

    // Draw coordinates
    if (showCoordinates) {
      const letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ".split("");
      ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
      ctx.font = `600 ${Math.max(10, layout.gridSize * 0.4)}px 'IBM Plex Mono', monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // Bottom letters
      for (let i = 0; i < boardSize; i++) {
        const pos = gridToCanvas(layout, i, 0);
        ctx.fillText(letters[i], pos.x, layout.offsetY + layout.boardHeight - layout.gridSize * 0.5);
      }
      // Top letters
      for (let i = 0; i < boardSize; i++) {
        const pos = gridToCanvas(layout, i, boardSize - 1);
        ctx.fillText(letters[i], pos.x, layout.offsetY + layout.gridSize * 0.5);
      }
      // Left numbers
      for (let j = 0; j < boardSize; j++) {
        const pos = gridToCanvas(layout, 0, j);
        ctx.fillText((j + 1).toString(), layout.offsetX + layout.gridSize * 0.5, pos.y);
      }
      // Right numbers
      for (let j = 0; j < boardSize; j++) {
        const pos = gridToCanvas(layout, boardSize - 1, j);
        ctx.fillText((j + 1).toString(), layout.offsetX + layout.boardWidth - layout.gridSize * 0.5, pos.y);
      }
    }

    // Draw hint if enabled
    if (showHint && hintCoords) {
      const pos = gridToCanvas(layout, hintCoords[0], hintCoords[1]);
      ctx.fillStyle = "rgba(74, 222, 128, 0.5)"; // Green hint
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, layout.gridSize * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }

    // Draw stones
    const stoneSize = layout.gridSize * 0.505;
    stones.forEach(stone => {
      const pos = gridToCanvas(layout, stone.coords[0], stone.coords[1]);
      const img = stone.player === 'B' ? imagesRef.current.blackStone : imagesRef.current.whiteStone;

      if (img) {
        ctx.drawImage(img, pos.x - stoneSize, pos.y - stoneSize, stoneSize * 2, stoneSize * 2);
      } else {
        // Fallback circle
        ctx.fillStyle = stone.player === 'B' ? '#1a1a1a' : '#f5f5f5';
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, stoneSize * 0.95, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = stone.player === 'B' ? '#000' : '#ccc';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    // Draw move numbers if enabled and we have move history
    if (showMoveNumbers && moveHistory.length > 0) {
      ctx.font = `bold ${Math.max(12, layout.gridSize * 0.45)}px 'IBM Plex Mono', monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      moveHistory.forEach((move, index) => {
        // Only draw number if stone still exists on the board (not captured)
        const stoneExists = stones.some(s =>
          s.coords[0] === move.coords[0] &&
          s.coords[1] === move.coords[1] &&
          s.player === move.player
        );
        if (!stoneExists) return;

        // Only draw if this is the latest move at this position
        // (handles case where a captured position is replayed)
        const hasLaterMoveAtSamePosition = moveHistory.slice(index + 1).some(laterMove =>
          laterMove.coords[0] === move.coords[0] &&
          laterMove.coords[1] === move.coords[1]
        );
        if (hasLaterMoveAtSamePosition) return;

        const pos = gridToCanvas(layout, move.coords[0], move.coords[1]);
        // Contrast color for visibility
        ctx.fillStyle = move.player === 'B' ? "rgba(255, 255, 255, 0.95)" : "rgba(0, 0, 0, 0.95)";
        ctx.fillText((index + 1).toString(), pos.x, pos.y);
      });
    } else if (lastMove) {
      // Draw last move indicator only when not showing move numbers
      const lastStone = stones.find(s => s.coords[0] === lastMove[0] && s.coords[1] === lastMove[1]);
      if (lastStone) {
        const pos = gridToCanvas(layout, lastMove[0], lastMove[1]);
        const circleRadius = layout.gridSize * 0.25;

        ctx.beginPath();
        ctx.arc(pos.x, pos.y, circleRadius, 0, Math.PI * 2);
        ctx.strokeStyle = lastStone.player === 'B' ? "rgba(255, 255, 255, 0.9)" : "rgba(0, 0, 0, 0.9)";
        ctx.lineWidth = Math.max(2, layout.gridSize * 0.08);
        ctx.stroke();
      }
    }

    // Draw disabled overlay
    if (disabled) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.15)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    // Draw wrong/extra-stone markers LAST (on top of everything): a bold red ✕ over each flagged
    // intersection. The physical LED under such a stone is occluded by the stone itself, so this
    // screen cue is the reliable "take this one off" signal.
    if (extraMarkers.length > 0) {
      const arm = layout.gridSize * 0.34;
      ctx.strokeStyle = "rgba(220, 38, 38, 0.95)"; // red
      ctx.lineWidth = Math.max(3, layout.gridSize * 0.12);
      ctx.lineCap = "round";
      extraMarkers.forEach(([x, y]) => {
        const pos = gridToCanvas(layout, x, y);
        ctx.beginPath();
        ctx.moveTo(pos.x - arm, pos.y - arm);
        ctx.lineTo(pos.x + arm, pos.y + arm);
        ctx.moveTo(pos.x + arm, pos.y - arm);
        ctx.lineTo(pos.x - arm, pos.y + arm);
        ctx.stroke();
      });
    }
  }, [boardSize, stones, lastMove, hintCoords, showHint, disabled, imagesLoaded, boardLayout, gridToCanvas, moveHistory, showMoveNumbers, showCoordinates, extraMarkers]);

  // Re-render on state changes
  useEffect(() => {
    renderBoard();
  }, [renderBoard, canvasSize]);

  // Handle click
  const handleClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (disabled) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    const layout = boardLayout(canvas);
    const relX = (x - layout.offsetX) / layout.gridSize - layout.gridMargins.x[0];
    const relY = (y - layout.offsetY) / layout.gridSize - layout.gridMargins.y[1];
    const gridX = Math.round(relX);
    const invertedY = Math.round(relY);
    const gridY = boardSize - 1 - invertedY;

    if (gridX >= 0 && gridX < boardSize && gridY >= 0 && gridY < boardSize) {
      onPlaceStone(gridX, gridY);
    }
  }, [boardSize, disabled, onPlaceStone, boardLayout]);

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: showCoordinates ? '4px' : 0
      }}
    >
      <canvas
        ref={canvasRef}
        width={canvasSize}
        height={canvasSize}
        onClick={handleClick}
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          display: 'block',
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          cursor: disabled ? 'default' : 'pointer'
        }}
      />
    </Box>
  );
};

export default TsumegoBoard;
