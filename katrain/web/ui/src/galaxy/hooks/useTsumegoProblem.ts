/**
 * Custom hook for managing tsumego problem solving logic
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  parseSGF,
  findChildMove,
  isCorrectPath,
  isSolutionComplete,
  getAIResponse,
  getValidMoves,
  sgfToCoords
} from '../../utils/sgfParser';
import type { SGFNode, ParsedSGF } from '../../utils/sgfParser';

export interface ProblemDetail {
  id: string;
  level: string;
  category: string;
  hint: string;
  boardSize: number;
  initialBlack: string[];
  initialWhite: string[];
  sgfContent: string;
}

export interface Stone {
  player: 'B' | 'W';
  coords: [number, number];
}

export interface MoveResult {
  type: 'correct' | 'incorrect' | 'solved' | 'continue';
  message?: string;
}

export interface TsumegoProblemState {
  // Problem data
  problem: ProblemDetail | null;
  loading: boolean;
  error: string | null;

  // Board state
  boardSize: number;
  stones: Stone[];
  lastMove: [number, number] | null;

  // Solving state
  currentNode: SGFNode | null;
  nextPlayer: 'B' | 'W';
  moveHistory: Stone[];
  isSolved: boolean;
  isFailed: boolean;

  // Timing
  startTime: number | null;
  elapsedTime: number;
  attempts: number;

  // Hint
  showHint: boolean;
  hintCoords: [number, number] | null;
}

export interface UseTsumegoProblemReturn extends TsumegoProblemState {
  // Actions
  placeStone: (x: number, y: number) => MoveResult | null;
  undo: () => void;
  reset: () => void;
  toggleHint: () => void;

  // Progress
  saveProgress: () => void;
}


export function useTsumegoProblem(problemId: string): UseTsumegoProblemReturn {
  // Problem data
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Parsed SGF
  const parsedSGFRef = useRef<ParsedSGF | null>(null);

  // Board state
  const [boardSize, setBoardSize] = useState(19);
  const [stones, setStones] = useState<Stone[]>([]);
  const [lastMove, setLastMove] = useState<[number, number] | null>(null);

  // Solving state
  const [currentNode, setCurrentNode] = useState<SGFNode | null>(null);
  const [nextPlayer, setNextPlayer] = useState<'B' | 'W'>('B');
  const [moveHistory, setMoveHistory] = useState<Stone[]>([]);
  const [isSolved, setIsSolved] = useState(false);
  const [isFailed, setIsFailed] = useState(false);

  // Timing
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [attempts, setAttempts] = useState(0);

  // Hint
  const [showHint, setShowHint] = useState(false);
  const [hintCoords, setHintCoords] = useState<[number, number] | null>(null);

  // Timer effect
  useEffect(() => {
    if (!startTime || isSolved || isFailed) return;

    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime, isSolved, isFailed]);

  // Fetch problem data
  useEffect(() => {
    if (!problemId) return;

    setLoading(true);
    setError(null);

    fetch(`/api/v1/tsumego/problems/${problemId}`)
      .then(res => {
        if (!res.ok) throw new Error('Problem not found');
        return res.json();
      })
      .then((data: ProblemDetail) => {
        setProblem(data);
        initializeProblem(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [problemId]);

  // Initialize problem state
  const initializeProblem = useCallback((data: ProblemDetail) => {
    const size = data.boardSize || 19;
    setBoardSize(size);

    // Parse initial stones from API data
    const initialStones: Stone[] = [];

    for (const coordStr of data.initialBlack) {
      const coords = sgfToCoords(coordStr, size);
      if (coords) {
        initialStones.push({ player: 'B', coords });
      }
    }

    for (const coordStr of data.initialWhite) {
      const coords = sgfToCoords(coordStr, size);
      if (coords) {
        initialStones.push({ player: 'W', coords });
      }
    }

    setStones(initialStones);
    setMoveHistory([]);
    setLastMove(null);
    setIsSolved(false);
    setIsFailed(false);
    setShowHint(false);
    setHintCoords(null);

    // Parse SGF if available
    if (data.sgfContent) {
      try {
        const parsed = parseSGF(data.sgfContent);
        parsedSGFRef.current = parsed;
        setCurrentNode(parsed.root);
        setNextPlayer(parsed.nextPlayer);

        // Update hint coords
        const validMoves = getValidMoves(parsed.root);
        const correctMove = validMoves.find(m => m.isCorrect);
        if (correctMove) {
          setHintCoords(correctMove.coords);
        }
      } catch (e) {
        console.error('Failed to parse SGF:', e);
        parsedSGFRef.current = null;
        setCurrentNode(null);
        // Default to black if SGF parse fails
        setNextPlayer('B');
      }
    }

    // Start timing
    setStartTime(Date.now());
    setElapsedTime(0);
  }, []);

  // Place a stone and validate against SGF tree
  const placeStone = useCallback((x: number, y: number): MoveResult | null => {
    if (isSolved || isFailed) return null;

    // Check if position is already occupied
    const isOccupied = stones.some(s => s.coords[0] === x && s.coords[1] === y);
    if (isOccupied) return null;

    const newStone: Stone = { player: nextPlayer, coords: [x, y] };

    // If no SGF or no current node, just place the stone (free play mode)
    if (!currentNode) {
      setStones(prev => [...prev, newStone]);
      setLastMove([x, y]);
      setMoveHistory(prev => [...prev, newStone]);
      setNextPlayer(prev => prev === 'B' ? 'W' : 'B');
      return { type: 'continue' };
    }

    // Find matching move in SGF tree
    const matchingChild = findChildMove(currentNode, nextPlayer, [x, y]);

    if (!matchingChild) {
      // Move not in tree - wrong move
      setIsFailed(true);
      setAttempts(prev => prev + 1);
      setStones(prev => [...prev, newStone]);
      setLastMove([x, y]);
      return { type: 'incorrect', message: 'This move is not correct. Try again!' };
    }

    // Check if this is a correct or wrong path
    const isOnCorrectPath = isCorrectPath(matchingChild);

    if (!isOnCorrectPath) {
      // Explicitly marked as wrong
      setIsFailed(true);
      setAttempts(prev => prev + 1);
      setStones(prev => [...prev, newStone]);
      setLastMove([x, y]);
      return { type: 'incorrect', message: matchingChild.comment || 'Wrong path!' };
    }

    // Correct move - update state
    setStones(prev => [...prev, newStone]);
    setLastMove([x, y]);
    setMoveHistory(prev => [...prev, newStone]);
    setCurrentNode(matchingChild);

    // Check if solved
    if (isSolutionComplete(matchingChild)) {
      setIsSolved(true);
      return { type: 'solved', message: 'Congratulations! Problem solved!' };
    }

    // Get AI response
    const aiResponse = getAIResponse(matchingChild);
    if (aiResponse) {
      // Play AI's response after a short delay
      setTimeout(() => {
        const aiStone: Stone = { player: aiResponse.player, coords: aiResponse.coords };
        setStones(prev => [...prev, aiStone]);
        setLastMove(aiResponse.coords);
        setMoveHistory(prev => [...prev, aiStone]);

        // Move to AI's node
        const aiNode = findChildMove(matchingChild, aiResponse.player, aiResponse.coords);
        if (aiNode) {
          setCurrentNode(aiNode);

          // Check if solved after AI move
          if (isSolutionComplete(aiNode)) {
            setIsSolved(true);
          } else {
            // Update hint for next move
            const validMoves = getValidMoves(aiNode);
            const correctMove = validMoves.find(m => m.isCorrect);
            if (correctMove) {
              setHintCoords(correctMove.coords);
            }
          }
        }

        // Switch player back to user's color after AI responds
        // In tsumego, user always plays the same color (e.g., Black for 黑先)
        setNextPlayer(aiResponse.player === 'B' ? 'W' : 'B');
      }, 300);
    } else {
      // Only switch player if no AI response (terminal node or free play)
      setNextPlayer(prev => prev === 'B' ? 'W' : 'B');
    }

    return { type: 'correct' };
  }, [stones, nextPlayer, currentNode, isSolved, isFailed]);

  // Undo last move
  const undo = useCallback(() => {
    if (moveHistory.length === 0 || isSolved) return;

    // If failed, just reset to last good state
    if (isFailed) {
      // Remove all moves made after last AI response
      const lastAIIndex = moveHistory.length - 1;
      const newHistory = moveHistory.slice(0, lastAIIndex);
      const newStones = stones.slice(0, -1);

      setStones(newStones);
      setMoveHistory(newHistory);
      setIsFailed(false);
      setLastMove(newHistory.length > 0 ? newHistory[newHistory.length - 1].coords : null);

      return;
    }

    // Normal undo - go back to parent node
    if (currentNode && currentNode.parent) {
      // Remove user's move and AI's response if any
      let movesToRemove = 1;
      if (currentNode.parent.parent && currentNode.move?.player !== nextPlayer) {
        // Current node is AI's move, remove both
        movesToRemove = 2;
      }

      const newHistory = moveHistory.slice(0, -movesToRemove);
      const newStones = stones.slice(0, -movesToRemove);

      setMoveHistory(newHistory);
      setStones(newStones);
      setLastMove(newHistory.length > 0 ? newHistory[newHistory.length - 1].coords : null);

      // Navigate back in SGF tree
      let newNode = currentNode;
      for (let i = 0; i < movesToRemove && newNode.parent; i++) {
        newNode = newNode.parent;
      }
      setCurrentNode(newNode);

      // Update player
      setNextPlayer(newNode === parsedSGFRef.current?.root
        ? parsedSGFRef.current.nextPlayer
        : (newNode.move?.player === 'B' ? 'W' : 'B'));

      // Update hint
      const validMoves = getValidMoves(newNode);
      const correctMove = validMoves.find(m => m.isCorrect);
      if (correctMove) {
        setHintCoords(correctMove.coords);
      }
    }
  }, [moveHistory, stones, currentNode, nextPlayer, isSolved, isFailed]);

  // Reset problem
  const reset = useCallback(() => {
    if (problem) {
      initializeProblem(problem);
      setAttempts(prev => prev + 1);
    }
  }, [problem, initializeProblem]);

  // Toggle hint
  const toggleHint = useCallback(() => {
    setShowHint(prev => !prev);
  }, []);

  // Save progress to localStorage and optionally to server
  const saveProgress = useCallback(() => {
    if (!problem) return;

    const progressKey = 'tsumego_progress';
    const stored = localStorage.getItem(progressKey);
    const progress = stored ? JSON.parse(stored) : {};

    progress[problem.id] = {
      completed: isSolved,
      attempts: attempts,
      lastDuration: elapsedTime,
      lastAttemptAt: new Date().toISOString()
    };

    localStorage.setItem(progressKey, JSON.stringify(progress));

    // TODO: Also save to server if user is logged in
  }, [problem, isSolved, attempts, elapsedTime]);

  // Auto-save progress when solved or failed
  useEffect(() => {
    if (isSolved || isFailed) {
      saveProgress();
    }
  }, [isSolved, isFailed, saveProgress]);

  return {
    // State
    problem,
    loading,
    error,
    boardSize,
    stones,
    lastMove,
    currentNode,
    nextPlayer,
    moveHistory,
    isSolved,
    isFailed,
    startTime,
    elapsedTime,
    attempts,
    showHint,
    hintCoords,

    // Actions
    placeStone,
    undo,
    reset,
    toggleHint,
    saveProgress
  };
}
