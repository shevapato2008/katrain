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

// ============ Capture Logic Utilities ============

/**
 * Get all stones in a connected group (same color, orthogonally connected)
 */
function getGroup(stones: Stone[], startCoord: [number, number], player: 'B' | 'W'): [number, number][] {
  const group: [number, number][] = [];
  const visited = new Set<string>();
  const queue: [number, number][] = [startCoord];

  const stoneMap = new Map<string, 'B' | 'W'>();
  for (const s of stones) {
    stoneMap.set(`${s.coords[0]},${s.coords[1]}`, s.player);
  }

  while (queue.length > 0) {
    const [x, y] = queue.shift()!;
    const key = `${x},${y}`;

    if (visited.has(key)) continue;
    if (stoneMap.get(key) !== player) continue;

    visited.add(key);
    group.push([x, y]);

    // Check orthogonal neighbors
    const neighbors: [number, number][] = [[x-1, y], [x+1, y], [x, y-1], [x, y+1]];
    for (const neighbor of neighbors) {
      const nKey = `${neighbor[0]},${neighbor[1]}`;
      if (!visited.has(nKey) && stoneMap.get(nKey) === player) {
        queue.push(neighbor);
      }
    }
  }

  return group;
}

/**
 * Count liberties (empty adjacent points) of a group
 */
function countLiberties(stones: Stone[], group: [number, number][], boardSize: number): number {
  const liberties = new Set<string>();

  const stoneMap = new Set<string>();
  for (const s of stones) {
    stoneMap.add(`${s.coords[0]},${s.coords[1]}`);
  }

  for (const [x, y] of group) {
    const neighbors: [number, number][] = [[x-1, y], [x+1, y], [x, y-1], [x, y+1]];
    for (const [nx, ny] of neighbors) {
      // Check bounds
      if (nx < 0 || nx >= boardSize || ny < 0 || ny >= boardSize) continue;

      const key = `${nx},${ny}`;
      if (!stoneMap.has(key)) {
        liberties.add(key);
      }
    }
  }

  return liberties.size;
}

/**
 * Find and remove captured stones after a move
 * Returns the new stones array with captured stones removed
 */
function removeCaptures(stones: Stone[], lastMovePlayer: 'B' | 'W', boardSize: number): Stone[] {
  const opponent = lastMovePlayer === 'B' ? 'W' : 'B';
  const captured = new Set<string>();
  const checked = new Set<string>();

  // Check all opponent stones for captures
  for (const stone of stones) {
    if (stone.player !== opponent) continue;

    const key = `${stone.coords[0]},${stone.coords[1]}`;
    if (checked.has(key)) continue;

    const group = getGroup(stones, stone.coords, opponent);
    for (const [gx, gy] of group) {
      checked.add(`${gx},${gy}`);
    }

    const liberties = countLiberties(stones, group, boardSize);
    if (liberties === 0) {
      // This group is captured
      for (const [gx, gy] of group) {
        captured.add(`${gx},${gy}`);
      }
    }
  }

  if (captured.size === 0) {
    return stones;
  }

  // Remove captured stones
  return stones.filter(s => !captured.has(`${s.coords[0]},${s.coords[1]}`));
}

// ============ End Capture Logic ============

export interface MoveResult {
  type: 'correct' | 'incorrect' | 'solved' | 'continue';
  message?: string;
  sound?: 'stone' | 'capture' | 'correct' | 'incorrect' | 'solved';
  captured?: number;
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

  // Try mode (free exploration)
  isTryMode: boolean;

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

  // Try mode (free exploration)
  enterTryMode: () => void;
  exitTryMode: () => void;

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

  // Try mode (free exploration without judgment)
  const [isTryMode, setIsTryMode] = useState(false);
  const tryModeSnapshotRef = useRef<{
    stones: Stone[];
    lastMove: [number, number] | null;
    currentNode: SGFNode | null;
    nextPlayer: 'B' | 'W';
    moveHistory: Stone[];
    isFailed: boolean;
  } | null>(null);

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
    // In normal mode, don't allow moves after solved/failed
    if (!isTryMode && (isSolved || isFailed)) return null;

    // Check if position is already occupied
    const isOccupied = stones.some(s => s.coords[0] === x && s.coords[1] === y);
    if (isOccupied) return null;

    const newStone: Stone = { player: nextPlayer, coords: [x, y] };

    // In try mode, just place stones freely without judgment
    if (isTryMode) {
      let capturedCount = 0;
      setStones(prev => {
        const newStones = [...prev, newStone];
        const afterCaptures = removeCaptures(newStones, newStone.player, boardSize);
        capturedCount = newStones.length - afterCaptures.length;
        return afterCaptures;
      });
      setLastMove([x, y]);
      setMoveHistory(prev => [...prev, newStone]);
      setNextPlayer(prev => prev === 'B' ? 'W' : 'B');
      return {
        type: 'continue',
        sound: capturedCount > 0 ? 'capture' : 'stone',
        captured: capturedCount
      };
    }

