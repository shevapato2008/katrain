import type { TopMove } from '../../types/live';

export type ReportCandidate = Pick<TopMove, 'move' | 'pv'> & Partial<Omit<TopMove, 'move' | 'pv'>> & {
  isActualMove: boolean;
  percentage: number | null;
};

/** Keep the full stored candidate denominator, including candidates below the visible five. */
export function reportCandidates(candidates: readonly TopMove[], actualMove?: string | null, limit = 5): ReportCandidate[] {
  const weight = (value: number | undefined) => value != null && Number.isFinite(value) ? Math.max(0, value) : 0;
  const psv = candidates.reduce((sum, move) => sum + weight(move.psv), 0);
  const visits = candidates.reduce((sum, move) => sum + weight(move.visits), 0);
  const rows: ReportCandidate[] = candidates.slice(0, limit).map(move => ({
    ...move, isActualMove: move.move === actualMove,
    percentage: psv > 0 ? weight(move.psv) / psv * 100 : visits > 0 ? weight(move.visits) / visits * 100 : null,
  }));
  if (actualMove && !rows.some(move => move.move === actualMove)) {
    const candidate = candidates.find(move => move.move === actualMove);
    rows.push(candidate ? {
      ...candidate, isActualMove: true,
      percentage: psv > 0 ? weight(candidate.psv) / psv * 100 : visits > 0 ? weight(candidate.visits) / visits * 100 : null,
    } : { move: actualMove, pv: [], isActualMove: true, percentage: null });
  }
  return rows;
}
