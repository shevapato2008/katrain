import { useMemo, memo } from 'react';
import { gridToSurface, getBoardDimensions } from '../constants';
import type { GameState } from '../../../api';

interface TerritoryProps {
  gameState: GameState;
}

const Territory = ({ gameState }: TerritoryProps) => {
  const boardSize = gameState.board_size[0];
  const ownership = gameState.analysis?.ownership;
  const dims = getBoardDimensions(boardSize);

  const patches = useMemo(() => {
    if (!ownership) return [];
    const result: { pos: [number, number, number]; color: string; alpha: number }[] = [];
    for (let y = 0; y < boardSize; y++) {
      for (let x = 0; x < boardSize; x++) {
        const val = ownership[y][x];
        if (Math.abs(val) > 0.05) {
          result.push({
            pos: gridToSurface(x, y, boardSize),
            color: val > 0 ? '#000000' : '#ffffff',
            alpha: Math.abs(val) * 0.4,
          });
        }
      }
    }
    return result;
  }, [ownership, boardSize]);

  const halfGrid = dims.gridSpacing * 0.48;

  return (
    <group>
      {patches.map((patch, i) => (
        <mesh key={i} position={patch.pos} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[halfGrid * 2, halfGrid * 2]} />
          <meshBasicMaterial color={patch.color} transparent opacity={patch.alpha} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
};

export default memo(Territory);
