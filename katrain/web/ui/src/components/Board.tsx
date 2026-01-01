import React, { useEffect, useRef } from 'react';
import { type GameState } from '../api';

interface BoardProps {
  gameState: GameState;
  onMove: (x: number, y: number) => void;
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
  "rgba(114, 33, 107, 0.8)", // Purple > 12
  "rgba(204, 0, 0, 0.8)",     // Red > 6
  "rgba(230, 102, 25, 0.8)",   // Orange > 3
  "rgba(242, 242, 0, 0.8)",    // Yellow > 1.5
  "rgba(171, 230, 46, 0.8)",   // Light Green > 0.5
  "rgba(30, 150, 0, 0.8)",     // Green <= 0.5
];

const Board: React.FC<BoardProps> = ({ gameState, onMove, analysisToggles }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<Record<string, HTMLImageElement>>({});

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

  useEffect(() => {
    renderBoard();
  }, [gameState, analysisToggles]);

  const boardLayout = (canvas: HTMLCanvasElement, boardSize: number) => {
    const gridMargins = { x: [2.0, 0.5], y: [2.0, 0.5] }; // Left, Right, Bottom, Top
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
      
      moves.forEach((move: any, index: number) => {
        if (!move.coords) return;
        const pos = gridToCanvas(layout, move.coords[0], move.coords[1], boardSize);
        const evalClass = getEvalClass(move.scoreLoss);
        const color = EVAL_COLORS[evalClass];
        
        // Hint Circle
        const radius = layout.gridSize * 0.35;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fill();

        // Best move highlight
        if (index === 0 && imagesRef.current.topMove) {
          const topSize = layout.gridSize * 0.45;
          ctx.drawImage(imagesRef.current.topMove, pos.x - topSize, pos.y - topSize, topSize * 2, topSize * 2);
        }

        // Text
        ctx.fillStyle = evalClass >= 3 ? "black" : "white";
        ctx.font = `bold ${Math.max(8, layout.gridSize * 0.25)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const text = move.scoreLoss > 0.5 ? `-${move.scoreLoss.toFixed(1)}` : `${(move.winrate * 100).toFixed(0)}%`;
        ctx.fillText(text, pos.x, pos.y);
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
        ctx.font = `bold ${Math.max(8, layout.gridSize * 0.25)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        // Use the actual move number from backend if available, fallback to index+1
        const numToDisplay = moveNumber !== null && moveNumber !== undefined ? moveNumber : index + 1;
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

    // Children (Ghost Stones)
    if (analysisToggles.children && gameState.children) {
      ctx.globalAlpha = 0.5;
      gameState.children.forEach(([player, coords]) => {
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

      const circleRadius = layout.gridSize * 0.35; // SET SIZE HERE (0.35 * gridSize)
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, circleRadius, 0, Math.PI * 2);
      ctx.strokeStyle = lastPlayer === "B" ? "rgba(255,255,255,0.9)" : "rgba(0,0,0,0.9)";
      ctx.lineWidth = Math.max(2, layout.gridSize * 0.08);
      ctx.stroke();
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
      ctx.font = `bold ${layout.gridSize * 1.5}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(gameState.end_result, centerX, centerY);
    }
  };

  // Helper draw functions
  const drawGrid = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.lineWidth = 1;
    for (let i = 0; i < boardSize; i++) {
      const start = gridToCanvas(layout, i, 0, boardSize);
      const end = gridToCanvas(layout, i, boardSize - 1, boardSize);
      ctx.beginPath(); ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); ctx.stroke();
    }
    for (let j = 0; j < boardSize; j++) {
      const start = gridToCanvas(layout, 0, j, boardSize);
      const end = gridToCanvas(layout, boardSize - 1, j, boardSize);
      ctx.beginPath(); ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); ctx.stroke();
    }
  };

  const drawStars = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    const stars = boardSize === 19 ? [3, 9, 15] : boardSize === 13 ? [3, 6, 9] : boardSize === 9 ? [2, 4, 6] : [];
    ctx.fillStyle = "rgba(0,0,0,0.8)";
    const starRadius = layout.gridSize * 0.1;
    stars.forEach(x => stars.forEach(y => {
      const pos = gridToCanvas(layout, x, y, boardSize);
      ctx.beginPath(); ctx.arc(pos.x, pos.y, starRadius, 0, Math.PI * 2); ctx.fill();
    }));
  };

  const drawCoordinates = (ctx: CanvasRenderingContext2D, layout: any, boardSize: number) => {
    const letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ".split("");
    ctx.fillStyle = "rgba(0,0,0,0.8)";
    ctx.font = `bold ${Math.max(14, layout.gridSize * 0.6)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let i = 0; i < boardSize; i++) {
      const pos = gridToCanvas(layout, i, 0, boardSize);
      ctx.fillText(letters[i], pos.x, layout.offsetY + layout.boardHeight - layout.gridSize * 1.0);
    }
    for (let j = 0; j < boardSize; j++) {
      const pos = gridToCanvas(layout, 0, j, boardSize);
      ctx.fillText((j + 1).toString(), layout.offsetX + layout.gridSize * 1.0, pos.y);
    }
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
      onMove(gridX, gridY);
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <canvas
        ref={canvasRef}
        width={800}
        height={800}
        onClick={handleCanvasClick}
        style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
      />
    </div>
  );
};

export default Board;
