import { useState, type KeyboardEvent, type MouseEvent } from 'react';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  LinearProgress,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from '@mui/material';

import type { ReportTaskSummary, ReportType } from '../../../api/reportApi';
import type { UserGameSummary } from '../../../api/userGamesApi';
import type { ReportGameStatus } from '../../../features/report/reportModel';
import { useTranslation } from '../../../hooks/useTranslation';
import KioskResultBadge from '../game/KioskResultBadge';
import { isScoringGame } from '../../../utils/gameTypes';

export type { ReportGameStatus } from '../../../features/report/reportModel';

interface ReportGameCardProps {
  game: UserGameSummary;
  selected?: boolean;
  reportState: ReportGameStatus;
  onSelect: () => void;
  onCreateReport: (reportType: ReportType) => void;
  onOpenReport: (taskId: number) => void;
  onRetry: (taskId: number) => void;
  onDelete: () => void;
}

type TFunction = (key: string, fallback?: string) => string;

function sourceTitle(game: UserGameSummary, t: TFunction): string {
  if (game.source === 'play_ai') {
    return isScoringGame(game.game_type)
      ? t('report:title_ai_ranked', 'AI 排位对局')
      : t('report:title_ai_free', 'AI 自由对局');
  }
  if (game.source === 'play_human') return t('report:title_human', '人人对局');
  if (game.source === 'import') return t('report:title_import', '本地导入棋谱');
  if (game.source === 'kifu_library') return t('report:title_kifu', '棋谱库导入');
  return t('report:unnamed_game', '未命名棋局');
}

function visibleTask(
  active: ReportTaskSummary | undefined,
  completed: ReportTaskSummary | undefined,
  failed: ReportTaskSummary | undefined,
): ReportTaskSummary | undefined {
  return active ?? completed ?? failed;
}

interface ReportStateRowProps {
  gameMoveCount: number;
  reportType: ReportType;
  task: ReportTaskSummary;
  onOpenReport: (taskId: number) => void;
  onRetry: (taskId: number) => void;
  t: TFunction;
}

