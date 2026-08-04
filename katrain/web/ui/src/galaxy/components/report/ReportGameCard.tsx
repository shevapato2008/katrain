import { useState } from 'react';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import {
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from '@mui/material';

import { useTranslation } from '../../../hooks/useTranslation';
import { translateResult } from '../../../utils/resultTranslation';
import type { UserGameSummary } from '../../../api/userGamesApi';
import type { ReportGameStatus } from '../../../features/report/reportModel';
import { isScoringGame } from '../../../utils/gameTypes';

export type { ReportGameStatus } from '../../../features/report/reportModel';

interface ReportGameCardProps {
  game: UserGameSummary;
  selected?: boolean;
  reportState: ReportGameStatus;
  onSelect: () => void;
  onCreateReport: (reportType: 'normal' | 'deep') => void;
  onOpenReport: (taskId: number) => void;
  onRetry: (taskId: number) => void;
  onDelete: () => void;
}

function reportBadgeColor(reportType: 'normal' | 'deep') {
  return reportType === 'normal' ? '#5e88c4' : '#4caf50';
}

function getGameDisplayTitle(game: UserGameSummary, t: (key: string, fallback?: string) => string): string {
  if (game.source === 'play_ai') {
    return isScoringGame(game.game_type)
      ? t('report:title_ai_ranked', 'AI Ranked Play')
      : t('report:title_ai_free', 'AI Free Play');
  }
  if (game.source === 'play_human') return t('report:title_human', 'Human vs Human');
  if (game.source === 'import') return t('report:title_import', 'Imported Game');
  if (game.source === 'kifu_library') return t('report:title_kifu', 'From Library');
  return t('report:unnamed_game', 'Untitled game');
}

export default function ReportGameCard({
  game,
  selected = false,
  reportState,
  onSelect,
  onCreateReport,
  onOpenReport,
  onRetry,
  onDelete,
}: ReportGameCardProps) {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const reportTypeLabel = (type: 'normal' | 'deep') =>
    type === 'normal' ? t('report:normal', 'Normal') : t('report:deep', 'Deep');

  const progressMeta = (() => {
    const activeTask = reportState.activeDeep || reportState.activeNormal;
    if (!activeTask) return null;
    const totalMoves = activeTask.total_moves > 0 ? activeTask.total_moves : game.move_count;
    const progress = totalMoves > 0
      ? (activeTask.analyzed_moves / totalMoves) * 100
      : 0;
    const typeLabel = reportTypeLabel(activeTask.report_type as 'normal' | 'deep');
    const statusLabel = activeTask.status === 'pending'
      ? `${typeLabel} ${t('report:queuing', 'Queued')}`
      : `${typeLabel} ${t('report:generating', 'Generating')}`;
    return { activeTask, progress, totalMoves, statusLabel };
  })();

  const normalColor = reportBadgeColor('normal');
  const deepColor = reportBadgeColor('deep');
  const showCompletedNormal = Boolean(reportState.completedNormal && !reportState.activeNormal);
  const showCompletedDeep = Boolean(reportState.completedDeep && !reportState.activeDeep);
  const showFailedNormal = Boolean(reportState.failedNormal && !reportState.activeNormal && !reportState.completedNormal);
  const showFailedDeep = Boolean(reportState.failedDeep && !reportState.activeDeep && !reportState.completedDeep);

  return (
    <Card
      sx={{
        bgcolor: selected ? 'rgba(76, 175, 80, 0.12)' : 'rgba(255,255,255,0.05)',
        border: selected ? 2 : 1,
        borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.1)',
        borderRadius: '8px',
        '&:hover': {
          borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.2)',
          bgcolor: selected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255,255,255,0.07)',
        },
      }}
    >
      <Box
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSelect();
          }
        }}
        sx={{ p: 1.5, cursor: 'pointer', outline: 'none' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
            {game.event || game.title || getGameDisplayTitle(game, t)}
          </Typography>
          {game.game_date && (
            <Typography variant="caption" color="text.secondary" sx={{ opacity: 0.7 }}>
              {game.game_date}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            {game.move_count} {t('report:moves_unit', 'moves')}
          </Typography>
          <IconButton
            size="small"
            aria-label={t('report:delete_game', 'Delete game')}
            onClick={(event) => {
              event.stopPropagation();
              onDelete();
            }}
            sx={{
              p: 0.25,
              color: 'text.secondary',
              opacity: 0.5,
              '&:hover': { color: 'error.main', opacity: 1 },
            }}
          >
            <DeleteOutlineIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                flexShrink: 0,
                mr: 0.75,
                bgcolor: '#1a1a1a',
                border: '1px solid rgba(255,255,255,0.18)',
              }}
            />
            <Typography variant="body2" noWrap sx={{ fontWeight: 700 }}>
              {game.player_black || t('report:black', 'Black')}
            </Typography>
            {game.black_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', ml: 0.5, flexShrink: 0 }}>
                {game.black_rank}
              </Typography>
            )}
          </Box>

          <Chip
            label={game.result ? translateResult(game.result, t, game.rules) : t('report:no_result', 'No result')}
            size="small"
            sx={{
              height: 22,
              fontSize: '0.72rem',
              bgcolor: 'rgba(255,255,255,0.06)',
              color: 'text.primary',
            }}
          />

          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, justifyContent: 'flex-end' }}>
            {game.white_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', mr: 0.5, flexShrink: 0 }}>
                {game.white_rank}
              </Typography>
            )}
            <Typography variant="body2" noWrap sx={{ fontWeight: 700 }}>
              {game.player_white || t('report:white', 'White')}
            </Typography>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                flexShrink: 0,
                ml: 0.75,
                bgcolor: '#e8e4df',
                border: '1px solid rgba(0,0,0,0.25)',
              }}
            />
          </Box>
        </Box>

        <Stack direction="row" spacing={1} sx={{ mt: 1.25 }} alignItems="center" flexWrap="wrap">
          {showCompletedNormal && (
            <Button
              size="small"
              variant="outlined"
              sx={{ color: normalColor, borderColor: normalColor }}
              onClick={(event) => {
                event.stopPropagation();
                onOpenReport(reportState.completedNormal!.id);
              }}
            >
              {t('report:normal', 'Normal')}
            </Button>
          )}
          {showCompletedDeep && (
            <Button
              size="small"
              variant="outlined"
              sx={{ color: deepColor, borderColor: deepColor }}
              onClick={(event) => {
                event.stopPropagation();
                onOpenReport(reportState.completedDeep!.id);
              }}
            >
              {t('report:deep', 'Deep')}
            </Button>
          )}

          {showFailedNormal && (
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={(event) => {
                event.stopPropagation();
                onRetry(reportState.failedNormal!.id);
              }}
            >
              {t('report:retry_normal', 'Retry normal')}
            </Button>
          )}
          {showFailedDeep && (
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={(event) => {
                event.stopPropagation();
                onRetry(reportState.failedDeep!.id);
              }}
            >
              {t('report:retry_deep', 'Retry deep')}
            </Button>
          )}

          {!progressMeta && (!showCompletedNormal || !showCompletedDeep) && !showFailedNormal && !showFailedDeep && (
            <>
              <Button
                size="small"
                variant="contained"
                onClick={(event) => {
                  event.stopPropagation();
                  setAnchorEl(event.currentTarget);
                }}
              >
                {showCompletedNormal && !showCompletedDeep
                  ? t('report:generate_deep', 'Generate deep report')
                  : !showCompletedNormal && showCompletedDeep
                    ? t('report:generate_normal', 'Generate normal report')
                    : t('report:generate', 'Generate report')}
              </Button>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => {
                  setAnchorEl(null);
                }}
              >
                {!showCompletedNormal && (
                  <MenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      setAnchorEl(null);
                      onCreateReport('normal');
                    }}
                  >
                    {t('report:normal', 'Normal')}
                  </MenuItem>
                )}
                {!showCompletedDeep && (
                  <MenuItem
                    onClick={(event) => {
                      event.stopPropagation();
                      setAnchorEl(null);
                      onCreateReport('deep');
                    }}
                  >
                    {t('report:deep', 'Deep')}
                  </MenuItem>
                )}
              </Menu>
            </>
          )}
        </Stack>

        {progressMeta && (
          <Box sx={{ mt: 1.25 }}>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
              <Typography variant="caption" color="warning.main">
                {progressMeta.statusLabel}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {progressMeta.activeTask.analyzed_moves}/{progressMeta.totalMoves || '?'}
              </Typography>
            </Stack>
            <LinearProgress variant="determinate" value={progressMeta.progress} />
          </Box>
        )}
      </Box>
    </Card>
  );
}
