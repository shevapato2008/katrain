import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { Box, Dialog, DialogContent, DialogTitle, IconButton, Typography, useTheme } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { translateResult } from '../../../utils/resultTranslation';
import { formatRank } from '../../../utils/rank';
import type { MoveAnalysis } from '../../../types/live';
import type { VerifiedAnalysisParameters } from '../../../types/kifu';
import { kifuDefaultRulesSource, kifuEventRules, kifuRulesLabel } from '../../../features/kifu/kifuRules';
import type { UserGameDetail } from '../../../api/userGamesApi';

interface Props {
  game: (Pick<UserGameDetail, 'game_date' | 'source' | 'event' | 'title' | 'round_name' | 'result' | 'player_black' | 'player_white' | 'black_rank' | 'white_rank' > & { rules: string | null; komi: number | null }) | null;
  task: { status: string; report_type: string; requested_visits?: number } | null;
  statusLabel?: string;
  currentMove: number;
  currentAnalysis: MoveAnalysis | null;
  professional?: boolean;
  analysisParameters?: VerifiedAnalysisParameters | null;
  backTo?: string;
}

const stone = (white: boolean) => ({ width: 17, height: 17, flexShrink: 0, borderRadius: '50%', bgcolor: white ? '#fafafa' : '#090b0a', border: '1px solid', borderColor: white ? '#fff' : '#b6c1b8' });

