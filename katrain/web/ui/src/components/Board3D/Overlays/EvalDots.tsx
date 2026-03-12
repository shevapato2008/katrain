import { memo } from 'react';
import { gridToWorld, getEvalColor, STONE_HEIGHT, ABOVE_STONE } from '../constants';
import type { GameState } from '../../../api';

interface EvalDotsProps {
  gameState: GameState;
}

const EvalDots = ({ gameState }: EvalDotsProps) => {
  const boardSize = gameState.board_size[0];

  return (
    <group>
      {gameState.stones.map(([, coords, scoreLoss], index) => {
        if (!coords || scoreLoss == null) return null;
        const [x, y] = coords;
        const pos = gridToWorld(x, y, boardSize);
        const color = getEvalColor(scoreLoss);

        // Stone apex is at center Y + STONE_HEIGHT. Dot sits just above to avoid clipping.
        const dotY = pos[1] + STONE_HEIGHT + ABOVE_STONE;

        return (
          <mesh key={`eval-${index}`} position={[pos[0], dotY, pos[2]]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.12, 16]} />
            <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} />
          </mesh>
        );
      })}
    </group>
  );
};

export default memo(EvalDots);
