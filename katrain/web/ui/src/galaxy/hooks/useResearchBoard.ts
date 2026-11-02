/**
 * useResearchBoard: Manages local board state for Level 1 (research setup).
 * Pure client-side — no backend session, no WebSocket, no KataGo.
 */
import { useState, useCallback, useRef, useMemo } from 'react';
import { movesToSGF, sgfToMoves } from '../../utils/sgfSerializer';
import { researchSetupAtCursor, researchPlayerAtCursor } from '../../utils/researchBoardReplay';
import type { SGFMetadata, SerializedSGF, ResearchSerializationOptions } from '../../utils/sgfSerializer';
import type { PlaceMode, EditMode } from '../components/research/ResearchToolbar';

export interface ResearchBoardState {
  // Board
  moves: string[];
  stoneColors: ('B' | 'W')[];
  currentMove: number;
  setupCount: number;
  initialPlayer: 'B' | 'W';
  editedSetup: boolean;
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
  handicapCount: number; // Number of leading setup stones (from handicap)

  // Board actions
  handleIntersectionClick: (x: number, y: number) => boolean;
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
  serializeToSGF: (options?: ResearchSerializationOptions) => SerializedSGF;
  loadFromSGF: (sgfContent: string) => { success: boolean; error?: string };
  openLocalSGF: () => void;
  saveLocalSGF: () => void;
  copyToClipboard: () => void;

  // Snapshot for L1↔L2 transitions
  getSnapshot: () => ResearchBoardState;
  restoreSnapshot: (snapshot: ResearchBoardState) => void;
}

