import { useCallback, memo } from 'react';
import type { ThreeEvent } from '@react-three/fiber';
import { getBoardDimensions, worldToGrid, BOARD_SURFACE_Y, OVERLAY_OFFSET } from './constants';
import type { GameState } from '../../api';

interface RaycastClickProps {
  gameState: GameState;
  onMove: (x: number, y: number) => void;
  onNavigate?: (nodeId: number) => void;
  playerColor?: 'B' | 'W' | null;
  onHover: (pos: { col: number; row: number } | null) => void;
}

const RaycastClick = ({
  gameState, onMove, onNavigate, playerColor, onHover,
}: RaycastClickProps) => {
  const boardSize = gameState.board_size[0];
  const dims = getBoardDimensions(boardSize);

  const handleClick = useCallback((event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    if (gameState.end_result) return;
    if (playerColor && gameState.player_to_move !== playerColor) return;

    const grid = worldToGrid(event.point.x, event.point.z, boardSize);
    if (!grid) return;

    const { col, row } = grid;

    // Check for existing stone → navigate to that move
    const clickedStone = gameState.stones.find(
      s => s[1] && s[1][0] === col && s[1][1] === row
    );

    if (clickedStone && onNavigate) {
      const moveNumber = clickedStone[3];
      if (moveNumber != null && moveNumber >= 0 && moveNumber < gameState.history.length) {
        onNavigate(gameState.history[moveNumber].node_id);
      }
    } else if (!clickedStone) {
      onMove(col, row);
    }
  }, [gameState.end_result, gameState.player_to_move, gameState.stones, gameState.history, boardSize, onMove, onNavigate, playerColor]);

  const handlePointerMove = useCallback((event: ThreeEvent<PointerEvent>) => {
    const grid = worldToGrid(event.point.x, event.point.z, boardSize);
    onHover(grid ? { col: grid.col, row: grid.row } : null);
  }, [boardSize, onHover]);

  const handlePointerLeave = useCallback(() => {
    onHover(null);
  }, [onHover]);

  return (
    <mesh
      position={[0, BOARD_SURFACE_Y + OVERLAY_OFFSET, 0]}
      rotation={[-Math.PI / 2, 0, 0]}
      onClick={handleClick}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <planeGeometry args={[dims.boardWidth, dims.boardWidth]} />
      <meshBasicMaterial visible={false} />
    </mesh>
  );
};

export default memo(RaycastClick);
