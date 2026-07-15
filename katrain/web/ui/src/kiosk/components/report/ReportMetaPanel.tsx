import { Box, Chip, LinearProgress, Typography } from '@mui/material';

import type { ReportTaskSummary } from '../../../api/reportApi';
import type { UserGameDetail } from '../../../api/userGamesApi';
import { useTranslation } from '../../../hooks/useTranslation';
import type { MoveAnalysis } from '../../../types/live';
import { translateResult } from '../../../utils/resultTranslation';

interface ReportMetaPanelProps {
  game: UserGameDetail | null;
  task: ReportTaskSummary | null;
  currentMove: number;
  currentAnalysis: MoveAnalysis | null;
}

type Translate = (key: string, fallback?: string) => string;

const STATUS_LABELS: Record<string, [string, string]> = {
  pending: ['report:queuing', '排队中'],
  running: ['report:generating', '生成中'],
  completed: ['report:completed', '已完成'],
  failed: ['report:failed', '失败'],
};

const SOURCE_LABELS: Record<string, [string, string]> = {
  import: ['report:source_import', '本地导入'],
  play_ai: ['report:source_play_ai', 'AI 对弈'],
  play_human: ['report:source_play_human', '人人对弈'],
  kifu_library: ['report:source_kifu_library', '棋谱库'],
};

const RULES_LABELS: Record<string, [string, string]> = {
  chinese: ['report:chinese_rules', '中国规则'],
  japanese: ['report:japanese_rules', '日本规则'],
  korean: ['report:korean_rules', '韩国规则'],
  aga: ['report:aga_rules', 'AGA 规则'],
};

function translatedLabel(
  value: string | undefined,
  labels: Record<string, [string, string]>,
  unknown: [string, string],
  t: Translate,
): string {
  const [key, fallback] = (value && labels[value]) || unknown;
  return t(key, fallback);
}

function statusLabel(status: string | undefined, t: Translate): string {
  return translatedLabel(status, STATUS_LABELS, ['report:unknown_status', '状态未知'], t);
}

function sourceLabel(source: string | undefined, t: Translate): string {
  return translatedLabel(source, SOURCE_LABELS, ['report:source_other', '其他来源'], t);
}

function rulesLabel(rules: string | undefined, t: Translate): string {
  if (rules && !RULES_LABELS[rules]) return rules;
  return translatedLabel(rules, RULES_LABELS, ['report:unknown_rules', '规则未知'], t);
}

