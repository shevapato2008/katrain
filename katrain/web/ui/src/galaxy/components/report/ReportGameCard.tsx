import { Box, Card, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { translateResult } from '../../../utils/resultTranslation';
import type { UserGameSummary } from '../../../api/userGamesApi';
import { presentReportTier, type ReportGameStatus } from '../../../features/report/reportModel';
import { ReportProgressColumn } from '../../../features/report/ReportProgressColumn';
import { reportPlatformLabel } from '../../../features/report/reportOrigin';
import { isRankedGameType } from '../../../features/aiLadder/gameType';
import { formatRank } from '../../../utils/rank';

export type { ReportGameStatus } from '../../../features/report/reportModel';

interface ReportGameCardProps {
  game: UserGameSummary;
  selected?: boolean;
  reportState: ReportGameStatus;
  onSelect: () => void;
}

function getGameDisplayTitle(game: UserGameSummary, t: (key: string, fallback?: string) => string): string {
  if (game.source === 'play_ai') {
    return isRankedGameType(game.game_type)
      ? t('report:title_ai_ranked', 'AI Ranked Play') : t('report:title_ai_free', 'AI Free Play');
  }
  if (game.source === 'play_human' || game.source === 'play_local') return t('report:title_human', 'Human vs Human');
  if (game.source === 'import') return t('report:title_import', 'Imported Game');
  if (game.source === 'kifu_library') return t('report:title_kifu', 'From Library');
  if (game.source === 'research') return t('report:title_research', 'Research archive');
  return t('report:unnamed_game', 'Untitled game');
}


export default function ReportGameCard({ game, selected = false, reportState, onSelect }: ReportGameCardProps) {
  const { t } = useTranslation();
  const platformLabel = reportPlatformLabel(game, t);
  const title = platformLabel || game.event || game.title || getGameDisplayTitle(game, t);
  const secondaryTitle = platformLabel ? game.event || game.title : null;
  const tiers = (['normal', 'deep'] as const).map(tier => presentReportTier(reportState, tier, game.move_count));
  const activeTiers = tiers.filter(value => value.status === 'running' || value.status === 'pending');
  const failed = tiers.some(value => value.status === 'failed');

  return <Box data-testid="report-game-row" sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 416px) 126px',
    gap: '10px', height: 104, minHeight: 104, alignItems: 'center', width: '100%' }}>
    <Card data-testid="report-game-card" sx={{ height: 104, width: '100%', minWidth: 0, boxSizing: 'border-box', p: '6px 10px',
      bgcolor: selected ? 'rgba(76,175,80,0.12)' : 'rgba(255,255,255,0.05)', border: '1px solid',
      borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.1)', borderRadius: '8px',
      '&:hover': { borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.2)' } }}>
      <Box role="button" tabIndex={0} aria-pressed={selected} onClick={onSelect} onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(); }
      }} sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '4px',
        cursor: 'pointer', '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, height: 20, minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 18, lineHeight: '20px', fontWeight: 600, minWidth: 0 }}>{title}</Typography>
          {secondaryTitle && <Typography variant="caption" color="text.secondary" noWrap sx={{ minWidth: 0, flex: 1 }}>{secondaryTitle}</Typography>}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, height: 18, minWidth: 0 }}>
          {failed && <Typography variant="caption" color="error.main">{t('review:tag_failed', 'Analysis failed')}</Typography>}
          {activeTiers.map(value => <Typography key={value.tier} component="span" variant="caption" color="text.secondary"
            data-active-report-tier={value.tier} sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
            {value.tier === 'normal' ? t('report:tier_normal', 'Normal report') : t('report:tier_deep', 'Advanced report')} {value.analyzed}/{value.total}
          </Typography>)}
          {game.game_date && <Typography variant="caption" color="text.secondary" noWrap sx={{ minWidth: 0 }}>{game.game_date}</Typography>}
          {activeTiers.length === 0 && <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap', ml: 'auto' }}>{game.move_count} {t('report:moves_unit', 'moves')}</Typography>}
          <Typography variant="caption" color="text.secondary" noWrap>{game.result ? translateResult(game.result, t, game.rules) : t('report:no_result', 'No result')}</Typography>
        </Box>
        <Box sx={{ display: 'grid', gridTemplateRows: '22px 22px', minWidth: 0 }}>
          {(['black', 'white'] as const).map(color => {
            const rank = color === 'black' ? game.black_rank : game.white_rank;
            const name = color === 'black' ? game.player_black : game.player_white;
            return <Box key={color} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
              <Box sx={{ width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                bgcolor: color === 'black' ? '#1a1a1a' : '#e8e4df', border: '1px solid rgba(255,255,255,0.18)' }} />
              <Typography variant="body2" noWrap sx={{ fontWeight: 700, fontSize: 16 }}>{name || (color === 'black' ? t('report:black', 'Black') : t('report:white', 'White'))}</Typography>
              {rank && <Typography component="span" sx={{ color: 'text.secondary', fontSize: 12 }}>{formatRank(rank, t)}</Typography>}
            </Box>;
          })}
        </Box>
      </Box>
    </Card>
    <ReportProgressColumn state={reportState} moveCount={game.move_count} surface="galaxy" t={t} />
  </Box>;
}
