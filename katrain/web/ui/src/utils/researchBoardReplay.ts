/** Research editing uses the same FF4 display replay as the record viewers. */
import { buildReplayBoardState } from './goReplay';

export { parseMove, buildReplayBoardState } from './goReplay';

/** Explicit editing starts a new setup from the visible board, including captures. */
export function researchSetupAtCursor(moves: string[], stoneColors: ('B' | 'W')[], currentMove: number, size: number, setupCount: number) {
  const { board } = buildReplayBoardState(moves, currentMove, size, stoneColors, setupCount);
  const setupMoves: string[] = [];
  const setupColors: ('B' | 'W')[] = [];
  const columns = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const color = board[y][x];
    if (color === 'B' || color === 'W') { setupMoves.push(`${columns[x]}${y + 1}`); setupColors.push(color); }
  }
  return { moves: setupMoves, stoneColors: setupColors };
}

export function researchPlayerAtCursor(stoneColors: ('B' | 'W')[], currentMove: number, setupCount: number, initialPlayer: 'B' | 'W'): 'B' | 'W' {
  if (currentMove <= setupCount) return initialPlayer;
  return stoneColors[currentMove - 1] === 'B' ? 'W' : 'B';
}
