/**
 * useResearchBoard: Manages local board state for Level 1 (research setup).
 * Pure client-side — no backend session, no WebSocket, no KataGo.
 */
import { useState, useCallback, useRef, useMemo } from 'react';
import { movesToSGF, sgfToMoves } from '../utils/sgfSerializer';
import type { SGFMetadata, SerializedSGF } from '../utils/sgfSerializer';
import type { PlaceMode, EditMode } from '../components/research/ResearchToolbar';

export interface ResearchBoardState {
  // Board
  moves: string[];
  stoneColors: ('B' | 'W')[];
  currentMove: number;
  boardSize: number;

  // Edit modes
  placeMode: PlaceMode;
  editMode: EditMode;
  showMoveNumbers: boolean;

  // Rules
  rules: string;
  komi: number;
  handicap: number;

  // Players
  playerBlack: string;
  playerWhite: string;
}

export interface UseResearchBoardReturn extends ResearchBoardState {
  // Computed
  nextColor: 'B' | 'W' | null; // null when no placeMode and no editMode that places

  // Board actions
  handleIntersectionClick: (x: number, y: number) => void;
  handlePass: () => void;
  handleClear: () => void;
  handleMoveChange: (move: number) => void;

  // Edit mode
  setPlaceMode: (mode: PlaceMode) => void;
  setEditMode: (mode: EditMode) => void;
  setShowMoveNumbers: (show: boolean) => void;

  // Rules
  setBoardSize: (size: number) => void;
  setRules: (rules: string) => void;
  setKomi: (komi: number) => void;
  setHandicap: (handicap: number) => void;

  // Players
  setPlayerBlack: (name: string) => void;
  setPlayerWhite: (name: string) => void;

  // SGF operations
  serializeToSGF: () => SerializedSGF;
  loadFromSGF: (sgfContent: string) => { success: boolean; error?: string };
  openLocalSGF: () => void;
  saveLocalSGF: () => void;

  // Snapshot for L1↔L2 transitions
  getSnapshot: () => ResearchBoardState;
  restoreSnapshot: (snapshot: ResearchBoardState) => void;
}