function ReportStateRow({
  gameMoveCount,
  reportType,
  task,
  onOpenReport,
  onRetry,
  t,
}: ReportStateRowProps) {
  const typeLabel = reportType === 'normal'
    ? t('report:normal', '普通复盘')
    : t('report:deep', '深度复盘');
  const isActive = task.status === 'pending' || task.status === 'running';
  const totalMoves = task.total_moves > 0 ? task.total_moves : gameMoveCount;
  const rawProgress = totalMoves > 0 ? (task.analyzed_moves / totalMoves) * 100 : 0;
  const progress = Math.round(Math.max(0, Math.min(100, rawProgress)));
  const statusLabel = task.status === 'pending'
    ? t('report:queuing', '排队中')
    : task.status === 'running'
      ? t('report:generating', '生成中')
      : task.status === 'completed'
        ? t('report:completed', '已完成')
        : t('report:failed', '失败');

  return (
    <Box
      data-testid={`${reportType}-report-state`}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        minWidth: 0,
        py: 0.25,
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="caption"
          color={task.status === 'failed' ? 'error.main' : isActive ? 'warning.main' : 'text.secondary'}
          noWrap
          sx={{ display: 'block' }}
        >
          {typeLabel} · {statusLabel}
        </Typography>
        {isActive && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.4 }}>
            <LinearProgress
              data-testid={`${reportType}-report-progress`}
              variant="determinate"
              value={progress}
              aria-label={t(
                `report:${reportType}_progress`,
                `${typeLabel}进度`,
              )}
              sx={{ flex: 1, minWidth: 36, height: 5, borderRadius: 3 }}
            />
            <Typography variant="caption" color="text.secondary" noWrap>
              {task.analyzed_moves} / {totalMoves || '?'} {t('report:moves_unit', '手')}
            </Typography>
          </Stack>
        )}
      </Box>

      {task.status === 'completed' && (
        <Button
          size="small"
          variant="outlined"
          aria-label={t(`report:open_${reportType}`, `打开${typeLabel}`)}
          onClick={(event) => {
            event.stopPropagation();
            onOpenReport(task.id);
          }}
          sx={{ minWidth: 48, minHeight: 48, flexShrink: 0, px: 1.25 }}
        >
          {t(`report:open_${reportType}`, `打开${typeLabel}`)}
        </Button>
      )}
      {task.status === 'failed' && (
        <Button
          size="small"
          variant="outlined"
          color="error"
          aria-label={t(`report:retry_${reportType}`, `重试${typeLabel}`)}
          onClick={(event) => {
            event.stopPropagation();
            onRetry(task.id);
          }}
          sx={{ minWidth: 48, minHeight: 48, flexShrink: 0, px: 1.25 }}
        >
          {t(`report:retry_${reportType}`, `重试${typeLabel}`)}
        </Button>
      )}
    </Box>
  );
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
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const heading = game.event || game.title || sourceTitle(game, t);
  const date = game.game_date || game.created_at?.slice(0, 10);
  const normalTask = visibleTask(
    reportState.activeNormal,
    reportState.completedNormal,
    reportState.failedNormal,
  );
  const deepTask = visibleTask(
    reportState.activeDeep,
    reportState.completedDeep,
    reportState.failedDeep,
  );

  const closeMenu = () => setMenuAnchor(null);
  const openMenu = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setMenuAnchor(event.currentTarget);
  };
  const runMenuAction = (event: MouseEvent<HTMLElement>, action: () => void) => {
    event.stopPropagation();
    closeMenu();
    action();
  };
  const handleSelectorKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect();
    }
  };

  return (
    <Card
      data-testid="report-game-card"
      data-selected={selected ? 'true' : 'false'}
      sx={{
        background: selected ? 'linear-gradient(135deg,#1f3a30,#18211f)' : 'background.paper',
        border: 1,
        borderColor: selected ? 'primary.main' : 'divider',
        borderRadius: '13px',
        overflow: 'hidden',
        '&:hover': { borderColor: selected ? 'primary.main' : '#3a4d45' },
      }}
    >
      <CardActionArea
        aria-label={`${t('report:select_game', '选择棋局')}：${heading}`}
        onClick={onSelect}
        onKeyDown={handleSelectorKeyDown}
        sx={{ p: 1.5, minWidth: 48, minHeight: 48 }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0, mb: 0.6 }}>
          <Typography
            data-testid="report-card-title"
            variant="caption"
            color="text.secondary"
            title={heading}
            noWrap
            sx={{ flex: 1, minWidth: 0 }}
          >
            {heading}
          </Typography>
          {game.round_name && (
            <Typography variant="caption" color="text.secondary" noWrap sx={{ opacity: 0.65, flexShrink: 0 }}>
              {game.round_name}
            </Typography>
          )}
          {date && (
            <Typography variant="caption" color="text.secondary" noWrap sx={{ opacity: 0.7, flexShrink: 0 }}>
              {date}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" noWrap sx={{ flexShrink: 0 }}>
            {game.move_count} {t('report:moves_unit', '手')}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
            <Box
              aria-hidden="true"
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                flexShrink: 0,
                mr: 0.7,
                bgcolor: '#1a1a1a',
                border: '1px solid rgba(255,255,255,0.18)',
                boxShadow: 'inset 0 -0.5px 1px rgba(255,255,255,0.1)',
              }}
            />
            <Typography data-testid="report-card-black" variant="body2" noWrap sx={{ minWidth: 0, fontWeight: 600 }}>
              {game.player_black || t('report:black', '黑方')}
            </Typography>
            {game.black_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', ml: 0.5, flexShrink: 0 }}>
                {game.black_rank}
              </Typography>
            )}
          </Box>

          <Box sx={{ px: 1, flexShrink: 0 }}>
            {game.result
              ? <KioskResultBadge result={game.result} rules={game.rules} />
              : (
                <Typography variant="caption" color="text.secondary" noWrap>
                  {t('report:no_result', '暂无结果')}
                </Typography>
              )}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, justifyContent: 'flex-end' }}>
            {game.white_rank && (
              <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', mr: 0.5, flexShrink: 0 }}>
                {game.white_rank}
              </Typography>
            )}
            <Typography data-testid="report-card-white" variant="body2" noWrap sx={{ minWidth: 0, fontWeight: 600 }}>
              {game.player_white || t('report:white', '白方')}
            </Typography>
            <Box
              aria-hidden="true"
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                flexShrink: 0,
                ml: 0.7,
                bgcolor: '#e8e4df',
                border: '1px solid rgba(0,0,0,0.25)',
                boxShadow: 'inset 0 0.5px 1px rgba(0,0,0,0.06)',
              }}
            />
          </Box>
        </Box>
      </CardActionArea>

      <Box sx={{ px: 1.5, pb: 1, display: 'flex', alignItems: 'flex-end', gap: 1, minWidth: 0 }}>
        <Stack spacing={0.25} sx={{ flex: 1, minWidth: 0 }}>
          {normalTask && (
            <ReportStateRow
              gameMoveCount={game.move_count}
              reportType="normal"
              task={normalTask}
              onOpenReport={onOpenReport}
              onRetry={onRetry}
              t={t}
            />
          )}
          {deepTask && (
            <ReportStateRow
              gameMoveCount={game.move_count}
              reportType="deep"
              task={deepTask}
              onOpenReport={onOpenReport}
              onRetry={onRetry}
              t={t}
            />
          )}
        </Stack>

        <Button
          aria-label={t('report:more_actions', '更多复盘操作')}
          aria-haspopup="menu"
          aria-expanded={Boolean(menuAnchor)}
          onClick={openMenu}
          variant="text"
          sx={{ minWidth: 48, width: 48, minHeight: 48, height: 48, flexShrink: 0, p: 0 }}
        >
          <MoreHorizIcon />
        </Button>
        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={closeMenu}
          slotProps={{
            list: {
              'aria-label': t('report:actions_menu', '复盘操作'),
              sx: { '& .MuiMenuItem-root': { minHeight: 48 } },
            },
          }}
        >
          {!normalTask && (
            <MenuItem
              onClick={(event) => runMenuAction(event, () => onCreateReport('normal'))}
              sx={{ minWidth: 48, minHeight: 48 }}
            >
              {t('report:generate_normal', '生成普通复盘')}
            </MenuItem>
          )}
          {!deepTask && (
            <MenuItem
              onClick={(event) => runMenuAction(event, () => onCreateReport('deep'))}
              sx={{ minWidth: 48, minHeight: 48 }}
            >
              {t('report:generate_deep', '生成深度复盘')}
            </MenuItem>
          )}
          <MenuItem
            onClick={(event) => runMenuAction(event, onDelete)}
            sx={{ minWidth: 48, minHeight: 48, color: 'error.main' }}
          >
            {t('report:delete_game', '删除棋谱')}
          </MenuItem>
        </Menu>
      </Box>
    </Card>
  );
}