    // If no SGF or no current node, just place the stone (free play mode)
    if (!currentNode) {
      let capturedCount = 0;
      setStones(prev => {
        const newStones = [...prev, newStone];
        const afterCaptures = removeCaptures(newStones, newStone.player, boardSize);
        capturedCount = newStones.length - afterCaptures.length;
        return afterCaptures;
      });
      setLastMove([x, y]);
      setMoveHistory(prev => [...prev, newStone]);
      setNextPlayer(prev => prev === 'B' ? 'W' : 'B');
      return {
        type: 'continue',
        sound: capturedCount > 0 ? 'capture' : 'stone',
        captured: capturedCount
      };
    }

    // Find matching move in SGF tree
    const matchingChild = findChildMove(currentNode, nextPlayer, [x, y]);

    if (!matchingChild) {
      // Move not in tree - wrong move
      setIsFailed(true);
      setAttempts(prev => prev + 1);
      setStones(prev => {
        const newStones = [...prev, newStone];
        return removeCaptures(newStones, newStone.player, boardSize);
      });
      setLastMove([x, y]);
      return { type: 'incorrect', sound: 'incorrect' };
    }

    // Check if this is a correct or wrong path
    const isOnCorrectPath = isCorrectPath(matchingChild);

    if (!isOnCorrectPath) {
      // Explicitly marked as wrong
      setIsFailed(true);
      setAttempts(prev => prev + 1);
      setStones(prev => {
        const newStones = [...prev, newStone];
        return removeCaptures(newStones, newStone.player, boardSize);
      });
      setLastMove([x, y]);
      return { type: 'incorrect', message: matchingChild.comment, sound: 'incorrect' };
    }

    // Correct move - update state with capture logic
    let capturedCount = 0;
    setStones(prev => {
      const newStones = [...prev, newStone];
      const afterCaptures = removeCaptures(newStones, newStone.player, boardSize);
      capturedCount = newStones.length - afterCaptures.length;
      return afterCaptures;
    });
    setLastMove([x, y]);
    setMoveHistory(prev => [...prev, newStone]);
    setCurrentNode(matchingChild);

    // Check if solved
    if (isSolutionComplete(matchingChild)) {
      setIsSolved(true);
      return { type: 'solved', sound: 'solved' };
    }

    // Get AI response
    const aiResponse = getAIResponse(matchingChild);
    if (aiResponse) {
      // Play AI's response after a short delay
      setTimeout(() => {
        const aiStone: Stone = { player: aiResponse.player, coords: aiResponse.coords };
        setStones(prev => {
          const newStones = [...prev, aiStone];
          return removeCaptures(newStones, aiStone.player, boardSize);
        });
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

    return {
      type: 'correct',
      sound: capturedCount > 0 ? 'capture' : 'stone',
      captured: capturedCount
    };
  }, [stones, nextPlayer, currentNode, isSolved, isFailed, boardSize, isTryMode]);

  // Undo last move
  const undo = useCallback(() => {
    if (moveHistory.length === 0 || isSolved) return;

    // Try mode undo - simply remove the last move
    if (isTryMode) {
      const snapshot = tryModeSnapshotRef.current;
      const snapshotMoveCount = snapshot?.moveHistory.length || 0;

      // Don't undo beyond the snapshot state
      if (moveHistory.length <= snapshotMoveCount) return;

      // Remove the last move
      const newHistory = moveHistory.slice(0, -1);

      // Recalculate stones from snapshot + remaining moves
      let newStones = snapshot ? [...snapshot.stones] : [];
      for (const move of newHistory.slice(snapshotMoveCount)) {
        newStones = [...newStones, move];
        newStones = removeCaptures(newStones, move.player, boardSize);
      }

      setStones(newStones);
      setMoveHistory(newHistory);
      setLastMove(newHistory.length > 0 ? newHistory[newHistory.length - 1].coords : (snapshot?.lastMove || null));
      setNextPlayer(prev => prev === 'B' ? 'W' : 'B');

      return;
    }

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
  }, [moveHistory, stones, currentNode, nextPlayer, isSolved, isFailed, isTryMode, boardSize]);

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

  // Enter try mode - save current state and allow free exploration
  const enterTryMode = useCallback(() => {
    if (isTryMode || isSolved) return;

    // Save current state
    tryModeSnapshotRef.current = {
      stones: [...stones],
      lastMove,
      currentNode,
      nextPlayer,
      moveHistory: [...moveHistory],
      isFailed
    };

    setIsTryMode(true);
    setIsFailed(false); // Clear failed state in try mode
  }, [isTryMode, isSolved, stones, lastMove, currentNode, nextPlayer, moveHistory, isFailed]);

  // Exit try mode - restore saved state
  const exitTryMode = useCallback(() => {
    if (!isTryMode) return;

    const snapshot = tryModeSnapshotRef.current;
    if (snapshot) {
      setStones(snapshot.stones);
      setLastMove(snapshot.lastMove);
      setCurrentNode(snapshot.currentNode);
      setNextPlayer(snapshot.nextPlayer);
      setMoveHistory(snapshot.moveHistory);
      setIsFailed(snapshot.isFailed);
    }

    setIsTryMode(false);
    tryModeSnapshotRef.current = null;
  }, [isTryMode]);

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
    isTryMode,
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
    enterTryMode,
    exitTryMode,
    saveProgress
  };
}
