import React, { useEffect, useRef, useState } from 'react';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface BoardProps {
  gameState: GameState;
  onMove: (x: number, y: number) => void;
  onNavigate?: (nodeId: number) => void;
  analysisToggles: Record<string, boolean>;
}

const ASSETS = {
  board: "/assets/img/board.png",
  blackStone: "/assets/img/B_stone.png",
  whiteStone: "/assets/img/W_stone.png",
  lastMove: "/assets/img/inner.png",
  topMove: "/assets/img/topmove.png",
};

const EVAL_COLORS = [
  "rgba(150, 50, 140, 0.85)", // Purple > 12 (blunder)
  "rgba(225, 107, 92, 0.85)",  // Red > 6 (big mistake)
  "rgba(212, 165, 116, 0.85)", // Warm orange > 3 (mistake)
  "rgba(232, 200, 100, 0.85)", // Yellow > 1.5 (inaccuracy)
  "rgba(171, 200, 100, 0.85)", // Light Green > 0.5 (ok)
  "rgba(74, 107, 92, 0.85)",   // Jade green <= 0.5 (excellent)
];

const Board: React.FC<BoardProps> = ({ gameState, onMove, onNavigate, analysisToggles }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imagesRef = useRef<Record<string, HTMLImageElement>>({});
  const [canvasSize, setCanvasSize] = useState(800);
  const { t } = useTranslation();

  // Translate game result
  const translateResult = (result: string): string => {
    if (result.includes('W+R')) return t('game:white_wins_resign', 'White wins by resignation');
    if (result.includes('B+R')) return t('game:black_wins_resign', 'Black wins by resignation');
    if (result.includes('W+T')) return t('game:white_wins_timeout', 'White wins by timeout');
    if (result.includes('B+T')) return t('game:black_wins_timeout', 'Black wins by timeout');
    if (result.match(/W\+[\d.]+/)) return result.replace(/W\+([\d.]+)/, (_, n) => t('game:white_wins_points', `White wins by ${n} points`).replace('{n}', n));
    if (result.match(/B\+[\d.]+/)) return result.replace(/B\+([\d.]+)/, (_, n) => t('game:black_wins_points', `Black wins by ${n} points`).replace('{n}', n));
    return result;
  };

  useEffect(() => {
    const loadImages = async () => {
      const entries = Object.entries(ASSETS);
      await Promise.all(
        entries.map(
          ([key, src]) =>
            new Promise<void>((resolve, reject) => {
              const img = new Image();
              img.onload = () => {
                imagesRef.current[key] = img;
                resolve();
              };
              img.onerror = () => reject(new Error(`Failed to load ${src}`));
              img.src = src;
            })
        )
      );
      renderBoard();
    };
    loadImages();
  }, []);

  // Track container size for responsive canvas
  useEffect(() => {
    const updateCanvasSize = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        // Use the smaller dimension to keep the board square, minus padding
        // Also cap at window height to handle cross-monitor DPI differences
        const maxSize = Math.min(width, height, window.innerHeight - 100);
        const size = Math.floor(maxSize - 8);
        // Clamp between 400 and 1200 for reasonable bounds
        setCanvasSize(Math.max(400, Math.min(1200, size)));
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
  }, []);

  // Add a ref for animation time
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  // Hover position for ghost stone preview
  const hoverPosRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const animate = () => {
      renderBoard();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [gameState, analysisToggles, canvasSize]);

  const boardLayout = (canvas: HTMLCanvasElement, boardSize: number) => {
    const gridMargins = { x: [1.5, 1.5], y: [1.5, 1.5] }; // Symmetric: Left/Right, Bottom/Top
    const xGridSpaces = boardSize - 1 + gridMargins.x[0] + gridMargins.x[1];
    const yGridSpaces = boardSize - 1 + gridMargins.y[0] + gridMargins.y[1];
    const gridSize = Math.floor(Math.min(canvas.width / xGridSpaces, canvas.height / yGridSpaces));
    const boardWidth = xGridSpaces * gridSize;
    const boardHeight = yGridSpaces * gridSize;
    const offsetX = Math.round((canvas.width - boardWidth) / 2);
    const offsetY = Math.round((canvas.height - boardHeight) / 2);
    return { gridMargins, gridSize, boardWidth, boardHeight, offsetX, offsetY };
  };

  const gridToCanvas = (layout: any, x: number, y: number, boardSize: number) => {
    const invertedY = boardSize - 1 - y;
    const px = layout.offsetX + (layout.gridMargins.x[0] + x) * layout.gridSize;
    const py = layout.offsetY + (layout.gridMargins.y[1] + invertedY) * layout.gridSize;
    return { x: px, y: py };
  };

  const getEvalClass = (scoreLoss: number) => {
    const thresholds = [12, 6, 3, 1.5, 0.5, 0];
    for (let i = 0; i < thresholds.length; i++) {
      if (scoreLoss >= thresholds[i]) return i;
    }
    return 5;
  };

  const renderBoard = () => {
    const canvas = canvasRef.current;
    if (!canvas || !gameState) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const boardSize = gameState.board_size[0];
    const layout = boardLayout(canvas, boardSize);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    if (imagesRef.current.board) {
      ctx.drawImage(imagesRef.current.board, layout.offsetX, layout.offsetY, layout.boardWidth, layout.boardHeight);
    }

    // Grid, Stars, Coordinates
    drawGrid(ctx, layout, boardSize);
    drawStars(ctx, layout, boardSize);
    if (analysisToggles.coords) {
      drawCoordinates(ctx, layout, boardSize);
    }

    // ... Ownership, Policy, Hints ...
    if (analysisToggles.ownership && gameState.analysis?.ownership) {
      // ... same as before ...
      const ownership = gameState.analysis.ownership;
      for (let y = 0; y < boardSize; y++) {
        for (let x = 0; x < boardSize; x++) {
          const val = ownership[y][x];
          if (Math.abs(val) > 0.05) {
            const pos = gridToCanvas(layout, x, y, boardSize);
            const alpha = Math.abs(val) * 0.4;
            ctx.fillStyle = val > 0 ? `rgba(0,0,0,${alpha})` : `rgba(255,255,255,${alpha})`;
            ctx.fillRect(pos.x - layout.gridSize / 2, pos.y - layout.gridSize / 2, layout.gridSize, layout.gridSize);
          }
        }
      }
    }

    // Policy Heatmap
    if (analysisToggles.policy && gameState.analysis?.policy) {
      const policy = gameState.analysis.policy;
      for (let y = 0; y < boardSize; y++) {
        for (let x = 0; x < boardSize; x++) {
          const prob = policy[y][x];
          if (prob > 0.001) {
            const pos = gridToCanvas(layout, x, y, boardSize);
            const polOrder = Math.max(0, 5 + Math.floor(Math.log10(Math.max(1e-9, prob - 1e-9))));
            ctx.fillStyle = EVAL_COLORS[polOrder].replace("0.8", "0.5");
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, layout.gridSize * 0.3, 0, Math.PI * 2);
            ctx.fill();
            
            if (prob > 0.01) {
              ctx.fillStyle = polOrder >= 3 ? "black" : "white";
              ctx.font = `${Math.max(6, layout.gridSize * 0.2)}px sans-serif`;
              ctx.fillText(`${(prob * 100).toFixed(0)}%`, pos.x, pos.y);
            }
          }
        }
      }
    }

    // Hints (Top Moves)
    if (analysisToggles.hints && gameState.analysis?.moves) {
      const moves = gameState.analysis.moves;
      const maxMoves = gameState.trainer_settings?.max_top_moves_on_board || 3;
      const time = (Date.now() - startTimeRef.current) / 1000; // time in seconds
      
      moves.slice(0, maxMoves).forEach((move: any, index: number) => {
        if (!move.coords) return;
        const pos = gridToCanvas(layout, move.coords[0], move.coords[1], boardSize);
        const evalClass = getEvalClass(move.scoreLoss);
        const color = EVAL_COLORS[evalClass];
        const radius = layout.gridSize * 0.42;

        // Premium Radial Gradient for the stone
        const grad = ctx.createRadialGradient(pos.x - radius * 0.3, pos.y - radius * 0.3, radius * 0.1, pos.x, pos.y, radius);
        grad.addColorStop(0, color.replace("0.85", "0.95")); // Highlight spot
        grad.addColorStop(1, color.replace("0.85", "1.0"));  // Base color
        ctx.fillStyle = grad;
        
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fill();

        // Best move highlight - Dynamic Pulsing Ring
        if (index === 0) {
          const pulse = Math.sin(time * 3) * 0.5 + 0.5; // 0 to 1 pulse
          
          // Layer 1: Core White Ring
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.8 + pulse * 0.2})`;
          ctx.lineWidth = Math.max(2.5, layout.gridSize * 0.08);
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, radius + 1, 0, Math.PI * 2);
          ctx.stroke();
          
          // Layer 2: Outer Glow
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.2 + pulse * 0.2})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, radius + 3 + pulse * 2, 0, Math.PI * 2);
          ctx.stroke();

          // Layer 3: Soft Wide Aura
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.05 + pulse * 0.05})`;
          ctx.lineWidth = 6;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, radius + 6 + pulse * 4, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Text - Two lines
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        // Precise Contrast Logic
        const isDarkBg = evalClass <= 2 || evalClass === 5;
        const mainTextColor = isDarkBg ? "rgba(255, 255, 255, 0.95)" : "rgba(0, 0, 0, 0.95)";
        const secondaryTextColor = isDarkBg ? "rgba(255, 255, 255, 0.85)" : "rgba(0, 0, 0, 0.85)";
        
        // Consistent font size for balance
        const fontSize = Math.max(7, layout.gridSize * 0.28);

        // Top line: Winrate (Monospace for precision)
        ctx.font = `bold ${fontSize}px 'IBM Plex Mono', monospace`;
        ctx.fillStyle = mainTextColor;
        const winrateText = (move.winrate * 100).toFixed(1);
        ctx.fillText(winrateText, pos.x, pos.y - layout.gridSize * 0.12);

        // Bottom line: Visits (Sans-serif for reference)
        ctx.font = `600 ${fontSize}px 'Manrope', sans-serif`;
        ctx.fillStyle = secondaryTextColor;
        const visitsText = move.visits >= 1000 ? `${(move.visits / 1000).toFixed(1)}k` : move.visits.toString();
        ctx.fillText(visitsText, pos.x, pos.y + layout.gridSize * 0.18);
      });
    }

    // Stones
    const stoneSize = layout.gridSize * 0.505;
    gameState.stones.forEach(([player, coords, scoreLoss, moveNumber], index) => {
      if (!coords) return;
      const pos = gridToCanvas(layout, coords[0], coords[1], boardSize);
      const img = player === "B" ? imagesRef.current.blackStone : imagesRef.current.whiteStone;
      if (img) ctx.drawImage(img, pos.x - stoneSize, pos.y - stoneSize, stoneSize * 2, stoneSize * 2);

      // Move numbers for all stones
      if (analysisToggles.numbers) {
        ctx.fillStyle = player === "B" ? "white" : "black";
        // Larger font size for better readability
        ctx.font = `bold ${Math.max(11, layout.gridSize * 0.38)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        // Use the actual move number from backend if available, fallback to index+1
        const numToDisplay = moveNumber !== null && moveNumber !== undefined ? moveNumber : index + 1;
        // Center the text on the stone consistently for all moves
        ctx.fillText(numToDisplay.toString(), pos.x, pos.y);
      }

      // Eval dots
      if (analysisToggles.eval && scoreLoss !== null && scoreLoss !== undefined) {
        const evalClass = getEvalClass(scoreLoss);
        const color = EVAL_COLORS[evalClass];
        const dotRadius = layout.gridSize * 0.15;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, dotRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.5)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    // Ghost Stones
    if (analysisToggles.children && gameState.ghost_stones) {
      ctx.globalAlpha = 0.5;
      gameState.ghost_stones.forEach(([player, coords]) => {
        if (!coords) return;
        const pos = gridToCanvas(layout, coords[0], coords[1], boardSize);
        const img = player === "B" ? imagesRef.current.blackStone : imagesRef.current.whiteStone;
        if (img) ctx.drawImage(img, pos.x - stoneSize, pos.y - stoneSize, stoneSize * 2, stoneSize * 2);
      });
      ctx.globalAlpha = 1.0;
    }

    // Last Move
    if (gameState.last_move) {
      const pos = gridToCanvas(layout, gameState.last_move[0], gameState.last_move[1], boardSize);
      const lastStone = gameState.stones.find(s => s[1] && s[1][0] === gameState.last_move![0] && s[1][1] === gameState.last_move![1]);
      const lastPlayer = lastStone ? lastStone[0] : null;

      const circleRadius = layout.gridSize * 0.35;

      // Outer glow for emphasis
      ctx.shadowColor = lastPlayer === "B" ? "rgba(255, 255, 255, 0.4)" : "rgba(0, 0, 0, 0.4)";
      ctx.shadowBlur = 8;

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, circleRadius, 0, Math.PI * 2);
      ctx.strokeStyle = lastPlayer === "B" ? "rgba(255, 255, 255, 0.95)" : "rgba(0, 0, 0, 0.95)";
      ctx.lineWidth = Math.max(2.5, layout.gridSize * 0.09);
      ctx.stroke();

      // Reset shadow
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
    }

    // Hover ghost stone preview
    if (hoverPosRef.current && !gameState.end_result) {
      const { x: hx, y: hy } = hoverPosRef.current;
      if (hx >= 0 && hx < boardSize && hy >= 0 && hy < boardSize) {
        // Check if position is empty
        const occupied = gameState.stones.some(s => s[1] && s[1][0] === hx && s[1][1] === hy);
        if (!occupied) {
          const ghostColor = gameState.player_to_move === 'W' ? 'W' : 'B';
          const pos = gridToCanvas(layout, hx, hy, boardSize);
          ctx.save();
          ctx.globalAlpha = 0.5;
          const img = ghostColor === 'B' ? imagesRef.current.blackStone : imagesRef.current.whiteStone;
          if (img) {
            ctx.drawImage(img, pos.x - stoneSize, pos.y - stoneSize, stoneSize * 2, stoneSize * 2);
          } else {
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, stoneSize * 0.95, 0, Math.PI * 2);
            ctx.fillStyle = ghostColor === 'B' ? '#000' : '#fff';
            ctx.fill();
          }
          ctx.restore();
        }
      }
    }

    // Game End Result
    if (gameState.end_result) {
      const centerX = layout.offsetX + layout.boardWidth / 2;
      const centerY = layout.offsetY + layout.boardHeight / 2;

      // Overlay
      ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Text
      ctx.fillStyle = "white";
      const fontSize = layout.gridSize * 1.2;
      ctx.font = `bold ${fontSize}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const translatedResult = translateResult(gameState.end_result);
      const lines = translatedResult.split('\n');
      if (lines.length > 1) {
        lines.forEach((line, i) => {
          ctx.fillText(line, centerX, centerY + (i - (lines.length - 1) / 2) * fontSize * 1.2);
        });
      } else {
        ctx.fillText(translatedResult, centerX, centerY);
      }
    }
  };

  // Helper draw functions
  const drawGrid = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    ctx.strokeStyle = "rgba(0, 0, 0, 0.7)";
    ctx.lineWidth = 1.2;
    ctx.lineCap = "round";

    for (let i = 0; i < boardSize; i++) {
      const start = gridToCanvas(layout, i, 0, boardSize);
      const end = gridToCanvas(layout, i, boardSize - 1, boardSize);
      ctx.beginPath();
      ctx.moveTo(Math.round(start.x) + 0.5, Math.round(start.y) + 0.5);
      ctx.lineTo(Math.round(end.x) + 0.5, Math.round(end.y) + 0.5);
      ctx.stroke();
    }
    for (let j = 0; j < boardSize; j++) {
      const start = gridToCanvas(layout, 0, j, boardSize);
      const end = gridToCanvas(layout, boardSize - 1, j, boardSize);
      ctx.beginPath();
      ctx.moveTo(Math.round(start.x) + 0.5, Math.round(start.y) + 0.5);
      ctx.lineTo(Math.round(end.x) + 0.5, Math.round(end.y) + 0.5);
      ctx.stroke();
    }
  };

  const drawStars = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    const stars = boardSize === 19 ? [3, 9, 15] : boardSize === 13 ? [3, 6, 9] : boardSize === 9 ? [2, 4, 6] : [];
    ctx.fillStyle = "rgba(0, 0, 0, 0.85)";
    const starRadius = layout.gridSize * 0.11;
    stars.forEach(x => stars.forEach(y => {
      const pos = gridToCanvas(layout, x, y, boardSize);
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, starRadius, 0, Math.PI * 2);
      ctx.fill();
    }));
  };

  const drawCoordinates = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    const letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ".split("");
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
  };


  const canvasToGridPos = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    const boardSize = gameState.board_size[0];
    const layout = boardLayout(canvas, boardSize);
    const relX = (x - layout.offsetX) / layout.gridSize - layout.gridMargins.x[0];
    const relY = (y - layout.offsetY) / layout.gridSize - layout.gridMargins.y[1];
    const gridX = Math.round(relX);
    const invertedY = Math.round(relY);
    const gridY = boardSize - 1 - invertedY;
    if (gridX >= 0 && gridX < boardSize && gridY >= 0 && gridY < boardSize) {
      return { x: gridX, y: gridY };
    }
    return null;
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = canvasToGridPos(event);
    hoverPosRef.current = pos;
  };

  const handleMouseLeave = () => {
    hoverPosRef.current = null;
  };

  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    const boardSize = gameState.board_size[0];
    const layout = boardLayout(canvas, boardSize);
    const relX = (x - layout.offsetX) / layout.gridSize - layout.gridMargins.x[0];
    const relY = (y - layout.offsetY) / layout.gridSize - layout.gridMargins.y[1];
    const gridX = Math.round(relX);
    const invertedY = Math.round(relY);
    const gridY = boardSize - 1 - invertedY;

    if (gridX >= 0 && gridX < boardSize && gridY >= 0 && gridY < boardSize) {
      // Check for existing stone
      const clickedStone = gameState.stones.find(s => s[1] && s[1][0] === gridX && s[1][1] === gridY);
      
      if (clickedStone && onNavigate) {
        const moveNumber = clickedStone[3];
        if (moveNumber !== null && moveNumber !== undefined) {
          // moveNumber corresponds to history index
          if (moveNumber >= 0 && moveNumber < gameState.history.length) {
            const nodeId = gameState.history[moveNumber].node_id;
            onNavigate(nodeId);
          }
        }
      } else {
        onMove(gridX, gridY);
      }
    }
  };

  return (
    <div
      ref={containerRef}
      style={{
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
        onClick={handleCanvasClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          borderRadius: '4px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 80px rgba(212, 165, 116, 0.05)',
          cursor: 'pointer'
        }}
      />
    </div>
  );
};

export default Board;