export function useResearchBoard(): UseResearchBoardReturn {
  const [moves, setMoves] = useState<string[]>([]);
  const [stoneColors, setStoneColors] = useState<('B' | 'W')[]>([]);
  const [currentMove, setCurrentMove] = useState(0);
  const [boardSize, setBoardSize] = useState(19);
  const [placeMode, setPlaceMode] = useState<PlaceMode>(null);
  const [editMode, setEditMode] = useState<EditMode>(null);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [rules, setRules] = useState('chinese');
  const [komi, setKomi] = useState(7.5);
  const [handicap, setHandicap] = useState(0);
  const [playerBlack, setPlayerBlack] = useState('');
  const [playerWhite, setPlayerWhite] = useState('');

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const getMetadata = useCallback((): SGFMetadata => ({
    boardSize, komi, handicap, rules, playerBlack, playerWhite,
  }), [boardSize, komi, handicap, rules, playerBlack, playerWhite]);

  // ── Board actions ──

  // Track selected stone for move mode
  const selectedStoneRef = useRef<{ x: number; y: number; moveIndex: number } | null>(null);

  const handleIntersectionClick = useCallback((x: number, y: number) => {
    const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
    const col = letters[x];
    const row = y + 1;
    const moveStr = `${col}${row}`;

    if (editMode === 'delete') {
      const newMoves = [...moves];
      const newColors = [...stoneColors];
      for (let i = newMoves.length - 1; i >= 0; i--) {
        if (newMoves[i] === moveStr) {
          newMoves.splice(i, 1);
          newColors.splice(i, 1);
          break;
        }
      }
      setMoves(newMoves);
      setStoneColors(newColors);
      setCurrentMove(newMoves.length);
      return;
    }

    if (editMode === 'move') {
      // Two-click move mode: first click selects stone, second click moves it
      if (!selectedStoneRef.current) {
        // First click: find the stone at this position
        for (let i = moves.length - 1; i >= 0; i--) {
          if (moves[i] === moveStr) {
            selectedStoneRef.current = { x, y, moveIndex: i };
            return;
          }
        }
        // No stone found at this position
        return;
      } else {
        // Second click: move the stone to the new position
        const { moveIndex } = selectedStoneRef.current;
        const newMoves = [...moves];
        newMoves[moveIndex] = moveStr;
        setMoves(newMoves);
        selectedStoneRef.current = null;
        return;
      }
    }

    // No placeMode selected = do nothing on click
    if (!placeMode) return;

    // Determine stone color based on placeMode
    let color: 'B' | 'W';
    if (placeMode === 'black') {
      color = 'B';
    } else if (placeMode === 'white') {
      color = 'W';
    } else {
      // alternate: based on the last stone color in the truncated sequence
      const truncatedColors = stoneColors.slice(0, currentMove);
      const lastColor = truncatedColors.length > 0 ? truncatedColors[truncatedColors.length - 1] : 'W';
      color = lastColor === 'B' ? 'W' : 'B';
    }

    // Place stone (truncate forward moves)
    const newMoves = moves.slice(0, currentMove);
    const newColors = stoneColors.slice(0, currentMove);
    newMoves.push(moveStr);
    newColors.push(color);
    setMoves(newMoves);
    setStoneColors(newColors);
    setCurrentMove(newMoves.length);
  }, [moves, stoneColors, currentMove, editMode, placeMode]);

  const handlePass = useCallback(() => {
    const newMoves = moves.slice(0, currentMove);
    const newColors = stoneColors.slice(0, currentMove);
    // Pass uses alternate color logic
    const lastColor = newColors.length > 0 ? newColors[newColors.length - 1] : 'W';
    newMoves.push('pass');
    newColors.push(lastColor === 'B' ? 'W' : 'B');
    setMoves(newMoves);
    setStoneColors(newColors);
    setCurrentMove(newMoves.length);
  }, [moves, stoneColors, currentMove]);

  const handleClear = useCallback(() => {
    setMoves([]);
    setStoneColors([]);
    setCurrentMove(0);
  }, []);

  const handleMoveChange = useCallback((move: number) => {
    setCurrentMove(Math.max(0, Math.min(moves.length, move)));
  }, [moves.length]);

  // ── SGF operations ──

  const serializeToSGF = useCallback((): SerializedSGF => {
    return movesToSGF(moves, getMetadata(), stoneColors);
  }, [moves, stoneColors, getMetadata]);

  const loadFromSGF = useCallback((sgfContent: string): { success: boolean; error?: string } => {
    try {
      const { moves: parsedMoves, stoneColors: parsedColors, metadata } = sgfToMoves(sgfContent);

      setMoves(parsedMoves);
      setStoneColors(parsedColors);
      setCurrentMove(parsedMoves.length);

      if (metadata.boardSize) setBoardSize(metadata.boardSize);
      if (metadata.komi !== undefined) setKomi(metadata.komi);
      if (metadata.handicap !== undefined) setHandicap(metadata.handicap);
      if (metadata.rules) setRules(metadata.rules);
      if (metadata.playerBlack) setPlayerBlack(metadata.playerBlack);
      if (metadata.playerWhite) setPlayerWhite(metadata.playerWhite);

      return { success: true };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }, []);

  const openLocalSGF = useCallback(() => {
    // Create file input dynamically
    if (!fileInputRef.current) {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.sgf,.SGF';
      input.style.display = 'none';
      input.addEventListener('change', (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          const content = reader.result as string;
          const result = loadFromSGF(content);
          if (!result.success) {
            console.error('Failed to load SGF:', result.error);
          }
        };
        reader.readAsText(file);
        // Reset so the same file can be re-selected
        input.value = '';
      });
      document.body.appendChild(input);
      fileInputRef.current = input;
    }
    fileInputRef.current.click();
  }, [loadFromSGF]);

  const saveLocalSGF = useCallback(() => {
    const { sgf } = serializeToSGF();
    const blob = new Blob([sgf], { type: 'application/x-go-sgf' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const title = playerBlack && playerWhite
      ? `${playerBlack}_vs_${playerWhite}.sgf`
      : 'research.sgf';
    a.download = title;
    a.click();
    URL.revokeObjectURL(url);
  }, [serializeToSGF, playerBlack, playerWhite]);

  // ── Snapshot ──

  const getSnapshot = useCallback((): ResearchBoardState => ({
    moves: [...moves],
    stoneColors: [...stoneColors],
    currentMove,
    boardSize,
    placeMode,
    editMode,
    showMoveNumbers,
    rules,
    komi,
    handicap,
    playerBlack,
    playerWhite,
  }), [moves, stoneColors, currentMove, boardSize, placeMode, editMode, showMoveNumbers, rules, komi, handicap, playerBlack, playerWhite]);

  const restoreSnapshot = useCallback((snapshot: ResearchBoardState) => {
    setMoves(snapshot.moves);
    setStoneColors(snapshot.stoneColors);
    setCurrentMove(snapshot.currentMove);
    setBoardSize(snapshot.boardSize);
    setPlaceMode(snapshot.placeMode);
    setEditMode(snapshot.editMode);
    setShowMoveNumbers(snapshot.showMoveNumbers);
    setRules(snapshot.rules);
    setKomi(snapshot.komi);
    setHandicap(snapshot.handicap);
    setPlayerBlack(snapshot.playerBlack);
    setPlayerWhite(snapshot.playerWhite);
  }, []);

  // Compute the next stone color for hover preview
  const nextColor = useMemo((): 'B' | 'W' | null => {
    if (!placeMode) return null; // No placeMode = no ghost stone
    if (placeMode === 'black') return 'B';
    if (placeMode === 'white') return 'W';
    // alternate: based on last stone color in truncated sequence
    const truncated = stoneColors.slice(0, currentMove);
    const lastColor = truncated.length > 0 ? truncated[truncated.length - 1] : 'W';
    return lastColor === 'B' ? 'W' : 'B';
  }, [placeMode, stoneColors, currentMove]);

  return {
    // State
    moves, stoneColors, currentMove, boardSize, placeMode, editMode, showMoveNumbers,
    rules, komi, handicap, playerBlack, playerWhite,
    // Computed
    nextColor,
    // Board actions
    handleIntersectionClick, handlePass, handleClear, handleMoveChange,
    // Edit mode
    setPlaceMode, setEditMode, setShowMoveNumbers: (v: boolean) => setShowMoveNumbers(v),
    // Rules
    setBoardSize, setRules, setKomi, setHandicap,
    // Players
    setPlayerBlack, setPlayerWhite,
    // SGF
    serializeToSGF, loadFromSGF, openLocalSGF, saveLocalSGF,
    // Snapshot
    getSnapshot, restoreSnapshot,
  };
}
