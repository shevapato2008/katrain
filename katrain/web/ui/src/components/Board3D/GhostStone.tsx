import { memo } from 'react';
import StoneMesh from './StoneMesh';
import { gridToWorld } from './constants';
import type { GameState } from '../../api';

interface GhostStoneProps {
  gameState: GameState;
  hoverPos: { col: number; row: number } | null;
  showChildren: boolean;
  playerColor?: 'B' | 'W' | null;
}

const GhostStone = ({ gameState, hoverPos, showChildren, playerColor }: GhostStoneProps) => {
  const boardSize = gameState.board_size[0];
  const playerToMove = gameState.player_to_move as 'B' | 'W';

  let hoverStone = null;
  // Only show hover preview if it's the player's turn (or no restriction)
  // Matches Board.tsx behavior: !playerColor || gameState.player_to_move === playerColor
  if (hoverPos && !gameState.end_result && (!playerColor || playerToMove === playerColor)) {
    const { col, row } = hoverPos;
    const occupied = gameState.stones.some(s => s[1] && s[1][0] === col && s[1][1] === row);
    if (!occupied) {
      hoverStone = <StoneMesh color={playerToMove} position={gridToWorld(col, row, boardSize)} opacity={0.5} />;
    }
  }

  const ghostStones = showChildren && gameState.ghost_stones
    ? gameState.ghost_stones.map(([player, coords], i) => {
        if (!coords) return null;
        return <StoneMesh key={`ghost-${i}`} color={player as 'B' | 'W'} position={gridToWorld(coords[0], coords[1], boardSize)} opacity={0.5} />;
      })
    : null;

  return (
    <group>
      {hoverStone}
      {ghostStones}
    </group>
  );
};

export default memo(GhostStone);
