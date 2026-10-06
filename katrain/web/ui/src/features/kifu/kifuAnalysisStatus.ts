import type { KifuAnalysisDetail } from '../../types/kifu';

export function kifuAnalysisStatus(
  detail: KifuAnalysisDetail | null,
  error: boolean,
  t: (key: string, fallback: string) => string,
): string {
  if (error) return t('kifu:analysis_read_error', '分析状态暂时无法读取');
  if (!detail) return t('kifu:analysis_loading', '正在读取分析');
  if (detail.status === 'rules_unresolved') return t('kifu:rules_unresolved', '规则待核验');
  if (detail.status === 'unavailable') return t('kifu:analysis_unavailable', '尚未安排分析');
  if (detail.status === 'pending') return t('kifu:analysis_pending', '等待分析');
  if (detail.status === 'running') return `${t('kifu:analysis_running', '分析中')} · ${detail.analyzed_moves} / ${detail.total_moves} ${t('kifu:moves_unit', '手')}`;
  if (detail.status === 'failed') return t('kifu:analysis_failed', '分析未完成');
  if (detail.status === 'completed' && detail.parameters_verified && detail.analysis_parameters?.verified && detail.moves.length > 0) return t('kifu:analysis_completed', '分析已完成');
  return t('kifu:analysis_failed', '分析未完成');
}
