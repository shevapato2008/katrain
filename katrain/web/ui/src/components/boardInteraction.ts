import type { GameState } from '../api';

export type BoardIntersectionAction =
  | { kind: 'move'; x: number; y: number }
  | { kind: 'navigate'; nodeId: number }
  | { kind: 'ignore' };

export function resolveBoardIntersectionAction(
  gameState: GameState,
  x: number,
  y: number,
  allowNavigation: boolean,
): BoardIntersectionAction {
  const clickedStone = gameState.stones.find(
    stone => stone[1]?.[0] === x && stone[1][1] === y,
  );

  if (!clickedStone) {
    return { kind: 'move', x, y };
  }

  const moveNumber = clickedStone[3];
  if (allowNavigation && moveNumber != null && moveNumber >= 0 && moveNumber < gameState.history.length) {
    return { kind: 'navigate', nodeId: gameState.history[moveNumber].node_id };
  }

  return { kind: 'ignore' };
}