function finiteNumber(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nonNegativeInteger(value: number | null | undefined): number {
  const finiteValue = finiteNumber(value);
  return finiteValue == null ? 0 : Math.max(0, Math.floor(finiteValue));
}

function positiveInteger(value: number | null | undefined): number | null {
  const normalized = nonNegativeInteger(value);
  return normalized > 0 ? normalized : null;
}

export default function ReportMetaPanel({
  game,
  task,
  currentMove,
  currentAnalysis,
}: ReportMetaPanelProps) {
  const { t } = useTranslation();
  const title = game?.event || game?.title || t('report:unnamed_game', '未命名棋局');
  const fullTitle = game?.round_name ? `${title} · ${game.round_name}` : title;
  const reportType = task?.report_type === 'deep'
    ? t('report:deep', '深度复盘')
    : task?.report_type === 'normal'
      ? t('report:normal', '普通复盘')
      : t('report:unknown_type', '类型未知');
  const totalMoves = positiveInteger(task?.total_moves) ?? positiveInteger(game?.move_count);
  const rawAnalyzedMoves = nonNegativeInteger(task?.analyzed_moves);
  const analyzedMoves = totalMoves == null ? rawAnalyzedMoves : Math.min(rawAnalyzedMoves, totalMoves);
  const reportProgress = totalMoves
    ? Math.max(0, Math.min(100, (analyzedMoves / totalMoves) * 100))
    : 0;
  const winrate = finiteNumber(currentAnalysis?.winrate);
  const blackWinrate = winrate == null
    ? null
    : Math.max(0, Math.min(1, winrate)) * 100;
  const whiteWinrate = blackWinrate == null ? null : 100 - blackWinrate;
  const scoreLead = finiteNumber(currentAnalysis?.score_lead);
  const displayedMove = nonNegativeInteger(currentMove);
  const komi = finiteNumber(game?.komi);
  const isActiveTask = task?.status === 'pending' || task?.status === 'running';

  return (
    <Box
      data-testid="report-meta-panel"
      sx={{
        minWidth: 0,
        px: 1.5,
        py: 0.75,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.default',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
        <Typography
          data-testid="report-meta-title"
          title={fullTitle}
          noWrap
          sx={{ flex: 1, minWidth: 0, fontSize: 15, fontWeight: 700 }}
        >
          {fullTitle}
        </Typography>
        {task && (
          <>
            <Chip
              data-testid="report-meta-status"
              label={statusLabel(task.status, t)}
              size="small"
              color={task.status === 'failed' ? 'error' : task.status === 'completed' ? 'success' : 'warning'}
              variant="outlined"
              sx={{ flexShrink: 0, height: 26 }}
            />
            <Chip
              data-testid="report-meta-type"
              label={reportType}
              size="small"
              sx={{
                flexShrink: 0,
                height: 26,
                bgcolor: task.report_type === 'deep' ? 'primary.dark' : 'var(--raise2)',
              }}
            />
          </>
        )}
      </Box>

      <Box
        data-testid="report-meta-identity-row"
        sx={{
          minHeight: 48,
          display: 'grid',
          gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)',
          alignItems: 'center',
          gap: 1,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ minWidth: 0, display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
          <Typography noWrap sx={{ minWidth: 0, fontSize: 14, fontWeight: 700 }}>
            {game?.player_black || t('report:black', '黑方')}
          </Typography>
          {game?.black_rank && <Typography variant="caption" color="text.secondary">{game.black_rank}</Typography>}
        </Box>
        <Typography variant="caption" color="text.secondary">
          {game?.result ? translateResult(game.result, t, game.rules) : t('report:no_result', '暂无结果')}
        </Typography>
        <Box sx={{ minWidth: 0, display: 'flex', justifyContent: 'flex-end', alignItems: 'baseline', gap: 0.5 }}>
          {game?.white_rank && <Typography variant="caption" color="text.secondary">{game.white_rank}</Typography>}
          <Typography noWrap sx={{ minWidth: 0, fontSize: 14, fontWeight: 700 }}>
            {game?.player_white || t('report:white', '白方')}
          </Typography>
        </Box>
      </Box>

      <Box
        data-testid="report-meta-analysis-row"
        sx={{
          minHeight: 48,
          display: 'grid',
          gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.15fr)',
          alignItems: 'center',
          gap: 1.5,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ flexShrink: 0 }}>
              {t('report:move_prefix', '第')} {displayedMove} {t('report:moves_unit', '手')}
            </Typography>
            {scoreLead != null && (
              <Typography variant="caption" color="primary.light" noWrap sx={{ minWidth: 0 }}>
                {scoreLead >= 0 ? t('report:black_leads', '黑领先') : t('report:white_leads', '白领先')}{' '}
                {Math.abs(scoreLead).toFixed(1)} {t('report:points_unit', '目')}
              </Typography>
            )}
          </Box>
          {blackWinrate == null || whiteWinrate == null ? (
            <Typography variant="caption" color="text.secondary">
              {t('report:no_current_analysis', '当前手暂无分析')}
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
              <Typography variant="caption" noWrap>{t('report:black', '黑')} {blackWinrate.toFixed(1)}%</Typography>
              <Typography variant="caption" noWrap>{t('report:white', '白')} {whiteWinrate.toFixed(1)}%</Typography>
            </Box>
          )}
        </Box>

        {task && (
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block', mb: 0.4 }}>
              {t('report:analyzed', '已分析')} {analyzedMoves} / {totalMoves ?? '?'} {t('report:moves_unit', '手')}
            </Typography>
            {(totalMoves != null || isActiveTask) && (
              <LinearProgress
                aria-label={t('report:analysis_progress', '复盘分析进度')}
                variant={totalMoves == null ? 'indeterminate' : 'determinate'}
                value={totalMoves == null ? undefined : reportProgress}
                sx={{ height: 5, borderRadius: 3, bgcolor: 'divider' }}
              />
            )}
          </Box>
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
        {game?.source && (
          <Typography data-testid="report-meta-source" variant="caption" color="text.secondary" noWrap>
            {sourceLabel(game.source, t)}
          </Typography>
        )}
        {game && (
          <>
            <Typography data-testid="report-meta-rules" variant="caption" color="text.secondary" noWrap>
              {rulesLabel(game.rules, t)}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {t('report:komi_label', '贴目')} {komi ?? '-'}
            </Typography>
          </>
        )}
      </Box>
    </Box>
  );
}
