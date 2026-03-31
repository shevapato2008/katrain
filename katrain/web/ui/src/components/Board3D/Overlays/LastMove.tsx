import { memo } from 'react';
import { gridToWorld, STONE_HEIGHT, ABOVE_STONE } from '../constants';
import type { GameState } from '../../../api';

interface LastMoveProps {
  gameState: GameState;
}

const LastMove = ({ gameState }: LastMoveProps) => {
  if (!gameState.last_move) return null;

  const boardSize = gameState.board_size[0];
  const [lx, ly] = gameState.last_move;
  const pos = gridToWorld(lx, ly, boardSize);

  const lastStone = gameState.stones.find(s => s[1] && s[1][0] === lx && s[1][1] === ly);
  const markerColor = lastStone?.[0] === 'B' ? '#ffffff' : '#000000';

  // Stone center is at pos[1]. Stone apex (top of flattened sphere) is at pos[1] + STONE_HEIGHT.
  // Ring sits just above the apex to avoid clipping.
  const ringY = pos[1] + STONE_HEIGHT + ABOVE_STONE;

  return (
    <mesh position={[pos[0], ringY, pos[2]]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.22, 0.30, 32]} />
      <meshBasicMaterial color={markerColor} transparent opacity={0.9} depthWrite={false} />
    </mesh>
  );
};

export default memo(LastMove);
