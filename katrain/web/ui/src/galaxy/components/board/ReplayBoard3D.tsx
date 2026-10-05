import { lazy, Suspense, useMemo } from 'react';
import { Box, CircularProgress } from '@mui/material';

import type { GameState } from '../../../api';
import { buildReplayBoardState, parseMove, type AiMoveMarker } from '../../../components/live/LiveBoard';

const Board3D = lazy(() => import('../../../components/Board3D'));

interface Props {
  moves: string[];
  currentMove: number;
  boardSize?: number;
  stoneColors?: ('B' | 'W')[];
  handicapCount?: number;
  showCoordinates: boolean;
  showMoveNumbers: boolean;
  showAiMarkers: boolean;
  aiMarkers?: AiMoveMarker[] | null;
  showTerritory: boolean;
  ownership?: number[][] | null;
  tryMoves?: string[];
  onTryMove?: (move: string) => void;
}

const columns = 'ABCDEFGHJKLMNOPQRST';

/** Adapt the same captured-stone position used by LiveBoard to the existing 3D renderer. */
export default function ReplayBoard3D({ moves, currentMove, boardSize = 19, stoneColors, handicapCount = 0, showCoordinates, showMoveNumbers, showAiMarkers, aiMarkers, showTerritory, ownership, tryMoves, onTryMove }: Props) {
  const gameState = useMemo(() => {
    const replayMoves = tryMoves?.length ? [...moves.slice(0, currentMove), ...tryMoves] : moves;
    const cursor = currentMove + (tryMoves?.length ?? 0);
    const { board, moveNumbers, lastMove, lastPlayer } = buildReplayBoardState(replayMoves, cursor, boardSize, stoneColors, handicapCount);
    const stones: GameState['stones'] = [];
    for (let y = 0; y < boardSize; y++) for (let x = 0; x < boardSize; x++) {
      const color = board[y][x];
      if (color) stones.push([color, [x, y], null, moveNumbers[y][x]]);
    }
    const analysisMoves = aiMarkers?.map((marker) => ({
      coords: parseMove(marker.move), winrate: marker.winrate, visits: marker.visits, scoreLoss: 0,
    })) ?? [];
    // Board3D only reads this subset of GameState in replay mode. RaycastClick uses
    // stones and history to decide whether a point is available for a trial move.
    return {
      board_size: [boardSize, boardSize], current_node_index: cursor, current_node_id: cursor,
      stones, last_move: lastMove, player_to_move: lastPlayer === 'B' ? 'W' : 'B',
      history: [], children: [], ghost_stones: [], end_result: null,
      analysis: { moves: analysisMoves, ownership: ownership?.map((_, y) => ownership[boardSize - 1 - y]) }, trainer_settings: { max_top_moves_on_board: 5 },
    } as unknown as GameState;
  }, [moves, currentMove, boardSize, stoneColors, handicapCount, tryMoves, aiMarkers, ownership]);

  return <Box data-testid="replay-board-3d" sx={{ width: '100%', height: '100%' }}>
    <Suspense fallback={<CircularProgress />}>
      <Board3D gameState={gameState} onMove={(x, y) => onTryMove?.(`${columns[x]}${y + 1}`)} readOnly={!onTryMove} analysisToggles={{ coords: showCoordinates, numbers: showMoveNumbers, hints: showAiMarkers, ownership: showTerritory }} />
    </Suspense>
  </Box>;
}
