/**
 * useResearchBoard: Manages local board state for Level 1 (research setup).
 * Pure client-side — no backend session, no WebSocket, no KataGo.
 *
 * Kiosk variant: board size is clamped to 19 always (SBC kiosk boards are
 * 19-only). Imported SGFs on a non-19 size no longer switch the board size;
 * `lastLoadedSize`/`lastLoadClamped` signal this so the page can toast
 * "仅支持 19 路".
 *
 * ## 2026-08-24:两组模式合并成一个 `boardTool`
 *
 * 原来是 `placeMode: 'alternate'|'black'|'white'|null` 和
 * `editMode: 'place'|'move'|'delete'|null` **两组互相清空**的状态 —— 调用方每换一个
 * 工具要写两次 set,还多出一个「两组都 null」的第五态。稿子(屏 21)画的是**一个四段
 * 分段控件**,而分段控件按定义总有一段是按下的。⇒ 合成一个 `boardTool`。
 *
 * 三件东西随之消失,各有各的理由:
 *
 * · **`'move'`(拖动已有的子)—— 删掉,因为它在触摸屏上是坏的,不是「用得少」。**
 *   选中态原来存在一个 `useRef` 里(`selectedStoneRef`),**ref 不触发重渲染,屏上
 *   零反馈**:第一下点在子上什么都不变,第二下点在别处那颗子瞬移过去;第一下点空
 *   静默 return;换工具不清 ref,中途没有取消入口。留下它就得连带把选中态画进共享的
 *   `LiveBoard` —— 买回来的是一个「删除 + 摆黑/摆白」两下就能替代、且每下都有反馈的
 *   工具。**丢的是「一手挪一子」。**
 * · **`'place'` —— 死枝。** 全仓从未被 set 过、也从未被读过,只活在类型声明里。
 * · **「两组都 null」—— 取消。** 它的全部含义是「点盘完全无响应」(锁盘防误触),
 *   而翻手键在右栏、不需要碰盘。
 *
 * 默认值 `'alternate'` 和原来的 `placeMode='alternate'/editMode=null` 是同一个初始态,
 * 所以合并对「进屏长什么样」零影响。
 */
import { useState, useCallback, useRef, useMemo } from 'react';
import { movesToSGF, sgfToMoves } from '../../utils/sgfSerializer';
import type { SGFMetadata, SerializedSGF } from '../../utils/sgfSerializer';

/** 屏 21 那个四段分段控件的四段。**互斥** —— 同一根手指点在盘上只能是其中一个意思。 */
export type BoardTool = 'alternate' | 'black' | 'white' | 'delete';

export interface ResearchBoardState {
  // Board
  moves: string[];
  stoneColors: ('B' | 'W')[];
  currentMove: number;
  boardSize: number;

  // 落子/删除工具(四选一,永远有一个选中)
  boardTool: BoardTool;

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
  nextColor: 'B' | 'W' | null; // 删除工具下没有落子预览 ⇒ null
  handicapCount: number; // Number of leading setup stones (from handicap)

  // Board actions
  handleIntersectionClick: (x: number, y: number) => void;
  handlePass: () => void;
  handleClear: () => void;
  handleMoveChange: (move: number) => void;

  setBoardTool: (tool: BoardTool) => void;

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

  // Kiosk 19-only clamp signal (not present in galaxy): the board size the
  // most recently loaded SGF actually declared, and whether it was clamped
  // to 19 because it differed. Consumed by the page to toast "仅支持 19 路".
  lastLoadedSize: number | null;
  lastLoadClamped: boolean;
}

