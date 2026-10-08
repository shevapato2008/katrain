import { useEffect, useRef } from 'react';
import { useSound } from './useSound';

/** Sound follows an explicit replay cursor, never an asynchronously arriving frontier. */
export function useReplayStoneSound({ identity, cursor, move, ready, selected }: {
  identity: number | null;
  cursor: number;
  move: string | undefined;
  ready: boolean;
  selected: boolean;
}) {
  const { play } = useSound();
  const previous = useRef<{ identity: number | null; cursor: number } | null>(null);
  useEffect(() => {
    if (!ready) { previous.current = null; return; }
    if (selected && previous.current?.identity === identity && previous.current.cursor !== cursor
      && cursor > 0 && move && /^[A-HJ-Z][1-9]\d*$/i.test(move)) play('stone');
    previous.current = { identity, cursor };
  }, [identity, cursor, move, ready, selected, play]);
}