export function useResearchBoard(): UseResearchBoardReturn {
  const [moves, setMoves] = useState<string[]>([]);
  const [stoneColors, setStoneColors] = useState<('B' | 'W')[]>([]);
  const [currentMove, setCurrentMove] = useState(0);
  const [setupCount, setSetupCount] = useState(0);
  const [initialPlayer, setInitialPlayer] = useState<'B' | 'W'>('B');
  const [editedSetup, setEditedSetup] = useState(false);
  const [boardSize, setBoardSize] = useState(19);
  const [placeMode, setPlaceMode] = useState<PlaceMode>('alternate');
  const [editMode, setEditMode] = useState<EditMode>(null);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [rules, setRules] = useState('chinese');
  const [komi, setKomi] = useState(7.5);
  const [handicap, setHandicap] = useState(0);
  const [playerBlack, setPlayerBlack] = useState('');
  const [playerWhite, setPlayerWhite] = useState('');

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Preserve original SGF to avoid round-trip corruption (e.g., tt pass notation)
  const rawSgfRef = useRef<string | null>(null);

  const getMetadata = useCallback((): SGFMetadata => ({
    boardSize, komi, handicap, rules, playerBlack, playerWhite, setupCount, initialPlayer,
  }), [boardSize, komi, handicap, rules, playerBlack, playerWhite, setupCount, initialPlayer]);

  const commitSetup = useCallback((setupMoves: string[], setupColors: ('B' | 'W')[]) => {
    const toPlay = researchPlayerAtCursor(stoneColors, currentMove, setupCount, initialPlayer);
    setMoves(setupMoves); setStoneColors(setupColors); setCurrentMove(setupMoves.length);
    setSetupCount(setupMoves.length); setInitialPlayer(toPlay); setEditedSetup(true); setHandicap(0);
    rawSgfRef.current = null;
  }, [currentMove, initialPlayer, setupCount, stoneColors]);

  // ── Board actions ──

  // Track selected stone for move mode
  const selectedStoneRef = useRef<{ x: number; y: number; moveIndex: number } | null>(null);

  const handleIntersectionClick = useCallback((x: number, y: number) => {
    if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= boardSize || y >= boardSize) return false;
    const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
    const col = letters[x];
    const row = y + 1;
    const moveStr = `${col}${row}`;

    if (editMode === 'delete' || editMode === 'move') {
      const setup = researchSetupAtCursor(moves, stoneColors, currentMove, boardSize, setupCount);
      const index = setup.moves.indexOf(moveStr);
      if (editMode === 'delete') {
        if (index >= 0) { setup.moves.splice(index, 1); setup.stoneColors.splice(index, 1); commitSetup(setup.moves, setup.stoneColors); }
        return false;
      }
      if (!selectedStoneRef.current) {
        if (index >= 0) selectedStoneRef.current = { x, y, moveIndex: index };
        return false;
      }
      const selected = selectedStoneRef.current;
      selectedStoneRef.current = null;
      if (selected.x === x && selected.y === y) return false;
      if (index >= 0) return false;
      const from = setup.moves.indexOf(`${letters[selected.x]}${selected.y + 1}`);
      if (from < 0) return false;
      setup.moves[from] = moveStr;
      commitSetup(setup.moves, setup.stoneColors);
      return true;
    }

    // No placeMode selected = do nothing on click
    if (!placeMode) return false;

    // Determine stone color based on placeMode
    let color: 'B' | 'W';
    if (placeMode === 'black') {
      color = 'B';
    } else if (placeMode === 'white') {
      color = 'W';
    } else {
      color = researchPlayerAtCursor(stoneColors, currentMove, setupCount, initialPlayer);
    }

    if (placeMode === 'black' || placeMode === 'white') {
      const setup = researchSetupAtCursor(moves, stoneColors, currentMove, boardSize, setupCount);
      const index = setup.moves.indexOf(moveStr);
      if (index >= 0) return false;
      setup.moves.push(moveStr); setup.stoneColors.push(color);
      commitSetup(setup.moves, setup.stoneColors);
      return true;
    }

    // Place stone (truncate forward moves)
    const newMoves = moves.slice(0, currentMove);
    const newColors = stoneColors.slice(0, currentMove);
    newMoves.push(moveStr);
    newColors.push(color);
    setMoves(newMoves);
    setStoneColors(newColors);
    setCurrentMove(newMoves.length);
    rawSgfRef.current = null;
    return true;
  }, [moves, stoneColors, currentMove, boardSize, editMode, placeMode, setupCount, initialPlayer, commitSetup]);

  const handlePass = useCallback(() => {
    const newMoves = moves.slice(0, currentMove);
    const newColors = stoneColors.slice(0, currentMove);
    newMoves.push('pass');
    newColors.push(researchPlayerAtCursor(stoneColors, currentMove, setupCount, initialPlayer));
    setMoves(newMoves);
    setStoneColors(newColors);
    setCurrentMove(newMoves.length);
    rawSgfRef.current = null;
  }, [moves, stoneColors, currentMove, setupCount, initialPlayer]);

  const handleClear = useCallback(() => {
    setMoves([]);
    setStoneColors([]);
    setCurrentMove(0);
    setSetupCount(0); setInitialPlayer('B'); setEditedSetup(false); setHandicap(0);
    rawSgfRef.current = null;
  }, []);

  const handleMoveChange = useCallback((move: number) => {
    setCurrentMove(Math.max(setupCount, Math.min(moves.length, move)));
  }, [moves.length, setupCount]);

  // ── SGF operations ──

  const serializeToSGF = useCallback((options: ResearchSerializationOptions = {}): SerializedSGF => {
    const metadata = getMetadata();
    if (options.position) { metadata.playerBlack = ''; metadata.playerWhite = ''; }
    const cursor = options.position ? currentMove : moves.length;
    return movesToSGF(moves.slice(0, cursor), metadata, stoneColors.slice(0, cursor));
  }, [moves, stoneColors, currentMove, getMetadata]);

  const loadFromSGF = useCallback((sgfContent: string): { success: boolean; error?: string } => {
    try {
      const { moves: parsedMoves, stoneColors: parsedColors, metadata, setupCount: parsedSetupCount, unsupportedSetup } = sgfToMoves(sgfContent);
      if (unsupportedSetup) throw new Error('棋谱含不支持的局面编辑或无效坐标，请先建立新的摆子局面');

      setMoves(parsedMoves);
      setStoneColors(parsedColors);
      setCurrentMove(parsedMoves.length);
      setSetupCount(parsedSetupCount); setInitialPlayer(metadata.initialPlayer ?? 'B'); setEditedSetup(false);
      rawSgfRef.current = sgfContent;  // Preserve original for backend

      setBoardSize(metadata.boardSize ?? 19);
      setKomi(metadata.komi ?? 7.5);
      setHandicap(metadata.handicap ?? 0);
      setRules(metadata.rules ?? 'chinese');
      setPlayerBlack(metadata.playerBlack ?? '');
      setPlayerWhite(metadata.playerWhite ?? '');

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

  const copyToClipboard = useCallback(() => {
    const { sgf } = serializeToSGF();
    navigator.clipboard.writeText(sgf).catch((err) => {
      console.error('Failed to copy SGF to clipboard:', err);
    });
  }, [serializeToSGF]);

  // ── Snapshot ──

  const getSnapshot = useCallback((): ResearchBoardState => ({
    moves: [...moves],
    stoneColors: [...stoneColors],
    currentMove,
    setupCount, initialPlayer, editedSetup,
    boardSize,
    placeMode,
    editMode,
    showMoveNumbers,
    rules,
    komi,
    handicap,
    playerBlack,
    playerWhite,
  }), [moves, stoneColors, currentMove, setupCount, initialPlayer, editedSetup, boardSize, placeMode, editMode, showMoveNumbers, rules, komi, handicap, playerBlack, playerWhite]);

  const restoreSnapshot = useCallback((snapshot: ResearchBoardState) => {
    setMoves(snapshot.moves);
    setStoneColors(snapshot.stoneColors);
    setCurrentMove(snapshot.currentMove);
    setSetupCount(snapshot.setupCount); setInitialPlayer(snapshot.initialPlayer); setEditedSetup(snapshot.editedSetup);
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

  // Existing board components call this offset handicapCount; it includes every initial AB/AW stone.
  const handicapCount = setupCount;

  // Compute the next stone color for hover preview
  const nextColor = useMemo((): 'B' | 'W' | null => {
    if (!placeMode) return null; // No placeMode = no ghost stone
    if (placeMode === 'black') return 'B';
    if (placeMode === 'white') return 'W';
    return researchPlayerAtCursor(stoneColors, currentMove, setupCount, initialPlayer);
  }, [placeMode, stoneColors, currentMove, setupCount, initialPlayer]);

  return {
    // State
    moves, stoneColors, currentMove, setupCount, initialPlayer, editedSetup, boardSize, placeMode, editMode, showMoveNumbers,
    rules, komi, handicap, playerBlack, playerWhite,
    // Computed
    nextColor,
    handicapCount,
    // Board actions
    handleIntersectionClick, handlePass, handleClear, handleMoveChange,
    // Edit mode
    setPlaceMode, setEditMode, setShowMoveNumbers: (v: boolean) => setShowMoveNumbers(v),
    // Rules
    setBoardSize, setRules, setKomi, setHandicap,
    // Players
    setPlayerBlack, setPlayerWhite,
    // SGF
    serializeToSGF, loadFromSGF, openLocalSGF, saveLocalSGF, copyToClipboard,
    // Snapshot
    getSnapshot, restoreSnapshot,
  };
}
