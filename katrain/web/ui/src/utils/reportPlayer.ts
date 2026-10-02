/** Color to play after a report position. SGF colors also cover handicap and white-to-play games. */
export function reportPlayerToMove(colors: readonly ('B' | 'W')[] | null | undefined, boardCursor: number, setupCount = 0): 'B' | 'W' {
  const next = colors?.[boardCursor];
  if (next) return next;
  const last = colors?.[boardCursor - 1];
  if (last) return last === 'B' ? 'W' : 'B';
  return setupCount > 0 ? 'W' : 'B';
}
