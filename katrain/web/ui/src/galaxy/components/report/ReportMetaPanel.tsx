import { Box, Chip, LinearProgress, Stack, Typography } from '@mui/material';

import { useTranslation } from '../../../hooks/useTranslation';
import type { MoveAnalysis } from '../../../types/live';
import type { UserGameDetail } from '../../api/userGamesApi';
import type { ReportTaskSummary } from '../../api/reportApi';

interface ReportMetaPanelProps {
  game: UserGameDetail | null;
  task: ReportTaskSummary | null;
  currentMove: number;
  currentAnalysis: MoveAnalysis | null;
}

function reportTypeLabel(reportType: string | undefined, t: (key: string, fallback: string) => string) {
  return reportType === 'deep' ? t('report:deep', 'Deep') : t('report:normal', 'Normal');
}

function statusLabel(status: string | undefined, t: (key: string, fallback: string) => string) {
  if (status === 'completed') return t('report:completed', 'Completed');
  if (status === 'running') return t('report:generating', 'Generating');
  if (status === 'pending') return t('report:queuing', 'Queued');
  if (status === 'failed') return t('report:failed', 'Failed');
  return t('report:unknown_status', 'Unknown');
}

function rulesLabel(rules: string | undefined, t: (key: string, fallback: string) => string) {
  if (rules === 'japanese') return t('report:japanese_rules', 'Japanese');
  if (rules === 'korean') return t('report:korean_rules', 'Korean');
  return t('report:chinese_rules', 'Chinese');
}

export default function ReportMetaPanel({
  game,
  task,
  currentMove,
  currentAnalysis,
}: ReportMetaPanelProps) {
  const { t } = useTranslation();
  const blackWinrate = currentAnalysis ? currentAnalysis.winrate * 100 : null;
  const whiteWinrate = blackWinrate == null ? null : 100 - blackWinrate;
  const progress = blackWinrate ?? 50;
  const scoreLead = currentAnalysis?.score_lead ?? null;
  const blackAdvantage = scoreLead == null ? (blackWinrate ?? 50) >= 50 : scoreLead >= 0;

  return (
    <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Chip label={statusLabel(task?.status, t)} size="small" variant="outlined" />
        {game?.game_date && <Typography variant="caption" color="text.secondary">{game.game_date}</Typography>}
        {task && (
          <Chip
            label={reportTypeLabel(task.report_type, t)}
            size="small"
            sx={{
              bgcolor: task.report_type === 'deep' ? 'rgba(76, 175, 80, 0.18)' : 'rgba(94, 136, 196, 0.18)',
              color: 'text.primary',
            }}
          />
        )}
      </Stack>

      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
        {game?.event || game?.title || t('report:unnamed_game', 'Untitled game')}
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, my: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                bgcolor: '#000',
                boxShadow: '0 1px 2px rgba(0,0,0,0.3)',
              }}
            />
            <Typography variant="body1" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
              {game?.player_black || t('report:black', 'Black')}
            </Typography>
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary">vs</Typography>
        <Box sx={{ flex: 1, textAlign: 'right' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
            <Typography variant="body1" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
              {game?.player_white || t('report:white', 'White')}
            </Typography>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                bgcolor: '#fff',
                border: '1px solid',
                borderColor: 'grey.400',
                boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
              }}
            />
          </Box>
        </Box>
      </Box>

      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" fontWeight={blackAdvantage ? 'bold' : 'normal'}>
            {blackWinrate != null ? `${blackWinrate.toFixed(1)}%` : '-'}
          </Typography>
          <Typography
            variant="caption"
            color={scoreLead != null && scoreLead > 0 ? 'text.primary' : 'text.secondary'}
            fontWeight="bold"
          >
            {scoreLead != null ? `${scoreLead > 0 ? '+' : ''}${scoreLead.toFixed(1)} ${t('report:points_unit', 'pts')}` : `${t('report:move_prefix', 'Move')} ${currentMove}`}
          </Typography>
          <Typography variant="caption" fontWeight={!blackAdvantage ? 'bold' : 'normal'}>
            {whiteWinrate != null ? `${whiteWinrate.toFixed(1)}%` : '-'}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            height: 8,
            borderRadius: 4,
            bgcolor: 'grey.200',
            '& .MuiLinearProgress-bar': {
              bgcolor: '#000',
              borderRadius: 4,
            },
          }}
        />
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          {rulesLabel(game?.rules, t)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t('report:komi_label', 'Komi')} {game?.komi ?? '-'}
        </Typography>
      </Box>
    </Box>
  );
}
