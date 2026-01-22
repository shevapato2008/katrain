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
        // Use the smaller dimension to keep the board square, minus padding
        const size = Math.floor(Math.min(width, height) - 8);
        // Clamp between 400 and 1200 for reasonable bounds (matching main Board component)
        setCanvasSize(Math.max(400, Math.min(1200, size)));
      }
    };

    updateCanvasSize();
    const resizeObserver = new ResizeObserver(updateCanvasSize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    return () => resizeObserver.disconnect();
  }, []);

  // Board layout calculations
  const boardLayout = useCallback((canvas: HTMLCanvasElement) => {
    const gridMargins = { x: [1.5, 1.5], y: [1.5, 1.5] };
    const xGridSpaces = boardSize - 1 + gridMargins.x[0] + gridMargins.x[1];
    const yGridSpaces = boardSize - 1 + gridMargins.y[0] + gridMargins.y[1];
    const gridSize = Math.floor(Math.min(canvas.width / xGridSpaces, canvas.height / yGridSpaces));
    const boardWidth = xGridSpaces * gridSize;
    const boardHeight = yGridSpaces * gridSize;
    const offsetX = Math.round((canvas.width - boardWidth) / 2);
    const offsetY = Math.round((canvas.height - boardHeight) / 2);
    return { gridMargins, gridSize, boardWidth, boardHeight, offsetX, offsetY };
  }, [boardSize]);

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

    // Draw last move indicator
    if (lastMove) {
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
  }, [boardSize, stones, lastMove, hintCoords, showHint, disabled, imagesLoaded, boardLayout, gridToCanvas]);

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
        padding: '4px'
      }}
    >
      <canvas
        ref={canvasRef}
        width={canvasSize}
        height={canvasSize}
        onClick={handleClick}
        style={{
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          cursor: disabled ? 'default' : 'pointer'
        }}
      />
    </Box>
  );
};

export default TsumegoBoard;
