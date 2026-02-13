/**
 * useAiSolverBoard: Manages board state for the AI Tsumego Solver feature.
 * Handles stone placement, region drawing, and KataGo analysis API calls.
 */
import { useState, useCallback } from 'react';
import { API } from '../../api';

// ── Types ──

export type AiSolverTool = 'placeBlack' | 'placeWhite' | 'alternate' | 'delete' | 'drawRect' | null;
export type AnalysisDepth = 'quick' | 'standard' | 'deep';

export interface AiSolverStone {
  color: 'B' | 'W';
  x: number;
  y: number;
}

export interface UseAiSolverBoardReturn {
  // State
  stones: AiSolverStone[];
  boardSize: number;
  activeTool: AiSolverTool;
  playerToMove: 'B' | 'W';
  region: { x1: number; y1: number; x2: number; y2: number } | null;
  analysisResult: any | null;
  isAnalyzing: boolean;
  analysisError: string | null;
  analysisDepth: AnalysisDepth;

  // Actions
  handleIntersectionClick: (x: number, y: number) => void;
  handleClear: () => void;
  clearRegion: () => void;
  setRegion: (region: { x1: number; y1: number; x2: number; y2: number } | null) => void;
  setActiveTool: (tool: AiSolverTool) => void;
  setPlayerToMove: (p: 'B' | 'W') => void;
  setBoardSize: (size: number) => void;
  setAnalysisDepth: (depth: AnalysisDepth) => void;
  getEffectiveRegion: () => { x1: number; y1: number; x2: number; y2: number } | null;
  startAnalysis: () => Promise<void>;
}

// ── Constants ──

const DEPTH_VISITS: Record<AnalysisDepth, number> = {
  quick: 200,
  standard: 500,
  deep: 2000,
};

const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';

function coordToStr(x: number, y: number): string {
  return letters[x] + (y + 1);
}

// ── Hook ──

export function useAiSolverBoard(): UseAiSolverBoardReturn {
  const [stones, setStones] = useState<AiSolverStone[]>([]);
  const [boardSize, setBoardSize] = useState(19);
  const [activeTool, setActiveTool] = useState<AiSolverTool>('placeBlack');
  const [playerToMove, setPlayerToMove] = useState<'B' | 'W'>('B');
  const [region, setRegion] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisDepth, setAnalysisDepth] = useState<AnalysisDepth>('standard');

  // ── Board actions ──

  const handleIntersectionClick = useCallback((x: number, y: number) => {
    if (activeTool === 'placeBlack') {
      setStones((prev) => {
        const filtered = prev.filter((s) => !(s.x === x && s.y === y));
        return [...filtered, { color: 'B', x, y }];
      });
    } else if (activeTool === 'placeWhite') {
      setStones((prev) => {
        const filtered = prev.filter((s) => !(s.x === x && s.y === y));
        return [...filtered, { color: 'W', x, y }];
      });
    } else if (activeTool === 'alternate') {
      setStones((prev) => {
        const lastStone = prev.length > 0 ? prev[prev.length - 1] : null;
        const color: 'B' | 'W' = lastStone ? (lastStone.color === 'B' ? 'W' : 'B') : 'B';
        const filtered = prev.filter((s) => !(s.x === x && s.y === y));
        return [...filtered, { color, x, y }];
      });
    } else if (activeTool === 'delete') {
      setStones((prev) => prev.filter((s) => !(s.x === x && s.y === y)));
    }
    // drawRect and null: do nothing
  }, [activeTool]);

  const handleClear = useCallback(() => {
    setStones([]);
    setRegion(null);
    setAnalysisResult(null);
    setAnalysisError(null);
  }, []);

  const clearRegion = useCallback(() => {
    setRegion(null);
  }, []);

  // ── Region computation ──

  const autoComputeRegion = useCallback((): { x1: number; y1: number; x2: number; y2: number } | null => {
    if (stones.length === 0) return null;

    let minX = stones[0].x;
    let maxX = stones[0].x;
    let minY = stones[0].y;
    let maxY = stones[0].y;

    for (const stone of stones) {
      if (stone.x < minX) minX = stone.x;
      if (stone.x > maxX) maxX = stone.x;
      if (stone.y < minY) minY = stone.y;
      if (stone.y > maxY) maxY = stone.y;
    }

    return {
      x1: Math.max(0, minX - 1),
      y1: Math.max(0, minY - 1),
      x2: Math.min(boardSize - 1, maxX + 1),
      y2: Math.min(boardSize - 1, maxY + 1),
    };
  }, [stones, boardSize]);

  const getEffectiveRegion = useCallback((): { x1: number; y1: number; x2: number; y2: number } | null => {
    return region ?? autoComputeRegion();
  }, [region, autoComputeRegion]);

  // ── Analysis ──

  const startAnalysis = useCallback(async () => {
    if (stones.length === 0) {
      setAnalysisError('请先摆放棋子');
      return;
    }

    const initialStones = stones.map((s) => [s.color, coordToStr(s.x, s.y)]);

    const effectiveRegion = region ?? autoComputeRegion();
    let kataGoRegion: { x1: number; y1: number; x2: number; y2: number } | null = null;
    if (effectiveRegion) {
      kataGoRegion = {
        x1: effectiveRegion.x1,
        y1: boardSize - 1 - effectiveRegion.y2,
        x2: effectiveRegion.x2,
        y2: boardSize - 1 - effectiveRegion.y1,
      };
    }

    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);

    try {
      const result = await API.tsumegoSolve({
        initial_stones: initialStones,
        board_size: boardSize,
        max_visits: DEPTH_VISITS[analysisDepth],
        player_to_move: playerToMove,
        region: kataGoRegion,
      });
      setAnalysisResult(result);
    } catch (error: any) {
      const message = error?.message ?? String(error);
      setAnalysisError('分析失败: ' + message);
    } finally {
      setIsAnalyzing(false);
    }
  }, [stones, boardSize, analysisDepth, playerToMove, region, autoComputeRegion]);

  return {
    // State
    stones,
    boardSize,
    activeTool,
    playerToMove,
    region,
    analysisResult,
    isAnalyzing,
    analysisError,
    analysisDepth,

    // Actions
    handleIntersectionClick,
    handleClear,
    clearRegion,
    setRegion,
    setActiveTool,
    setPlayerToMove,
    setBoardSize,
    setAnalysisDepth,
    getEffectiveRegion,
    startAnalysis,
  };
}
