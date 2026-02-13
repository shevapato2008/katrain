import { useEffect, useRef, useCallback, useState } from 'react';
import { Box } from '@mui/material';
import LiveBoard, { type AiMoveMarker } from '../live/LiveBoard';
import {
  calculateBoardLayout,
  gridToCanvas,
  canvasToGrid,
} from '../../../components/board/boardUtils';
import type { AiSolverStone, AiSolverTool } from '../../hooks/useAiSolverBoard';

interface AiSolverBoardProps {
  stones: AiSolverStone[];
  boardSize: number;
  activeTool: AiSolverTool;
  region: { x1: number; y1: number; x2: number; y2: number } | null;
  effectiveRegion: { x1: number; y1: number; x2: number; y2: number } | null;
  onIntersectionClick: (x: number, y: number) => void;
  onRegionChange: (region: { x1: number; y1: number; x2: number; y2: number }) => void;
  aiMarkers?: AiMoveMarker[] | null;
  pvMoves?: string[] | null;
  showAiMarkers?: boolean;
}

export default function AiSolverBoard({
  stones,
  boardSize,
  activeTool,
  region,
  effectiveRegion,
  onIntersectionClick,
  onRegionChange,
  aiMarkers,
  pvMoves,
  showAiMarkers = true,
}: AiSolverBoardProps) {
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState(600);

  // Rectangle drag state
  const dragRef = useRef<{
    isDragging: boolean;
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
  }>({ isDragging: false, startX: 0, startY: 0, currentX: 0, currentY: 0 });

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
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Convert stones to LiveBoard moves/colors format
  const moves = stones.map((s) => {
    const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
    return `${letters[s.x]}${s.y + 1}`;
  });
  const stoneColors = stones.map((s) => s.color);

  // Determine next color for ghost stone based on active tool
  const nextColor = activeTool === 'placeBlack' ? 'B' as const
    : activeTool === 'placeWhite' ? 'W' as const
    : activeTool === 'alternate' ? (stones.length > 0 ? (stones[stones.length - 1].color === 'B' ? 'W' as const : 'B' as const) : 'B' as const)
    : undefined;

  // Draw overlay (region rectangles)
  const drawOverlay = useCallback(() => {
    const canvas = overlayRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);

    // Helper: draw a region rectangle
    const drawRegionRect = (
      r: { x1: number; y1: number; x2: number; y2: number },
      strokeColor: string,
      lineWidth: number,
      dash: number[],
    ) => {
      const topLeft = gridToCanvas(layout, r.x1, r.y2, boardSize); // y2 is top in board coords
      const bottomRight = gridToCanvas(layout, r.x2, r.y1, boardSize); // y1 is bottom
      const halfGrid = layout.gridSize * 0.5;

      ctx.save();
      ctx.setLineDash(dash);
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = lineWidth;
      ctx.strokeRect(
        topLeft.x - halfGrid,
        topLeft.y - halfGrid,
        (bottomRight.x - topLeft.x) + layout.gridSize,
        (bottomRight.y - topLeft.y) + layout.gridSize,
      );
      ctx.restore();
    };

    // Draw auto-region (dashed gray) when no manual region and stones exist
    if (!region && effectiveRegion) {
      drawRegionRect(effectiveRegion, 'rgba(150, 150, 150, 0.6)', 2, [6, 4]);
    }

    // Draw manual region (solid blue)
    if (region) {
      drawRegionRect(region, 'rgba(66, 133, 244, 0.9)', 2.5, []);
    }

    // Draw drag preview (dashed blue)
    if (dragRef.current.isDragging) {
      const { startX, startY, currentX, currentY } = dragRef.current;
      const previewRegion = {
        x1: Math.min(startX, currentX),
        y1: Math.min(startY, currentY),
        x2: Math.max(startX, currentX),
        y2: Math.max(startY, currentY),
      };
      drawRegionRect(previewRegion, 'rgba(66, 133, 244, 0.7)', 2, [5, 3]);
    }
  }, [canvasSize, boardSize, region, effectiveRegion]);

  // Redraw overlay when dependencies change
  useEffect(() => {
    drawOverlay();
  }, [drawOverlay, stones]);

  // Mouse handlers for rectangle drawing
  const getGridFromMouse = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = overlayRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvasSize / rect.width;
    const scaleY = canvasSize / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;
    const layout = calculateBoardLayout(canvasSize, canvasSize, boardSize);
    return canvasToGrid(layout, mx, my, boardSize);
  }, [canvasSize, boardSize]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (activeTool !== 'drawRect') return;
    const pos = getGridFromMouse(e);
    if (pos) {
      dragRef.current = { isDragging: true, startX: pos.x, startY: pos.y, currentX: pos.x, currentY: pos.y };
      drawOverlay();
    }
  }, [activeTool, getGridFromMouse, drawOverlay]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!dragRef.current.isDragging) return;
    const pos = getGridFromMouse(e);
    if (pos) {
      dragRef.current.currentX = pos.x;
      dragRef.current.currentY = pos.y;
      drawOverlay();
    }
  }, [getGridFromMouse, drawOverlay]);

  const handleMouseUp = useCallback(() => {
    if (!dragRef.current.isDragging) return;
    const { startX, startY, currentX, currentY } = dragRef.current;
    dragRef.current.isDragging = false;

    const newRegion = {
      x1: Math.min(startX, currentX),
      y1: Math.min(startY, currentY),
      x2: Math.max(startX, currentX),
      y2: Math.max(startY, currentY),
    };
    onRegionChange(newRegion);
  }, [onRegionChange]);

  const isRectMode = activeTool === 'drawRect';

  return (
    <Box
      ref={containerRef}
      sx={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <LiveBoard
        moves={moves}
        stoneColors={stoneColors}
        currentMove={stones.length}
        boardSize={boardSize}
        showCoordinates={true}
        onIntersectionClick={isRectMode ? undefined : onIntersectionClick}
        nextColor={nextColor}
        aiMarkers={aiMarkers}
        showAiMarkers={showAiMarkers}
        pvMoves={pvMoves}
      />
      <canvas
        ref={overlayRef}
        width={canvasSize}
        height={canvasSize}
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          maxWidth: '100%',
          maxHeight: '100%',
          pointerEvents: isRectMode ? 'auto' : 'none',
          cursor: isRectMode ? 'crosshair' : 'default',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
    </Box>
  );
}
