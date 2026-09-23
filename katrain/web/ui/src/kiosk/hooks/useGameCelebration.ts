import { useEffect, useRef, useState } from 'react';
import type { GameState } from '../../api';
import { useSound } from '../../hooks/useSound';

/** Celebrate a live human win, never an ended game loaded or revisited for review. */
export function useGameCelebration(
  sessionId: string | null | undefined,
  gameState: GameState | null | undefined,
  humanColor: 'B' | 'W' | null,
): boolean {
  const { play } = useSound();
  const previous = useRef<{ key: string | null; finished: boolean }>({ key: null, finished: false });
  const finishedGames = useRef(new Set<string>());
  const [celebratingKey, setCelebratingKey] = useState<string | null>(null);
  const key = sessionId && gameState ? `${sessionId}|${gameState.game_id}` : null;
  const result = gameState?.end_result || gameState?.terminal_result || null;
  const finished = Boolean(result) && !gameState?.awaiting_count;
  const match = result?.match(/^([BW])\+(R|T|F|\d+(?:\.\d+)?)$/);
  const winner = match && (/[RTF]/.test(match[2]) || Number(match[2]) > 0) ? match[1] : null;
  const humanWon = winner !== null && (
    winner === humanColor || (humanColor === null && gameState?.game_type === 'pvp_local')
  );

  useEffect(() => {
    const prior = previous.current;
    previous.current = { key, finished };
    if (!key || !finished) return;

    const alreadyFinished = finishedGames.current.has(key);
    finishedGames.current.add(key);
    if (prior.key !== key || prior.finished || alreadyFinished || !humanWon) return;

    let timer: ReturnType<typeof setTimeout> | undefined;
    const frame = requestAnimationFrame(() => {
      play('solved');
      setCelebratingKey(key);
      timer = setTimeout(() => setCelebratingKey(null), 1600);
    });
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timer);
      setCelebratingKey(null);
    };
  }, [key, finished, humanWon, play]);

  return key !== null && celebratingKey === key && finished && humanWon;
}