export function useResearchBoard(): UseResearchBoardReturn {
  const [moves, setMoves] = useState<string[]>([]);
  const [stoneColors, setStoneColors] = useState<('B' | 'W')[]>([]);
  const [currentMove, setCurrentMove] = useState(0);
  const [boardSize, setBoardSize] = useState(19);
  const [boardTool, setBoardTool] = useState<BoardTool>('alternate');
  const [rules, setRules] = useState('chinese');
  const [komi, setKomi] = useState(7.5);
  const [handicap, setHandicap] = useState(0);
  const [playerBlack, setPlayerBlack] = useState('');
  const [playerWhite, setPlayerWhite] = useState('');
  const [lastLoadedSize, setLastLoadedSize] = useState<number | null>(null);
  const [lastLoadClamped, setLastLoadClamped] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Preserve original SGF to avoid round-trip corruption (e.g., tt pass notation)
  const rawSgfRef = useRef<string | null>(null);

  const getMetadata = useCallback((): SGFMetadata => ({
    boardSize, komi, handicap, rules, playerBlack, playerWhite,
  }), [boardSize, komi, handicap, rules, playerBlack, playerWhite]);

  // ── Board actions ──

  // Track selected stone for move mode

  const handleIntersectionClick = useCallback((x: number, y: number) => {
    const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
    const col = letters[x];
    const row = y + 1;
    const moveStr = `${col}${row}`;

    if (boardTool === 'delete') {
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
      rawSgfRef.current = null;
      return;
    }

    // 剩下三段都是落子。颜色由工具决定。
    let color: 'B' | 'W';
    if (boardTool === 'black') {
      color = 'B';
    } else if (boardTool === 'white') {
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
    rawSgfRef.current = null;
  }, [moves, stoneColors, currentMove, boardTool]);

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
    rawSgfRef.current = null;
  }, [moves, stoneColors, currentMove]);

  const handleClear = useCallback(() => {
    setMoves([]);
    setStoneColors([]);
    setCurrentMove(0);
    rawSgfRef.current = null;
  }, []);

  const handleMoveChange = useCallback((move: number) => {
    setCurrentMove(Math.max(0, Math.min(moves.length, move)));
  }, [moves.length]);

  // ── SGF operations ──

  const serializeToSGF = useCallback((): SerializedSGF => {
    // Re-serialize from moves[]. When handicap > 0, movesToSGF emits the first
    // N black stones as AB[] setup (per SGF standard), keeping the backend's
    // game tree consistent with convention (move 1 = White in handicap games).
    return movesToSGF(moves, getMetadata(), stoneColors);
  }, [moves, stoneColors, getMetadata]);

  const loadFromSGF = useCallback((sgfContent: string): { success: boolean; error?: string } => {
    try {
      const { moves: parsedMoves, stoneColors: parsedColors, metadata } = sgfToMoves(sgfContent);

      setMoves(parsedMoves);
      setStoneColors(parsedColors);
      setCurrentMove(parsedMoves.length);
      rawSgfRef.current = sgfContent;  // Preserve original for backend

      // Kiosk 19-only clamp: board size never leaves 19, regardless of what
      // the imported SGF declares. Record the SGF's actual size + whether it
      // was clamped so the page can toast "仅支持 19 路".
      if (metadata.boardSize) {
        setLastLoadedSize(metadata.boardSize);
        setLastLoadClamped(metadata.boardSize !== 19);
      } else {
        setLastLoadedSize(null);
        setLastLoadClamped(false);
      }
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


  // Compute handicap setup count: number of leading consecutive B stones
  // that correspond to the handicap metadata (these are AB[] setup, not game moves)
  const handicapCount = useMemo((): number => {
    if (handicap <= 0) return 0;
    let count = 0;
    for (let i = 0; i < Math.min(handicap, moves.length); i++) {
      if (stoneColors[i] === 'B' && moves[i].toLowerCase() !== 'pass') {
        count++;
      } else {
        break;
      }
    }
    return count;
  }, [handicap, moves, stoneColors]);

  // Compute the next stone color for hover preview
  const nextColor = useMemo((): 'B' | 'W' | null => {
    if (boardTool === 'delete') return null; // 删除工具没有落子预览
    if (boardTool === 'black') return 'B';
    if (boardTool === 'white') return 'W';
    // alternate: based on last stone color in truncated sequence
    const truncated = stoneColors.slice(0, currentMove);
    const lastColor = truncated.length > 0 ? truncated[truncated.length - 1] : 'W';
    return lastColor === 'B' ? 'W' : 'B';
  }, [boardTool, stoneColors, currentMove]);

  return {
    // State
    moves, stoneColors, currentMove, boardSize, boardTool,
    rules, komi, handicap, playerBlack, playerWhite,
    // Computed
    nextColor,
    handicapCount,
    // Board actions
    handleIntersectionClick, handlePass, handleClear, handleMoveChange,
    setBoardTool,
    // Rules
    setBoardSize, setRules, setKomi, setHandicap,
    // Players
    setPlayerBlack, setPlayerWhite,
    // SGF
    serializeToSGF, loadFromSGF, openLocalSGF, saveLocalSGF,
    // Kiosk 19-only clamp signal
    lastLoadedSize, lastLoadClamped,
  };
}
