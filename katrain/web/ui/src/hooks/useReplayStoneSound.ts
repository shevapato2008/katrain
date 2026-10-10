import { useEffect, useRef } from 'react';
import { useSound } from './useSound';

/** Display coordinates must describe a stone inside the actual board. */
export function isReplayStoneMove(move: string | null | undefined, boardSize = 19): boolean {
  const coordinate = move?.match(/^([A-HJ-Z])([1-9]\d*)$/i);
  if (!coordinate) return false;
  const column = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'.indexOf(coordinate[1].toUpperCase());
  const row = Number(coordinate[2]);
  return column >= 0 && column < boardSize && row > 0 && row <= boardSize;
}

/** Sound follows an explicit replay cursor, never an asynchronously arriving frontier. */
export function useReplayStoneSound({ identity, cursor, move, ready, selected, boardSize = 19 }: {
  identity: string | number | null;
  cursor: number;
  move: string | undefined;
  ready: boolean;
  selected: boolean;
  boardSize?: number;
}) {
  const { play } = useSound();
  const previous = useRef<{ identity: string | number | null; cursor: number } | null>(null);
  useEffect(() => {
    if (!ready) { previous.current = null; return; }
    if (identity !== null && selected && previous.current?.identity === identity && previous.current.cursor !== cursor
      && cursor > 0 && isReplayStoneMove(move, boardSize)) play('stone');
    previous.current = { identity, cursor };
  }, [identity, cursor, move, ready, selected, boardSize, play]);
}