export default function ReportMetaPanel({ game, task, currentMove, currentAnalysis, professional = false, analysisParameters, statusLabel, backTo }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const effectiveRules = professional ? analysisParameters?.rules ?? game?.rules : game?.rules;
  const rules = professional ? kifuRulesLabel(kifuEventRules(analysisParameters, game?.rules), t, analysisParameters) : game?.rules === 'japanese' ? t('report:japanese_rules', '日本规则') : game?.rules === 'korean' ? t('report:korean_rules', '韩国规则') : t('report:chinese_rules', '中国规则');
  const defaultRulesSource = professional ? kifuDefaultRulesSource(analysisParameters, t) : null;
  const event = [game?.event || game?.title || t('report:unnamed_game', '未命名对局'), game?.round_name].filter(Boolean).join(' · ');
  const black = game?.player_black || t('report:black', '黑');
  const white = game?.player_white || t('report:white', '白');
  const result = game?.result ? translateResult(game.result, t, effectiveRules) : '—';
  const source = professional ? t('kifu:professional_game', '职业棋谱') : game?.source === 'import' ? t('review:row_import', '导入的棋谱') : game?.source === 'play_local' ? t('review:row_local', '本地对局') : game?.source === 'research' ? t('review:row_research', '研究局面') : game?.source || '—';
  const status = statusLabel ?? (task?.status === 'rules_unresolved' ? t('kifu:rules_unresolved', '规则待核验') : task?.status === 'completed' ? t('report:completed', '已完成') : task?.status === 'running' ? t('report:generating', '生成中') : task?.status === 'pending' ? t('report:queuing', '排队中') : task?.status === 'failed' ? t('report:failed', '失败') : t('report:unknown_status', '未知状态'));
  const blackRate = currentAnalysis ? Math.max(0, Math.min(100, currentAnalysis.winrate * 100)) : null;
  const whiteRate = blackRate == null ? null : 100 - blackRate;
  const lead = currentAnalysis?.score_lead;
  const leadText = lead == null ? `${t('report:move_prefix', '第')} ${currentMove} ${t('live:moves', '手')}` : Math.abs(lead) < 0.05 ? t('report:even_position', '形势均衡') : `${lead > 0 ? t('review:black', '黑') : t('review:white', '白')}${t('report:leads', '领先')} ${Math.abs(lead).toFixed(1)} ${t('report:points_unit', '目')}`;
  const detailRows = [
    [t('report:date', '日期'), game?.game_date || '—'],
    [t('report:event', '赛事／标题'), event],
    [t('report:black', '黑'), [black, game?.black_rank ? formatRank(game.black_rank, t) : null].filter(Boolean).join(' ')],
    [t('report:white', '白'), [white, game?.white_rank ? formatRank(game.white_rank, t) : null].filter(Boolean).join(' ')],
    [t('report:result', '结果'), result],
    [t('report:rules', '规则'), rules],
    [professional ? t('report:sgf_komi', 'SGF 贴目') : t('report:komi_label', '贴目'), game?.komi ?? '—'],
    ...(professional ? [
      [t('report:sgf_rules', 'SGF 规则'), defaultRulesSource ? '—' : game?.rules || '—'],
      [analysisParameters?.verified === true ? t('report:analysis_rules', '分析规则（已核验）') : t('report:analysis_rules_unverified', '分析规则'), analysisParameters ? kifuRulesLabel(analysisParameters.rules, t, analysisParameters) : '—'],
      [analysisParameters?.verified === true ? t('report:analysis_komi', '分析贴目（已核验）') : t('report:analysis_komi_short', '分析贴目'), analysisParameters?.komi ?? '—'],
      ...(defaultRulesSource ? [[t('kifu:rules_source', '规则来源'), defaultRulesSource]] : []),
    ] : []),
    [t('report:source', '来源'), source],
    ...(task ? [
      [t('report:report_type', '报告类型'), task.report_type === 'deep' ? t('report:deep', '深度报告') : t('report:normal', '普通报告')],
      [t('report:status', '状态'), status],
      [t('report:visits_per_position', '每局面 visits'), task.requested_visits ?? '—'],
    ] : []),
  ] as const;
  const text = { fontSize: 18, lineHeight: 1.25 };

  return <>
    <Box data-testid="report-meta-panel" sx={{ display: 'grid', gridTemplateRows: '28px 38px 32px 24px', gap: '4px', minHeight: 154, p: '9px 12px', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, bgcolor: 'background.paper', color: 'text.primary', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 0, gap: 1 }}>
        {backTo && <IconButton component={RouterLink} to={backTo} aria-label={professional ? t('kifu:back_kifu', '返回棋谱库') : t('review:back_review', '返回复盘')} size="small" sx={{ width: 32, height: 32, color: 'text.primary' }}><ArrowBackIosNewIcon fontSize="small" /></IconButton>}
        <Typography title={event} sx={{ ...text, flex: 1, minWidth: 0, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event}</Typography>
        <Typography sx={{ ...text, color: 'text.secondary', whiteSpace: 'nowrap' }}>{game?.game_date || '—'}</Typography>
        <IconButton onClick={() => setDetailsOpen(true)} aria-label={t('report:game_details', '对局详情')} size="small" sx={{ width: 32, height: 32, color: 'text.primary' }}><InfoOutlinedIcon fontSize="small" /></IconButton>
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)', alignItems: 'center', gap: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 0, gap: 0.75 }}><Box sx={stone(false)} /><Typography noWrap sx={{ fontSize: 18, fontWeight: 600 }}>{black}</Typography></Box>
        <Typography sx={{ ...text, fontWeight: 600, color: '#8fdfad', whiteSpace: 'nowrap' }}>{leadText}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', minWidth: 0, justifyContent: 'flex-end', gap: 0.75 }}><Typography noWrap sx={{ fontSize: 18, fontWeight: 600 }}>{white}</Typography><Box sx={stone(true)} /></Box>
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography sx={{ ...text, whiteSpace: 'nowrap' }}>{t('review:black', '黑')} {blackRate == null ? '—' : `${blackRate.toFixed(1)}%`}</Typography>
        <Box role="img" aria-label={blackRate == null ? t('report:winrate_unavailable', '暂无胜率数据') : t('report:winrate_bar', '黑白胜率')} sx={{ height: 9, flex: 1, minWidth: 0, borderRadius: 9, bgcolor: blackRate == null ? 'divider' : '#f4f7f4', overflow: 'hidden' }}>{blackRate != null && <Box sx={{ height: '100%', width: `${blackRate}%`, bgcolor: '#101411' }} />}</Box>
        <Typography sx={{ ...text, whiteSpace: 'nowrap' }}>{t('review:white', '白')} {whiteRate == null ? '—' : `${whiteRate.toFixed(1)}%`}</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, color: 'text.secondary', overflow: 'hidden' }}>
        <Typography noWrap title={result} sx={{ ...text, flex: '1 1 0', minWidth: 0 }}>{result}</Typography><Typography noWrap sx={{ ...text, flexShrink: 0 }}>{rules}</Typography><Typography noWrap sx={{ ...text, flexShrink: 0 }}>{professional ? analysisParameters ? t('report:analysis_komi_short', '分析贴目') : t('report:sgf_komi', 'SGF 贴目') : t('report:komi_label', '贴目')} {analysisParameters?.komi ?? game?.komi ?? '—'}</Typography>
      </Box>
    </Box>
    <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} maxWidth="sm" fullWidth aria-labelledby="report-details-title" slotProps={{ paper: { sx: { fontFamily: theme.typography.fontFamily, '& .MuiTypography-root': { fontFamily: theme.typography.fontFamily } } } }}>
      <DialogTitle id="report-details-title" sx={{ fontSize: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>{t('report:game_details', '对局详情')}<IconButton onClick={() => setDetailsOpen(false)} aria-label={t('common:close', '关闭')}><CloseIcon /></IconButton></DialogTitle>
      <DialogContent dividers>{detailRows.map(([label, value]) => <Box key={label} sx={{ display: 'grid', gridTemplateColumns: '108px minmax(0,1fr)', gap: 2, py: 0.75, fontSize: 18 }}><Box sx={{ color: 'text.secondary' }}>{label}</Box><Box>{String(value)}</Box></Box>)}</DialogContent>
    </Dialog>
  </>;
}
