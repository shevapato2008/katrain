import { useEffect, useMemo, useState } from 'react';
import { KifuAPI } from '../../api/kifuApi';
import type { KifuAnalysisDetail } from '../../types/kifu';
import type { MoveAnalysis } from '../../types/live';

export function useKifuAnalysis(albumId: number | null) {
  const [loaded, setLoaded] = useState<{ id: number; detail: KifuAnalysisDetail } | null>(null);
  const [failedId, setFailedId] = useState<number | null>(null);

  useEffect(() => {
    if (albumId === null) return;
    let cancelled = false;
    const fetchAnalysis = async () => {
      try {
        const detail = await KifuAPI.getAnalysis(albumId);
        if (!cancelled) { setLoaded({ id: albumId, detail }); setFailedId(null); }
      } catch {
        if (!cancelled) setFailedId(albumId);
      }
    };
    void fetchAnalysis();
    const timer = window.setInterval(() => {
      if (loaded?.id === albumId && ['pending', 'running'].includes(loaded.detail.status)) void fetchAnalysis();
    }, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [albumId, loaded?.id, loaded?.detail.status]);

  const detail = loaded?.id === albumId ? loaded.detail : null;
  const error = failedId === albumId;
  const analysisByMove = useMemo((): Record<number, MoveAnalysis> => {
    const map: Record<number, MoveAnalysis> = {};
    for (const row of detail?.moves ?? []) {
      if (row.winrate == null || row.score_lead == null) continue;
      const deltaScore = row.delta_score ?? 0;
      map[row.move_number] = {
        match_id: String(detail!.canonical_album_id), move_number: row.move_number,
        move: row.actual_move, player: row.actual_player, winrate: row.winrate,
        score_lead: row.score_lead, top_moves: row.top_moves ?? [], ownership: row.ownership,
        delta_score: deltaScore, delta_winrate: row.delta_winrate ?? 0,
        is_brilliant: deltaScore >= 2, is_mistake: deltaScore <= -3,
        is_questionable: deltaScore <= -1.5, grade: row.grade,
        points_lost: row.points_lost, is_top_move: row.is_top_move,
        top_prior: row.top_prior, brilliance: row.brilliance,
      };
    }
    return map;
  }, [detail]);
  return { detail, analysisByMove, error };
}
